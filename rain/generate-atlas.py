#!/usr/bin/env python3
"""Generate glyphs.png: the symbol atlas the rain shader samples.

The symbols are exactly those of `ttfx matrix --rain-symbols`, the effect that
runs in Omarchy's screensaver: HALFWIDTH katakana plus a few ASCII marks. They
are drawn white on transparent; the shader tints them.

An 8x7 grid of 38x80 px cells. Two numbers matter and both were measured, not
guessed:

  The RATIO. A cell is 0.475 wide for its height, against the 0.47 the shader
  lays its own cells out at, so a glyph arrives on screen shaped the way the
  font drew it. The atlas used to be 48x64 -- a ratio of 0.75 -- and every
  katakana reached the screen squeezed to 63% of its width, filling 42% of its
  cell. At this ratio and point size they fill 66% of it, undistorted.

  The MARGIN. The cell is padded so no glyph's ink comes within 2 px of the
  edge. The shader samples with plain bilinear filtering and no mipmaps, so ink
  sitting on a cell boundary is dragged into the neighbouring cell and draws a
  ghost stroke beside every character. It never happened before only because the
  glyphs were small enough to be nowhere near an edge; drawing them at their
  proper size is what makes the gutter necessary.

`check_margins` is what keeps the second one true, and it is not optional
guesswork: the glyph that decides the point size is NOT the widest one. It is
`¦`, because `label:` centres the text BOX on the font's baseline rather than
centring the ink, so a tall thin mark ends up hard against the top of the cell
while `_`, which spans a terminal cell by design, still has room. Measuring the
widest glyph and stopping there picks a size that fails.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

SYMBOLS = [
    "2", "5", "9", "8", "Z", "*", ")", ":", ".", '"', "=", "+", "-", "¦", "|", "_",
    "ｦ", "ｱ", "ｳ", "ｴ", "ｵ", "ｶ", "ｷ", "ｹ", "ｺ", "ｻ", "ｼ", "ｽ", "ｾ", "ｿ", "ﾀ", "ﾂ",
    "ﾃ", "ﾅ", "ﾆ", "ﾇ", "ﾈ", "ﾊ", "ﾋ", "ﾎ", "ﾏ", "ﾐ", "ﾑ", "ﾒ", "ﾓ", "ﾔ", "ﾕ", "ﾗ",
    "ﾘ", "ﾜ",
]

COLS, ROWS = 8, 7
CW, CH = 38, 80
FONT = "Noto-Sans-CJK-JP"
POINT_SIZE = 52
MARGIN = 2                  # px of clear cell border the filtering needs


def cell(symbol):
    if symbol is None:
        return ["(", "-size", f"{CW}x{CH}", "xc:none", ")"]
    return ["(", "-size", f"{CW}x{CH}", "-background", "none", "-fill", "white",
            "-font", FONT, "-pointsize", str(POINT_SIZE), "-gravity", "center",
            f"label:{symbol}", ")"]


def ink_box(path, col, row):
    """The bounding box of one cell's ink, as (x, y, w, h) within the cell.

    Returns None for a cell with no ink at all: `-trim` fails on a fully
    transparent image, and six of the 56 cells are deliberately empty.
    """
    crop = f"{CW}x{CH}+{col * CW}+{row * CH}"
    result = subprocess.run(
        ["magick", path, "-crop", crop, "+repage", "-alpha", "extract",
         "-format", "%w %h %X %Y", "-trim", "info:"],
        capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    width, height, x, y = result.stdout.split()
    return int(x.lstrip("+")), int(y.lstrip("+")), int(width), int(height)


def check_margins(path):
    """No glyph may come within MARGIN px of its cell's edge.

    Without this the atlas can be regenerated at a point size that looks fine
    and bleeds into the next cell on screen, which reads as a faint second
    stroke beside every character and is very hard to attribute.
    """
    tight = []
    for index, symbol in enumerate(SYMBOLS):
        box = ink_box(path, index % COLS, index // COLS)
        if box is None:
            continue
        x, y, width, height = box
        clear = min(x, y, CW - (x + width), CH - (y + height))
        if clear < MARGIN:
            tight.append((symbol, f"{width}x{height}", clear))
    if tight:
        print(f"generate-atlas: {len(tight)} glyph(s) closer than {MARGIN}px to "
              f"the cell edge, at pointsize {POINT_SIZE}:", file=sys.stderr)
        for symbol, size, clear in tight:
            print(f"  {symbol!r}  ink {size}  clear {clear}px", file=sys.stderr)
        print("  lower POINT_SIZE or raise CW/CH -- but keep CW/CH near the "
              "shader's 0.47 ratio.", file=sys.stderr)
        sys.exit(1)


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

    check_margins(output)
    print(f"  glyphs.png  {COLS}x{ROWS} cells of {CW}x{CH}  "
          f"{os.path.getsize(output) // 1024} KB")


if __name__ == "__main__":
    main()
