#!/usr/bin/env python3
"""Derive the provider's boot splash from the Plymouth this machine has.

Omarchy's splash is a SCRIPT theme (`omarchy.script`), and what
`omarchy plymouth set-by-theme` lets a theme change is three things: background
colour, text colour and one still PNG. No animation fits through that door.

So it is done the way the lock is done: start from $OMARCHY_PATH's
`omarchy.script` and apply a minimal patch that replaces the static logo with
the line being typed out. Everything else -- password dialog, progress bar, boot
messages -- is Omarchy's, untouched. A post-update.d hook derives it again after
every `omarchy update`.

It installs as a SEPARATE theme under /usr/share/plymouth/themes/, so Omarchy's
own is never overwritten: going back is `omarchy plymouth reset`.

    ./derive-plymouth.py --stage-only    # build it, no sudo
    ./derive-plymouth.py                 # build and install

MIND: if your disk is encrypted, Plymouth is also what asks for the passphrase
at boot. That is why the patch is additive and touches none of the password
callbacks, and why it installs alongside rather than on top.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Loaded by path rather than by name: this file may be exec'd from a spec, or
# run from ~/.local/bin, where bin/ is not on sys.path either way.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from provider import PROVIDER  # noqa: E402

OMARCHY = Path(os.environ.get("OMARCHY_PATH", "/usr/share/omarchy"))
SOURCE = OMARCHY / "default/plymouth"
SLUG = PROVIDER["slug"]
CLI = PROVIDER["cli"]
THEME = PROVIDER["plymouth"]["theme"]
TARGET = Path("/usr/share/plymouth/themes") / THEME

# What is typed out at boot, in order, and in the provider's colour.
LINES = PROVIDER["plymouth"]["lines"]
COLOUR = PROVIDER["plymouth"]["color"]
CURSOR = "█"               # full block: the terminal cursor
FONT = "JetBrainsMono Nerd Font"
# The point size is NOT fixed: Plymouth draws at the panel's NATIVE resolution,
# not the logical one. On a 3072 px laptop panel a size chosen for 1080p comes
# out tiny. It is worked out at derive time, which is when we know what machine
# we are on, and written into the .plymouth.
LINE_WIDTH = 0.40          # fraction of the screen width the longest line takes
MONO_ADVANCE = 0.60        # cell width / em in JetBrains Mono
FPS = 50                   # the rate omarchy.script assumes
FRAMES_PER_CHAR = 3        # -> about 17 keystrokes a second
BLINK = 15                 # frames per half-blink of the cursor
BLINKS = 4                 # half-blinks once a line is complete


def die(message):
    print(f"derive-plymouth: {message}", file=sys.stderr)
    sys.exit(1)


def screen_width():
    """The NATIVE width of the largest monitor. Plymouth knows nothing of scaling."""
    try:
        import json
        output = subprocess.run(["hyprctl", "monitors", "-j"],
                                capture_output=True, text=True, check=True).stdout
        widths = [m["width"] for m in json.loads(output)]
        return max(widths) if widths else 1920
    except Exception:
        return 1920


def point_size_for(width):
    """Points that make the longest line take up LINE_WIDTH of the screen."""
    cells = max(len(line) for line in LINES) + 1        # +1 for the cursor
    cell_px = (width * LINE_WIDTH) / cells
    return max(12, round(cell_px / MONO_ADVANCE * 0.75))   # px -> points at 96 dpi


def available_font():
    """The font has to exist: the mkinitcpio hook resolves it with fc-match from
    the .plymouth's `Font=` and copies it into the initramfs. Without it, boot
    would have no text at all."""
    try:
        output = subprocess.run(["fc-match", "-f", "%{family}", FONT],
                                capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return "monospace"
    return FONT if FONT.lower() in output.lower() else "monospace"


def storyboard():
    """The animation, already resolved into steps.

    Generated here rather than inside the Plymouth script on purpose: that way
    the .script needs no SubString, no Length and no string concatenation. Every
    step carries its literal text, how many frames it lasts, and which line it
    belongs to (for placing the X).
    """
    text, duration, line = [], [], []
    for i, phrase in enumerate(LINES):
        for n in range(1, len(phrase) + 1):
            text.append(phrase[:n] + CURSOR)
            duration.append(FRAMES_PER_CHAR)
            line.append(i)
        for b in range(BLINKS):
            text.append(phrase + (" " if b % 2 else CURSOR))
            duration.append(BLINK)
            line.append(i)
    return text, duration, line


def literal(string):
    return '"' + string.replace("\\", "\\\\").replace('"', '\\"') + '"'


def typing_block():
    text, duration, line = storyboard()
    widths = "\n".join(
        f'  global.mx_width[{i}] = Image.Text({literal(phrase + CURSOR)}, '
        f'global.mx_r, global.mx_g, global.mx_b).GetWidth();'
        for i, phrase in enumerate(LINES))
    table = "\n".join(
        f'global.mx_txt[{i}] = {literal(t)}; global.mx_dur[{i}] = {d}; '
        f'global.mx_line[{i}] = {p};'
        for i, (t, d, p) in enumerate(zip(text, duration, line)))

    name = PROVIDER["displayName"]
    rule = "-" * max(1, 35 - len(name))
    return f'''
#----------------------------------------- {name} {rule}
# Put here by {CLI}. DO NOT edit this file by hand: it is derived again
# from Omarchy's omarchy.script on every `omarchy update`.
#
# It replaces the static logo with the line being typed. logo.png is still
# loaded, just invisible: its box is what the password dialog below uses to
# place itself, and we do not want to move anything.
#
# The step table is generated: each entry carries its literal text, so there is
# no string slicing or concatenation to do in here.

global.mx_r = {COLOUR[0]};
global.mx_g = {COLOUR[1]};
global.mx_b = {COLOUR[2]};

global.mx_steps = {len(text)};
{table}

global.mx_step = 0;
global.mx_frame = 0;
global.mx_painted = "";
global.mx_cx = Window.GetWidth() / 2;
global.mx_cy = logo.sprite.GetY() + logo.image.GetHeight() / 2;

mx.sprite = Sprite();

fun mx_measure() {{
{widths}
}}

mx_measure();

fun mx_paint(index) {{
  text = global.mx_txt[index];
  if (text == global.mx_painted) return;
  global.mx_painted = text;

  image = Image.Text(text, global.mx_r, global.mx_g, global.mx_b);
  # X fixed per line: the text grows rightwards from a stable edge instead of
  # re-centring on every character, which is how a terminal types.
  x = global.mx_cx - global.mx_width[global.mx_line[index]] / 2;
  mx.sprite.SetImage(image);
  mx.sprite.SetPosition(x, global.mx_cy - image.GetHeight() / 2, 10000);
}}

fun mx_tick() {{
  if (global.mx_step >= global.mx_steps) return;

  if (global.mx_painted == "") {{
    mx_paint(0);
    return;
  }}

  global.mx_frame++;
  if (global.mx_frame < global.mx_dur[global.mx_step]) return;

  global.mx_frame = 0;
  global.mx_step++;
  # At the end it rests on the last line rather than looping: a boot is shorter
  # than the whole animation, and starting over would be noticeable.
  if (global.mx_step >= global.mx_steps) return;
  mx_paint(global.mx_step);
}}
'''


def patch(text):
    # 1. The logo stops being visible but is still loaded: its box places the
    #    password dialog.
    anchor = "logo.sprite.SetOpacity(1);"
    if text.count(anchor) != 1:
        die(f"expected exactly one `{anchor}` in omarchy.script, found "
            f"{text.count(anchor)}. Omarchy's splash has changed: leaving it alone.")
    text = text.replace(
        anchor,
        "logo.sprite.SetOpacity(0);  # the mark is typed by mx_tick(), below\n"
        + typing_block())

    # 2. Hook the animation onto the 50 fps refresh that already exists.
    anchor = "fun refresh_callback() {"
    if text.count(anchor) != 1:
        die("cannot find refresh_callback() in omarchy.script: leaving it alone.")
    return text.replace(anchor, anchor + "\n  mx_tick();")


def stage(target, colours):
    background, foreground, logo = colours
    if not (SOURCE / "omarchy.script").is_file():
        die(f"cannot find Omarchy's Plymouth at {SOURCE}")
    if not Path(logo).is_file():
        die(f"cannot find the theme's logo: {logo}")

    for f in SOURCE.iterdir():
        if f.is_file():
            shutil.copy2(f, target / f.name)
    shutil.copy2(logo, target / "logo.png")

    # The same asset re-tinting omarchy-plymouth-set does.
    for asset in ("bullet.png", "entry.png", "lock.png", "progress_bar.png"):
        path = target / asset
        if path.is_file():
            subprocess.run(["magick", str(path), "-channel", "RGB",
                            "+level-colors", f"#{foreground},#{foreground}", str(path)],
                           check=True)

    r, g, b = (int(background[i:i + 2], 16) / 255 for i in (0, 2, 4))
    script = (target / "omarchy.script").read_text()
    script = re.sub(r"^Window\.SetBackgroundTopColor.*$",
                    f"Window.SetBackgroundTopColor({r:.3f}, {g:.3f}, {b:.3f});",
                    script, count=1, flags=re.M)
    script = re.sub(r"^Window\.SetBackgroundBottomColor.*$",
                    f"Window.SetBackgroundBottomColor({r:.3f}, {g:.3f}, {b:.3f});",
                    script, count=1, flags=re.M)
    script = patch(script)

    (target / f"{THEME}.script").write_text(script)
    (target / "omarchy.script").unlink()
    (target / "omarchy.plymouth").unlink(missing_ok=True)

    font = available_font()
    width = screen_width()
    size = point_size_for(width)
    (target / f"{THEME}.plymouth").write_text(f"""[Plymouth Theme]
