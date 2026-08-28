# Matrix — a pack for Omarchy 4

Phosphor green on black. A normal Omarchy theme and, on top of it, the same
digital rain on the desktop, as the screensaver, and behind the lock.

![preview](preview.png)

## Install

One line, both halves:

```bash
omarchy theme install https://github.com/tymurbogach/omarchy-matrix &&
  ~/.config/omarchy/themes/matrix/install.sh
```

The first command is the **theme** — colours, backgrounds and the boot mark —
and it depends on nothing else. The second is the **pack**: the rain, which is a
shell plugin and cannot live inside an Omarchy theme, plus the switches, the
menu row and the boot splash. It asks which pieces you want.

Chain them. Nothing in Omarchy's theme installer can tell you the second half
exists, so on its own the first line leaves you with a theme and no idea there
is more.

That script is the only supported way in. `omarchy plugin add <this repo>` looks
like it should work — the manifest is at the root — but it installs the whole
repository as the plugin and skips the CLI, the hooks and the menu, which is
most of the pack.

The desktop rain is one more background in the carousel, `1-live-rain`.
`omarchy-matrix wallpaper on` selects it for you. Mind that `omarchy theme set`
rotates to the theme's next background, so re-applying the theme takes you off
the rain — come back with that same command, or from the menu.

## The pieces

Each one switches on and off separately, from the menu
(**SUPER → Style → Matrix**, with ✓) or from the command line:

```bash
omarchy-matrix status
omarchy-matrix wallpaper off
omarchy-matrix boot on
```

| Piece | What it is | How it is done |
|---|---|---|
| `wallpaper` | Rain on the desktop | A layer of the plugin's own at `WlrLayer.Bottom`: above the wallpaper, below every window, with `mask: Region {}` so clicks reach the desktop. **Omarchy's background is not touched.** Shows while the `1-live-rain` background is selected. On mains it always rains; on battery, only while no window is on the active workspace. |
| `screensaver` | Rain when you go idle, behaving like Omarchy's own: hides the pointer, the mouse does not dismiss it, any key does | The same layer at `WlrLayer.Overlay`, using the `idle.screensaver` timing from your `shell.json`. It sets the native `screensaver-off` flag so Omarchy does not also open its terminal screensaver. |
| `lock` | Rain behind the password field | One of the two derived pieces. See below. |
| `boot` | The screen before login, typing out the four lines from the film | The other derived piece. See below. Needs a password and rebuilds the initramfs, so it never applies on its own. |

The first three are **the same shader**, instantiated three times. That is the
whole point: the screensaver used to be `ttfx` inside a terminal — a different
program drawing a different rain — and there was no way to make all three match.

The last two are the same problem solved the same way: `lock` and `boot` are the
two pieces Omarchy gives no way to configure, and both are handled by
**deriving** its code rather than shipping a copy.

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

`bin/derive-plymouth.py` starts from your machine's `omarchy.script` and
replaces the static logo with the four lines from the start of the film, typed
out:

```
Wake up, Neo...
The Matrix has you...
Follow the white rabbit.
Knock, knock, Neo.
```

The password dialog, the progress bar and the boot messages are Omarchy's,
untouched. It installs as a **separate** theme at
`/usr/share/plymouth/themes/omarchy-matrix/`, never overwriting its own: going
back is `omarchy plymouth reset`. The `post-update.d` hook derives it again
after every `omarchy update`.

Three details that explain the design:

- **The step table is generated in Python** and reaches the `.script` with every
  text already literal, so the script needs no `SubString`, no `Length` and no
  string concatenation — code you cannot test without booting the machine.
- **The point size is worked out at derive time**, from the panel's *native*
  width. Plymouth draws at native resolution, not the logical one: a size chosen
  for 1080p comes out tiny on a 3072 px screen.
- **`logo.png` is still loaded, just invisible.** Its box is what
  `omarchy.script` uses to place the password field, and we do not want to move
  it.

> **If your disk is encrypted**, Plymouth is also what asks for your passphrase.
> That is why the patch is additive and touches none of the password callbacks.
> If anything goes wrong: `omarchy plymouth reset` from a running system, or
> `plymouth.enable=0` on the kernel line from your boot loader.

## What it touches on your system

