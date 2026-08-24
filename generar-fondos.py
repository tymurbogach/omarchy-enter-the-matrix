#!/usr/bin/env python3
"""Genera los fondos estaticos del tema matrix.

    ./generar-fondos.py                  regenera los fondos del tema
    ./generar-fondos.py --only 0-lluvia-viva
    ./generar-fondos.py --out /tmp/x.png --seed 99 --density 0.7

Dibuja un fichero MVG y lo pasa por ImageMagick.

Lo que pinta es **un fotograma del shader** de lluvia/matrix.frag, no una lluvia
distinta: mismos katakana de media anchura (los de `ttfx matrix`), mismos colores
(cabeza #dbffdb, cuerpo a un punto al azar del degradado #92be92 -> #185318),
cabeza ABAJO y estela hacia arriba, y la misma rejilla de celda alta y estrecha
del terminal. Antes esto dibujaba una lluvia propia -- katakana de anchura
completa, espejados y con bloom -- y la miniatura del carrusel no tenia nada que
ver con lo que luego se veia en pantalla.
"""

import argparse
import os
import random
import subprocess
import sys
import tempfile

W, H = 3840, 2400

# Rejilla medida sobre una captura del screensaver real (alacritty a font-size
# 18 en un panel a escala 2): 29x64 px nativos. El PNG se ve 1:1 en ese panel.
CELL_W, CELL_H = 30, 64
FUENTE = "Noto-Sans-CJK-JP"

# Los mismos de `ttfx matrix --rain-symbols`. Duplicados a proposito respecto a
# lluvia/generar-atlas.py: son dos programas independientes y un import cruzado
# entre ellos seria mas fragil que estas cuatro lineas.
GLIFOS = [
    "2", "5", "9", "8", "Z", "*", ")", ":", ".", '"', "=", "+", "-", "¦", "|", "_",
    "ｦ", "ｱ", "ｳ", "ｴ", "ｵ", "ｶ", "ｷ", "ｹ", "ｺ", "ｻ", "ｼ", "ｽ", "ｾ", "ｿ", "ﾀ", "ﾂ",
    "ﾃ", "ﾅ", "ﾆ", "ﾇ", "ﾈ", "ﾊ", "ﾋ", "ﾎ", "ﾏ", "ﾐ", "ﾑ", "ﾒ", "ﾓ", "ﾔ", "ﾕ", "ﾗ",
    "ﾘ", "ﾜ",
]

CABEZA = (0xDB, 0xFF, 0xDB)
LLUVIA_A = (0x92, 0xBE, 0x92)
LLUVIA_B = (0x18, 0x53, 0x18)


def mezcla(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def hexa(rgb):
    return "#%02X%02X%02X" % rgb


def reguero(draw, cx, cabeza, largo, size, escala_y, atenuar=1.0):
    """Un reguero: la cabeza abajo y la estela subiendo, como en el shader."""
    x = cx * CELL_W
    for i in range(largo):
        fila = cabeza - i
        if fila < 0:
            break
        y = fila * CELL_H
        if y > H:
            continue
        if i == 0:
            color = mezcla((0, 0, 0), CABEZA, atenuar)
        else:
            # mix(1.0, 0.62, t**0.75) del shader: la estela se apaga pero no
            # desaparece, que es como se comporta ttfx.
            t = i / max(largo - 1, 1)
            brillo = 1.0 - 0.38 * (t ** 0.75)
            color = mezcla((0, 0, 0),
                           mezcla(LLUVIA_A, LLUVIA_B, random.random()),
                           brillo * atenuar)
        ch = random.choice(GLIFOS)
        draw.append(f"fill '{hexa(color)}' font-size {size} "
                    f"text {x},{y + escala_y} '{ch}'")


def construir(semilla, densidad, escala, salida, minimo=False):
    random.seed(semilla)
    size = int(CELL_H * 0.62 * escala)
    # Los glifos se anclan por la base, asi que hay que bajarlos dentro de la
    # celda para que queden centrados como en el terminal.
    escala_y = int(CELL_H * 0.72)
    filas = H // CELL_H + 1
    columnas = W // CELL_W + 1

    draw = [f"fill black rectangle 0,0 {W},{H}"]
    elegidas = random.sample(range(columnas), max(1, int(columnas * densidad)))
    for cx in elegidas:
        # Cada columna con su cabeza y su longitud, como los hashes por columna
        # del shader. La cabeza puede caer fuera por abajo: entonces solo se ve
        # el final de la estela, que es lo que da la sensacion de caida.
        if minimo:
            # Todas las cabezas arriba: la lluvia acaba de entrar en cuadro y
            # los dos tercios de abajo quedan negros. Es composicion, no
            # dispersar poco los mismos regueros por toda la pantalla -- eso
            # solo daba ruido tenue sin sitio donde mirar.
            cabeza = random.randint(1, max(2, int(filas * 0.38)))
            largo = random.randint(10, 24)
        else:
            cabeza = random.randint(0, filas + 12)
            largo = random.randint(22, 48)
        reguero(draw, cx, cabeza, largo, size, escala_y,
                atenuar=0.85 if minimo else 1.0)

    if minimo:
        # Un unico reguero a plena luz que baja mas que los demas. Es lo que se
        # lee; el resto es textura.
        reguero(draw, int(columnas * 0.41), int(filas * 0.58), 26, size, escala_y)

    with tempfile.NamedTemporaryFile("w", suffix=".mvg", delete=False) as fh:
        fh.write("\n".join(draw) + "\n")
        mvg = fh.name
    try:
        subprocess.run(
            ["magick", "-size", f"{W}x{H}", "xc:black", "-font", FUENTE,
             "-draw", f"@{mvg}", "-depth", "8",
             # Verde sobre negro: 256 colores no se notan y bajan mucho el peso.
             "-dither", "None", "-colors", "256",
             "-strip", "-define", "png:compression-level=9", salida],
            check=True)
    finally:
        os.remove(mvg)
    print(f"  {salida}  {os.path.getsize(salida) // 1024} KB")


# semilla, densidad, escala de glifo.
# Solo esta el fotograma del fondo vivo: es la miniatura que sale en el carrusel
# y el marcador que enciende el shader de lluvia (ver lluvia/). Con --out se
# sacan sueltos.
PRESETS = {
    # semilla, densidad, escala, minimo
    "0-lluvia-viva": (11, 0.92, 1.0, False),
    # Sin marca ni logotipo: negro, unas pocas columnas muy apagadas de textura
    # y un unico reguero encendido. La idea es el ambiente, no un cartel.
    "1-minimo":      (29, 0.50, 1.0, True),
}


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--only", help="regenerar solo este preset")
    p.add_argument("--out", help="ruta de salida (uno suelto, fuera del tema)")
    p.add_argument("--seed", type=int)
    p.add_argument("--density", type=float)
    p.add_argument("--scale", type=float, default=1.0)
    args = p.parse_args()

    if args.out:
        construir(args.seed if args.seed is not None else 11,
                  args.density if args.density is not None else 0.9,
                  args.scale, args.out)
        return

    destino = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backgrounds")
    os.makedirs(destino, exist_ok=True)
    presets = PRESETS if not args.only else {args.only: PRESETS[args.only]}
    print(f"Generando {len(presets)} fondo(s) a {W}x{H}:")
    for nombre, (semilla, densidad, escala, minimo) in presets.items():
        construir(semilla, densidad, escala,
                  os.path.join(destino, nombre + ".png"), minimo)


if __name__ == "__main__":
    sys.exit(main())
