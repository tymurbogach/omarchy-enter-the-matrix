#!/usr/bin/env python3
"""Derive the provider's boot splash from the Plymouth this machine has.

Omarchy's splash is a SCRIPT theme (`omarchy.script`), and what
`omarchy plymouth set-by-theme` lets a theme change is three things: background
colour, text colour and one still PNG. No animation fits through that door.

So it is done the way the lock is done: start from $OMARCHY_PATH's
`omarchy.script` and apply a minimal patch. Everything the patch does not name
-- the boot progress plumbing, the message callbacks, the entry and lock
sprites -- is Omarchy's, untouched. A post-update.d hook derives it again after
every `omarchy update`.

It installs as a SEPARATE theme under /usr/share/plymouth/themes/, so Omarchy's
own is never overwritten: going back is `omarchy plymouth reset`.

    ./derive-plymouth.py --stage-only    # build it, no sudo
    ./derive-plymouth.py                 # build and install

What it draws is Neo's monitor:

    Wake up, Neo...█                     upper left, one line at a time, the
                                         screen clearing between them

           > ••••••••█                   and in the middle, where Omarchy puts
                                         its dialog, the passphrase as a
                                         terminal rather than a rounded box

    ████████▒▒▒▒▒▒▒▒  42%                and, once it is answered, the boot's
                                         progress on the same grid: one track,
                                         drawn twice, at two brightnesses

MIND: if your disk is encrypted, Plymouth is also what asks for the passphrase
at boot. The patch adds a display-password callback AFTER Omarchy's rather than
rewriting it -- the last registration wins -- so not one line of the passphrase
path is edited. Escape hatches remain `omarchy plymouth reset` and
`plymouth.enable=0` on the kernel line.

Verify it with `bin/preview-plymouth.sh`, which runs this for real in a window.
"""

import os
import re
import shutil
import string
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

# What is typed out at boot, in order.
LINES = PROVIDER["plymouth"]["lines"]

# The typed lines take the THEME's `green` -- its accent, out of colors.toml at
# derive time. Repeating the hex in provider.json would work today and drift the
# first time the palette moved.
#
# Not the phosphor #00FF41 the shader's heads use: on a black screen, at the
# size these lines are drawn, that reads as glare rather than as a monitor. And
# not `foreground` either, which is the theme's text colour and comes out sage.
# A provider that wants something else says so with `color`.
COLOUR = PROVIDER["plymouth"].get("color")
COLOUR_HEX = ("".join(f"{round(channel * 255):02X}" for channel in COLOUR)
              if COLOUR else None)

# The boxed prompt is a different colour from the lines, on purpose: in the film
# the terminal runs green and the boxed prompt is a pale aqua. A provider that
# does not say gets the one colour, so nothing older changes shape.
DIALOG_COLOUR = PROVIDER["plymouth"].get("dialogColor") or COLOUR or [1, 1, 1]
DIALOG_HEX = "".join(f"{round(channel * 255):02X}" for channel in DIALOG_COLOUR)
BOX_TITLE = PROVIDER["plymouth"].get("boxTitle", "enter password")
PROGRESS_TITLE = PROVIDER["plymouth"].get("progressTitle", "booting")

# The family Plymouth is told about in the .plymouth. It decides which single
# TTF the mkinitcpio hook copies into the initramfs, and therefore what the few
# things still drawn as TEXT come out in -- the disk's own prompt and the caps
# lock label. Everything whose shape matters is a PNG instead; see FONT_FILE.
FONT = "JetBrainsMono Nerd Font"

# ...and the face the splash is actually drawn in, as a FILE, out of the theme's
# own fonts/ directory rather than out of fc-match.
#
# Naming a family here instead would be a trap: at derive time fc-match may not
# have it, and when it misses it does not fail -- it returns `monospace`, and the
# splash comes out in the wrong face with nothing anywhere to say so. A file in
# the theme cannot miss. It is also why the typed lines are baked: at boot there
# is no fc-match at all, so a per-call family is ignored outright.
FONT_FILE = "fonts/TerminessNerdFont-Regular.ttf"

BLOCK = "█"                 # full block: the progress track is a row of these
# One typed character of the passphrase. A dash, and NOT any kind of block.
#
# This was `▊` first -- seven-eighths of a cell, chosen over `█` precisely so the
# characters would not butt together into one solid bar. It did not work, and the
# reason is worth keeping: the progress readout lives in the SAME row and is also
# made of blocks, so a boot went `solid bar` (typing) -> `empty track` ->
# `filling track`, and the eye read all three as one meter behaving strangely.
# What separates the passphrase from the progress is the GLYPH, not the gap.
#
# Then it was `•`, which worked. It is a dash now because that is what the film's
# boxed prompt shows, and a dash is further still from a block: 4.4 % of one in
# Terminus, against the dot's 6 %.
MASK = "-"
# The progress readout's characters, as one strip to crop cells out of. Baked
# for the same reason everything else here is: at boot the font is whatever the
# initramfs happens to hold, and digits in a face that does not match the box
# they sit inside is exactly the kind of seam this design exists to close.
ATLAS = "0123456789% "

# --- the animation, in frames of the 50 fps refresh omarchy.script assumes ---
FPS = 50
FRAMES_PER_CHAR = 5         # -> 10 keystrokes a second
OPEN_PAUSE = 60             # black, before the first letter
HOLD_PAUSE = 120            # once a line is complete
GAP_PAUSE = 60              # cleared screen, before the next line
#
# At 10 keystrokes a second the four lines take 22 s, and the storyboard plays
# ONCE -- `mx_advance` returns for good at the last step, it does not loop. Only
# 3.3 s of the splash is deterministic (plymouth-start to plymouth-quit); all
# the rest is the initrd phase, for as long as the disk's passphrase takes. So
# on a machine that boots fast, or unlocks fast, the later lines are simply
# never reached. That is the accepted price of a readable pace: the film's
# terminal types slowly, and 25 keystrokes a second read as a blur.

