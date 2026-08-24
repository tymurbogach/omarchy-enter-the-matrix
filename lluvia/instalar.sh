#!/usr/bin/env bash
# Deja las tres pantallas del tema lloviendo: salvapantallas, bloqueo y fondo.
#
#   ./instalar.sh
#
# Las tres funcionan de forma distinta y ninguna se configura, asi que hay que
# tocarlas una a una:
#
#   · salvapantallas -- es ttfx dentro de un terminal. omarchy-launch-screensaver
#     llama a `omarchy-screensaver` por NOMBRE, asi que hay que poner un clon con
#     el efecto fijo antes en el PATH, y eso va en hypr/autostart.lua (ver abajo
#     por que uwsm/env.d no vale).
#   · bloqueo y fondo -- son plugins de Quickshell que pintan una imagen fija.
#     No hay forma de meterles una animacion por configuracion: hay que clonar
#     los plugins y sustituirles el QML.
#
# Efecto secundario que conviene saber: un plugin clonado queda congelado. Lo
# que Omarchy arregle en lock o background en futuros `omarchy update` no llega
# solo. Para volver atras:
#
#   omarchy plugin remove $USER.lock
#   omarchy plugin remove $USER.background
#   rm ~/.local/bin/omarchy-screensaver

set -euo pipefail

AQUI=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROBADO_EN="4.0.0"

command -v omarchy >/dev/null || { echo "esto necesita Omarchy" >&2; exit 1; }

version=$(omarchy version 2>/dev/null | head -1)
if [[ $version != "$PROBADO_EN"* ]]; then
  echo "Aviso: escrito contra Omarchy $PROBADO_EN y aqui hay '$version'."
  echo "Los QML sustituyen enteros a los de fabrica, asi que puede faltarte algo"
  echo "que Omarchy haya anadido desde entonces. Sigo, pero revisa el bloqueo con"
  echo "'omarchy-shell lock preview' antes de fiarte."
  echo
fi

# ─── Salvapantallas ─────────────────────────────────────────────────────────
# El clon NO va empaquetado: se deriva del que tenga instalado esta maquina
# cambiando una sola linea. Asi hereda los arreglos de tu version de Omarchy en
# vez de congelar una copia de la mia.

CABECERA='
# Clon de omarchy-screensaver generado por el tema matrix, con el efecto fijo en
# "matrix --rain-time 86400" en vez de "--random-effect". ttfx resuelve matrix al
# ASCII de screensaver.txt en cuanto termina de llover (--rain-time, 15s por
# defecto) y termina, lo que el "while true" de abajo relanzaba en bucle; con un
# rain-time enorme la lluvia no para y el texto nunca llega a mostrarse.
# --rain-time 0 no vale: ttfx lo valida como int > 0 y sale con codigo 2.
#
# Se regenera con: ~/.config/omarchy/themes/matrix/lluvia/instalar.sh
'

instalar_screensaver() {
  local stock destino tmp
  stock="${OMARCHY_PATH:-/usr/share/omarchy}/bin/omarchy-screensaver"
  destino="$HOME/.local/bin/omarchy-screensaver"

  if [[ ! -f $stock ]]; then
    echo "  ! no encuentro $stock, me salto el salvapantallas" >&2
    return
  fi
  if omarchy-cmd-missing ttfx 2>/dev/null; then
    echo "  ! falta ttfx; el salvapantallas no funcionara hasta instalarlo" >&2
  fi

  tmp=$(mktemp)
  sed -e '/^# omarchy:summary=Run the Omarchy screensaver/d' \
      -e 's/--random-effect --no-eol --no-restore-cursor &/--no-eol --no-restore-cursor matrix --rain-time 86400 \&/' \
      "$stock" >"$tmp"

  # Si el flag no estaba donde se esperaba, Omarchy ha cambiado el script y esto
  # habria instalado un clon identico al original: mejor no tocar nada.
  if ! grep -q 'matrix --rain-time 86400' "$tmp"; then
    rm -f "$tmp"
    echo "  ! $stock no tiene el '--random-effect' donde se esperaba." >&2
    echo "    Salvapantallas sin tocar; hay que rehacer la sustitucion a mano." >&2
    return
  fi

  mkdir -p "$HOME/.local/bin"
  [[ -f $destino ]] && cp "$destino" "$destino.bak.$(date +%s)"
  { head -1 "$tmp"; printf '%s\n' "$CABECERA"; tail -n +2 "$tmp"; } >"$destino"
  chmod +x "$destino"
  rm -f "$tmp"
  echo "→ salvapantallas fijado en matrix: $destino"
}

