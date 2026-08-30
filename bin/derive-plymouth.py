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

# What is typed out at boot, in order, and in the provider's colour.
LINES = PROVIDER["plymouth"]["lines"]
COLOUR = PROVIDER["plymouth"]["color"]
# ...and the same colour as ImageMagick wants it, for the generated PNGs.
COLOUR_HEX = "".join(f"{round(channel * 255):02X}" for channel in COLOUR)

FONT = "JetBrainsMono Nerd Font"
CURSOR = "█"                # full block: the terminal cursor
BLANK = " "                 # a cleared line. NOT "", which has no image
# One typed character of the passphrase. A dot, and NOT any kind of block.
#
# This was `▊` -- seven-eighths of a cell, chosen over `█` precisely so the
# characters would not butt together into one solid green bar. It did not work,
# and the reason is worth keeping: the progress readout lives in the SAME row
# and is also made of blocks, so a boot went `solid bar` (typing) -> `empty
# bracketed bar` -> `filling bar`, and the eye read all three as one meter
# behaving strangely. What separates the passphrase from the progress is the
# GLYPH, not the gap between glyphs.
MASK = "•"

# --- the animation, in frames of the 50 fps refresh omarchy.script assumes ---
FPS = 50
FRAMES_PER_CHAR = 5         # -> 10 keystrokes a second
BLINK = 30                  # frames per half-blink of the cursor
OPEN_BLINKS = 2             # the cursor alone, before the first letter
HOLD_BLINKS = 4             # once a line is complete
GAP_BLINKS = 2              # cleared screen, before the next line
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
KEY_WIDTH = 0.46            # the passphrase line, all 23 cells of it
KEY_CELLS = 21              # blocks shown for a passphrase, at most
PROMPT_WIDTH = 0.42         # the disk's own prompt, when it fits

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