# --- layout, all of it in fractions of the window ---------------------------
# NOTHING here is a pixel count, and no point size is worked out at derive time.
# Plymouth draws at the panel's NATIVE resolution, so a size chosen against
# `hyprctl` today is wrong the moment the machine is docked to another screen
# -- and wrong in the preview, where the script sees half the panel's width.
# The script measures its own text instead (see mx_fit), which is exact
# whatever the panel and whatever the font's metrics turn out to be.
TEXT_X = 0.055              # left margin of Neo's terminal
TEXT_Y = 0.085              # and how far down it starts
TEXT_WIDTH = 0.42           # what the longest line takes up
KEY_CELLS = 21              # dashes shown for a passphrase, at most
PROMPT_WIDTH = 0.42         # the disk's own prompt, when it fits

# --- the box ----------------------------------------------------------------
# The film's prompt is a framed panel with a caption on its top rule. It is one
# baked PNG per caption rather than a frame plus text composed at boot: Plymouth
# has no blit, and two images that have to line up are two images that can drift.
#
# Its interior is wide enough for BOTH phases, so the panel never changes size
# between asking for the passphrase and reporting progress -- 21 dashes, and
# 20 track blocks + a gap + 4 digits, is 25 either way.
BOX_WIDTH = 0.46            # of the window
BOX_CELLS = 26              # interior width, in cells: 25 of content and air

# --- the progress track -----------------------------------------------------
# Not a fraction of the window: it is measured in CELLS of the passphrase line,
# so the dots, the blocks and the digits all land on one monospace grid. The
# track is one image drawn twice -- the whole of it at TRACK_ALPHA, and the part
# that is done, opaque, on top -- so an empty track is the same object as a full
# one rather than a different material. `[████░░░░] 42%` was the old readout:
# `░` is a dither pattern and `█` is solid ink, which made 0% and 50% look like
# two unrelated widgets.
BAR_CELLS = 20              # blocks in the track
BAR_GAP_CELLS = 1           # between the track and the digits
PCT_CELLS = 4               # "  0%" .. "100%", padded, so the width is fixed
TRACK_ALPHA = 0.25          # the part still to do


def die(message):
    print(f"derive-plymouth: {message}", file=sys.stderr)
    sys.exit(1)


