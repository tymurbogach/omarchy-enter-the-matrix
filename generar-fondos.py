#!/usr/bin/env python3
"""Genera los fondos de lluvia digital del tema matrix.

    ./generar-fondos.py                  regenera los tres fondos del tema
    ./generar-fondos.py --only 1-lluvia-densa
    ./generar-fondos.py --out /tmp/prueba.png --seed 99 --density 0.7

Dibuja un fichero MVG y lo pasa por ImageMagick. Cuatro cosas que el
generador anterior no hacia y que son las que dan el pego:

  · 3840x2400 -- superconjunto 16:10. Cubre el 4K de DP-1 (3840x2160) sin
    recortar por los lados y el 3072x1920 del portatil sin escalar hacia
    arriba. Antes salia a 3072x1920 y el 4K le comia arriba y abajo.
  · Glifos espejados -- los katakana de la peli estan invertidos. Se hace
    con un affine por glifo, no hay forma barata de hacerlo con una fuente.
  · Dos capas de profundidad -- una de fondo, pequena y apagada, y otra de
    primer plano, grande y brillante. Sin eso la lluvia sale plana.
  · Bloom -- el resultado se compone consigo mismo desenfocado en modo
    screen. Es lo que convierte el verde plano en fosforo.

La densidad se reparte por columnas con jitter en vez de tirar un dado por
columna: el metodo viejo dejaba calvas grandes (se ve en el
2-lluvia-suave.png original).
"""

import argparse
import os
import random
import subprocess
import sys
import tempfile

W, H = 3840, 2400
FUENTE = "Noto-Sans-CJK-JP"

# Katakana + los signos que se cuelan en los regueros de la peli. Sin comilla
# simple: el MVG delimita el texto con ella.
GLIFOS = [chr(c) for c in range(0x30A1, 0x30FA)] + list("0123456789:.=*+-<>#%$@")

# La rampa sale de la paleta del tema (colors.toml): la cabeza es
# bright_foreground, el cuerpo cae hacia accent y se apaga en el verde del
# borde inactivo.
CABEZA = (0xDF, 0xFF, 0xE9)
CALIENTE = (0x6B, 0xFF, 0x92)
CUERPO = (0x00, 0xFF, 0x41)
COLA = (0x00, 0x38, 0x1A)


def mezcla(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def hexa(rgb):
    return "#%02X%02X%02X" % rgb


def reguero(draw, x, y0, largo, cell_h, size, brillo, espejo):
    """Un reguero vertical: cabeza casi blanca que se apaga hacia arriba."""
    for i in range(largo):
        y = y0 - i * cell_h
        if y < -cell_h or y > H + cell_h:
            continue
        if i == 0:
            color = CABEZA
        elif i == 1:
            color = CALIENTE
        else:
            # Gamma 1.7: el desvanecido es rapido al principio y largo al
            # final, que es como se ve en pantalla de fosforo.
            t = (i / max(largo - 1, 1)) ** 1.7
            color = mezcla(mezcla(CUERPO, COLA, t), (0, 0, 0), 1 - brillo)
        ch = random.choice(GLIFOS)
        draw.append(f"fill '{hexa(color)}' font-size {size}")
        if espejo:
            draw.append("push graphic-context")
            draw.append(f"affine -1 0 0 1 {x + size} {y}")
            draw.append(f"text 0,0 '{ch}'")
            draw.append("pop graphic-context")
        else:
            draw.append(f"text {x},{y} '{ch}'")


def capa(draw, semilla, cell_w, cell_h, size, densidad, brillo, espejo):
    """Una pasada de regueros. cell_w fija el paso de columna."""
    random.seed(semilla)
    columnas = W // cell_w + 1
    # Reparto uniforme con jitter: se elige un subconjunto de columnas en vez
    # de tirar el dado columna a columna, que es lo que dejaba calvas.
    elegidas = random.sample(range(columnas), max(1, int(columnas * densidad)))
    for cx in elegidas:
        x = cx * cell_w + random.randint(-cell_w // 3, cell_w // 3)
        for _ in range(random.randint(1, 3)):
            y0 = random.randint(-H // 4, H + cell_h * 4)
            reguero(draw, x, y0, random.randint(6, 34), cell_h, size,
                    brillo * random.uniform(0.6, 1.0), espejo)


def construir(semilla, densidad, escala, salida, espejo=True):
    draw = [f"fill black rectangle 0,0 {W},{H}"]
    # Capa de fondo: glifos pequenos, apagados, densos. Da la profundidad.
    capa(draw, semilla, int(24 * escala), int(26 * escala), int(20 * escala),
         min(1.0, densidad * 1.15), 0.45, espejo)
    # Capa de primer plano: grandes, brillantes, sueltos.
    capa(draw, semilla + 1, int(52 * escala), int(56 * escala), int(44 * escala),
         densidad * 0.55, 1.0, espejo)

    with tempfile.NamedTemporaryFile("w", suffix=".mvg", delete=False) as fh:
        fh.write("\n".join(draw) + "\n")
        mvg = fh.name

    try:
        nitido = salida + ".nitido.png"
        subprocess.run(
            ["magick", "-size", f"{W}x{H}", "xc:black", "-font", FUENTE,
             "-draw", f"@{mvg}", "-depth", "8", nitido],
            check=True)
        # Bloom: el mismo fotograma desenfocado por debajo, en screen. El
        # -evaluate baja el halo para que no lave los negros.
        subprocess.run(
            ["magick", nitido,
             "(", "+clone", "-blur", "0x9", "-evaluate", "multiply", "0.85", ")",
             "-compose", "screen", "-composite",
             # La imagen es verde sobre negro: 256 colores la dejan igual a
             # ojo (el bloom no bandea) y bajan de ~3 MB a ~0.8 MB.
             "-dither", "None", "-colors", "256",
             "-strip", "-define", "png:compression-level=9", salida],
            check=True)
        os.remove(nitido)
    finally:
        os.remove(mvg)

    print(f"  {salida}  {os.path.getsize(salida) // 1024} KB")


# semilla, densidad, escala de glifo
PRESETS = {
    "1-lluvia-densa": (7, 0.85, 1.0),
    "2-lluvia-suave": (23, 0.42, 1.15),
    "3-cascada":      (61, 0.70, 1.45),
}


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--only", help="regenerar solo este preset")
    p.add_argument("--out", help="ruta de salida (uno suelto, fuera del tema)")
    p.add_argument("--seed", type=int)
    p.add_argument("--density", type=float)
    p.add_argument("--scale", type=float, default=1.0)
    p.add_argument("--no-mirror", action="store_true",
                   help="glifos sin espejar (menos fiel, mas legibles)")
    args = p.parse_args()

    if args.out:
        construir(args.seed if args.seed is not None else 7,
                  args.density if args.density is not None else 0.7,
                  args.scale, args.out, not args.no_mirror)
        return

    destino = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backgrounds")
    os.makedirs(destino, exist_ok=True)
    presets = PRESETS if not args.only else {args.only: PRESETS[args.only]}
    print(f"Generando {len(presets)} fondo(s) a {W}x{H}:")
    for nombre, (semilla, densidad, escala) in presets.items():
        construir(semilla, densidad, escala,
                  os.path.join(destino, nombre + ".png"), not args.no_mirror)


if __name__ == "__main__":
    sys.exit(main())
