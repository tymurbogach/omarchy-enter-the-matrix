# DESIGN.md — why the pack is built this way

The [README](README.md) says what the pack does. This says why, and it is mostly
a record of ceilings found by reading Omarchy's source rather than guessing. If
you are changing the pack, [CLAUDE.md](CLAUDE.md) is the one to read first — it
carries the rules and the traps.

## The lock

A `WlSessionLock` is exclusive by protocol: nothing may draw inside its surface
but itself. So raining there means replacing the lock plugin, and there is no
way around that.

What is **not** done is publishing a frozen copy. That plugin carries the PAM
and fingerprint flows, and an old copy is the last one you want.
`bin/derive-lock.py` always starts from **your** Omarchy's `LockView.qml` and
applies one minimal change: it drops the blurred wallpaper and puts the rain
there. The other ~200 lines are yours. A `post-update.d` hook derives it again
after every `omarchy update`, so Omarchy's fixes keep arriving.

If the block to replace does not appear exactly once, the script **aborts and
tells you** rather than leaving things half done.

Try it without locking yourself out: `omarchy-shell lock preview`. To go back to
Omarchy's: `omarchy-matrix lock off`.

## The boot splash

Omarchy's splash is a script theme too (`omarchy.script`, `ModuleName=script`),
and what `omarchy plymouth set-by-theme` lets a theme change is three things:
background colour, text colour and **one still PNG**. No animation fits through
that door.

`bin/derive-plymouth.py` starts from your machine's `omarchy.script` and turns
it into Neo's monitor. Upper left, one line at a time, the screen clearing
between them, a block cursor blinking at the end:

```
Wake up, Neo...█
```

```
The Matrix has you...█        Follow the white rabbit.█       Knock, knock, Neo.█
```

And in the middle, where Omarchy puts its dialog, the passphrase — as a
terminal line rather than a rounded box. The disk's own prompt above it, dimmed;
one dot per character typed; the same block cursor as the line above;
`[ CAPS LOCK ]` underneath when it is on, which Omarchy's dialog does not tell
you:

```
              Please enter passphrase for disk nvme0n1p2 (cryptroot)

                          > ••••••••█
```

Once it is answered, the boot's progress takes that row — on the same grid, so
the dots, the blocks and the digits are all one monospace line:

```
                      ████████▒▒▒▒▒▒▒▒▒▒▒▒  42%
```

One track, drawn twice: the whole of it dimmed, and the part that is done,
opaque, on top. That matters more than it sounds. It was `[████░░░░░░░░] 42%`,
and `░` is a dither pattern where `█` is solid ink — so an empty bar and a
half-full one looked like two unrelated widgets, and the passphrase, then still
drawn in blocks, looked like a third. The boot messages are Omarchy's,
untouched. It installs as a **separate**
theme at `/usr/share/plymouth/themes/omarchy-matrix/`, never overwriting its
own: going back is `omarchy plymouth reset`. The `post-update.d` hook derives it
again after every `omarchy update`.

Details that explain the design, each of them forced by something:

- **Nothing is a pixel count.** Every size is measured at boot: the script
  renders a probe string, reads its width back and scales from there. Plymouth
  draws at the panel's *native* resolution, so anything worked out at derive
  time from `hyprctl` is wrong the moment you dock to another screen.
- **The step table is generated in Python** and reaches the `.script` with every
  text already literal, so the script needs no `SubString` and no `Length`.
- **The passphrase line and the progress track are PNGs, cropped one cell at a
  time.** In the initramfs there is no `fc-match`, and `label-freetype` resolves
  font families by shelling out to it — so at boot a per-call font *family* is
  ignored and only the size survives. Anything whose exact shape matters has to
  arrive as pixels. It also means a keystroke and a percent each cost one
  `Image.Crop`, not a text render. Both are rendered at the same point size and
  font, which is what puts them on one grid.
- **`logo.png` is still loaded, just invisible.** Its box is what
  `omarchy.script` uses to place the dialog, and we do not want to move it.
- **Omarchy's password callback is not rewritten, it is out-registered.** Ours
  is registered after it, and the last registration wins. And if the generated
  PNG is ever missing, ours is not registered at all and Omarchy's own dialog —
  padlock, box and bullets — comes up instead, whole.

You do not have to reboot to see any of it. `bin/preview-plymouth.sh` runs the
real splash in a window, through Plymouth's own X11 renderer, inside a user
namespace that needs no `sudo` and cannot touch your actual boot — down to
hiding `label-pango` and every font but the three the initramfs would have.

> **If your disk is encrypted**, Plymouth is also what asks for your passphrase.
> That is why the patch adds a callback rather than editing one, and why the
> pack falls back to Omarchy's dialog rather than to no dialog. If anything goes
> wrong: `omarchy plymouth reset` from a running system, or `plymouth.enable=0`
> on the kernel line from your boot loader.
## What is inside