def available_font():
    """The font has to exist: the mkinitcpio hook resolves it with fc-match from
    the .plymouth's `Font=` and copies it into the initramfs. Without it, boot
    would have no text at all -- and label-freetype does not fall back politely
    when it finds nothing, it segfaults."""
    try:
        output = subprocess.run(["fc-match", "-f", "%{family}", FONT],
                                capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return "monospace"
    return FONT if FONT.lower() in output.lower() else "monospace"


def literal(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def storyboard():
    """The typing, already resolved into steps: which line, how much of it, and
    for how many frames.

    Generated here rather than inside the Plymouth script on purpose -- that way
    the .script needs no SubString, no Length and no string slicing. It used to
    carry every step's literal text; now a step is two integers, because the
    drawing is one Crop of a picture that already exists.

    The film's shape, not a terminal's: a line types, holds, and the screen
    CLEARS before the next one. They do not pile up.

    NOTHING BLINKS. The block cursor that used to trail every step is gone, and
    that is what makes the rest of this cheap: with nothing after the text, the
    first N characters of a line are exactly the first N cells of its image, so
    typing is a crop and needs no font at boot at all.

    A step with 0 characters shown is a held blank -- the pause before the first
    line, and the cleared screen between them.
    """
    steps = [(0, 0, OPEN_PAUSE)]
    for index, phrase in enumerate(LINES):
        for n in range(1, len(phrase) + 1):
            steps.append((index, n, FRAMES_PER_CHAR))
        steps.append((index, len(phrase), HOLD_PAUSE))
        if index != len(LINES) - 1:
            steps.append((index, 0, GAP_PAUSE))
    return steps


def percent_cells():
    """`  0%` .. `100%` as indices into the digit atlas, four per percent.

    A table, for the same reason the storyboard is one: no string is ever built
    up inside the .script. The atlas is ATLAS, so a digit's index is its own
    value, `%` is 10 and a space is 11.
    """
    rows = []
    for percent in range(101):
        label = f"{percent:>{PCT_CELLS - 1}}%"
        rows.append([ATLAS.index(character) for character in label])
    return rows


TYPING = string.Template("""
#----------------------------------------- $NAME $RULE
# Put here by $CLI. DO NOT edit this file by hand: it is derived again
# from Omarchy's omarchy.script on every `omarchy update`.
#
# Neo's monitor. The logo is still loaded, just invisible -- its box is what
# the password dialog below measures itself against, and moving that would move
# Omarchy's own geometry with it.
#
# The four lines are PICTURES, one per line, baked at derive time in the theme's
# own face. At boot there is no fc-match, so a font family asked for by name is
# ignored and every Image.Text comes out in whatever single TTF the initramfs
# holds -- which is no way to choose a typeface. Typing is therefore a Crop: N
# characters of a monospace line is the first N cells of its picture, exact at
# any panel size, and it costs no text rendering at all.
#
# Nothing here is a pixel count. Sizes come from the window and from ratios
# measured at derive time, never from the machine this was generated on.

global.mx_r = $R;   # the box's colour. The only things still drawn as TEXT are
global.mx_g = $G;   # the disk's own prompt and the caps label -- both of them
global.mx_b = $B;   # belong to the box, so both take its colour.
global.mx_font = "$FONT";
global.mx_w = Window.GetWidth();
global.mx_h = Window.GetHeight();

# Ask the font how big it really is at a known size, then scale to the width we
# actually want. 40 is arbitrary and cancels out. Still needed for the prompt
# and the caps label, which are the only text left.
fun mx_fit(text, target) {
  probe = Image.Text(text, 1, 1, 1, 1, global.mx_font + " 40");
  width = probe.GetWidth();
  if (width < 1) return 12;
  size = Math.Int(40 * target / width);
  if (size < 8) size = 8;
  return size;
}

# One cell for all four lines: they were rendered at one point size in one
# monospace face, so scaling each to its own character count keeps them on a
# single grid. $LINE_ASPECT is a RATIO measured at derive time -- the line's
# height over one cell's width -- so it survives any panel.
global.mx_cell_w = global.mx_w * $TEXT_WIDTH / $WIDEST_CELLS;
global.mx_line_h = Math.Int(global.mx_cell_w * $LINE_ASPECT);
$LINE_LOAD

global.mx_steps = $STEPS;
$TABLE

global.mx_step = 0;
global.mx_frame = 0;
global.mx_painted = -1;

mx.sprite = Sprite();
# The left edge never moves: the line grows rightwards from a fixed column, the
# way a terminal does. Centring it would shuffle the whole line sideways on
# every keystroke.
mx.sprite.SetPosition(Math.Int(global.mx_w * $TEXT_X),
                      Math.Int(global.mx_h * $TEXT_Y), 10000);
mx.sprite.SetOpacity(0);

fun mx_paint(step) {
  if (step == global.mx_painted) return;
  global.mx_painted = step;
  shown = global.mx_shown[step];
  if (shown < 1) {
    # A held blank: the pause before the first line, and between them.
    mx.sprite.SetOpacity(0);
    return;
  }
  mx.sprite.SetImage(global.mx_img[global.mx_line[step]].Crop(
    0, 0, Math.Int(shown * global.mx_cell_w), global.mx_line_h));
  mx.sprite.SetOpacity(1);
}

fun mx_tick() {
  mx_caps_tick();

  if (global.mx_step >= global.mx_steps) return;

  if (global.mx_painted == -1) {
    mx_paint(0);
    return;
  }

  global.mx_frame++;
  if (global.mx_frame < global.mx_dur[global.mx_step]) return;

  global.mx_frame = 0;
  global.mx_step++;
  # At the end it rests on the last line rather than looping: a boot is shorter
  # than the whole sequence, and starting over would be noticeable.
  if (global.mx_step >= global.mx_steps) return;
  mx_paint(global.mx_step);
}

# Defined here because refresh_callback below calls it on every frame, and it
# has to exist before the first one. The dialog it drives is set up at the end
# of this file, where `entry` finally has a position to hang off.
#
# MIND the names. A global holding a number and an object holding sprites
# cannot share an identifier: `global.mx_caps = -1` followed by
# `mx_caps.image = ...` further down assigns to a number, silently does
# nothing, and the sprite draws nothing with no error anywhere. Hence the
# _state suffix, and why the progress track's numbers are mx_bar_* while its
# sprites are mx_track / mx_fill -- no name is ever both.
global.mx_dialog_on = 0;
global.mx_bullets = -1;
global.mx_caps_state = -1;
global.mx_percent = -1;
""")


DIALOG = string.Template("""
#----------------------------------------- $NAME dialog $RULE
# The passphrase, as the film's framed panel rather than a rounded box.
#
# Omarchy's own dialog is NOT rewritten. Its callbacks are registered further
# up this file; ours are registered below, and the last registration wins. So
# `display_password_callback` simply stops being called, its entry, lock and
# bullet sprites stay at the opacity 0 they were created with, and nothing on
# the passphrase path has been edited. If any of this ever fails to load,
# Omarchy's dialog is still whole underneath.
#
# It hangs off `entry.y`, which is Omarchy's own idea of where a dialog goes.
# That is deliberate: the middle of the screen should stay where Omarchy puts
# it, whatever Omarchy decides that is.
#
# ONE panel, two captions. The passphrase and the progress readout are never on
# screen together, so they share the frame as well as the row -- swapping a
# whole baked image rather than composing a frame and a caption, because
# Plymouth has no blit and two images that must line up are two images that can
# drift. It also means the boot never cuts from a framed panel to a bare bar,
# which is the "three unrelated widgets taking turns" this design exists to
# avoid.

global.mx_box_w = Math.Int(global.mx_w * $BOX_WIDTH);
global.mx_box_h = Math.Int(global.mx_box_w * $BOX_ASPECT);

mx_box.key = Image("box-key.png");
mx_box.bar = Image("box-bar.png");
mx_box.key_scaled = mx_box.key.Scale(global.mx_box_w, global.mx_box_h);
mx_box.bar_scaled = mx_box.bar.Scale(global.mx_box_w, global.mx_box_h);

global.mx_box_x = Math.Int((global.mx_w - global.mx_box_w) / 2);
global.mx_box_y = entry.y;

mx_box.sprite = Sprite();
mx_box.sprite.SetPosition(global.mx_box_x, global.mx_box_y, 10000);
mx_box.sprite.SetOpacity(0);

# The interior grid. All three of these are FRACTIONS OF THE BOX'S WIDTH,
# measured when the box was drawn, so they scale with it and no pixel count ever
# crosses from the machine that derived this to the one that boots it.
#
# Everything inside is scaled to a whole number of these cells and rendered at
# one point size, which is what puts the dashes, the track and the digits on a
# single monospace grid instead of three that nearly agree.
global.mx_cell = global.mx_box_w * $BOX_CELL_FRAC;
global.mx_in_x = global.mx_box_x + Math.Int(global.mx_box_w * $BOX_PAD_FRAC);
global.mx_in_y = global.mx_box_y + Math.Int(global.mx_box_w * $BOX_ROW_FRAC);
global.mx_in_h = Math.Int(global.mx_cell * $CELL_ASPECT);

# The passphrase: one image of $KEY_CELLS dashes, revealed a cell at a time.
mx_key.image = Image("keyline.png");
mx_key.scaled = mx_key.image.Scale(Math.Int($KEY_CELLS * global.mx_cell), global.mx_in_h);
mx_key.sprite = Sprite();
mx_key.sprite.SetPosition(global.mx_in_x, global.mx_in_y, 10001);
mx_key.sprite.SetOpacity(0);

# The disk's own prompt, dimmed, above the panel. It is the one thing here that
# cannot be baked -- LUKS writes it at boot -- so it stays text, in whatever
# face the initramfs holds. That is defensible: it is the system talking, not
# the theme.
global.mx_prompt_size = mx_fit($PROMPT_PROBE, global.mx_w * $PROMPT_WIDTH);
global.mx_prompt_face = global.mx_font + " " + global.mx_prompt_size;
global.mx_prompt_shown = "";

mx_prompt.sprite = Sprite();
mx_prompt.sprite.SetOpacity(0);

mx_caps.image = Image.Text($CAPS_TEXT, global.mx_r, global.mx_g, global.mx_b, 1,
                           global.mx_prompt_face);
mx_caps.sprite = Sprite(mx_caps.image);
mx_caps.sprite.SetPosition(
  Math.Int((global.mx_w - mx_caps.image.GetWidth()) / 2),
  global.mx_box_y + global.mx_box_h + Math.Int(global.mx_prompt_size * 0.6),
  10001);
mx_caps.sprite.SetOpacity(0);

# The progress track, inside the same panel and on the same grid.
#
# ONE image, drawn by TWO sprites: the whole track at $TRACK_ALPHA underneath,
# and the part that is done, opaque, cropped over it. That is deliberate -- an
# empty track has to be the same object as a full one, merely unlit. The old
# readout spelt `[####....]`, where the empty half was a dither pattern and the
# full half was solid ink, so 0% and 50% looked like two different things.
mx_track.image = Image("bar.png");
mx_track.scaled = mx_track.image.Scale(Math.Int($BAR_CELLS * global.mx_cell), global.mx_in_h);
mx_track.sprite = Sprite(mx_track.scaled);
mx_track.sprite.SetPosition(global.mx_in_x, global.mx_in_y, 10001);
mx_track.sprite.SetOpacity(0);

mx_fill.sprite = Sprite();
mx_fill.sprite.SetPosition(global.mx_in_x, global.mx_in_y, 10002);
mx_fill.sprite.SetOpacity(0);

# The digits, cropped out of a baked strip rather than typeset. Image.Text would
# put them in the initramfs's font -- a different face from the panel they sit
# inside, and the one seam a reader would actually notice.
mx_digits.image = Image("digits.png");
mx_digits.scaled = mx_digits.image.Scale(Math.Int($ATLAS_CELLS * global.mx_cell),
                                         global.mx_in_h);
$PCT_TABLE
$PCT_SPRITES

fun mx_pct_show(on) {
$PCT_SHOW
}

fun mx_bar_show(on) {
  # The fill is never turned on from here, only off: mx_progress owns it,
  # because it is the only thing that knows how wide the crop should be. Clearing
  # mx_percent makes the next update repaint rather than short-circuit, so the
  # fill comes back with a fresh crop instead of the one from the last boot
  # phase.
  global.mx_percent = -1;
  mx_fill.sprite.SetOpacity(0);
  if (on == 0) {
    mx_track.sprite.SetOpacity(0);
    mx_pct_show(0);
  } else {
    mx_box.sprite.SetImage(mx_box.bar_scaled);
    mx_box.sprite.SetOpacity(1);
    mx_track.sprite.SetOpacity($TRACK_ALPHA);
    mx_pct_show(1);
  }
}

fun mx_prompt_show(text) {
  if (text != global.mx_prompt_shown) {
    global.mx_prompt_shown = text;
    # Dimmed with alpha rather than a darker colour: it stays the same hue as
    # the panel, which is what makes it read as one thing.
    image = Image.Text(text, global.mx_r, global.mx_g, global.mx_b, 0.55,
                       global.mx_prompt_face);
    # A LUKS prompt naming a device by UUID can be far wider than the screen,
    # and there is no wrapping to save us. Too wide, and we say it ourselves.
    if (image.GetWidth() > global.mx_w * 0.9) {
      image = Image.Text($PROMPT_FALLBACK, global.mx_r, global.mx_g, global.mx_b,
                         0.55, global.mx_prompt_face);
    }
    mx_prompt.sprite.SetImage(image);
    mx_prompt.sprite.SetPosition(
      Math.Int((global.mx_w - image.GetWidth()) / 2),
      global.mx_box_y - Math.Int(global.mx_prompt_size * 1.8),
      10001);
  }
  mx_prompt.sprite.SetOpacity(1);
}

# Driven from mx_tick() on every frame. It used to hang off the caret's blink;
# with the caret gone it needs a driver of its own, and a flag of its own to say
# the panel is up.
fun mx_caps_tick() {
  if (global.mx_dialog_on == 0) return;
  state = Plymouth.GetCapslockState();
  if (state == global.mx_caps_state) return;
  global.mx_caps_state = state;
  if (state == 0) {
    mx_caps.sprite.SetOpacity(0);
  } else {
    mx_caps.sprite.SetOpacity(1);
  }
}

fun mx_hide_dialog() {
  global.mx_dialog_on = 0;
  global.mx_bullets = -1;
  global.mx_caps_state = -1;
  mx_key.sprite.SetOpacity(0);
  mx_prompt.sprite.SetOpacity(0);
  mx_caps.sprite.SetOpacity(0);
  mx_box.sprite.SetOpacity(0);
}

fun mx_password_callback(prompt, bullets) {
  # Omarchy's own callback sets this, and its display_normal_callback needs it
  # to know a password was asked for. Ours has to set it too.
  global.password_shown = 1;
  stop_fake_progress();
  hide_progress_bar();
  mx_bar_show(0);

  mx_box.sprite.SetImage(mx_box.key_scaled);
  mx_box.sprite.SetOpacity(1);
  mx_prompt_show(prompt);

  shown = bullets;
  if (shown > $KEY_CELLS) shown = $KEY_CELLS;
  if (shown != global.mx_bullets) {
    global.mx_bullets = shown;
    if (shown < 1) {
      # Crop() to zero width is not worth trusting, and an empty field is what
      # "nothing typed yet" should look like anyway.
      mx_key.sprite.SetOpacity(0);
    } else {
      mx_key.sprite.SetImage(
        mx_key.scaled.Crop(0, 0, Math.Int(shown * global.mx_cell), global.mx_in_h));
      mx_key.sprite.SetOpacity(1);
    }
  }

  global.mx_dialog_on = 1;
  mx_caps_tick();
}

fun mx_normal_callback() {
  # Omarchy's first: it hides its dialog and starts the fake progress, and that
  # timing is its business, not ours.
  display_normal_callback();
  # ...but the bar it just showed is the rounded one, and we draw a readout.
  progress_box.sprite.SetOpacity(0);
  progress_bar.sprite.SetOpacity(0);
  mx_hide_dialog();
  if (global.password_shown == 1) mx_bar_show(1);
}

fun mx_progress(fraction) {
  percent = Math.Int(fraction * 100);
  if (percent < 0) percent = 0;
  if (percent > 100) percent = 100;
  if (percent == global.mx_percent) return;
  global.mx_percent = percent;

  # Whole cells only. A partial cell would mean a block cut down the middle,
  # which is the one thing a monospace grid must never show.
  filled = Math.Int(percent * $BAR_CELLS / 100);
  if (filled < 1) {
    # Crop() to zero width is not worth trusting, and an unlit track already
    # says "nothing done yet" -- that is the whole point of drawing it.
    mx_fill.sprite.SetOpacity(0);
  } else {
    mx_fill.sprite.SetImage(
      mx_track.scaled.Crop(0, 0, Math.Int(filled * global.mx_cell), global.mx_in_h));
    mx_fill.sprite.SetOpacity(1);
  }

$PCT_PAINT
}

# Only take the dialog over if there is something to draw it with.
#
# Tested by deleting keyline.png from a staged theme: Plymouth does NOT abort
# the script over Scale() on an image that failed to load, it carries on. So
# without this guard the prompt appeared with no field, no dashes and no panel
# -- you could still type your passphrase, but with nothing on screen to say
# so, which on an encrypted disk at 7am is its own kind of broken.
#
# It asks for the WIDTH, not for the image: `Image()` on a file that is not
# there still hands back something that tests as true, and the first version of
# this guard let the broken case straight through.
#
# EVERY asset, not just the passphrase line. Taking the password callback over
# also takes the progress readout over -- mx_normal_callback hides Omarchy's
# rounded bar -- so a missing bar.png, or missing digits, or a missing panel
# would leave a boot with no progress of any kind and nothing to say why.
#
# With it, a theme missing its assets falls back to Omarchy's own dialog:
# registered further up, never unregistered, and whole.
if (mx_key.image.GetWidth() > 0 && mx_track.image.GetWidth() > 0 &&
    mx_digits.image.GetWidth() > 0 && mx_box.key.GetWidth() > 0 &&
    mx_box.bar.GetWidth() > 0) {
  Plymouth.SetDisplayPasswordFunction(mx_password_callback);
  Plymouth.SetDisplayNormalFunction(mx_normal_callback);
}
""")


def typing_block(font, metrics):
    steps = storyboard()
    table = "\n".join(
        f"global.mx_line[{i}] = {line}; global.mx_shown[{i}] = {shown}; "
        f"global.mx_dur[{i}] = {frames};"
        for i, (line, shown, frames) in enumerate(steps))

    # One Image() and one Scale() per line, at start-up, never again. Each is
    # scaled to its OWN character count times the shared cell, which is what
    # keeps four pictures of different lengths on one grid.
    load = "\n".join(
        f'global.mx_img[{i}] = Image("line{i}.png").Scale('
        f"Math.Int({cells} * global.mx_cell_w), global.mx_line_h);"
        for i, cells in enumerate(metrics["LINE_CELLS"]))

    name = PROVIDER["displayName"]
    return TYPING.substitute(
        NAME=name, RULE="-" * max(1, 35 - len(name)), CLI=CLI, FONT=font,
        R=DIALOG_COLOUR[0], G=DIALOG_COLOUR[1], B=DIALOG_COLOUR[2],
        TEXT_X=TEXT_X, TEXT_Y=TEXT_Y, TEXT_WIDTH=TEXT_WIDTH,
        WIDEST_CELLS=metrics["WIDEST_CELLS"], LINE_ASPECT=metrics["LINE_ASPECT"],
        LINE_LOAD=load, STEPS=len(steps), TABLE=table)


# The four cells of the progress readout. The TABLES and the SPRITES are
# deliberately on different prefixes -- mx_pd_* against mx_pct_* -- because a
# global holding a number and an object holding sprites cannot share a name:
# the second assignment goes to the number, silently does nothing, and the
# sprite draws nothing with no error anywhere. It cost an hour once already.
PCT_NAMES = ("a", "b", "c", "d")


def dialog_block(metrics):
    rows = percent_cells()
    table = "\n".join(
        " ".join(f"global.mx_pd_{PCT_NAMES[cell]}[{percent}] = {index};"
                 for cell, index in enumerate(row))
        for percent, row in enumerate(rows))

    offset = BAR_CELLS + BAR_GAP_CELLS
    sprites = "\n".join(
        f"mx_pct_{n}.sprite = Sprite();\n"
        f"mx_pct_{n}.sprite.SetPosition(global.mx_in_x + "
        f"Math.Int(({offset + i}) * global.mx_cell), global.mx_in_y, 10001);\n"
        f"mx_pct_{n}.sprite.SetOpacity(0);"
        for i, n in enumerate(PCT_NAMES))

    show = ("  if (on == 0) {\n"
            + "".join(f"    mx_pct_{n}.sprite.SetOpacity(0);\n" for n in PCT_NAMES)
            + "  } else {\n"
            + "".join(f"    mx_pct_{n}.sprite.SetOpacity(1);\n" for n in PCT_NAMES)
            + "  }")

    paint = "\n".join(
        f"  mx_pct_{n}.sprite.SetImage(mx_digits.scaled.Crop("
        f"Math.Int(global.mx_pd_{n}[percent] * global.mx_cell), 0, "
        f"Math.Int(global.mx_cell), global.mx_in_h));"
        for n in PCT_NAMES)

    name = PROVIDER["displayName"]
    return DIALOG.substitute(
        NAME=name, RULE="-" * max(1, 28 - len(name)),
        BOX_WIDTH=BOX_WIDTH, BOX_ASPECT=metrics["BOX_ASPECT"],
        BOX_CELL_FRAC=metrics["BOX_CELL_FRAC"],
        BOX_PAD_FRAC=metrics["BOX_PAD_FRAC"],
        BOX_ROW_FRAC=metrics["BOX_ROW_FRAC"],
        CELL_ASPECT=metrics["CELL_ASPECT"],
        KEY_CELLS=KEY_CELLS, BAR_CELLS=BAR_CELLS, BAR_GAP_CELLS=BAR_GAP_CELLS,
        PCT_CELLS=PCT_CELLS, ATLAS_CELLS=len(ATLAS), TRACK_ALPHA=TRACK_ALPHA,
        PROMPT_WIDTH=PROMPT_WIDTH,
        PROMPT_PROBE=literal("Please enter passphrase for disk nvme0n1p2 (cryptroot):"),
        PROMPT_FALLBACK=literal("Passphrase required to unlock this disk"),
        CAPS_TEXT=literal("[ CAPS LOCK ]"),
        PCT_TABLE=table, PCT_SPRITES=sprites, PCT_SHOW=show, PCT_PAINT=paint)


def splash_assets(target, font_path, line_hex):
    """Everything the splash draws, baked to PNG here rather than typeset there.

    At boot there is no fc-match, so `label-freetype` ignores any font family
    asked for by name and renders everything in the one TTF the mkinitcpio hook
    put in the initramfs. A theme therefore cannot choose a typeface through
    Image.Text -- it can only choose one through pixels. So the four lines, the
    passphrase field, the progress track, its digits and the panel around them
    all arrive as pictures, and the only text left at boot is the disk's own
    prompt and the caps label, which are the system's words rather than ours.

    It buys two more things. Typing costs no rendering at all -- N characters is
    one Crop of a picture that already exists -- and every element is scaled to
    a whole number of ONE cell, so the dashes, the blocks and the digits land on
    a single grid instead of three that nearly agree.

    Returns the metrics the two templates need, all of them RATIOS. Not one
    pixel count crosses from this machine to the one that boots.
    """
    if not shutil.which("magick"):
        die("ImageMagick is not installed, so the splash cannot be generated.\n"
            "  Install it (`omarchy pkg add imagemagick`) and run this again.")
    if not Path(font_path).is_file():
        die(f"the splash's font is missing: {font_path}\n"
            f"  It ships with the theme, in {FONT_FILE}. Re-install the theme.")

    size = 120                      # generous: everything is only scaled DOWN

    def render(text, colour, out):
        subprocess.run(
            ["magick", "-background", "none", "-fill", colour,
             "-font", str(font_path), "-pointsize", str(size), f"label:{text}",
             "-background", "none", "-flatten", "-strip", str(out)], check=True)

    def measure(path):
        out = subprocess.run(["identify", "-format", "%w %h", str(path)],
                             capture_output=True, text=True, check=True).stdout
        return tuple(int(n) for n in out.split())

    def ink(path):
        """How much of the image the glyphs actually cover, 0..1."""
        return float(subprocess.run(
            ["magick", str(path), "-alpha", "extract", "-format", "%[fx:mean]",
             "info:"], capture_output=True, text=True, check=True).stdout)

    # --- the typed lines ----------------------------------------------------
    line_cells = [len(line) for line in LINES]
    for index, line in enumerate(LINES):
        render(line, f"#{line_hex}", target / f"line{index}.png")
    sizes = [measure(target / f"line{index}.png") for index in range(len(LINES))]

    # Is the face really monospace? The whole typewriter rests on it: a crop of
    # N cells is only the first N characters if every character is one cell.
    # Asked of the PICTURES, per line, because that is what will be cropped.
    units = [w / c for (w, _), c in zip(sizes, line_cells)]
    if max(units) - min(units) > 1:
        die(f"the splash's font ({font_path}) is not monospace: its cell "
            f"measures between {min(units):.1f} and {max(units):.1f} px across "
            f"the four lines,\n  so a half-typed line would be cropped mid-glyph.")
    heights = {h for _, h in sizes}
    if len(heights) != 1:
        die(f"the four lines came out {sorted(heights)} px tall. They are drawn "
            f"by one sprite at one height,\n  so they have to agree.")
    line_cell = sum(units) / len(units)
    line_height = sizes[0][1]

    # --- what goes inside the panel -----------------------------------------
    render(MASK * KEY_CELLS, f"#{DIALOG_HEX}", target / "keyline.png")
    render(BLOCK * BAR_CELLS, f"#{DIALOG_HEX}", target / "bar.png")
    render(ATLAS, f"#{DIALOG_HEX}", target / "digits.png")

    inside = {"keyline.png": KEY_CELLS, "bar.png": BAR_CELLS,
              "digits.png": len(ATLAS)}
    cells = {}
    for name, count in inside.items():
        w, h = measure(target / name)
        cells[name] = (w / count, h)
    widths = [c for c, _ in cells.values()]
    if max(widths) - min(widths) > 1:
        die("the dashes, the track and the digits came out on different cell "
            "widths\n  ({}), so they would not share a grid.".format(
                ", ".join(f"{n} {c:.1f}px" for n, (c, _) in cells.items())))
    cell = sum(widths) / len(widths)

    # One height for all three, so one aspect describes them and the row cannot
    # sit a pixel high. Padded rather than assumed equal: `label:` hands back a
    # line box, and whether a row of blocks and a row of digits produce the same
    # one is a property of the font, not something to take on trust.
    row_height = max(h for _, h in cells.values())
    for name in inside:
        subprocess.run(["magick", str(target / name), "-background", "none",
                        "-gravity", "north",
                        "-extent", f"{measure(target / name)[0]}x{row_height}",
                        "-strip", str(target / name)], check=True)

    # And is what it drew actually a mask? Two ways for that to go wrong, and
    # neither says anything at the time. Ask the PICTURE rather than the font:
    # measure how much of its cell the mask inks, against a full block.
    #
    # Measured in Terminus, which is what ships with the theme:
    #
    #   missing glyph  0%      -  4.4%    .  3%      *  12%
    #   #             46%      @  38%     block 100%
    #
    # TOO LITTLE, and the font has no MASK at all. It does not draw .notdef --
    # no box, no warning -- it draws NOTHING and advances the cell, so you get a
    # passphrase prompt that does not react as you type. On an encrypted disk at
    # 7am that is indistinguishable from a dead keyboard.
    #
    # TOO MUCH, and whatever it drew is block-shaped, which puts the row of
    # solid rectangles back and undoes the entire point of MASK (see its
    # comment). Cascadia Code was rejected here while choosing the face: its
    # dashes touch, and a row of them reads as a rule rather than as characters.
    block_ink = ink(target / "bar.png")
    mask_ink = ink(target / "keyline.png") * KEY_CELLS / BAR_CELLS
    if block_ink > 0:
        share = mask_ink / block_ink
        if share < 0.01:
            die(f"the mask glyph {MASK!r} draws nothing in {font_path}.\n"
                f"  That font has no {MASK!r}, and freetype renders a missing "
                f"glyph as blank rather than as a box --\n"
                f"  so the passphrase prompt would not react as you typed. Pick "
                f"a MASK the font actually has.")
        if share > 0.6:
            die(f"the mask glyph {MASK!r} inks {share:.0%} of a full block in "
                f"{font_path}.\n"
                f"  A row of that reads as a progress bar rather than as typed "
                f"characters, which is the\n"
                f"  one thing this design exists to avoid. Pick a lighter MASK.")

    # --- the panel ----------------------------------------------------------
    interior = BOX_CELLS * cell
    pad = cell                      # a cell of air either side of the content
    box_w = int(interior + pad * 2)
    rule_y = int(size * 0.55)       # the top rule, where the caption sits
    stroke = max(2, int(size * 0.045))
    block = int(size * 0.30)        # the caption's little square widgets

    # The panel is sized to its CONTENT, not to the point size: a fixed multiple
    # of `size` gave a box with the row of dashes stranded in the top third and
    # a hand's width of nothing under it.
    box_h = rule_y + int(row_height * 1.55)

    # ...and the row is centred on the INK, not on the line box. `label:` returns
    # a full line box with room for ascenders and descenders, and a dash inks a
    # band across the middle of it -- so centring the box leaves the only thing
    # anyone can see sitting noticeably high. Measured off the track, because
    # blocks fill their cell and are therefore the honest extent of the row; the
    # dashes share a baseline with them, so they land where they should.
    trimmed = subprocess.run(["magick", str(target / "bar.png"), "-format", "%@",
                              "info:"], capture_output=True, text=True,
                             check=True).stdout
    ink_h, ink_y = (int(n) for n in re.match(
        r"\d+x(\d+)\+\d+\+(\d+)", trimmed).groups())
    content_y = rule_y + int(((box_h - rule_y) - ink_h) / 2) - ink_y

    for name, caption in (("box-key.png", BOX_TITLE),
                          ("box-bar.png", PROGRESS_TITLE)):
        render(caption, f"#{DIALOG_HEX}", target / ".caption.png")
        caption_w = measure(target / ".caption.png")[0] * 62 // 100
        subprocess.run(["magick", str(target / ".caption.png"), "-resize",
                        f"{caption_w}x", "-strip", str(target / ".caption.png")],
                       check=True)
        gap = int(size * 0.45)
        left = (box_w - caption_w) // 2
        # The frame is drawn as five strokes rather than as a rectangle with a
        # hole knocked in it. Knocking the hole is what this did first, with
        # `-compose clear` over a `-draw rectangle`, and it silently did
        # nothing: `-draw` takes its colour from `-fill`, and `-fill none` means
        # "do not fill" rather than "erase". The rule came out straight through
        # the caption, which is only visible by looking.
        #
        # The alternative -- painting the gap in the background colour -- is
        # worse than it sounds: the background belongs to Omarchy's theme, so
        # our guess at it would show as a patch on any other.
        bottom, right = box_h - stroke, box_w - stroke
        subprocess.run([
            "magick", "-size", f"{box_w}x{box_h}", "xc:none",
            "-stroke", f"#{DIALOG_HEX}", "-strokewidth", str(stroke),
            "-fill", "none",
            "-draw", f"line {stroke},{rule_y} {left - gap},{rule_y}",
            "-draw", f"line {left + caption_w + gap},{rule_y} {right},{rule_y}",
            "-draw", f"line {stroke},{rule_y} {stroke},{bottom}",
            "-draw", f"line {right},{rule_y} {right},{bottom}",
            "-draw", f"line {stroke},{bottom} {right},{bottom}",
            "-stroke", "none", "-fill", f"#{DIALOG_HEX}",
            "-draw", f"rectangle {pad},{rule_y - block // 2} "
                     f"{pad + block},{rule_y + block // 2}",
            "-draw", f"rectangle {pad + block * 1.4},{rule_y - block // 2} "
                     f"{pad + block * 2.4},{rule_y + block // 2}",
            "-draw", f"rectangle {box_w - pad - block * 2.2},{rule_y - block // 2} "
                     f"{box_w - pad},{rule_y + block // 2}",
            "-strip", str(target / name)], check=True)
        subprocess.run([
            "magick", str(target / name), str(target / ".caption.png"),
            "-geometry", f"+{left}+{rule_y - measure(target / '.caption.png')[1] // 2}",
            "-composite", "-strip", str(target / name)], check=True)
    (target / ".caption.png").unlink(missing_ok=True)

    return {
        "WIDEST_CELLS": max(line_cells),
        "LINE_ASPECT": round(line_height / line_cell, 4),
        "LINE_CELLS": line_cells,
        "BOX_ASPECT": round(box_h / box_w, 4),
        "BOX_CELL_FRAC": round(cell / box_w, 6),
        "BOX_PAD_FRAC": round(pad / box_w, 6),
        "BOX_ROW_FRAC": round(content_y / box_w, 6),
        "CELL_ASPECT": round(row_height / cell, 4),
    }


def patch(text, font, metrics):
    # 1. The logo stops being visible but is still loaded: its box places the
    #    password dialog.
    anchor = "logo.sprite.SetOpacity(1);"
    if text.count(anchor) != 1:
        die(f"expected exactly one `{anchor}` in omarchy.script, found "
            f"{text.count(anchor)}. Omarchy's splash has changed: leaving it alone.")
    text = text.replace(
        anchor,
        "logo.sprite.SetOpacity(0);  # the line is typed by mx_tick(), below\n"
        + typing_block(font, metrics))

    # 2. Hook the typing onto the 50 fps refresh that already exists.
    anchor = "fun refresh_callback() {"
    if text.count(anchor) != 1:
        die("cannot find refresh_callback() in omarchy.script: leaving it alone.")
    text = text.replace(anchor, anchor + "\n  mx_tick();")

    # 3. Every progress update, real or faked, also drives the readout.
    anchor = "fun update_progress_bar(progress) {"
    if text.count(anchor) != 1:
        die("cannot find update_progress_bar() in omarchy.script: leaving it alone.")
    text = text.replace(anchor, anchor + "\n  mx_progress(progress);")

    # 4. Ours must be the LAST word on what a password dialog looks like, and
    #    that only holds if Omarchy still registers its own where we think.
    for anchor in ("Plymouth.SetDisplayPasswordFunction(display_password_callback);",
                   "fun display_normal_callback() {"):
        if text.count(anchor) != 1:
            die(f"expected exactly one `{anchor}` in omarchy.script. Its dialog "
                f"has changed shape: leaving it alone rather than half-overriding it.")

    # Appended, not spliced: there is no anchor to get wrong, and by the end of
    # the file `entry` exists to hang the dialog off.
    return text + dialog_block(metrics)


def stage(target, colours, theme_dir):
    background, foreground, accent, logo = colours
    if not (SOURCE / "omarchy.script").is_file():
        die(f"cannot find Omarchy's Plymouth at {SOURCE}")
    if not Path(logo).is_file():
        die(f"cannot find the theme's logo: {logo}")

    for f in SOURCE.iterdir():
        if f.is_file():
            shutil.copy2(f, target / f.name)
    shutil.copy2(logo, target / "logo.png")

    # The same asset re-tinting omarchy-plymouth-set does. Nothing we draw uses
    # these, but Omarchy's script still loads them, and if our override ever
    # failed to take, its dialog should at least come up in the right colour.
    for asset in ("bullet.png", "entry.png", "lock.png", "progress_bar.png"):
        path = target / asset
        if path.is_file():
            subprocess.run(["magick", str(path), "-channel", "RGB",
                            "+level-colors", f"#{foreground},#{foreground}", str(path)],
                           check=True)

    # Two different fonts, and the difference is the point.
    #
    # `font` is a FAMILY, and all it does is decide which single TTF the
    # mkinitcpio hook copies into the initramfs -- which is what the disk's own
    # prompt and the caps label come out in, and what stops plymouthd
    # segfaulting when it can resolve nothing at all.
    #
    # `face` is a FILE, out of the theme, and it is what the splash is actually
    # drawn in: every picture below is baked from it here, because at boot a
    # font asked for by name is ignored.
    font = available_font()
    face = theme_dir / FONT_FILE
    metrics = splash_assets(target, face, COLOUR_HEX or accent)

    r, g, b = (int(background[i:i + 2], 16) / 255 for i in (0, 2, 4))
    script = (target / "omarchy.script").read_text()
    script = re.sub(r"^Window\.SetBackgroundTopColor.*$",
                    f"Window.SetBackgroundTopColor({r:.3f}, {g:.3f}, {b:.3f});",
                    script, count=1, flags=re.M)
    script = re.sub(r"^Window\.SetBackgroundBottomColor.*$",
                    f"Window.SetBackgroundBottomColor({r:.3f}, {g:.3f}, {b:.3f});",
                    script, count=1, flags=re.M)
    script = patch(script, font, metrics)

    (target / f"{THEME}.script").write_text(script)
    (target / "omarchy.script").unlink()
    (target / "omarchy.plymouth").unlink(missing_ok=True)

    # The size on this line is only a floor: every size the splash actually
    # draws at is measured at run time. What matters here is the FAMILY, which
    # is what the mkinitcpio hook feeds to fc-match to decide which single TTF
    # gets copied into the initramfs.
    (target / f"{THEME}.plymouth").write_text(f"""[Plymouth Theme]
Name={PROVIDER["plymouth"]["name"]}
Description={PROVIDER["plymouth"]["description"]}

ModuleName=script

[script]
ImageDir={TARGET}
ScriptFile={TARGET}/{THEME}.script
ConsoleLogBackgroundColor=0x{background}
MonospaceFont={font} 16
Font={font} 16
""")
    return font, face


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
               theme_colour("green", theme_dir),
               theme_dir / "unlock.png")

    staging = Path(tempfile.mkdtemp(prefix=f"{SLUG}-plymouth."))
    try:
        font, face = stage(staging, colours, theme_dir)
        steps = storyboard()
        seconds = sum(frames for _, _, frames in steps) / FPS
        print(f"  {THEME}: {len(steps)} steps, {seconds:.1f}s of typing")
        print(f"  drawn in {face.name}, baked to PNG; {font!r} only for the "
              f"disk's own prompt")
        print(f"  every size measured at boot, none baked in")

        if stage_only:
            out = Path.home() / f".cache/{CLI}/plymouth"
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.rmtree(out, ignore_errors=True)
            shutil.copytree(staging, out)
            print(f"  staged at {out} (not installed)")
            print(f"  see it: bin/preview-plymouth.sh <scenario>")
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