def font_file(family):
    """The file behind a family, for ImageMagick. Deliberately resolved the same
    way the mkinitcpio hook resolves it, so the PNG this script generates and
    the text Plymouth renders at boot come out of the same TTF."""
    try:
        return subprocess.run(["fc-match", "-f", "%{file}", family],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def literal(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def storyboard():
    """The typing, already resolved into steps.

    Generated here rather than inside the Plymouth script on purpose: that way
    the .script needs no SubString, no Length and no string slicing. Every step
    carries its literal text and how many frames it lasts.

    The film's shape, not a terminal's: a line types, holds, and the screen
    CLEARS before the next one. They do not pile up.
    """
    steps = []
    for blink in range(OPEN_BLINKS):                    # a cursor, on black
        steps.append((CURSOR if blink % 2 == 0 else BLANK, BLINK))
    for index, phrase in enumerate(LINES):
        for n in range(1, len(phrase) + 1):
            steps.append((phrase[:n] + CURSOR, FRAMES_PER_CHAR))
        for blink in range(HOLD_BLINKS):
            steps.append((phrase + (BLANK if blink % 2 else CURSOR), BLINK))
        if index != len(LINES) - 1:
            for blink in range(GAP_BLINKS):
                steps.append((CURSOR if blink % 2 == 0 else BLANK, BLINK))
    return steps


def percent_labels():
    """`  0%` .. `100%`, one per whole percent.

    A table, for the same reason the storyboard is one: no string can be built
    up inside the .script. And `update_progress_bar` is called from the 50 fps
    refresh, so redrawing on anything finer than a whole percent would be a
    hundred wasted Image.Text calls a second.

    Padded to PCT_CELLS so the label's width never changes: the track, the gap
    and the digits are one centred group, and a group that changes width would
    slide sideways as the boot progressed.
    """
    return [f"{percent:>{PCT_CELLS - 1}}%" for percent in range(101)]


TYPING = string.Template("""
#----------------------------------------- $NAME $RULE
# Put here by $CLI. DO NOT edit this file by hand: it is derived again
# from Omarchy's omarchy.script on every `omarchy update`.
#
# Neo's monitor. The logo is still loaded, just invisible -- its box is what
# the password dialog below measures itself against, and moving that would move
# Omarchy's own geometry with it.
#
# Every size here is measured, not assumed. mx_fit() renders a probe string and
# reads its width back, which is exact whatever the panel's resolution and
# whatever label-freetype decides a "size" means. Nothing in this file is a
# pixel count that came from the machine it was generated on.

global.mx_r = $R;
global.mx_g = $G;
global.mx_b = $B;
global.mx_font = "$FONT";
global.mx_w = Window.GetWidth();
global.mx_h = Window.GetHeight();

# Ask the font how big it really is at a known size, then scale to the width we
# actually want. 40 is arbitrary and cancels out.
fun mx_fit(text, target) {
  probe = Image.Text(text, 1, 1, 1, 1, global.mx_font + " 40");
  width = probe.GetWidth();
  if (width < 1) return 12;
  size = Math.Int(40 * target / width);
  if (size < 8) size = 8;
  return size;
}

global.mx_size = mx_fit($WIDEST, global.mx_w * $TEXT_WIDTH);
global.mx_face = global.mx_font + " " + global.mx_size;
global.mx_x = Math.Int(global.mx_w * $TEXT_X);
global.mx_y = Math.Int(global.mx_h * $TEXT_Y);

global.mx_steps = $STEPS;
$TABLE

global.mx_step = 0;
global.mx_frame = 0;
global.mx_painted = "";

mx.sprite = Sprite();

fun mx_paint(index) {
  text = global.mx_txt[index];
  if (text == global.mx_painted) return;
  global.mx_painted = text;

  image = Image.Text(text, global.mx_r, global.mx_g, global.mx_b, 1, global.mx_face);
  # The left edge never moves: the line grows rightwards from a fixed column,
  # which is what a terminal does. Centring it would make every character
  # shuffle the whole line sideways.
  mx.sprite.SetImage(image);
  mx.sprite.SetPosition(global.mx_x, global.mx_y, 10000);
}

fun mx_tick() {
  mx_caret_tick();

  if (global.mx_step >= global.mx_steps) return;

  if (global.mx_painted == "") {
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
# MIND the names. A global holding a number and an object holding sprites
# cannot share an identifier: `global.mx_caps = -1` followed by
# `mx_caps.image = ...` further down assigns to a number, silently does
# nothing, and the sprite draws nothing with no error anywhere. Hence the
# _state suffix, and why the progress track's numbers are mx_bar_* while its
# sprites are mx_track / mx_fill / mx_pct -- no name is ever both.
global.mx_caret_on = 0;
global.mx_caret_frame = 0;
global.mx_caret_lit = 1;
global.mx_bullets = -1;
global.mx_caps_state = -1;
global.mx_percent = -1;

fun mx_caret_tick() {
  if (global.mx_caret_on == 0) return;
  global.mx_caret_frame++;
  if (global.mx_caret_frame < $BLINK) return;
  global.mx_caret_frame = 0;
  if (global.mx_caret_lit == 1) {
    global.mx_caret_lit = 0;
    mx_caret.sprite.SetOpacity(0);
  } else {
    global.mx_caret_lit = 1;
    mx_caret.sprite.SetOpacity(1);
  }
  mx_caps_tick();
}
""")


DIALOG = string.Template("""
#----------------------------------------- $NAME dialog $RULE
# The passphrase, as a terminal line instead of a rounded box.
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

global.mx_key_h = 0;
global.mx_cell = 0;

mx_key.image = Image("keyline.png");
# Scaled to the width we want, once, at start-up. Every crop below comes off
# THIS image, so the cell width divides it exactly and the blocks never drift.
mx_key.scaled = mx_key.image.Scale(
  Math.Int(global.mx_w * $KEY_WIDTH),
  Math.Int(mx_key.image.GetHeight() * global.mx_w * $KEY_WIDTH / mx_key.image.GetWidth()));
global.mx_key_h = mx_key.scaled.GetHeight();
global.mx_cell = mx_key.scaled.GetWidth() / $CELLS_TOTAL;

# Centred on a passphrase of average length rather than on the full 21 blocks:
# centring the maximum would leave every real passphrase hanging left of middle.
global.mx_key_x = Math.Int((global.mx_w - (2 + 12) * global.mx_cell) / 2);
global.mx_key_y = entry.y;

mx_key.sprite = Sprite();
mx_key.sprite.SetPosition(global.mx_key_x, global.mx_key_y, 10001);
mx_key.sprite.SetOpacity(0);

mx_caret.image = Image("caret.png");
mx_caret.scaled = mx_caret.image.Scale(global.mx_cell, global.mx_key_h);
mx_caret.sprite = Sprite(mx_caret.scaled);
mx_caret.sprite.SetPosition(global.mx_key_x, global.mx_key_y, 10002);
mx_caret.sprite.SetOpacity(0);

# The disk's own prompt, dimmed, above the line. Sized off a string of about
# the length these actually run to.
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
  global.mx_key_y + global.mx_key_h + Math.Int(global.mx_prompt_size * 1.1),
  10001);
mx_caps.sprite.SetOpacity(0);

# The progress track, in the same row the passphrase uses -- the two are never
# on screen together, so they share the row AND the grid: the track is scaled to
# a whole number of the dialog's own cells, and the digits are sized to four
# more of them. Dots, blocks and numbers therefore sit on one monospace grid,
# which is what stops the row reading as three unrelated widgets.
#
# ONE image, drawn by TWO sprites: the whole track at $TRACK_ALPHA underneath,
# and the part that is done, opaque, cropped over it. That is deliberate -- an
# empty track has to be the same object as a full one, merely unlit. The old
# readout spelt `[████░░░░]`, where `░` is a dither pattern and `█` is solid
# ink, so 0% and 50% looked like two different things.
global.mx_bar_count = 101;
$BAR_TABLE

mx_track.image = Image("bar.png");
mx_track.scaled = mx_track.image.Scale(
  Math.Int($BAR_CELLS * global.mx_cell),
  Math.Int(mx_track.image.GetHeight() * $BAR_CELLS * global.mx_cell / mx_track.image.GetWidth()));
global.mx_bar_h = mx_track.scaled.GetHeight();
# The cell of the SCALED track, which is what every crop below is measured in.
# Not global.mx_cell: the two images are rendered at the same point size and the
# same font, but they go through different Scale() calls, and rounding there
# would put the crops a pixel or two out over twenty cells.
global.mx_bar_cell = mx_track.scaled.GetWidth() / $BAR_CELLS;

# The group -- track, gap, digits -- centred as a unit.
global.mx_bar_x = Math.Int(
  (global.mx_w - ($BAR_CELLS + $BAR_GAP_CELLS + $PCT_CELLS) * global.mx_bar_cell) / 2);

mx_track.sprite = Sprite(mx_track.scaled);
mx_track.sprite.SetPosition(global.mx_bar_x, global.mx_key_y, 10001);
mx_track.sprite.SetOpacity(0);

mx_fill.sprite = Sprite();
mx_fill.sprite.SetPosition(global.mx_bar_x, global.mx_key_y, 10002);
mx_fill.sprite.SetOpacity(0);

# The digits, vertically centred against the track rather than sharing its top
# edge: Image.Text hands back a full line box, and a block glyph does not fill
# one, so aligning the tops would sit the numbers noticeably high.
global.mx_pct_size = mx_fit(global.mx_bar_text[100], $PCT_CELLS * global.mx_bar_cell);
global.mx_pct_face = global.mx_font + " " + global.mx_pct_size;
mx_pct.sprite = Sprite();
mx_pct.sprite.SetOpacity(0);

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
    mx_pct.sprite.SetOpacity(0);
  } else {
    mx_track.sprite.SetOpacity($TRACK_ALPHA);
    mx_pct.sprite.SetOpacity(1);
  }
}

fun mx_prompt_show(text) {
  if (text != global.mx_prompt_shown) {
    global.mx_prompt_shown = text;
    # Dimmed with alpha rather than a darker green: it stays the same hue as
    # the rest, which is what makes it read as one terminal.
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
      global.mx_key_y - Math.Int(global.mx_prompt_size * 2.2),
      10001);
  }
  mx_prompt.sprite.SetOpacity(1);
}

fun mx_caps_tick() {
  if (global.mx_caret_on == 0) return;
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
  global.mx_caret_on = 0;
  global.mx_bullets = -1;
  global.mx_caps_state = -1;
  mx_key.sprite.SetOpacity(0);
  mx_caret.sprite.SetOpacity(0);
  mx_prompt.sprite.SetOpacity(0);
  mx_caps.sprite.SetOpacity(0);
}

fun mx_password_callback(prompt, bullets) {
  # Omarchy's own callback sets this, and its display_normal_callback needs it
  # to know a password was asked for. Ours has to set it too.
  global.password_shown = 1;
  stop_fake_progress();
  hide_progress_bar();
  mx_bar_show(0);

  mx_prompt_show(prompt);

  shown = bullets;
  if (shown > $CELLS) shown = $CELLS;
  if (shown != global.mx_bullets) {
    global.mx_bullets = shown;
    width = (2 + shown) * global.mx_cell;
    mx_key.sprite.SetImage(mx_key.scaled.Crop(0, 0, width, global.mx_key_h));
    mx_caret.sprite.SetX(global.mx_key_x + width);
  }
  mx_key.sprite.SetOpacity(1);

  # Restart the blink on every keystroke, the way a real cursor does: it should
  # be solid while you type, not winking mid-word.
  global.mx_caret_on = 1;
  global.mx_caret_frame = 0;
  global.mx_caret_lit = 1;
  mx_caret.sprite.SetOpacity(1);
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
      mx_track.scaled.Crop(0, 0, Math.Int(filled * global.mx_bar_cell), global.mx_bar_h));
    mx_fill.sprite.SetOpacity(1);
  }

  image = Image.Text(global.mx_bar_text[percent], global.mx_r, global.mx_g, global.mx_b,
                     1, global.mx_pct_face);
  mx_pct.sprite.SetImage(image);
  mx_pct.sprite.SetPosition(
    global.mx_bar_x + Math.Int(($BAR_CELLS + $BAR_GAP_CELLS) * global.mx_bar_cell),
    global.mx_key_y + Math.Int((global.mx_bar_h - image.GetHeight()) / 2),
    10001);
}

# Only take the dialog over if there is something to draw it with.
#
# Tested by deleting keyline.png from a staged theme: Plymouth does NOT abort
# the script over Scale() on an image that failed to load, it carries on. So
# without this guard the prompt appeared with no line, no dots and no cursor
# -- you could still type your passphrase, but with nothing on screen to say
# so, which on an encrypted disk at 7am is its own kind of broken.
#
# It asks for the WIDTH, not for the image: `Image()` on a file that is not
# there still hands back something that tests as true, and the first version of
# this guard let the broken case straight through.
#
# BOTH images, not just the passphrase line. Taking the password callback over
# also takes the progress readout over -- mx_normal_callback hides Omarchy's
# rounded bar -- so a missing bar.png would leave a boot with no progress of any
# kind, and nothing to say why.
#
# With it, a theme missing its assets falls back to Omarchy's own dialog:
# registered further up, never unregistered, and whole.
if (mx_key.image.GetWidth() > 0 && mx_track.image.GetWidth() > 0) {
  Plymouth.SetDisplayPasswordFunction(mx_password_callback);
  Plymouth.SetDisplayNormalFunction(mx_normal_callback);
}
""")


def typing_block(font):
    steps = storyboard()
    table = "\n".join(
        f"global.mx_txt[{i}] = {literal(text)}; global.mx_dur[{i}] = {duration};"
        for i, (text, duration) in enumerate(steps))
    widest = max(LINES, key=len) + CURSOR
    name = PROVIDER["displayName"]
    return TYPING.substitute(
        NAME=name, RULE="-" * max(1, 35 - len(name)), CLI=CLI, FONT=font,
        R=COLOUR[0], G=COLOUR[1], B=COLOUR[2],
        WIDEST=literal(widest), TEXT_WIDTH=TEXT_WIDTH,
        TEXT_X=TEXT_X, TEXT_Y=TEXT_Y,
        STEPS=len(steps), TABLE=table, BLINK=BLINK)


def dialog_block():
    table = "\n".join(f"global.mx_bar_text[{i}] = {literal(row)};"
                      for i, row in enumerate(percent_labels()))
    name = PROVIDER["displayName"]
    return DIALOG.substitute(
        NAME=name, RULE="-" * max(1, 28 - len(name)),
        KEY_WIDTH=KEY_WIDTH, CELLS=KEY_CELLS, CELLS_TOTAL=KEY_CELLS + 2,
        PROMPT_WIDTH=PROMPT_WIDTH,
        PROMPT_PROBE=literal("Please enter passphrase for disk nvme0n1p2 (cryptroot):"),
        PROMPT_FALLBACK=literal("Passphrase required to unlock this disk"),
        CAPS_TEXT=literal("[ CAPS LOCK ]"),
        BAR_CELLS=BAR_CELLS, BAR_GAP_CELLS=BAR_GAP_CELLS, PCT_CELLS=PCT_CELLS,
        TRACK_ALPHA=TRACK_ALPHA,
        BAR_TABLE=table)


def keyline_assets(target, font_path):
    """`> ` and twenty-one dots as one image, the cursor, and the progress track.

    PNGs rather than Image.Text for the same reason the rain would have needed
    one: at boot there is no fc-match, so a per-call font FAMILY is ignored and
    only the size survives. Anything whose exact shape matters has to arrive as
    pixels. It also means neither the passphrase nor the track costs any text
    rendering at all -- a keystroke and a percent are each one Crop of an image
    that already exists.

    One image for `> ` and the dots, so the two cannot drift apart: the line is
    monospace, so its width divides into 23 equal cells by construction. That is
    asserted below rather than assumed. The track is rendered separately but at
    the SAME point size and font, so both come out on the same grid.

    Nothing here glows. The bloom was here, on the passphrase line only, and it
    made the middle of the screen a different material from the line typed above
    it -- which was half of what made a boot look like three unrelated widgets
    taking turns. The other half was the glyph, see MASK.
    """
    if not shutil.which("magick"):
        die("ImageMagick is not installed, so the passphrase line cannot be "
            "generated.\n  Install it (`omarchy pkg add imagemagick`) and run "
            "this again.")

    line = "> " + MASK * KEY_CELLS
    cells = KEY_CELLS + 2
    size = 120                      # generous: it is only ever scaled DOWN

    def render(text, colour, out):
        command = ["magick", "-background", "none", "-fill", colour]
        if font_path:
            command += ["-font", font_path]
        command += ["-pointsize", str(size), f"label:{text}",
                    "-background", "none", "-flatten", "-strip", str(out)]
        subprocess.run(command, check=True)

    def measure(path):
        return int(subprocess.run(["identify", "-format", "%w", str(path)],
                                  capture_output=True, text=True, check=True).stdout)

    def ink(path):
        """How much of the image the glyphs actually cover, 0..1."""
        return float(subprocess.run(
            ["magick", str(path), "-alpha", "extract", "-format", "%[fx:mean]",
             "info:"], capture_output=True, text=True, check=True).stdout)

    keyline = target / "keyline.png"
    caret = target / "caret.png"
    track = target / "bar.png"
    render(line, f"#{COLOUR_HEX}", keyline)
    # The cursor is the same green as everything else now. It used to be a
    # paler #C9FFD5, which read as a third colour on a screen that only has two.
    render(CURSOR, f"#{COLOUR_HEX}", caret)
    render(CURSOR * BAR_CELLS, f"#{COLOUR_HEX}", track)

    # Is the font really monospace? Not answered by "does the width divide by
    # 23" -- rendering rounds, and the first attempt at this rejected a
    # perfectly good JetBrains Mono over a single pixel. The question that
    # actually matters is whether `> ` occupies the same room as two masks, so
    # ask exactly that: same glyph count, one with the prompt, one without.
    reference = target / ".cells.png"
    render(MASK * cells, f"#{COLOUR_HEX}", reference)
    drift = abs(measure(keyline) - measure(reference))
    mask_ink = ink(reference)
    reference.unlink()
    if drift > cells:
        die(f"`> ` and two masks differ by {drift} px over {cells} cells: the "
            f"font resolved for the splash ({font_path or 'unknown'}) is not "
            f"monospace, so the cursor would not sit where the dots end.")

    # And is what it drew actually a mask? Two ways for that to go wrong, and
    # neither says anything at the time. Ask the PICTURE rather than the font:
    # measure how much of its cell the mask inks, against a full block.
    #
    # Measured here with JetBrains Mono, which is what the numbers below are
    # calibrated against:
    #
    #   missing glyph  0%      ·  3%     ▪ 11%     •  6%
    #   *             12%      ● 38%     ■ 46%     ▊ 75%     █ 100%
    #
    # TOO LITTLE, and the font has no MASK at all. It does not draw .notdef --
    # no box, no warning -- it draws NOTHING and advances the cell, so you get a
    # passphrase prompt that does not react as you type. On an encrypted disk at
    # 7am that is indistinguishable from a dead keyboard.
    #
    # TOO MUCH, and whatever it drew is block-shaped, which puts the row of
    # solid rectangles back and undoes the entire point of MASK (see its
    # comment). 75% is the old `▊` this replaced; 46% is a `■`, which is still
    # legible as a character.
    block_ink = ink(track)
    if block_ink > 0:
        share = mask_ink / block_ink
        if share < 0.01:
            die(f"the mask glyph {MASK!r} draws nothing in "
                f"{font_path or 'the resolved font'}.\n"
                f"  That font has no {MASK!r}, and freetype renders a missing "
                f"glyph as blank rather than as a box --\n"
                f"  so the passphrase prompt would not react as you typed. Pick "
                f"a MASK the font actually has.")
        if share > 0.6:
            die(f"the mask glyph {MASK!r} inks {share:.0%} of a full block in "
                f"{font_path or 'the resolved font'}.\n"
                f"  A row of that reads as a progress bar rather than as typed "
                f"characters, which is the\n"
                f"  one thing this design exists to avoid. Pick a lighter MASK.")

    return measure(keyline) / cells



def patch(text):
    # 1. The logo stops being visible but is still loaded: its box places the
    #    password dialog.
    anchor = "logo.sprite.SetOpacity(1);"
    if text.count(anchor) != 1:
        die(f"expected exactly one `{anchor}` in omarchy.script, found "
            f"{text.count(anchor)}. Omarchy's splash has changed: leaving it alone.")
    text = text.replace(
        anchor,
        "logo.sprite.SetOpacity(0);  # the line is typed by mx_tick(), below\n"
        + typing_block(available_font()))

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
    return text + dialog_block()


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

    # The same asset re-tinting omarchy-plymouth-set does. Nothing we draw uses
    # these, but Omarchy's script still loads them, and if our override ever
    # failed to take, its dialog should at least come up in the right colour.
    for asset in ("bullet.png", "entry.png", "lock.png", "progress_bar.png"):
        path = target / asset
        if path.is_file():
            subprocess.run(["magick", str(path), "-channel", "RGB",
                            "+level-colors", f"#{foreground},#{foreground}", str(path)],
                           check=True)

    font = available_font()
    cell = keyline_assets(target, font_file(font))

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
    return font, cell


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
        font, cell = stage(staging, colours)
        steps = storyboard()
        seconds = sum(duration for _, duration in steps) / FPS
        print(f"  {THEME}: {len(steps)} steps, {seconds:.1f}s of typing")
        print(f"  font {font!r}; every size measured at boot, none baked in")

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