# omarchy-launch-screensaver resuelve el binario por NOMBRE, asi que el clon
# solo se usa si ~/.local/bin gana en el PATH. Y eso NO se arregla en
# ~/.config/uwsm/env.d/: default/hypr/envs.lua vuelve a anteponer
# $OMARCHY_PATH/bin en cada arranque de Hyprland y en cada `hyprctl reload`,
# pisando lo que pusiera uwsm. hypr/autostart.lua se carga DESPUES de esos
# defaults (hyprland.lua lo hace en require("hypr.autostart"), tras
# require("default.hypr.omarchy")), asi que es el unico sitio donde aguanta.
MARCA="tema-matrix:path-local-bin"

prioridad_path() {
  local f="$HOME/.config/hypr/autostart.lua"

  if [[ -f $f ]] && grep -q "$MARCA" "$f"; then
    echo "  · prioridad de PATH ya puesta"
    return
  fi
  # Puesta a mano antes de que existiera este script: se reconoce igual.
  if [[ -f $f ]] && grep -q 'hl.env("PATH"' "$f" && grep -q '\.local/bin' "$f"; then
    echo "  · prioridad de PATH ya puesta (a mano)"
    return
  fi

  mkdir -p "$(dirname "$f")"
  cat >>"$f" <<LUA

-- $MARCA
-- default/hypr/envs.lua fuerza \$OMARCHY_PATH/bin al frente del PATH en cada
-- arranque de Hyprland y en cada \`hyprctl reload\`, pisando cualquier orden que
-- pusiera ~/.config/uwsm/env.d/. Este fichero se carga despues de esos defaults,
-- asi que aqui si aguanta. Sin esto el clon de omarchy-screensaver (matrix fijo)
-- no llega a usarse nunca.
local home = os.getenv("HOME")
local local_bin = home .. "/.local/bin"
local kept = {}
for entry in (os.getenv("PATH") or ""):gmatch("[^:]+") do
  if entry ~= local_bin then table.insert(kept, entry) end
end
table.insert(kept, 1, local_bin)
hl.env("PATH", table.concat(kept, ":"))
LUA
  echo "→ prioridad de PATH: $f  (necesita 'hyprctl reload' + 'omarchy restart shell')"
}

# ─── Bloqueo y fondo ────────────────────────────────────────────────────────

instalar_plugin() {
  local origen=$1 qml=$2
  local id="${USER}.${origen#omarchy.}"
  local dir="$HOME/.config/omarchy/plugins/$id"

  if [[ ! -d $dir ]]; then
    echo "→ clonando $origen"
    omarchy plugin clone "$origen" >/dev/null
  else
    echo "→ $id ya existe, se sobrescribe su QML"
  fi

  cp "$AQUI/$qml" "$AQUI/MatrixRain.qml" "$AQUI/matrix.frag.qsb" \
     "$AQUI/glifos.png" "$dir/"

  # Siempre, no solo al clonar. Que un plugin este ACTIVO se guarda en
  # ~/.config/omarchy/shell.json, y `omarchy refresh shell` lo resetea a los
  # valores de fabrica: los clones quedan desactivados y vuelven el lock y el
  # fondo de serie, con la imagen quieta. Volver a correr este script lo arregla.
  omarchy plugin enable "$id" >/dev/null 2>&1 || true
  echo "  $qml + shader -> $dir  (activado)"
}

instalar_screensaver
prioridad_path
instalar_plugin omarchy.lock LockView.qml
instalar_plugin omarchy.background Background.qml

omarchy restart shell >/dev/null 2>&1 || true

cat <<'FIN'

Listo. Las tres pantallas:

  · Salvapantallas — deja de sortear efectos y llueve siempre.
    Para que el PATH tome efecto:  hyprctl reload && omarchy restart shell
    Probarlo:                      omarchy-launch-screensaver force

  · Bloqueo — llueve siempre, con el fondo que sea.
    Compruebalo SIN bloquearte:  omarchy-shell lock preview
    (se cierra con un clic). Hazlo antes de bloquear de verdad.

  · Fondo — elige "0-lluvia-viva.png" en el carrusel de fondos.
    Con el cargador puesto llueve siempre; con bateria, solo mientras no
    haya ninguna ventana en el espacio de trabajo.
FIN