Everything the pack installs is either its own file or a file Omarchy leaves for
extending. **Nothing** under `/usr/share/omarchy/`, nor `hyprland.lua`, nor the
background, nor the bar:

```
~/.config/omarchy/plugins/matrix.rain/     the plugin
~/.config/omarchy/matrix.json              which pieces are on
~/.config/omarchy/hooks/{theme-set,post-update}.d/matrix
~/.config/omarchy/extensions/omarchy-menu.jsonc   (block between markers)
~/.local/bin/{omarchy-matrix,derive-lock.py,derive-plymouth.py}
~/.config/omarchy/plugins/<username>.lock  only while `lock` is on
/usr/share/plymouth/themes/omarchy-matrix/ only while `boot` is on
```

The last two are the derived pieces, and neither overwrites the original:
`omarchy.lock` and Plymouth's `omarchy` theme stay where they were.

"Only while it is on" is meant literally, including for the one path outside
your home directory: `omarchy-matrix boot off` hands the splash back **and**
removes that directory. Turning a piece off leaves nothing behind, whether or
not you ever run `uninstall.sh`.

Removing it is **SUPER → Style → Matrix → Uninstall**, or `./uninstall.sh`. It
takes all of it back — the plugin, the lock clone, the CLI, the hooks, the menu
block, the boot splash and the theme directory itself — and leaves Omarchy's own
lock, screensaver and splash in charge again.

Pass `--keep-theme` if you want the colours and backgrounds to stay behind as an
ordinary Omarchy theme.

> **Do not use Omarchy's `Remove → Theme` on its own.** That command deletes the
> theme folder and nothing else, which would leave the plugin, the lock clone,
> the CLI and the hooks installed and pointing at a theme that is gone — and it
> deletes `uninstall.sh` along with the folder. Uninstall first, remove the theme
> after. If you already did it the other way round, `install.sh` leaves a copy of
> the uninstaller on your PATH as `omarchy-matrix-uninstall` for exactly this.

> **With "stay awake" on, the screensaver never comes up.** The pack respects
> the same switch Omarchy's idle service does
> (`~/.local/state/omarchy/indicators/stay-awake`): with it set there is no
> screensaver, neither ours nor theirs.

> **Careful with Omarchy's own toggle.** The `screensaver` piece uses the native
> `screensaver-off` flag, so `omarchy toggle screensaver` (SUPER → Toggle →
> Screensaver) turns it off underneath and `matrix.json` still says yes.
> `omarchy-matrix doctor` puts them back in agreement.

> **`omarchy refresh shell` turns the rain off.** That command rewrites
> `shell.json` wholesale, and that is where Omarchy records which plugins are
> enabled. There is no hook to attach to afterwards. Recover with
> `omarchy-matrix doctor`, or by re-applying the theme — the `theme-set` hook
> does it for you.

## Automatic

| When | What happens |
|---|---|
| `omarchy theme set matrix` | Whatever you had on comes back |
| `omarchy theme set <other>` | The pack stands down, keeping your settings |
| `omarchy update` | The lock and the boot splash are derived again from the updated sources |

Standing down means: the plugin is disabled, Omarchy's screensaver returns, and
**the lock clone is deleted** — with `omarchy plugin remove`, which is what
re-enables Omarchy's own; merely disabling it would leave you with no lock
enabled at all. Your settings are untouched: going back to matrix restores
exactly what you had.

`boot` is the exception and does not stand down: the Plymouth splash belongs to
the system, not to the theme. Its ✓ asks the system which theme is really
installed, so it never lies either.

While the pack is stood down, the menu **ticks nothing** and `omarchy-matrix
status` says why. The ✓ means "this is happening now", not "you have it
configured".

## What is inside