Name={PROVIDER["plymouth"]["name"]}
Description={PROVIDER["plymouth"]["description"]}

ModuleName=script

[script]
ImageDir={TARGET}
ScriptFile={TARGET}/{THEME}.script
ConsoleLogBackgroundColor=0x{background}
MonospaceFont={font} {size}
Font={font} {size}
""")
    return font, width, size


def theme_colour(key, theme_dir):
    for row in (theme_dir / "colors.toml").read_text().splitlines():
        if "=" in row:
            k, v = row.split("=", 1)
            if k.strip() == key:
                return v.strip().strip('"').lstrip("#")
    die(f"`{key}` is missing from colors.toml")


def main():
    stage_only = "--stage-only" in sys.argv
    theme_dir = Path(subprocess.run(["omarchy-theme-dir", SLUG],
                                    capture_output=True, text=True,
                                    check=True).stdout.strip())

    colours = (theme_colour("background", theme_dir),
               theme_colour("foreground", theme_dir),
               theme_dir / "unlock.png")

    staging = Path(tempfile.mkdtemp(prefix=f"{SLUG}-plymouth."))
    try:
        font, width, size = stage(staging, colours)
        steps = len(storyboard()[0])
        seconds = sum(storyboard()[1]) / FPS
        print(f"  {THEME}: {steps} steps, {seconds:.1f}s of animation")
        print(f"  font {font!r} at {size} pt, sized for a {width} px panel")

        if stage_only:
            out = Path.home() / f".cache/{CLI}/plymouth"
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.rmtree(out, ignore_errors=True)
            shutil.copytree(staging, out)
            print(f"  staged at {out} (not installed)")
            return

        # The four privileged steps. sudo may have nowhere to ask for a
        # password -- from a hook, from an agent, from an editor's shell -- or
        # the answer may simply be no. A Python traceback is a terrible way to
        # say "you did not authenticate": it reads as a broken pack rather than
        # an unauthorised one, and install.sh prints it in the middle of an
        # otherwise successful run.
        already_installed = TARGET.is_dir()
        try:
            subprocess.run(["sudo", "mkdir", "-p", str(TARGET)], check=True)
            subprocess.run(["sudo", "cp", "-a", "--no-preserve=mode,ownership",
                            f"{staging}/.", f"{TARGET}/"], check=True)
            subprocess.run(["sudo", "plymouth-set-default-theme", THEME], check=True)

            if shutil.which("limine-mkinitcpio"):
                subprocess.run(["sudo", "limine-mkinitcpio"], check=True)
            else:
                subprocess.run(["sudo", "mkinitcpio", "-P"], check=True)
        except subprocess.CalledProcessError as failure:
            # Failing between the copy and the initramfs would leave a directory
            # that is not yet a theme. Only what THIS run created is taken back:
            # re-deriving over a splash that already worked must not delete it.
            if not already_installed:
                subprocess.run(["sudo", "-n", "rm", "-rf", str(TARGET)],
                               check=False, capture_output=True)
            die(f"`{' '.join(failure.cmd[:3])}` failed, so the boot splash was "
                f"not installed.\n"
                f"  Nothing was left half written, and the rest of the pack is "
                f"unaffected.\n"
                f"  This step writes outside your home directory and needs a "
                f"real terminal to ask\n"
                f"  for your password. From one, run: {CLI} boot on")
        print("  installed and set as default. To go back: omarchy plymouth reset")
    finally:
        shutil.rmtree(staging, ignore_errors=True)


if __name__ == "__main__":
    main()
