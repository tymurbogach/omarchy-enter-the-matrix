#!/usr/bin/env bash
# Installs the Matrix pack: the rain plugin, the CLI, the hooks and the menu.
#
#   ./install.sh            interactive when there is a terminal
#   ./install.sh --sync     copy the files and nothing else
#
# It is additive. Nothing under /usr/share/omarchy is touched, nor hyprland.lua,
# nor Omarchy's background: the desktop rain draws on a layer of its own above
# it. The only two things of Omarchy's that get replaced are the lock plugin and
# the Plymouth theme, and neither ships as a frozen copy -- both are DERIVED
# from whatever this machine has (see bin/derive-lock.py, bin/derive-plymouth.py).
#
# To undo all of it: ./uninstall.sh

set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TESTED_ON="4.0.1"

# --sync copies the files and stops: no questions, no doctor, no boot splash.
# It is what `omarchy-matrix doctor` calls when it notices the theme directory
# has moved on. `omarchy theme update` is a bare `git pull` per theme and fires
# no hooks at all, so nothing else would ever refresh these copies.
SYNC_ONLY=0
[[ ${1:-} != "--sync" ]] || SYNC_ONLY=1

command -v omarchy >/dev/null || { echo "this needs Omarchy" >&2; exit 1; }

# --- the provider -----------------------------------------------------------
# provider.json is the only file that names the provider; everything below is
# machinery. It is installed next to the CLI's other files so that the CLI can
# still read it while another theme is current -- which is exactly when
# `suspend` and `lock off` run.

PROVIDER="$HERE/provider.json"
[[ -f $PROVIDER ]] || { echo "cannot find $PROVIDER" >&2; exit 1; }
eval "$(jq -r '@sh "SLUG=\(.slug) DISPLAY_NAME=\(.displayName) CLI=\(.cli) ACCENT=\(.accent) PLUGIN_ID=\(.plugin.id) PLUGIN_SRC=\(.plugin.dir) WIDGET_ID=\(.widget.id) WIDGET_SRC=\(.widget.dir) RAIN_QML=\(.rainFiles[0])"' "$PROVIDER")"
mapfile -t PLUGIN_FILES < <(jq -r '.plugin.files[]' "$PROVIDER")
mapfile -t WIDGET_FILES < <(jq -r '.widget.files[]' "$PROVIDER")

# `omarchy theme install` names the theme's folder after the REPO -- basename of
# the URL with `omarchy-` stripped (omarchy-theme-install) -- and the slug in
# provider.json has to be that same name, because pack_in_effect() compares the
# slug against ~/.local/state/omarchy/current/theme.name. Renaming the repo
# without renaming the slug is silent: everything installs, and then every piece
# stands down forever because the pack never considers itself the current theme.
# Written down after exactly that happened.
here_name=$(basename "$HERE")
if [[ $HERE == "$HOME/.config/omarchy/themes/"* && $here_name != "$SLUG" ]]; then
  echo "this theme is installed as '$here_name' but provider.json says '$SLUG'." >&2
  echo "The folder name comes from the repo name; the two have to agree." >&2
  exit 1
fi

PLUGINS_DIR="$HOME/.config/omarchy/plugins"
PLUGIN_DIR="$PLUGINS_DIR/$PLUGIN_ID"
BIN_DIR="$HOME/.local/bin"
SHARE_DIR="$HOME/.local/share/omarchy-matrix"
HOOKS="$HOME/.config/omarchy/hooks"
MENU="$HOME/.config/omarchy/extensions/omarchy-menu.jsonc"
CONFIG="$HOME/.config/omarchy/$SLUG.json"

version=$(omarchy version 2>/dev/null || echo unknown)
[[ $version == $TESTED_ON* ]] || cat >&2 <<WARNING
  warning: written and tested against Omarchy $TESTED_ON, this is $version.
  The rain plugin should not care. The lock and the boot splash are derived
  from yours, and if a patch no longer fits they abort and say so rather than
  leaving things half done.
WARNING

