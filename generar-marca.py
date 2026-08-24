#!/usr/bin/env python3
"""Genera los tres PNG de identidad del tema matrix.

    ./generar-marca.py

  · unlock.png          marca del splash de arranque de Plymouth (con alfa;
                        Plymouth la pinta sobre `background` del colors.toml).
                        Es una marca propia -- wordmark en la fuente del
                        sistema con el bloque de cursor del terminal --, no el
                        logotipo de la pelicula.
  · preview-unlock.png  como se ve ese splash, para el selector de Plymouth.
  · preview.png         tarjeta del tema para el carrusel de `omarchy theme`:
                        el fondo de lluvia con una ventana de terminal y la
                        paleta debajo.

Depende de rsvg-convert e ImageMagick, y de backgrounds/1-lluvia-densa.png
(lo genera generar-fondos.py).
"""

import os
import random
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
MONO = "JetBrainsMono Nerd Font, monospace"
CJK = "Noto Sans CJK JP"

BG = "#030805"
ELEVADO = "#0A1A0F"
BARRA = "#000200"
FG = "#A8F5BC"
BRIGHT = "#DFFFE9"
DARK_FG = "#2E5C3C"
ACCENT = "#00FF41"

PALETA = [
    ("bg", "#030805"), ("red", "#F0263F"), ("green", "#00FF41"),
    ("yellow", "#C6FF57"), ("blue", "#12A96A"), ("magenta", "#35D68F"),
    ("cyan", "#7BFFD4"), ("fg", "#A8F5BC"),
    ("muted", "#1B3A25"), ("red+", "#FF5C74"), ("green+", "#6BFF92"),
    ("yellow+", "#E2FF8F"), ("blue+", "#2BD68C"), ("magenta+", "#66F0B4"),
    ("cyan+", "#B8FFE8"), ("fg+", "#DFFFE9"),
]


def render(svg, ancho, alto, salida):
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as fh:
        fh.write(svg)
        ruta = fh.name
    try:
        subprocess.run(["rsvg-convert", "-w", str(ancho), "-h", str(alto),
                        ruta, "-o", salida], check=True)
    finally:
        os.remove(ruta)


