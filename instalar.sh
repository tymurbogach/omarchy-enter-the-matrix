#!/usr/bin/env bash
# Instala el pack Matrix: el plugin de la lluvia, el CLI, los hooks y el menu.
#
#   ./instalar.sh
#
# Es aditivo. No se toca nada de /usr/share/omarchy, ni hyprland.lua, ni el
# fondo de Omarchy: la lluvia del escritorio va en su propia capa por encima.
# El unico plugin de Omarchy que se sustituye es el lock, y no con una copia
# congelada sino derivandolo del que tengas (ver bin/derivar-lock.py).
#
# Para deshacerlo entero: ./desinstalar.sh

set -euo pipefail

AQUI=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PLUGIN_ID="matrix.rain"
PLUGIN_DIR="$HOME/.config/omarchy/plugins/$PLUGIN_ID"
BIN_DIR="$HOME/.local/bin"
HOOKS="$HOME/.config/omarchy/hooks"
MENU="$HOME/.config/omarchy/extensions/omarchy-menu.jsonc"
CONFIG="$HOME/.config/omarchy/matrix.json"
PROBADO_EN="4.0.0"

command -v omarchy >/dev/null || { echo "esto necesita Omarchy" >&2; exit 1; }

version=$(omarchy version 2>/dev/null || echo desconocida)
[[ $version == $PROBADO_EN* ]] || cat >&2 <<AVISO
  aviso: escrito y probado contra Omarchy $PROBADO_EN, aqui hay $version.
  El plugin de la lluvia deberia dar igual. El lock se deriva del tuyo, y si el
  parche no encaja aborta y te lo dice en vez de dejarlo a medias.
AVISO

# --- el plugin --------------------------------------------------------------
# Se copian solo los ficheros que el plugin necesita, no el tema entero: asi el
# directorio de plugins queda legible y `omarchy plugin validate` pasa.

echo "· plugin $PLUGIN_ID"
mkdir -p "$PLUGIN_DIR"
for f in manifest.json Service.qml MatrixRain.qml matrix.frag.qsb glifos.png; do
  cp -f "$AQUI/$f" "$PLUGIN_DIR/$f"
done
omarchy-plugin-validate "$PLUGIN_DIR" >/dev/null || {
  echo "  el plugin no pasa la validacion de Omarchy; no sigo" >&2
  exit 1
}

# --- el CLI -----------------------------------------------------------------

echo "· omarchy-matrix en $BIN_DIR"
mkdir -p "$BIN_DIR"
install -m 755 "$AQUI/bin/omarchy-matrix" "$BIN_DIR/omarchy-matrix"
install -m 755 "$AQUI/bin/derivar-lock.py" "$BIN_DIR/derivar-lock.py"

# --- los hooks --------------------------------------------------------------
# theme-set: enciende el pack al elegir matrix y lo aparta al elegir otro tema.
# post-update: vuelve a derivar el lock del LockView.qml recien actualizado.

echo "· hooks theme-set y post-update"
for hook in theme-set post-update; do
  mkdir -p "$HOOKS/$hook.d"
  install -m 755 "$AQUI/hooks/$hook" "$HOOKS/$hook.d/matrix"
done

# --- el menu ----------------------------------------------------------------
# Se empalma en el archivo de extensiones del usuario, que es el sitio que
# Omarchy deja para esto. El bloque va entre marcas y todo lo de fuera se
# respeta; se mete justo tras la llave de apertura para no depender de si la
# ultima entrada del usuario lleva coma (y el parser de Omarchy tolera la coma
# sobrante antes de la llave de cierre).

echo "· entradas de menu"
mkdir -p "$(dirname "$MENU")"
[[ -f $MENU ]] || echo '{}' >"$MENU"
python3 - "$MENU" "$AQUI/extensions/matrix-menu.jsonc" <<'PY'
import sys, pathlib, re
menu, fragmento = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
texto = menu.read_text()
bloque = fragmento.read_text().rstrip("\n") + "\n"

