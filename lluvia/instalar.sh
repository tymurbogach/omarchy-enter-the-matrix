#!/usr/bin/env bash
# Instala la lluvia animada en el lock y como fondo del escritorio.
#
# Omarchy pinta las dos superficies con plugins de Quickshell que muestran una
# imagen fija, asi que no hay forma de anadir esto por configuracion: hay que
# clonar los dos plugins y sustituir su QML. `omarchy plugin clone` hace el clon
# bajo tu usuario y desactiva el de fabrica; esto copia encima los ficheros.
#
# Efecto secundario que conviene saber: un plugin clonado queda congelado. Lo
# que Omarchy arregle en lock o background en futuros `omarchy update` no llega
# solo. Para volver atras:  omarchy plugin remove $USER.lock
#
#   ./instalar.sh

set -euo pipefail

AQUI=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROBADO_EN="4.0.0"

command -v omarchy >/dev/null || { echo "esto necesita Omarchy" >&2; exit 1; }

version=$(omarchy version 2>/dev/null | head -1)
if [[ $version != "$PROBADO_EN"* ]]; then
  echo "Aviso: escrito contra Omarchy $PROBADO_EN y aqui hay '$version'."
  echo "Los QML sustituyen enteros a los de fabrica, asi que puede faltarte"
  echo "algo que Omarchy haya anadido desde entonces. Sigo, pero revisa el lock"
  echo "con 'omarchy-shell lock preview' antes de fiarte."
  echo
fi

instalar() {
  local origen=$1 destino_qml=$2
  local id="${USER}.${origen#omarchy.}"
  local dir="$HOME/.config/omarchy/plugins/$id"

  if [[ ! -d $dir ]]; then
    echo "→ clonando $origen"
    omarchy plugin clone "$origen" >/dev/null
  else
    echo "→ $id ya existe, se sobrescribe su QML"
  fi

  cp "$AQUI/$destino_qml" "$AQUI/MatrixRain.qml" "$AQUI/matrix.frag.qsb" \
     "$AQUI/glifos.png" "$dir/"
  echo "  $destino_qml + shader -> $dir"
}

instalar omarchy.lock LockView.qml
instalar omarchy.background Background.qml

omarchy restart shell >/dev/null 2>&1 || true

cat <<'FIN'

Listo.

  · El bloqueo ya llueve. Compruebalo SIN bloquearte:
        omarchy-shell lock preview
    (se cierra con un clic). Hazlo antes de bloquear de verdad.

  · Para el fondo animado, elige "0-lluvia-viva.png" en el carrusel de fondos.
    Con el cargador puesto llueve siempre; con bateria, solo mientras no haya
    ninguna ventana en el espacio de trabajo.
FIN