def lluvia(w, h, semilla, paso, tam, opacidad, centrado_libre=True):
    """Regueros de fondo. centrado_libre los apaga hacia el centro para no
    competir con lo que se pinte encima."""
    random.seed(semilla)
    glifos = [chr(c) for c in range(0x30A1, 0x30FA)]
    out = []
    for cx in range(w // paso + 1):
        x = cx * paso + random.randint(-paso // 4, paso // 4)
        centro = abs(x - w / 2) / (w / 2)
        umbral = (0.34 + centro * 0.52) if centrado_libre else 0.75
        if random.random() > umbral:
            continue
        largo = random.randint(6, 16)
        y0 = random.randint(int(h * 0.1), h)
        for i in range(largo):
            y = y0 - i * int(tam * 1.45)
            if y < tam:
                break
            op = max(0.0, (1 - i / largo) ** 1.6) * opacidad * (
                (0.4 + centro * 0.9) if centrado_libre else 1.0)
            col = BRIGHT if i == 0 else ACCENT
            out.append(
                f'<text x="0" y="0" transform="translate({x + tam},{y}) scale(-1,1)" '
                f'font-family="{CJK}" font-size="{tam}" fill="{col}" '
                f'opacity="{op:.3f}">{random.choice(glifos)}</text>')
    return "".join(out)


FOSFORO = f'''
    <filter id="fosforo" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="6" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <linearGradient id="regla" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0"   stop-color="{ACCENT}" stop-opacity="0"/>
      <stop offset="0.5" stop-color="{ACCENT}" stop-opacity="0.55"/>
      <stop offset="1"   stop-color="{ACCENT}" stop-opacity="0"/>
    </linearGradient>'''


def marca(w=1108, h=523, fondo=None):
    """El wordmark. `fondo` en None deja alfa (lo que Plymouth necesita)."""
    # El wordmark medido: tinta en x 265..782 con text-anchor middle en 522.
    # El cursor va justo detras, a la altura de mayuscula (240..316).
    base = f'<rect width="{w}" height="{h}" fill="{fondo}"/>' if fondo else ""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 1108 523">
  <defs>{FOSFORO}</defs>
  {base}
  <g>{lluvia(1108, 523, 11, 46, 26, 0.32)}</g>
  <g filter="url(#fosforo)">
    <text x="522" y="316" text-anchor="middle" font-family="{MONO}"
          font-weight="700" font-size="104" letter-spacing="30" fill="{ACCENT}">MATRIX</text>
    <rect x="808" y="240" width="34" height="76" fill="{BRIGHT}"/>
  </g>
  <rect x="220" y="380" width="668" height="2" fill="url(#regla)"/>
  <text x="554" y="424" text-anchor="middle" font-family="{MONO}" font-size="23"
        letter-spacing="11" fill="#3D7A4E">WAKE UP</text>
</svg>'''


def preview_unlock(w=1920, h=1080):
    """El splash tal cual se ve: la marca centrada y el campo de contrasena."""
    cx, cy = w / 2, h * 0.46
    mw, mh = 1108, 523
    campo_y = h * 0.74
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">
  <defs>{FOSFORO}</defs>
  <rect width="{w}" height="{h}" fill="{BG}"/>
  <g transform="translate({cx - mw/2},{cy - mh/2})">
    {marca().split('</defs>')[1].rsplit('</svg>')[0]}
  </g>
  <g>
    <rect x="{cx - 150}" y="{campo_y}" width="300" height="42" rx="6"
          fill="{ELEVADO}" stroke="{ACCENT}" stroke-opacity="0.45"/>
    <rect x="{cx - 176}" y="{campo_y + 11}" width="14" height="11" rx="2" fill="{DARK_FG}"/>
    <path d="M {cx - 173} {campo_y + 11} v -4 a 4 4 0 0 1 8 0 v 4"
          fill="none" stroke="{DARK_FG}" stroke-width="2"/>
    <g fill="{FG}">
      <circle cx="{cx - 124}" cy="{campo_y + 21}" r="4"/>
      <circle cx="{cx - 108}" cy="{campo_y + 21}" r="4"/>
      <circle cx="{cx - 92}"  cy="{campo_y + 21}" r="4"/>
      <circle cx="{cx - 76}"  cy="{campo_y + 21}" r="4"/>
    </g>
  </g>
</svg>'''


CODIGO = [
    [("def ", "#12A96A"), ("despertar", "#00FF41"), ("(", FG), ("sujeto", "#C6FF57"),
     (", ", FG), ("pastilla", "#C6FF57"), ("=", FG), ('"roja"', "#7BFFD4"), ("):", FG)],
    [("    ", FG), ("if", "#12A96A"), (" pastilla ", FG), ("==", FG), (' "azul"', "#7BFFD4"), (":", FG)],
    [("        raise ", "#12A96A"), ("SigueDurmiendo", "#F0263F"), ("(sujeto)", FG)],
    [("    ", FG), ("return", "#12A96A"), (" sujeto.", FG), ("desconectar", "#35D68F"), ("()", FG)],
]


def preview(w=1800, h=1012):
    """Tarjeta del carrusel: la ventana de terminal sobre la lluvia."""
    vw, vh = 1120, 404
    vx, vy = (w - vw) / 2, 150
    # Una <text> por linea con los tspan encadenados sin x propia: dejar que
    # fluyan es lo unico que respeta el avance real de la fuente. Calcular la
    # x de cada tspan a ojo descuadraba los operadores.
    lineas = []
    y = vy + 122
    for linea in CODIGO:
        tspans = "".join(
            '<tspan fill="%s">%s</tspan>' % (
                col, txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            for txt, col in linea)
        lineas.append(f'<text x="{vx + 44}" y="{y}" font-family="{MONO}" font-size="27" '
                      f'xml:space="preserve">{tspans}</text>')
        y += 46
    # Panel bajo la paleta: sin el, las etiquetas caen sobre la lluvia y no se
    # leen.
    sw, gap = 92, 12
    total = len(PALETA) * sw + (len(PALETA) - 1) * gap
    sx = (w - total) / 2
    py = 700
    swatches = [f'<rect x="{sx - 34}" y="{py - 30}" width="{total + 68}" height="150" rx="10" '
                f'fill="{BG}" opacity="0.93"/>']
    for i, (nombre, hexa) in enumerate(PALETA):
        x = sx + i * (sw + gap)
        swatches.append(
            f'<rect x="{x}" y="{py}" width="{sw}" height="54" rx="3" fill="{hexa}" '
            f'stroke="{FG}" stroke-opacity="0.18"/>'
            f'<text x="{x + sw/2}" y="{py + 82}" text-anchor="middle" font-family="{MONO}" '
            f'font-size="17" fill="{DARK_FG}">{nombre}</text>')
    prompt = (f'<tspan fill="{ACCENT}">~</tspan><tspan fill="{DARK_FG}"> on </tspan>'
              f'<tspan fill="{BRIGHT}">main</tspan><tspan fill="{ACCENT}"> ❯ </tspan>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">
  <rect width="{w}" height="{h}" fill="{BG}" opacity="0.62"/>

  <rect width="{w}" height="46" fill="{BARRA}"/>
  <text x="26" y="30" font-family="{MONO}" font-size="20" fill="{FG}">1 2 3</text>
  <text x="{w/2}" y="30" text-anchor="middle" font-family="{MONO}" font-size="20" fill="{FG}">matrix</text>
  <text x="{w - 26}" y="30" text-anchor="end" font-family="{MONO}" font-size="20" fill="{FG}">23:58</text>

  <rect x="{vx - 2}" y="{vy - 2}" width="{vw + 4}" height="{vh + 4}" rx="10" fill="{ACCENT}"/>
  <rect x="{vx}" y="{vy}" width="{vw}" height="{vh}" rx="8" fill="{ELEVADO}"/>
  <text x="{vx + 44}" y="{vy + 62}" font-family="{MONO}" font-size="27" xml:space="preserve">{prompt}<tspan fill="{FG}">bat despertar.py</tspan></text>
  {"".join(lineas)}
  <text x="{vx + 44}" y="{vy + 356}" font-family="{MONO}" font-size="27" xml:space="preserve">{prompt}<tspan fill="{BRIGHT}">▊</tspan></text>

  {"".join(swatches)}
</svg>'''


def main():
    unlock = os.path.join(AQUI, "unlock.png")
    render(marca(), 1108, 523, unlock)
    print(f"  unlock.png  {os.path.getsize(unlock) // 1024} KB")

    pu = os.path.join(AQUI, "preview-unlock.png")
    render(preview_unlock(), 1920, 1080, pu)
    subprocess.run(["magick", pu, "-strip", "-dither", "None", "-colors", "256", pu], check=True)
    print(f"  preview-unlock.png  {os.path.getsize(pu) // 1024} KB")

    fondo = os.path.join(AQUI, "backgrounds", "1-lluvia-densa.png")
    if not os.path.exists(fondo):
        print("  ! falta backgrounds/1-lluvia-densa.png: corre antes generar-fondos.py",
              file=sys.stderr)
        return 1
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
        capa = fh.name
    p = os.path.join(AQUI, "preview.png")
    try:
        render(preview(), 1800, 1012, capa)
        subprocess.run(
            ["magick", fondo, "-resize", "1800x1012^", "-gravity", "center",
             "-extent", "1800x1012", capa, "-composite",
             "-strip", "-dither", "None", "-colors", "256",
             "-define", "png:compression-level=9", p], check=True)
    finally:
        os.remove(capa)
    print(f"  preview.png  {os.path.getsize(p) // 1024} KB")


if __name__ == "__main__":
    sys.exit(main())