# --- the plugin -------------------------------------------------------------
# Only the files the plugin needs are copied, not the whole theme: that keeps
# the plugins directory readable and passes `omarchy plugin validate`.
#
# Built in a staging directory and moved into place, rather than copied file by
# file over the live one. Saving ANY file under ~/.config/omarchy/plugins/
# hot-reloads that plugin, so the old way fired one reload per file -- eleven in
# under a second, which is the two-instances trap idling (see CLAUDE.md). A
# dot-prefixed name is skipped by the plugin scanner on purpose: Omarchy uses
# the same idiom for its own clone staging (PluginRegistry.qml:707).

stage_plugin() { # <id> <source subdir> <file>...
  local id="$1" src="$2" f
  shift 2
  local dest="$PLUGINS_DIR/$id" staging="$PLUGINS_DIR/.$id.staging"

  rm -rf "$staging"
  mkdir -p "$staging"
  for f in "$@"; do
    cp -f "$HERE/$src/$f" "$staging/$f"
  done

  # Validated BEFORE it goes live: a folder that fails validation must never be
  # the one the shell picks up.
  if ! omarchy-plugin-validate "$staging" >/dev/null; then
    rm -rf "$staging"
    echo "  $id does not pass Omarchy's validation; stopping here" >&2
    exit 1
  fi

  # `rm -rf "$dest"` fires one watcher event per file deleted -- the same burst
  # this staging exists to avoid, just on the way out instead of on the way in.
  # Renaming the live folder to a dot-prefixed name is a single event the
  # scanner ignores, and the removal after the swap is invisible.
  local retired="$PLUGINS_DIR/.$id.retired"
  rm -rf "$retired"
  [[ ! -e $dest ]] || mv "$dest" "$retired"
  mv "$staging" "$dest"
  rm -rf "$retired"
}

echo "· plugin $PLUGIN_ID"
stage_plugin "$PLUGIN_ID" "$PLUGIN_SRC" "${PLUGIN_FILES[@]}"

# The switchboard on the bar. A plugin of its own rather than another kind on
# the rain: for a `bar-widget`, enabled means present in bar.layout, so folding
# the two together would take the icon off the bar the moment both rain layers
# were switched off.
echo "· bar widget $WIDGET_ID"
stage_plugin "$WIDGET_ID" "$WIDGET_SRC" "${WIDGET_FILES[@]}"

# --- the CLI ----------------------------------------------------------------

echo "· $CLI in $BIN_DIR"
mkdir -p "$BIN_DIR" "$SHARE_DIR"
install -m 755 "$HERE/bin/$CLI" "$BIN_DIR/$CLI"
install -m 755 "$HERE/bin/derive-lock.py" "$BIN_DIR/derive-lock.py"
install -m 755 "$HERE/bin/derive-plymouth.py" "$BIN_DIR/derive-plymouth.py"
# Imported by both derivers, and the python half of the provider lookup.
install -m 644 "$HERE/bin/provider.py" "$BIN_DIR/provider.py"
install -m 644 "$PROVIDER" "$SHARE_DIR/provider.json"
# uninstall.sh lives in the theme directory, and `omarchy theme remove` deletes
# that directory and nothing else -- leaving the whole pack installed with no
# script left to undo it. So a copy goes on PATH, where it outlives the theme.
install -m 755 "$HERE/uninstall.sh" "$BIN_DIR/$CLI-uninstall"

# --- the hooks --------------------------------------------------------------
# theme-set: brings the pack back when you pick matrix, stands it down when you
# pick anything else.
# post-update: re-derives the lock and the boot splash from the freshly updated
# sources.

echo "· theme-set and post-update hooks"
for hook in theme-set post-update; do
  mkdir -p "$HOOKS/$hook.d"
  install -m 755 "$HERE/hooks/$hook" "$HOOKS/$hook.d/$SLUG"
done

# --- the menu, which we no longer write ------------------------------------
# The four switches used to be spliced into the user's extensions file, between
# markers. That was the last thing the pack wrote into a file that is not its
# own, and it put the switches three clicks deep under Style. They live on the
# bar now, so the block is taken back out -- including from installs that
# predate the widget.

if [[ -f $MENU ]] && grep -q '>>> omarchy-matrix' "$MENU"; then
  echo "· removing the old menu block (the switches are on the bar now)"
  python3 - "$MENU" <<'PY'
import sys, pathlib, re
menu = pathlib.Path(sys.argv[1])
text = menu.read_text()

