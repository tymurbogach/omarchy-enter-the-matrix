#!/usr/bin/env python3
"""Generate the matrix theme's static backgrounds.

    ./generate-backgrounds.py                  regenerate every preset
    ./generate-backgrounds.py --only 0-live-rain
    ./generate-backgrounds.py --out /tmp/test.png --seed 99 --density 0.7

What it paints is **a frame of the rain/matrix.frag shader**, not a rain of its
own: the same glyphs, the same colours, the same head-at-the-bottom geometry.
That is what makes the still background and the animated one look alike -- the
still one is the thumbnail in the carousel and the marker that switches the
shader on, so any difference between them would read as the rain having frozen.

Output is 3840x2400, a 16:10 superset: it covers a 4K screen without cropping
the sides and a 3072x1920 laptop panel without upscaling.
"""

import argparse
import os
import random
import subprocess
import sys
import tempfile

W, H = 3840, 2400

# Grid measured off a screenshot of the real screensaver (alacritty at
# font-size 18 on a panel at scale 2): 29x64 native px. The PNG shows 1:1 there.
CELL_W, CELL_H = 30, 64
FONT = "Noto-Sans-CJK-JP"

# The same ones as `ttfx matrix --rain-symbols`. Duplicated on purpose from
# rain/generate-atlas.py: they are two independent programs, and a cross-import
# between them would be more fragile than these four lines.
GLYPHS = [
    "2", "5", "9", "8", "Z", "*", ")", ":", ".", '"', "=", "+", "-", "¦", "|", "_",
    "ｦ", "ｱ", "ｳ", "ｴ", "ｵ", "ｶ", "ｷ", "ｹ", "ｺ", "ｻ", "ｼ", "ｽ", "ｾ", "ｿ", "ﾀ", "ﾂ",
    "ﾃ", "ﾅ", "ﾆ", "ﾇ", "ﾈ", "ﾊ", "ﾋ", "ﾎ", "ﾏ", "ﾐ", "ﾑ", "ﾒ", "ﾓ", "ﾔ", "ﾕ", "ﾗ",
    "ﾘ", "ﾜ",
]

HEAD = (0xE2, 0xFF, 0xE2)
RAIN_A = (0x7E, 0xBB, 0x7E)
RAIN_B = (0x0E, 0x3A, 0x12)


def mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def as_hex(rgb):
    return "#%02X%02X%02X" % rgb


def streak(draw, cx, head, length, size, y_scale, dim=1.0):
    """One streak: head at the bottom, trail rising, the way the shader does it."""
    x = cx * CELL_W
    for i in range(length):
        row = head - i
        if row < 0:
            break
        y = row * CELL_H
        if y > H:
            continue
        if i == 0:
            color = mix((0, 0, 0), HEAD, dim)
        else:
            # The shader's mix(1.0, 0.30, t**0.75): the trail fades but never
            # disappears, which is how ttfx behaves.
            t = i / max(length - 1, 1)
            brightness = 1.0 - 0.70 * (t ** 0.75)
            color = mix((0, 0, 0),
                        mix(RAIN_A, RAIN_B, random.random()),
                        brightness * dim)
        ch = random.choice(GLYPHS)
        draw.append(f"fill '{as_hex(color)}' font-size {size} "
                    f"text {x},{y + y_scale} '{ch}'")


def build(seed, density, scale, output, minimal=False):
    random.seed(seed)
    size = int(CELL_H * 0.62 * scale)
    # Glyphs are anchored on their baseline, so they have to be pushed down
    # inside the cell to sit centred the way they do in a terminal.
    y_scale = int(CELL_H * 0.72)
    rows = H // CELL_H + 1
    columns = W // CELL_W + 1

    draw = [f"fill black rectangle 0,0 {W},{H}"]
    chosen = random.sample(range(columns), max(1, int(columns * density)))
    for cx in chosen:
        # Every column gets its own head and length, like the shader's per-column
        # hashes. The head may fall off the bottom: then only the tail end shows,
        # and that is what sells the falling.
        if minimal:
            # Every head near the top: the rain has only just entered frame and
            # the bottom two thirds stay black. That is composition -- thinly
            # scattering the same streaks over the whole screen only gave faint
            # noise with nowhere to look.
            head = random.randint(1, max(2, int(rows * 0.38)))
            length = random.randint(10, 24)
        else:
            head = random.randint(0, rows + 12)
            length = random.randint(16, 38)
        streak(draw, cx, head, length, size, y_scale,
               dim=0.85 if minimal else 1.0)

    if minimal:
        # One streak at full brightness, falling further than the rest. That is
        # what reads; everything else is texture.
        streak(draw, int(columns * 0.41), int(rows * 0.58), 26, size, y_scale)

    with tempfile.NamedTemporaryFile("w", suffix=".mvg", delete=False) as fh:
        fh.write("\n".join(draw) + "\n")
        mvg = fh.name
    try:
        subprocess.run(
            ["magick", "-size", f"{W}x{H}", "xc:black", "-font", FONT,
             "-draw", f"@{mvg}", "-depth", "8",
             # Green on black: 256 colours are invisible and cut the size a lot.
             "-dither", "None", "-colors", "256",
             "-strip", "-define", "png:compression-level=9", output],
            check=True)
    finally:
        os.remove(mvg)
    print(f"  {output}  {os.path.getsize(output) // 1024} KB")


# seed, density, glyph scale.
# Only the live-rain frame is a real preset: it is the thumbnail shown in the
# carousel and the marker that switches the rain shader on (see rain/). Use
# --out for one-offs.
PRESETS = {
    # seed, density, scale, minimal
    "0-live-rain": (11, 0.92, 1.0, False),
    # No mark and no logo: black, a few very dim columns of texture and one lit
    # streak. The idea is atmosphere, not a poster.
    "1-minimal":   (29, 0.50, 1.0, True),
}


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--only", help="regenerate only this preset")
    p.add_argument("--out", help="output path (a one-off, outside the theme)")
    p.add_argument("--seed", type=int)
    p.add_argument("--density", type=float)
    p.add_argument("--scale", type=float, default=1.0)
    args = p.parse_args()

    if args.out:
        build(args.seed if args.seed is not None else 11,
              args.density if args.density is not None else 0.9,
              args.scale, args.out)
        return

    target = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backgrounds")
    os.makedirs(target, exist_ok=True)
    presets = PRESETS if not args.only else {args.only: PRESETS[args.only]}
    print(f"Generating {len(presets)} background(s) at {W}x{H}:")
    for name, (seed, density, scale, minimal) in presets.items():
        build(seed, density, scale,
              os.path.join(target, name + ".png"), minimal)


if __name__ == "__main__":
    sys.exit(main())
