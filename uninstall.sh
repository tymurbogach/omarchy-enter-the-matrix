#!/usr/bin/env bash
# Undoes the Matrix pack and leaves Omarchy the way it was.
#
#   ./uninstall.sh
#
# The theme itself is NOT touched: it stays a normal Omarchy theme, with its
# colours and its backgrounds. What goes is the moving parts.

set -uo pipefail

# provider.json is the only file that names the provider. Look for it where
# install.sh put it first, then beside this script -- this runs both from PATH,
# with the theme directory possibly already gone, and from a working copy.
BIN_DIR="$HOME/.local/bin"
SHARE_DIR="$HOME/.local/share/omarchy-matrix"
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

for candidate in "${OMARCHY_MATRIX_PROVIDER:-}" "$SHARE_DIR/provider.json" "$HERE/provider.json"; do
  [[ -n $candidate && -f $candidate ]] || continue
  PROVIDER="$candidate"
  break
done
[[ -n ${PROVIDER:-} ]] || { echo "cannot find provider.json; nothing to undo" >&2; exit 1; }

eval "$(jq -r '@sh "THEME_SLUG=\(.slug) CLI=\(.cli) PLUGIN_ID=\(.plugin.id) WIDGET_ID=\(.widget.id) PLYMOUTH_THEME=\(.plymouth.theme) RAIN_QML=\(.rainFiles[0])"' "$PROVIDER")"

HOOKS="$HOME/.config/omarchy/hooks"
MENU="$HOME/.config/omarchy/extensions/omarchy-menu.jsonc"
PLUGINS_DIR="$HOME/.config/omarchy/plugins"
THEME_DIR="$HOME/.config/omarchy/themes/$THEME_SLUG"

# The theme goes too, unless you say otherwise. It used to be kept -- it is a
# perfectly good theme on its own -- but "uninstall" that leaves a directory
# behind is not what anybody means by the word, and the menu row that calls this
# is labelled Uninstall, not Disable.
KEEP_THEME=0
[[ ${1:-} != "--keep-theme" ]] || KEEP_THEME=1