# Take the newline install.sh used to put BEFORE the block, not just the block:
# without the leading \n? every install/uninstall cycle left one more blank line
# behind. Nine had stacked up in a file that is not ours to litter.
text = re.sub(r"\n?[ \t]*// >>> omarchy-matrix.*?// <<< omarchy-matrix[ \t]*\n",
              "", text, flags=re.S)

# And collect what the older versions already left there. Blank lines directly
# after the opening brace mean nothing in JSONC and every one of them is ours.
opening = text.index("{")
text = text[:opening + 1] + re.sub(r"^\n(?:[ \t]*\n)+", "\n", text[opening + 1:])
menu.write_text(text)
PY
fi

# Everything above is a file copy, and that is all --sync is for: refreshing
# what a `omarchy theme update` pulled into the theme directory. What follows
# migrates old installs and switches pieces on, neither of which a refresh may
# do behind the user's back.
if ((SYNC_ONLY)); then
  omarchy-shell shell rescanPlugins >/dev/null 2>&1 || true
  exit 0
fi

# --- migrate an older install ----------------------------------------------
# This used to live in a clone of omarchy.background, a clone of
# omarchy-screensaver in ~/.local/bin and a PATH block inside hypr/autostart.lua.
# None of that is needed any more, and removing it hands a Hyprland file back
# the way it was.

old_background=$(omarchy-plugin-list --json 2>/dev/null |
  jq -r '.[] | select(.id | endswith(".background")) | select(.firstParty | not) | .id' | head -1)
if [[ -n ${old_background:-} ]]; then
  echo "· removing the old background clone ($old_background)"
  omarchy-plugin-remove "$old_background" --yes >/dev/null 2>&1 ||
    omarchy-plugin-remove "$old_background" >/dev/null 2>&1 || true
fi

# The clone itself, and the timestamped copies an even older install.sh left
# beside it. Both are ours: Omarchy's own launcher is on PATH and is untouched.
if compgen -G "$BIN_DIR/omarchy-screensaver*" >/dev/null; then
  echo "· removing the old omarchy-screensaver clone"
  rm -f "$BIN_DIR"/omarchy-screensaver "$BIN_DIR"/omarchy-screensaver.bak.*
fi

# `omarchy plugin remove` renames rather than deletes, so every clone the pack
# ever handed back is still on disk as .<id>.bak.<timestamp>. Ours are the ones
# carrying the rain's QML; a clone somebody made themselves has the same name
# shape and is left alone.
pruned=0
for dir in "$PLUGINS_DIR"/.*.bak.*; do
  [[ -d $dir ]] || continue
  id=$(jq -r '.id // empty' "$dir/manifest.json" 2>/dev/null)
  if [[ -f $dir/$RAIN_QML || $id == "$PLUGIN_ID" || $id == "$WIDGET_ID" ]]; then
    rm -rf "$dir"
    pruned=$((pruned + 1))
  fi
done
((pruned == 0)) || echo "· removed $pruned stale plugin backup(s) of ours"

AUTOSTART="$HOME/.config/hypr/autostart.lua"
if [[ -f $AUTOSTART ]] && grep -q 'hl.env("PATH"' "$AUTOSTART"; then
  echo "· removing the PATH priority from hypr/autostart.lua (no longer needed)"
  cp "$AUTOSTART" "$AUTOSTART.bak.$(date +%s)"
  python3 - "$AUTOSTART" <<'PY'
import sys, pathlib, re
f = pathlib.Path(sys.argv[1])
text = f.read_text()
# The whole block: the comment that explains it, the five lines of code and the
# final hl.env. It is recognised by the hl.env("PATH") and walked back up to the
# first adjacent comment.
pattern = re.compile(
    r"\n*(?:^--[^\n]*\n)*^local home = os\.getenv\(\"HOME\"\)\n"
    r"^local local_bin[^\n]*\n(?:^[^\n]*\n)*?^hl\.env\(\"PATH\"[^\n]*\)\n",
    re.M)
new, n = pattern.subn("\n", text)
if n != 1:
    print("  warning: PATH block not recognised; leaving it alone", file=sys.stderr)
else:
    f.write_text(new.rstrip("\n") + "\n")
