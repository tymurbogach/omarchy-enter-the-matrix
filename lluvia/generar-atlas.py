#!/usr/bin/env python3
"""Genera glifos.png: el atlas de simbolos que muestrea el shader de lluvia.

Los simbolos son exactamente los de `ttfx matrix --rain-symbols`, el efecto que
corre en el screensaver de Omarchy: katakana de MEDIA anchura mas unos signos
ASCII. Van blancos sobre transparente; el shader los tine.

Rejilla de 8x7 celdas de 60x128 px: la misma relacion que la celda del shader
(alta y estrecha, como la del terminal).
"""
import os
import subprocess

AQUI = os.path.dirname(os.path.abspath(__file__))

SIMBOLOS = [
    "2", "5", "9", "8", "Z", "*", ")", ":", ".", '"', "=", "+", "-", "¦", "|", "_",
    "ｦ", "ｱ", "ｳ", "ｴ", "ｵ", "ｶ", "ｷ", "ｹ", "ｺ", "ｻ", "ｼ", "ｽ", "ｾ", "ｿ", "ﾀ", "ﾂ",
    "ﾃ", "ﾅ", "ﾆ", "ﾇ", "ﾈ", "ﾊ", "ﾋ", "ﾎ", "ﾏ", "ﾐ", "ﾑ", "ﾒ", "ﾓ", "ﾔ", "ﾕ", "ﾗ",
    "ﾘ", "ﾜ",
]

COLS, FILAS = 8, 7
# La celda del atlas tiene que tener la MISMA relacion que la celda que dibuja
# el shader (cellW = cellH * 0.47). Estaba a 48x64 (0.75) y el shader la metia
# en 30x64: los glifos salian aplastados de ancho, y por tanto mas finos y mas
# apagados que en el screensaver de verdad. 60x128 es 0.469, que si cuadra; el
# doble de resolucion es solo para que no pixele al escalar.
CW, CH = 60, 128
FUENTE = "Noto-Sans-CJK-JP"
CUERPO = 84


def celda(simbolo):
    if simbolo is None:
        return ["(", "-size", f"{CW}x{CH}", "xc:none", ")"]
    return ["(", "-size", f"{CW}x{CH}", "-background", "none", "-fill", "white",
            "-font", FUENTE, "-pointsize", str(CUERPO), "-gravity", "center",
            f"label:{simbolo}", ")"]


def main():
    assert len(SIMBOLOS) <= COLS * FILAS, "los simbolos no caben en la rejilla"
    salida = os.path.join(AQUI, "glifos.png")

    # Fila a fila y luego apilado: +append/-append respetan el orden, mientras
    # que -montage lo reordena por su cuenta.
    filas = []
    for f in range(FILAS):
        trozo = []
        for c in range(COLS):
            i = f * COLS + c
            trozo += celda(SIMBOLOS[i] if i < len(SIMBOLOS) else None)
        ruta = os.path.join(AQUI, f".fila{f}.png")
        subprocess.run(["magick"] + trozo + ["-background", "none", "+append", ruta],
                       check=True)
        filas.append(ruta)

    subprocess.run(["magick"] + filas +
                   ["-background", "none", "-append", "-strip", salida], check=True)
    for r in filas:
        os.remove(r)
    print(f"  glifos.png  {COLS}x{FILAS} celdas de {CW}x{CH}  "
          f"{os.path.getsize(salida) // 1024} KB")


if __name__ == "__main__":
    main()