texto = re.sub(r"[ \t]*// >>> omarchy-matrix.*?// <<< omarchy-matrix[ \t]*\n",
               "", texto, flags=re.S)

abre = texto.index("{")
menu.write_text(texto[:abre + 1] + "\n" + bloque + texto[abre + 1:])
PY

# --- migrar la instalacion antigua -----------------------------------------
# Antes esto vivia en un clon de omarchy.background, un clon de omarchy-screensaver
# en ~/.local/bin y un bloque de PATH dentro de hypr/autostart.lua. Nada de eso
# hace falta ya, y quitarlo devuelve un archivo de Hyprland a como estaba.

viejo_fondo=$(omarchy-plugin-list --json 2>/dev/null |
  jq -r '.[] | select(.id | endswith(".background")) | select(.firstParty | not) | .id' | head -1)
if [[ -n ${viejo_fondo:-} ]]; then
  echo "· quitando el clon antiguo del fondo ($viejo_fondo)"
  omarchy-plugin-remove "$viejo_fondo" --yes >/dev/null 2>&1 ||
    omarchy-plugin-remove "$viejo_fondo" >/dev/null 2>&1 || true
fi

if [[ -f $BIN_DIR/omarchy-screensaver ]]; then
  echo "· quitando el clon antiguo de omarchy-screensaver"
  rm -f "$BIN_DIR/omarchy-screensaver"
fi

AUTOSTART="$HOME/.config/hypr/autostart.lua"
if [[ -f $AUTOSTART ]] && grep -q 'hl.env("PATH"' "$AUTOSTART"; then
  echo "· quitando la prioridad de PATH de hypr/autostart.lua (ya no hace falta)"
  cp "$AUTOSTART" "$AUTOSTART.bak.$(date +%s)"
  python3 - "$AUTOSTART" <<'PY'
import sys, pathlib, re
f = pathlib.Path(sys.argv[1])
texto = f.read_text()
# El bloque entero: el comentario que lo explica, las cinco lineas de codigo y
# el hl.env final. Se reconoce por el hl.env("PATH") y se sube hasta el primer
# comentario contiguo.
patron = re.compile(
    r"\n*(?:^--[^\n]*\n)*^local home = os\.getenv\(\"HOME\"\)\n"
    r"^local local_bin[^\n]*\n(?:^[^\n]*\n)*?^hl\.env\(\"PATH\"[^\n]*\)\n",
    re.M)
nuevo, n = patron.subn("\n", texto)
if n != 1:
    print("  aviso: no reconozco el bloque de PATH; lo dejo como esta", file=sys.stderr)
else:
    f.write_text(nuevo.rstrip("\n") + "\n")
PY
fi

# --- encender ---------------------------------------------------------------

if [[ ! -f $CONFIG ]]; then
  echo '{"wallpaper": true, "screensaver": true, "lock": true, "boot": false}' >"$CONFIG"
fi

omarchy-shell shell rescanPlugins >/dev/null 2>&1 || true
sleep 0.5

echo
"$BIN_DIR/omarchy-matrix" doctor
# Una vez, para que una instalacion nueva acabe viendo la lluvia. `doctor` no lo
# hace: se llama desde el hook de theme-set y forzar el fondo en cada cambio de
# tema seria pelearse con la rotacion de Omarchy.
"$BIN_DIR/omarchy-matrix" wallpaper on >/dev/null

cat <<'FIN'

Listo.

  omarchy theme set matrix        aplica el tema (y enciende el pack)
  omarchy-matrix status           que esta encendido
  SUPER -> Style -> Matrix        los interruptores, con ✓

Ojo: `omarchy theme set` rota al siguiente fondo del tema, asi que reaplicar el
tema te saca de la lluvia. Para volver:
  omarchy-matrix wallpaper on

El arranque Matrix (la imagen de antes del login) va aparte porque pide
contrasena:
  omarchy-matrix boot on
FIN