PY
fi

# --- switch it on -----------------------------------------------------------
# Interactive when there is a terminal to ask on, and silent-but-identical to
# the old behaviour when there is not: this also runs from `omarchy theme
# install` chained on one line, from a hook, and from an agent.

G=$'\033[38;2;'$((16#${ACCENT:1:2}))';'$((16#${ACCENT:3:2}))';'$((16#${ACCENT:5:2}))'m'  # the provider's accent
DIM=$'\033[2m'
BOLD=$'\033[1m'
OFF=$'\033[0m'

INTERACTIVE=0
[[ -t 0 && -t 1 ]] && INTERACTIVE=1

# Default yes. Anything starting with n is a no; Enter is a yes.
ask() {
  local reply=""
  ((INTERACTIVE)) || return 0
  printf '  %s%s%s  %s%s%s [Y/n] ' "$G" "$1" "$OFF" "$DIM" "$2" "$OFF"
  read -r reply || true
  [[ ${reply,,} != n* ]]
}

if [[ ! -f $CONFIG ]]; then
  if ((INTERACTIVE)); then
    echo
    echo "  ${BOLD}Which pieces do you want?${OFF} Each one switches on and off later,"
    echo "  ${DIM}from the $DISPLAY_NAME icon on the bar, or with '$CLI'.${OFF}"
    echo
  fi
  w=true; s=true; l=true; g=true
  ask "Background " "rain on the desktop"                  || w=false
  ask "Screensaver" "rain when idle, instead of Omarchy's" || s=false
  ask "Lock       " "rain behind the password field"       || l=false
  ask "Bar icon   " "these switches, one click away"       || g=false
  printf '{"wallpaper": %s, "screensaver": %s, "lock": %s, "boot": true, "widget": %s, "soft": false}\n' \
    "$w" "$s" "$l" "$g" >"$CONFIG"
fi

omarchy-shell shell rescanPlugins >/dev/null 2>&1 || true
sleep 0.5

echo
"$BIN_DIR/$CLI" doctor

# One restart at the end, and only here. Two reasons, both paid for:
#
# - A hot reload is not enough for a bar widget that has just appeared or
#   changed shape. Watched here: the icon's slot stayed 0 px wide through
#   several reloads and only took its size after a restart.
# - It guarantees exactly one instance of every plugin the pack touches, which
#   is the two-instances trap closed rather than dodged.
omarchy-restart-shell >/dev/null 2>&1 || true

# The boot splash is last because it is the only piece that needs a password and
# rebuilds the initramfs.
if ! "$BIN_DIR/$CLI" status --is boot 2>/dev/null; then
  echo
  echo "  ${BOLD}Boot splash${OFF} — the screen before login, typing out the four lines"
  echo "  from the film. ${DIM}Writes to /usr/share/plymouth and rebuilds the initramfs,"
  echo "  so it asks for your password.${OFF}"
  if ask "Install it" "you can also do this later"; then
    "$BIN_DIR/$CLI" boot on || echo "  skipped — the rest of the pack is installed and working" >&2
  else
    "$BIN_DIR/$CLI" boot off >/dev/null 2>&1 || true
    echo "  ${DIM}skipped. Turn it on later with: omarchy-matrix boot on${OFF}"
  fi
fi

cat <<EOF

  ${G}${BOLD}Done.${OFF}

  ${BOLD}omarchy-matrix${OFF}                 ${DIM}the switchboard${OFF}
  ${DIM}installed at${OFF} $BIN_DIR/omarchy-matrix

    omarchy-matrix status         ${DIM}what is on right now${OFF}
    omarchy-matrix wallpaper off  ${DIM}any piece: wallpaper screensaver lock boot${OFF}
    omarchy-matrix doctor         ${DIM}re-apply everything after 'omarchy refresh shell'${OFF}

  ${BOLD}The $DISPLAY_NAME icon on your bar${OFF}  ${DIM}the same switches, with a tick${OFF}
  ${DIM}and Repair and Uninstall beneath them. Not there? '$CLI widget on'${OFF}

  ${DIM}Note: 'omarchy theme set' rotates to the next background, so re-applying
  the theme takes you off the rain. Back with: omarchy-matrix wallpaper on${OFF}
EOF
