#!/usr/bin/env bash
# Undoes the Matrix pack and leaves Omarchy the way it was.
#
#   ./uninstall.sh
#
# The theme itself is NOT touched: it stays a normal Omarchy theme, with its
# colours and its backgrounds. What goes is the moving parts.

set -uo pipefail

PLUGIN_ID="matrix.rain"
PLYMOUTH_THEME="omarchy-matrix"
BIN_DIR="$HOME/.local/bin"
HOOKS="$HOME/.config/omarchy/hooks"
MENU="$HOME/.config/omarchy/extensions/omarchy-menu.jsonc"
PLUGINS_DIR="$HOME/.config/omarchy/plugins"
THEME_SLUG="matrix"
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

echo "· removing the rain plugin"
omarchy-plugin-remove "$PLUGIN_ID" --yes >/dev/null 2>&1 ||
  omarchy-plugin-remove "$PLUGIN_ID" >/dev/null 2>&1 || true

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
# nine of them. Only folders carrying MatrixRain.qml are removed -- a lock clone
# somebody made for their own reasons has the same name shape and stays.
echo "· removing the plugin backups the pack left behind"
for dir in "$PLUGINS_DIR"/.*.bak.*; do
  [[ -d $dir ]] || continue
  if [[ -f $dir/MatrixRain.qml ]] ||
    [[ $(jq -r '.id // empty' "$dir/manifest.json" 2>/dev/null) == "$PLUGIN_ID" ]]; then
    rm -rf "$dir"
  fi
done

echo "· removing hooks, menu entries and the CLI"
rm -f "$HOOKS/theme-set.d/matrix" "$HOOKS/post-update.d/matrix"
rm -f "$BIN_DIR/omarchy-matrix" "$BIN_DIR/derive-lock.py" "$BIN_DIR/derive-plymouth.py"
# Including this script, when it is the copy on PATH that is running. Unlinking
# a running bash script is safe -- the open inode survives to the last line --
# but truncating it is not, so never rewrite it here.
rm -f "$BIN_DIR/omarchy-matrix-uninstall"
rm -f "$HOME/.config/omarchy/matrix.json"
# Left by a much older version of the pack, which cloned omarchy-screensaver into
# ~/.local/bin instead of drawing the screensaver itself.
rm -f "$BIN_DIR"/omarchy-screensaver "$BIN_DIR"/omarchy-screensaver.bak.*
# Where derive-plymouth.py --stage-only leaves a build for inspection.
rm -rf "$HOME/.cache/omarchy-matrix"

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
  cat <<'DONE'

Done. The matrix theme was kept and works like any other theme.

To remove that too:
  omarchy-matrix-uninstall     (or: rm -rf ~/.config/omarchy/themes/matrix)
DONE
  exit 0
fi

if [[ $(cat "$HOME/.local/state/omarchy/current/theme.name" 2>/dev/null) == "$THEME_SLUG" ]]; then
  # Any stock theme will do; the first one is the least surprising choice and is
  # guaranteed to exist, unlike whatever the user had before.
  fallback=$(find /usr/share/omarchy/themes -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort | head -1)
  if [[ -n ${fallback:-} ]]; then
    echo "· stepping off the matrix theme onto $fallback"
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