| | |
|---|---|
| `colors.toml` | The palette. Semantic, not `color0..15`. Includes the Hyprland border colours, which go through the template. |
| `shell.{bar,menu,launcher,notifications}.toml` | Shell section overrides: they give the bar and the cards some relief, which otherwise all paint the same black. |
| `backgrounds/` | The carousel. `0-pills.jpg` is the default, so installing only the theme still gives you a wallpaper. `1-live-rain.png` is a still frame of the shader: thumbnail, marker and fallback in one — selecting it is what turns the desktop rain on, and the shader finds it by the `-live-` in its name. The rest are stills: four from the film, three not. |
| `unlock.png`, `preview-unlock.png` | The static boot mark, for anyone installing the theme without the pack. With the pack, `logo.png` goes invisible and the lines are typed instead. |
| `manifest.json`, `Service.qml`, `MatrixRain.qml`, `matrix.frag.qsb`, `glyphs.png` | The plugin. |
| `widget/` | The bar widget: one icon, four switches, Repair and Uninstall. |
| `provider.json` | The only file that names this provider — slug, plugin ids, Plymouth theme, the lines typed at boot. Everything else is machinery. |
| `bin/` | `omarchy-matrix` (the switch CLI), the two derivers, `provider.py`, and `preview-plymouth.sh` — which runs the real boot splash in a window. |
| `hooks/` | The self-repair on theme change and update. |
| `rain/` | The shader sources: `matrix.frag` and the atlas generator. |
| `generate-brand.py` | Regenerates `unlock.png`, `preview-unlock.png` and `preview.png`. Nothing here is an untouchable binary. |
| `generate-backgrounds.py` | Paints a still frame of the rain to `--out`. It generates none of the shipped backgrounds — see Regenerating. |

### About the borders

The theme sets the border **colour** (`hyprland_active_border`, flat green) but
not its thickness or the rounding: `omarchy theme install` **rejects any `.lua`**
from a theme that came from git, because Lua runs code inside the compositor.
That is Omarchy's decision, not a bug. Borders keep the stock thickness.

If you want the thin frame, it belongs in your `~/.config/hypr/looknfeel.lua`:

```lua
hl.config({
  general = { border_size = 1 },
  decoration = {
    rounding = 2,
    shadow = { enabled = true, range = 14, color = "rgba(00FF4130)",
               color_inactive = "rgba(00000000)" },
  },
})
```

### The palette

Everything is green except the red, which is reserved for errors. What sets it
apart from any other green theme is that each ANSI slot sits on a **different
rung of luminance**, so in `nvim` or `bat` the syntactic roles stay apart instead
of blurring into one smear. Minimum contrast against the background: 5.2.

The hue axis is **126°**, which is where the rain itself lives (120°). That
matters more than it sounds: the palette used to sit at 135–158°, drifting into
mint and teal while the wallpaper stayed true green, and the mismatch is the
kind the eye notices without being able to name. Saturation is held at 42–52%
— the rain's own trail is 25% — so the interface accompanies the wallpaper
instead of competing with it.

And the accent is not the border. `#60C76B` marks what the eye should find;
window frames, selections and card edges run dimmer, around 4.3:1 against the
surface they sit on. A border delimits; it does not need to shout.

| | | |
|---|---|---|
| `cyan` | `#92D9BB` | mint · 12.1 |
| `yellow` | `#B6CF7D` | lime · 11.4 |
| `green` | `#60C76B` | the hero · 9.3 |
| `magenta` | `#4FC482` | jade · 9.0 |
| `orange` | `#81B851` | olive · 8.4 |
| `blue` | `#319B4A` | emerald · 5.5 |
| `red` | `#D85A63` | errors · 5.2 |

### Regenerating

```bash
./generate-brand.py                     # unlock, preview-unlock and preview
./rain/generate-atlas.py                # the shader's glyph atlas
./generate-backgrounds.py --out /tmp/x.png --seed 42 --density 0.7

# recompile the shader (qsb is not on PATH; qt6-shadertools puts it here)
/usr/lib/qt6/bin/qsb --glsl 300es,330 --hlsl 50 --msl 12 \
    -o matrix.frag.qsb rain/matrix.frag
```

**The backgrounds are not regenerated.** `generate-backgrounds.py` requires
`--out` and writes nowhere by default, on purpose: every shipped background is
now either a still or `1-live-rain.png`, all of them committed, and an
argument-less run had one job left — to overwrite a file somebody had
deliberately removed. It stays because a fresh frame of the rain is still worth
being able to paint.

Those `qsb` targets are the ones the shipped `matrix.frag.qsb` was built with —
GLSL 300 es and 330, HLSL 50, MSL 12. Using different ones silently produces a
different set of shader variants.

Needs ImageMagick, `rsvg-convert`, Python 3, the Noto Sans CJK JP font and
`qt6-shadertools` for `qsb`.

## Working on the pack

`~/.config/omarchy/themes/enter-the-matrix` is what `omarchy theme install` puts
there and it gets regenerated, so editing in it loses the change. Keep a working
copy elsewhere:

```bash
git clone https://github.com/tymurbogach/omarchy-enter-the-matrix ~/dev/omarchy-matrix
# edit, commit and push there, then:
cd ~/.config/omarchy/themes/enter-the-matrix && git pull && ./install.sh
```

That is a detour, but it is exactly the path anyone installing the pack takes,
so mistakes surface on your machine rather than on theirs.

Editing `Service.qml` can skip the detour by copying it straight into
`~/.config/omarchy/plugins/matrix.rain/`, but **finish with `omarchy restart
shell`**: hot reloads can leave two instances alive, the old one still answering
IPC while the new one paints, and the symptom is maddening.
