#!/usr/bin/env python3
"""Generate glyphs.png: the symbol atlas the rain shader samples.

The symbols are exactly those of `ttfx matrix --rain-symbols`, the effect that
runs in Omarchy's screensaver: HALFWIDTH katakana plus a few ASCII marks. They
are drawn white on transparent; the shader tints them.

An 8x7 grid of 48x64 px cells. That ratio mirrors a terminal's, where the row is
a good deal taller than the column.
"""
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))

SYMBOLS = [
    "2", "5", "9", "8", "Z", "*", ")", ":", ".", '"', "=", "+", "-", "¦", "|", "_",
    "ｦ", "ｱ", "ｳ", "ｴ", "ｵ", "ｶ", "ｷ", "ｹ", "ｺ", "ｻ", "ｼ", "ｽ", "ｾ", "ｿ", "ﾀ", "ﾂ",
    "ﾃ", "ﾅ", "ﾆ", "ﾇ", "ﾈ", "ﾊ", "ﾋ", "ﾎ", "ﾏ", "ﾐ", "ﾑ", "ﾒ", "ﾓ", "ﾔ", "ﾕ", "ﾗ",
    "ﾘ", "ﾜ",
]

COLS, ROWS = 8, 7
CW, CH = 48, 64
FONT = "Noto-Sans-CJK-JP"
POINT_SIZE = 44


def cell(symbol):
    if symbol is None:
        return ["(", "-size", f"{CW}x{CH}", "xc:none", ")"]
    return ["(", "-size", f"{CW}x{CH}", "-background", "none", "-fill", "white",
            "-font", FONT, "-pointsize", str(POINT_SIZE), "-gravity", "center",
            f"label:{symbol}", ")"]


def main():
    assert len(SYMBOLS) <= COLS * ROWS, "the symbols do not fit the grid"
    # The atlas lives at the repo root, next to the MatrixRain.qml that loads it.
    output = os.path.join(HERE, os.pardir, "glyphs.png")

    # Row by row and then stacked: +append/-append keep the order, whereas
    # -montage reorders on its own.
    rows = []
    for r in range(ROWS):
        pieces = []
        for c in range(COLS):
            i = r * COLS + c
            pieces += cell(SYMBOLS[i] if i < len(SYMBOLS) else None)
        path = os.path.join(HERE, f".row{r}.png")
        subprocess.run(["magick"] + pieces + ["-background", "none", "+append", path],
                       check=True)
        rows.append(path)

    subprocess.run(["magick"] + rows +
                   ["-background", "none", "-append", "-strip", output], check=True)
    for path in rows:
        os.remove(path)
    print(f"  glyphs.png  {COLS}x{ROWS} cells of {CW}x{CH}  "
          f"{os.path.getsize(output) // 1024} KB")


if __name__ == "__main__":
    main()
