#!/usr/bin/env bash
# Deshace el pack Matrix y deja Omarchy como estaba.
#
#   ./desinstalar.sh
#
# El tema en si NO se toca: sigue siendo un tema normal de Omarchy, con sus
# colores y sus fondos. Lo que se va es la parte animada.

set -uo pipefail

PLUGIN_ID="matrix.rain"
BIN_DIR="$HOME/.local/bin"
HOOKS="$HOME/.config/omarchy/hooks"
MENU="$HOME/.config/omarchy/extensions/omarchy-menu.jsonc"
PLUGINS_DIR="$HOME/.config/omarchy/plugins"

echo "· devolviendo el lock de Omarchy"
for d in "$PLUGINS_DIR"/*.lock; do
  [[ -d $d ]] || continue
  jq -e '.omarchy.clonedFrom == "omarchy.lock"' "$d/manifest.json" >/dev/null 2>&1 || continue
  id=$(jq -r '.id' "$d/manifest.json")
  # `plugin remove` es quien reactiva omarchy.lock (cloneSourceRestores).
  # Quitar el directorio a mano dejaria la sesion sin ningun lock habilitado.
  omarchy-plugin-remove "$id" --yes >/dev/null 2>&1 ||
    omarchy-plugin-remove "$id" >/dev/null 2>&1 || true
done

echo "· quitando el plugin de la lluvia"
omarchy-plugin-remove "$PLUGIN_ID" --yes >/dev/null 2>&1 ||
  omarchy-plugin-remove "$PLUGIN_ID" >/dev/null 2>&1 || true

echo "· devolviendo el salvapantallas de Omarchy"
omarchy-toggle screensaver-off off

echo "· quitando hooks, menu y CLI"
rm -f "$HOOKS/theme-set.d/matrix" "$HOOKS/post-update.d/matrix"
rm -f "$BIN_DIR/omarchy-matrix" "$BIN_DIR/derivar-lock.py"
rm -f "$HOME/.config/omarchy/matrix.json"

if [[ -f $MENU ]]; then
  python3 - "$MENU" <<'PY'
import sys, pathlib, re
f = pathlib.Path(sys.argv[1])
f.write_text(re.sub(r"[ \t]*// >>> omarchy-matrix.*?// <<< omarchy-matrix[ \t]*\n",
                    "", f.read_text(), flags=re.S))
PY
fi

omarchy-shell shell rescanPlugins >/dev/null 2>&1 || true

cat <<'FIN'

Hecho. El tema matrix sigue instalado y funciona como cualquier otro tema.

Si tambien quieres quitar la imagen de arranque:
  omarchy plymouth reset
FIN
