#!/usr/bin/env bash
# Installs the Matrix pack: the rain plugin, the CLI, the hooks and the menu.
#
#   ./install.sh
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
PLUGIN_ID="matrix.rain"
PLUGIN_DIR="$HOME/.config/omarchy/plugins/$PLUGIN_ID"
BIN_DIR="$HOME/.local/bin"
HOOKS="$HOME/.config/omarchy/hooks"
MENU="$HOME/.config/omarchy/extensions/omarchy-menu.jsonc"
CONFIG="$HOME/.config/omarchy/matrix.json"
TESTED_ON="4.0"

command -v omarchy >/dev/null || { echo "this needs Omarchy" >&2; exit 1; }

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

echo "· plugin $PLUGIN_ID"
mkdir -p "$PLUGIN_DIR"
for f in manifest.json Service.qml MatrixRain.qml matrix.frag.qsb glyphs.png; do
  cp -f "$HERE/$f" "$PLUGIN_DIR/$f"
done
omarchy-plugin-validate "$PLUGIN_DIR" >/dev/null || {
  echo "  the plugin does not pass Omarchy's validation; stopping here" >&2
  exit 1
}

# --- the CLI ----------------------------------------------------------------

echo "· omarchy-matrix in $BIN_DIR"
mkdir -p "$BIN_DIR"
install -m 755 "$HERE/bin/omarchy-matrix" "$BIN_DIR/omarchy-matrix"
install -m 755 "$HERE/bin/derive-lock.py" "$BIN_DIR/derive-lock.py"
install -m 755 "$HERE/bin/derive-plymouth.py" "$BIN_DIR/derive-plymouth.py"

# --- the hooks --------------------------------------------------------------
# theme-set: brings the pack back when you pick matrix, stands it down when you
# pick anything else.
# post-update: re-derives the lock and the boot splash from the freshly updated
# sources.

echo "· theme-set and post-update hooks"
for hook in theme-set post-update; do
  mkdir -p "$HOOKS/$hook.d"
  install -m 755 "$HERE/hooks/$hook" "$HOOKS/$hook.d/matrix"
done

# --- the menu ---------------------------------------------------------------
# Spliced into the user's extensions file, which is the place Omarchy leaves for
# this. The block sits between markers and everything outside it is kept; it
# goes right after the opening brace so it does not depend on whether the user's
# last entry has a trailing comma (and Omarchy's parser tolerates a dangling one
# before the closing brace).

echo "· menu entries"
mkdir -p "$(dirname "$MENU")"
[[ -f $MENU ]] || echo '{}' >"$MENU"
python3 - "$MENU" "$HERE/extensions/matrix-menu.jsonc" <<'PY'
import sys, pathlib, re
menu, fragment = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
text = menu.read_text()
block = fragment.read_text().rstrip("\n") + "\n"

text = re.sub(r"[ \t]*// >>> omarchy-matrix.*?// <<< omarchy-matrix[ \t]*\n",
              "", text, flags=re.S)

opening = text.index("{")
menu.write_text(text[:opening + 1] + "\n" + block + text[opening + 1:])
PY

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

if [[ -f $BIN_DIR/omarchy-screensaver ]]; then
  echo "· removing the old omarchy-screensaver clone"
  rm -f "$BIN_DIR/omarchy-screensaver"
fi

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

if [[ ! -f $CONFIG ]]; then
  echo '{"wallpaper": true, "screensaver": true, "lock": true, "boot": true}' >"$CONFIG"
fi

omarchy-shell shell rescanPlugins >/dev/null 2>&1 || true
sleep 0.5

echo
"$BIN_DIR/omarchy-matrix" doctor
# Once, so a fresh install ends up actually looking at the rain. `doctor` does
# not do this: it runs from the theme-set hook, and forcing the background on
# every theme change would be fighting Omarchy's rotation.
"$BIN_DIR/omarchy-matrix" wallpaper on >/dev/null

# The boot splash is last because it is the only piece that needs a password and
# rebuilds the initramfs. If you would rather not, answer nothing: the install
# is already complete and you can turn it on later.
if [[ $("$BIN_DIR/omarchy-matrix" status --is boot && echo yes || echo no) == "no" ]]; then
  echo
  echo "· boot splash: needs your password (writes to /usr/share/plymouth and"
  echo "  rebuilds the initramfs). Ctrl-C to skip; turn it on later with"
  echo "  'omarchy-matrix boot on'."
  "$BIN_DIR/omarchy-matrix" boot on || {
    echo "  skipped — the rest of the pack is installed and working" >&2
  }
fi

cat <<'DONE'

Done.

  omarchy theme set matrix        apply the theme (and bring the pack back)
  omarchy-matrix status           what is on
  SUPER -> Style -> Matrix        the switches, with ✓

Note: `omarchy theme set` rotates to the theme's next background, so re-applying
the theme takes you off the rain. Back with:
  omarchy-matrix wallpaper on
DONE