| | |
|---|---|
| `colors.toml` | The palette. Semantic, not `color0..15`. Includes the Hyprland border colours, which go through the template. |
| `shell.{bar,menu,launcher,notifications}.toml` | Shell section overrides: they give the bar and the cards some relief, which otherwise all paint the same black. |
| `backgrounds/` | The carousel. `0-neo-sleep` is the default, so installing only the theme still gives you a wallpaper. `1-live-rain` is a still frame of the shader: thumbnail, marker and fallback in one — selecting it is what turns the desktop rain on. The rest are film stills. |
| `unlock.png`, `preview-unlock.png` | The static boot mark, for anyone installing the theme without the pack. With the pack, `logo.png` goes invisible and the lines are typed instead. |
| `manifest.json`, `Service.qml`, `MatrixRain.qml`, `matrix.frag.qsb`, `glyphs.png` | The plugin. |
| `bin/` | `omarchy-matrix` (the switch CLI) and the two derivers, `derive-lock.py` and `derive-plymouth.py`. |
| `hooks/`, `extensions/` | The self-repair on theme change and update, and the menu entries. |
| `rain/` | The shader sources: `matrix.frag` and the atlas generator. |
| `generate-backgrounds.py`, `generate-brand.py` | Regenerate the PNGs. Neither is an untouchable binary. |

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
./generate-backgrounds.py               # the backgrounds
./generate-backgrounds.py --out /tmp/x.png --seed 42 --density 0.7
./generate-brand.py                     # unlock, preview-unlock and preview
./rain/generate-atlas.py                # the shader's glyph atlas

# recompile the shader (qsb is not on PATH; qt6-shadertools puts it here)
/usr/lib/qt6/bin/qsb --glsl 300es,330 --hlsl 50 --msl 12 \
    -o matrix.frag.qsb rain/matrix.frag
```

Those `qsb` targets are the ones the shipped `matrix.frag.qsb` was built with —
GLSL 300 es and 330, HLSL 50, MSL 12. Using different ones silently produces a
different set of shader variants.

Needs ImageMagick, `rsvg-convert`, Python 3, the Noto Sans CJK JP font and
`qt6-shadertools` for `qsb`.

## Working on the pack

`~/.config/omarchy/themes/matrix` is what `omarchy theme install` puts there and
it gets regenerated, so editing in it loses the change. Keep a working copy
elsewhere:

```bash
git clone https://github.com/tymurbogach/omarchy-matrix ~/dev/omarchy-matrix
# edit, commit and push there, then:
cd ~/.config/omarchy/themes/matrix && git pull && ./install.sh
```

That is a detour, but it is exactly the path anyone installing the pack takes,
so mistakes surface on your machine rather than on theirs.

Editing `Service.qml` can skip the detour by copying it straight into
`~/.config/omarchy/plugins/matrix.rain/`, but **finish with `omarchy restart
shell`**: hot reloads can leave two instances alive, the old one still answering
IPC while the new one paints, and the symptom is maddening.

## Contributing

`CLAUDE.md` holds the working agreement for this repo: the rules, the two-clone
workflow, and a list of traps that each cost real debugging time. Read it before
changing anything — several of them are invisible from the code. `AGENTS.md` is a
short pointer to it, for tools that look for that name.

## The backgrounds

```
0-pills.jpg        the default: what you get with the theme alone
1-live-rain.png    the live one — selecting it turns the desktop rain on
2-neo-sleep.jpg
3-morpheus.jpg
4-sunglasses.jpg
5-minimal.png
```

The rain has an entry of its own, and it is the only one with `-live-` in its
name: that substring, not a fixed filename or a position in the list, is what
the shader watches for. Everything else is an ordinary wallpaper and stays one
when you pick it.

The default is a photograph rather than the rain frame, so installing the theme
without the pack leaves you with a wallpaper instead of a frozen picture of the
one thing the theme is about making move.

> `omarchy theme set` rotates to the *next* background, so re-applying the theme
> does not put you back on the default — that only happens on a first install,
> when there is no selection to advance from.

> The stills are frames from *The Matrix* (1999), © Warner Bros. They are here
> because this is a fan theme and they are what the theme is about. They are not
> covered by this repository's MIT licence, which applies to the code. If you
> would rather not carry them, delete `backgrounds/*.jpg` and pick your own — any
> file with `-live-` in its name becomes the rain's marker.

## Credits

The rain shader started from [`matrix.frag` in
bjarneo/quickshell](https://github.com/bjarneo/quickshell) (MIT). It swaps the
original's procedural blocks for an atlas of the real halfwidth katakana — the
very ones `ttfx matrix` uses, the effect behind Omarchy's screensaver — and
keeps its colours.

## Licence

MIT.
