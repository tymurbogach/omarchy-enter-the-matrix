#!/usr/bin/env python3
"""Deriva un arranque Matrix a partir del Plymouth que tenga esta maquina.

El splash de Omarchy es un tema de SCRIPT (`omarchy.script`), y lo que
`omarchy plymouth set-by-theme` deja cambiar son tres cosas: color de fondo,
color de texto y un PNG estatico. Por esa puerta no entra una animacion.

Asi que se hace como con el lock: se parte del `omarchy.script` de
$OMARCHY_PATH y se le aplica un parche minimo que sustituye el logo estatico
por la linea que se teclea. Todo lo demas —dialogo de contrasena, barra de
progreso, mensajes de arranque— es el de Omarchy, sin tocar. Un hook
post-update.d vuelve a derivarlo tras cada `omarchy update`.

Se instala como tema APARTE, /usr/share/plymouth/themes/omarchy-matrix/, para
no pisar el de Omarchy: volver es `omarchy plymouth reset`.

    ./derivar-plymouth.py --preparar        # solo construye, sin sudo
    ./derivar-plymouth.py                   # construye e instala

OJO: el disco de esta maquina esta cifrado, asi que Plymouth es tambien quien
pide la frase de paso al arrancar. Por eso el parche es aditivo y no toca
ninguno de los callbacks de contrasena, y por eso se instala aparte.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

OMARCHY = Path(os.environ.get("OMARCHY_PATH", "/usr/share/omarchy"))
ORIGEN = OMARCHY / "default/plymouth"
TEMA = "omarchy-matrix"
DESTINO = Path("/usr/share/plymouth/themes") / TEMA

# Las cuatro frases del principio de la pelicula, en orden.
FRASES = [
    "Wake up, Neo...",
    "The Matrix has you...",
    "Follow the white rabbit.",
    "Knock, knock, Neo.",
]
CURSOR = "█"          # bloque lleno: el cursor del terminal
FUENTE = "JetBrainsMono Nerd Font"
# El cuerpo NO es fijo: Plymouth dibuja a la resolucion NATIVA del panel, no a
# la logica. En este portatil son 3072 px, asi que un cuerpo pensado para 1080p
# saldria diminuto. Se calcula al derivar, que es cuando se sabe en que maquina
# estamos, y se escribe en el .plymouth.
ANCHO_LINEA = 0.40         # que fraccion del ancho de pantalla ocupa la frase larga
AVANCE_MONO = 0.60         # ancho de celda / em en JetBrains Mono
FPS = 50                   # el que asume omarchy.script
PASOS_LETRA = 3            # fotogramas por caracter -> ~17 pulsaciones/s
ESPERA = 15                # fotogramas por medio parpadeo del cursor
PARPADEOS = 4              # medios parpadeos al terminar cada frase


def morir(mensaje):
    print(f"derivar-plymouth: {mensaje}", file=sys.stderr)
    sys.exit(1)


def ancho_pantalla():
    """El ancho NATIVO del monitor mas grande. Plymouth no sabe de escalado."""
    try:
        import json
        salida = subprocess.run(["hyprctl", "monitors", "-j"],
                                capture_output=True, text=True, check=True).stdout
        anchos = [m["width"] for m in json.loads(salida)]
        return max(anchos) if anchos else 1920
    except Exception:
        return 1920


def cuerpo_para(ancho):
    """Puntos para que la frase mas larga ocupe ANCHO_LINEA de la pantalla."""
    celdas = max(len(f) for f in FRASES) + 1          # +1 por el cursor
    px_celda = (ancho * ANCHO_LINEA) / celdas
    return max(12, round(px_celda / AVANCE_MONO * 0.75))   # px -> puntos a 96 dpi


def fuente_disponible():
    """La fuente tiene que existir: el hook de mkinitcpio la resuelve con
    fc-match desde el `Font=` del .plymouth y la mete en el initramfs. Si no
    esta, el arranque se quedaria sin texto."""
    try:
        salida = subprocess.run(["fc-match", "-f", "%{family}", FUENTE],
                                capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return "monospace"
    return FUENTE if FUENTE.lower() in salida.lower() else "monospace"


def guion_animacion():
    """El guion de la animacion, ya resuelto en pasos.

    Se genera aqui y no en el script de Plymouth a proposito: asi el .script no
    necesita SubString, Length ni concatenar cadenas. Cada paso lleva su texto
    literal, cuantos fotogramas dura y a que frase pertenece (para colocar la X).
    """
    txt, dur, frase = [], [], []
    for i, f in enumerate(FRASES):
        for n in range(1, len(f) + 1):
            txt.append(f[:n] + CURSOR)
            dur.append(PASOS_LETRA)
            frase.append(i)
        for p in range(PARPADEOS):
            txt.append(f + (" " if p % 2 else CURSOR))
            dur.append(ESPERA)
            frase.append(i)
    return txt, dur, frase


def literal(cadena):
    return '"' + cadena.replace("\\", "\\\\").replace('"', '\\"') + '"'


def bloque_matrix():
    txt, dur, frase = guion_animacion()
    anchos = "\n".join(
        f'  global.mx_ancho[{i}] = Image.Text({literal(f + CURSOR)}, '
        f'global.mx_r, global.mx_g, global.mx_b).GetWidth();'
        for i, f in enumerate(FRASES))
    tabla = "\n".join(
        f'global.mx_txt[{i}] = {literal(t)}; global.mx_dur[{i}] = {d}; '
        f'global.mx_frase[{i}] = {p};'
        for i, (t, d, p) in enumerate(zip(txt, dur, frase)))

    return f'''
#----------------------------------------- Matrix -----------------------------
# Puesto aqui por omarchy-matrix. NO edites este fichero a mano: se vuelve a
# derivar del omarchy.script de Omarchy en cada `omarchy update`.
#
# Sustituye el logo estatico por la linea que se teclea. logo.png se sigue
# cargando, pero invisible: su caja es la que usa el dialogo de contrasena de
# mas abajo para colocarse, y no queremos mover nada de sitio.
#
# La tabla de pasos viene generada: cada entrada trae su texto literal, asi que
# aqui no hace falta cortar ni concatenar cadenas.

global.mx_r = 0.0;
global.mx_g = 1.0;
global.mx_b = 0.255;

global.mx_pasos = {len(txt)};
{tabla}

global.mx_paso = 0;
global.mx_frame = 0;
global.mx_pintado = "";
global.mx_cx = Window.GetWidth() / 2;
global.mx_cy = logo.sprite.GetY() + logo.image.GetHeight() / 2;

mx.sprite = Sprite();

fun mx_medir() {{
{anchos}
}}

mx_medir();

fun mx_pintar(indice) {{
  texto = global.mx_txt[indice];
  if (texto == global.mx_pintado) return;
  global.mx_pintado = texto;

  imagen = Image.Text(texto, global.mx_r, global.mx_g, global.mx_b);
  # X fija por frase: la linea crece hacia la derecha desde un borde estable en
  # vez de recentrarse en cada letra, que es como se escribe en un terminal.
  x = global.mx_cx - global.mx_ancho[global.mx_frase[indice]] / 2;
  mx.sprite.SetImage(imagen);
  mx.sprite.SetPosition(x, global.mx_cy - imagen.GetHeight() / 2, 10000);
}}

fun mx_tick() {{
  if (global.mx_paso >= global.mx_pasos) return;

  if (global.mx_pintado == "") {{
    mx_pintar(0);
    return;
  }}

  global.mx_frame++;
  if (global.mx_frame < global.mx_dur[global.mx_paso]) return;

  global.mx_frame = 0;
  global.mx_paso++;
  # Al llegar al final se queda en la ultima frase, sin repetir el ciclo: un
  # arranque dura menos que la animacion entera y volver a empezar se notaria.
  if (global.mx_paso >= global.mx_pasos) return;
  mx_pintar(global.mx_paso);
}}
'''


def parchear(texto):
    # 1. El logo deja de verse, pero se sigue cargando: su caja coloca el
    #    dialogo de contrasena.
    ancla = "logo.sprite.SetOpacity(1);"
    if texto.count(ancla) != 1:
        morir(f"esperaba un unico `{ancla}` en omarchy.script y hay "
              f"{texto.count(ancla)}. El splash de Omarchy ha cambiado: no lo toco.")
    texto = texto.replace(
        ancla,
        "logo.sprite.SetOpacity(0);  # la marca la teclea mx_tick(), mas abajo\n"
        + bloque_matrix())

    # 2. Enganchar la animacion al refresco de 50 fps que ya existe.
    ancla = "fun refresh_callback() {"
    if texto.count(ancla) != 1:
        morir("no encuentro refresh_callback() en omarchy.script: no lo toco.")
    texto = texto.replace(ancla, ancla + "\n  mx_tick();")
    return texto


def preparar(destino, colores):
    bg, fg, logo = colores
    if not (ORIGEN / "omarchy.script").is_file():
        morir(f"no encuentro el Plymouth de Omarchy en {ORIGEN}")
    if not Path(logo).is_file():
        morir(f"no encuentro el logo del tema: {logo}")

    for f in ORIGEN.iterdir():
        if f.is_file():
            shutil.copy2(f, destino / f.name)
    shutil.copy2(logo, destino / "logo.png")

    # Mismo retintado de piezas que hace omarchy-plymouth-set.
    for pieza in ("bullet.png", "entry.png", "lock.png", "progress_bar.png"):
        ruta = destino / pieza
        if ruta.is_file():
            subprocess.run(["magick", str(ruta), "-channel", "RGB",
                            "+level-colors", f"#{fg},#{fg}", str(ruta)], check=True)

    r, g, b = (int(bg[i:i + 2], 16) / 255 for i in (0, 2, 4))
    guion = (destino / "omarchy.script").read_text()
    guion = re.sub(r"^Window\.SetBackgroundTopColor.*$",
                   f"Window.SetBackgroundTopColor({r:.3f}, {g:.3f}, {b:.3f});",
                   guion, count=1, flags=re.M)
    guion = re.sub(r"^Window\.SetBackgroundBottomColor.*$",
                   f"Window.SetBackgroundBottomColor({r:.3f}, {g:.3f}, {b:.3f});",
                   guion, count=1, flags=re.M)
    guion = parchear(guion)

    (destino / f"{TEMA}.script").write_text(guion)
    (destino / "omarchy.script").unlink()
    (destino / "omarchy.plymouth").unlink(missing_ok=True)

    fuente = fuente_disponible()
    ancho = ancho_pantalla()
    cuerpo = cuerpo_para(ancho)
    (destino / f"{TEMA}.plymouth").write_text(f"""[Plymouth Theme]