echo "· handing Omarchy's lock back"
for dir in "$PLUGINS_DIR"/*.lock; do
  [[ -d $dir ]] || continue
  jq -e '.omarchy.clonedFrom == "omarchy.lock"' "$dir/manifest.json" >/dev/null 2>&1 || continue
  id=$(jq -r '.id' "$dir/manifest.json")
  # `plugin remove` is what re-enables omarchy.lock (cloneSourceRestores).
  # Deleting the directory by hand would leave the session with no lock enabled
  # at all.
  omarchy-plugin-remove "$id" --yes >/dev/null 2>&1 ||
    omarchy-plugin-remove "$id" >/dev/null 2>&1 || true
done

echo "· removing the rain plugin and the bar widget"
for id in "$PLUGIN_ID" "$WIDGET_ID"; do
  omarchy-plugin-remove "$id" --yes >/dev/null 2>&1 ||
    omarchy-plugin-remove "$id" >/dev/null 2>&1 || true
done

echo "· handing Omarchy's screensaver back"
omarchy-toggle screensaver-off off

# The boot splash is the only piece that lives outside your home directory, so
# it is also the only one that would survive an uninstall unnoticed. It needs a
# password and rebuilds the initramfs, which is why it is asked for last.
current_plymouth=$(plymouth-set-default-theme 2>/dev/null) ||
  current_plymouth=$(sed -n 's/^Theme=//p' /etc/plymouth/plymouthd.conf 2>/dev/null)

# Two separate questions, and they used to be conflated. Handing the splash back
# is only needed when OURS is the live one. Deleting the folder is needed
# whenever the folder exists -- and it exists after any `boot off`, which is
# precisely the case the old `if` skipped, leaving the theme on disk forever.
if [[ ${current_plymouth:-} == "$PLYMOUTH_THEME" ]]; then
  echo "· handing the boot splash back (needs your password, rebuilds the initramfs)"
  omarchy-plymouth-reset ||
    echo "  skipped — undo it later with: omarchy plymouth reset" >&2
fi

# Asked again, AFTER the reset. Never before it: removing the folder of a theme
# that is still the default is how a machine boots to a black screen. Asked into
# a variable rather than through a pipe, because `set -o pipefail` plus grep's
# early exit can turn "still ours" into a zero and invert the test.
live_plymouth=$(plymouth-set-default-theme 2>/dev/null) || live_plymouth=""
if [[ -d "/usr/share/plymouth/themes/$PLYMOUTH_THEME" && ${live_plymouth:-} != "$PLYMOUTH_THEME" ]]; then
  echo "· removing the boot theme from /usr/share/plymouth (needs your password)"
  sudo rm -rf "/usr/share/plymouth/themes/$PLYMOUTH_THEME" ||
    echo "  skipped — remove it later with: sudo rm -rf /usr/share/plymouth/themes/$PLYMOUTH_THEME" >&2
fi

# `omarchy plugin remove` renames rather than deletes: every folder it took away
# above is still on disk as .<id>.bak.<timestamp>, and a development machine had
# nine of them. Only folders carrying the rain's QML are removed -- a lock clone
# somebody made for their own reasons has the same name shape and stays.
echo "· removing the plugin backups the pack left behind"
for dir in "$PLUGINS_DIR"/.*.bak.*; do
  [[ -d $dir ]] || continue
  id=$(jq -r '.id // empty' "$dir/manifest.json" 2>/dev/null)
  if [[ -f $dir/$RAIN_QML || $id == "$PLUGIN_ID" || $id == "$WIDGET_ID" ]]; then
    rm -rf "$dir"
  fi
done

echo "· removing hooks, the old menu block and the CLI"
rm -f "$HOOKS/theme-set.d/$THEME_SLUG" "$HOOKS/post-update.d/$THEME_SLUG"
rm -f "$BIN_DIR/$CLI" "$BIN_DIR/derive-lock.py" "$BIN_DIR/derive-plymouth.py" \
  "$BIN_DIR/provider.py"
# Including this script, when it is the copy on PATH that is running. Unlinking
# a running bash script is safe -- the open inode survives to the last line --
# but truncating it is not, so never rewrite it here.
rm -f "$BIN_DIR/$CLI-uninstall"
rm -f "$HOME/.config/omarchy/$THEME_SLUG.json"
# Where install.sh keeps provider.json, so the CLI could read it from anywhere.
rm -rf "$SHARE_DIR"
# Left by a much older version of the pack, which cloned omarchy-screensaver into
# ~/.local/bin instead of drawing the screensaver itself.
rm -f "$BIN_DIR"/omarchy-screensaver "$BIN_DIR"/omarchy-screensaver.bak.*
# Where derive-plymouth.py --stage-only leaves a build for inspection.
rm -rf "$HOME/.cache/$CLI"

if [[ -f $MENU ]]; then
  python3 - "$MENU" <<'PY'
import sys, pathlib, re
f = pathlib.Path(sys.argv[1])
text = f.read_text()
# Take the newline install.sh puts BEFORE the block, not just the block: without
# the leading \n? every install/uninstall cycle left one more blank line behind.
# Nine had stacked up in a file that is not ours to litter.
text = re.sub(r"\n?[ \t]*// >>> omarchy-matrix.*?// <<< omarchy-matrix[ \t]*\n",
              "", text, flags=re.S)

# And collect what the older versions already left there. Blank lines directly
# after the opening brace mean nothing in JSONC and every one of them is ours.
opening = text.index("{")
text = text[:opening + 1] + re.sub(r"^\n(?:[ \t]*\n)+", "\n", text[opening + 1:])
f.write_text(text)
PY
fi

omarchy-shell shell rescanPlugins >/dev/null 2>&1 || true

# --- the theme itself ---------------------------------------------------------
# Last, and only now: everything above still needed the theme directory to be
# there. Deleting it while Omarchy still names it as the current theme leaves
# current/theme.name pointing at nothing, so step off it first.

if ((KEEP_THEME)); then
  cat <<DONE

Done. The theme was kept and works like any other Omarchy theme.

To remove that too:
  $CLI-uninstall     (or: rm -rf $THEME_DIR)
DONE
  exit 0
fi

if [[ $(cat "$HOME/.local/state/omarchy/current/theme.name" 2>/dev/null) == "$THEME_SLUG" ]]; then
  # Any stock theme will do; the first one is the least surprising choice and is
  # guaranteed to exist, unlike whatever the user had before.
  fallback=$(find /usr/share/omarchy/themes -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort | head -1)
  if [[ -n ${fallback:-} ]]; then
    echo "· stepping off the $THEME_SLUG theme onto $fallback"
    omarchy-theme-set "$fallback" >/dev/null 2>&1 || true
  fi
fi

echo "· removing the theme"
rm -rf "$THEME_DIR"
# Omarchy remembers a background per theme, and a hook of the user's may read it.
rm -f "$HOME/.local/state/omarchy/backgrounds/$THEME_SLUG"
rm -rf "$HOME/.config/omarchy/backgrounds/$THEME_SLUG"

cat <<'DONE'

Done. Nothing of the Matrix pack is left, the theme included.

Omarchy's own lock, screensaver and boot splash are back.
DONE
