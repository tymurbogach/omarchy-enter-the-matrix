#!/usr/bin/env python3
"""Deriva el lock con lluvia a partir del que tenga instalado esta maquina.

El pack NO publica un LockView.qml congelado. Un plugin clonado se queda atras
en cada `omarchy update`, y el del lock lleva dentro los flujos de PAM y de
huella: la ultima copia que quieres es una vieja. Asi que aqui se parte SIEMPRE
del LockView.qml de $OMARCHY_PATH y se le aplica un cambio minimo: quitar el
wallpaper borroso y poner la lluvia en su sitio.

Las otras ~200 lineas (contrasena, huella, BorderSurface, despertar) vienen del
Omarchy instalado. El hook post-update.d vuelve a llamar aqui despues de cada
actualizacion, asi que las correcciones de Omarchy siguen llegando al lock.

Si el bloque a sustituir no aparece exactamente una vez, esto aborta y deja el
lock nativo intacto. Un lock a medias es un equipo que no se desbloquea.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
PLUGINS = HOME / ".config/omarchy/plugins"
OMARCHY = Path(os.environ.get("OMARCHY_PATH", "/usr/share/omarchy"))
ORIGEN = OMARCHY / "shell/plugins/lock"
ARCHIVOS_LLUVIA = ("MatrixRain.qml", "matrix.frag.qsb", "glifos.png")

REEMPLAZO = """    // El fondo del lock es la lluvia, no el wallpaper desenfocado.
    // loadBackground ya valia "esta vista se esta viendo de verdad" (root.locked,
    // o la previsualizacion de `omarchy-shell lock preview`), asi que gobierna
    // directamente si la lluvia corre: bloqueado llueve, y al desbloquear se para.
    //
    // Puesto aqui por omarchy-matrix. No edites este archivo a mano: se vuelve a
    // derivar del LockView.qml de Omarchy en cada `omarchy update`.
    MatrixRain {
      anchors.fill: parent
      running: root.loadBackground
    }
"""


def morir(mensaje):
    print(f"derivar-lock: {mensaje}", file=sys.stderr)
    sys.exit(1)


def fin_del_bloque(texto, inicio):
    """Devuelve el indice justo despues de la llave que cierra el bloque."""
    profundidad = 0
    i = texto.index("{", inicio)
    while i < len(texto):
        if texto[i] == "{":
            profundidad += 1
        elif texto[i] == "}":
            profundidad -= 1
            if profundidad == 0:
                return i + 1
        i += 1
    morir("llaves sin cerrar en LockView.qml")


def parchear(texto):
    imagenes = [m for m in re.finditer(r"^[ \t]*Image\s*\{", texto, re.M)
                if "id: wallpaper" in texto[m.start():fin_del_bloque(texto, m.start())]]
    if len(imagenes) != 1:
        morir(
            f"esperaba un unico `Image {{ id: wallpaper }}` en LockView.qml y he encontrado "
            f"{len(imagenes)}. El lock de Omarchy ha cambiado: no lo toco.\n"
            f"  Abre un issue en https://github.com/tymurbogach/omarchy-matrix con tu "
            f"`omarchy version`."
        )

    inicio = imagenes[0].start()
    fin = fin_del_bloque(texto, inicio)

    # El MultiEffect que desenfoca esa imagen va justo detras y se va con ella.
    resto = texto[fin:]
    efecto = re.match(r"\s*MultiEffect\s*\{", resto)
    if efecto:
        fin += fin_del_bloque(resto, 0)
    else:
        print("derivar-lock: aviso, no habia MultiEffect tras el wallpaper; sigo igual",
              file=sys.stderr)

    return texto[:inicio] + REEMPLAZO + texto[fin:]


def clon_existente():
    for directorio in sorted(PLUGINS.glob("*.lock")):
        manifiesto = directorio / "manifest.json"
        if not manifiesto.is_file():
            continue
        try:
            datos = json.loads(manifiesto.read_text())
        except ValueError:
            continue
        if datos.get("omarchy", {}).get("clonedFrom") == "omarchy.lock":
            return directorio, datos["id"]
    return None, None


def origen_lluvia():
    """De donde salen MatrixRain.qml y sus dos ficheros de datos."""
    candidatos = [PLUGINS / "matrix.rain", Path(__file__).resolve().parent.parent]
    for candidato in candidatos:
        if all((candidato / nombre).is_file() for nombre in ARCHIVOS_LLUVIA):
            return candidato
    morir("no encuentro MatrixRain.qml; instala primero el plugin matrix.rain")


def main():
    if not (ORIGEN / "LockView.qml").is_file():
        morir(f"no encuentro el lock de Omarchy en {ORIGEN}")

    lluvia = origen_lluvia()
    destino, plugin_id = clon_existente()

    if destino is None:
        subprocess.run(["omarchy-plugin-clone", "omarchy.lock"], check=True)
        destino, plugin_id = clon_existente()
        if destino is None:
            morir("el clon del lock no aparecio despues de crearlo")
        print(f"Clonado el lock de Omarchy como {plugin_id}")

    # Partir siempre de limpio: se recopian los fuentes de Omarchy sobre el clon
    # y solo despues se parchea. Asi un clon viejo se pone al dia y el parche no
    # se aplica dos veces sobre si mismo.
    for fuente in ORIGEN.iterdir():
        if fuente.name == "manifest.json":
            continue  # el del clon lleva id propio y clonedFrom; no se pisa
        shutil.copy2(fuente, destino / fuente.name)

    lock_view = destino / "LockView.qml"
    lock_view.write_text(parchear(lock_view.read_text()))

    for nombre in ARCHIVOS_LLUVIA:
        shutil.copy2(lluvia / nombre, destino / nombre)

    subprocess.run(["omarchy-shell", "shell", "rescanPlugins"],
                   check=False, capture_output=True)
    subprocess.run(["omarchy-plugin-enable", plugin_id], check=False, capture_output=True)
    print(f"Lock derivado en {destino} (desde {ORIGEN})")


if __name__ == "__main__":
    main()