Name=Omarchy Matrix
Description=El splash de Omarchy con la linea del principio de la pelicula.

ModuleName=script

[script]
ImageDir={DESTINO}
ScriptFile={DESTINO}/{TEMA}.script
ConsoleLogBackgroundColor=0x{bg}
MonospaceFont={fuente} {cuerpo}
Font={fuente} {cuerpo}
""")
    return fuente, ancho, cuerpo


def color_del_tema(clave, tema_dir):
    for linea in (tema_dir / "colors.toml").read_text().splitlines():
        if "=" in linea:
            k, v = linea.split("=", 1)
            if k.strip() == clave:
                return v.strip().strip('"').lstrip("#")
    morir(f"falta `{clave}` en colors.toml")


def main():
    solo_preparar = "--preparar" in sys.argv
    tema_dir = Path(subprocess.run(["omarchy-theme-dir", "matrix"],
                                   capture_output=True, text=True,
                                   check=True).stdout.strip())

    colores = (color_del_tema("background", tema_dir),
               color_del_tema("foreground", tema_dir),
               tema_dir / "unlock.png")

    escenario = Path(tempfile.mkdtemp(prefix="matrix-plymouth."))
    try:
        fuente, ancho, cuerpo = preparar(escenario, colores)
        pasos = len(guion_animacion()[0])
        segundos = sum(guion_animacion()[1]) / FPS
        print(f"  {TEMA}: {pasos} pasos, {segundos:.1f}s de animacion")
        print(f"  fuente {fuente!r} a {cuerpo} pt, calculado para un panel de {ancho} px")

        if solo_preparar:
            final = Path.home() / ".cache/omarchy-matrix/plymouth"
            final.parent.mkdir(parents=True, exist_ok=True)
            shutil.rmtree(final, ignore_errors=True)
            shutil.copytree(escenario, final)
            print(f"  preparado en {final} (sin instalar)")
            return

        subprocess.run(["sudo", "mkdir", "-p", str(DESTINO)], check=True)
        subprocess.run(["sudo", "cp", "-a", "--no-preserve=mode,ownership",
                        f"{escenario}/.", f"{DESTINO}/"], check=True)
        subprocess.run(["sudo", "plymouth-set-default-theme", TEMA], check=True)

        if shutil.which("limine-mkinitcpio"):
            subprocess.run(["sudo", "limine-mkinitcpio"], check=True)
        else:
            subprocess.run(["sudo", "mkinitcpio", "-P"], check=True)
        print(f"  instalado y por defecto. Volver: omarchy plymouth reset")
    finally:
        shutil.rmtree(escenario, ignore_errors=True)


if __name__ == "__main__":
    main()
