# Matrix — a pack for Omarchy 4

Phosphor green on black. A normal Omarchy theme and, on top of it, the same
digital rain on the desktop, as the screensaver, and behind the lock.

![preview](preview.png)

## Install

One line, both halves:

```bash
omarchy theme install https://github.com/tymurbogach/omarchy-enter-the-matrix &&
  ~/.config/omarchy/themes/enter-the-matrix/install.sh
```

The first command is the **theme** — colours, backgrounds and the boot mark —
and it depends on nothing else. The second is the **pack**: the rain, which is a
shell plugin and cannot live inside an Omarchy theme, plus the switches on your
bar and the boot splash. It asks which pieces you want.

Chain them. Nothing in Omarchy's theme installer can tell you the second half
exists, so on its own the first line leaves you with a theme and no idea there
is more.

That script is the only supported way in. `omarchy plugin add <this repo>` looks
like it should work — the manifest is at the root — but it installs the whole
repository as the plugin and skips the CLI, the hooks and the bar widget, which
is most of the pack.

> **Installed this before it was renamed?** Run `omarchy-matrix-uninstall` first.
> The repo used to be `omarchy-matrix`, so the theme installed under the name
> `matrix`; it is `enter-the-matrix` now, and the old install is a separate one
> that will not be picked up or replaced.

## The pieces

Five switches, each one on and off on its own, from the **Matrix icon on your
bar** or from the command line:

```bash
omarchy-matrix status            # what is on right now
omarchy-matrix wallpaper off     # any piece: wallpaper screensaver lock boot widget
omarchy-matrix boot on
omarchy-matrix doctor            # assert everything again
```

| Piece | What it is |
|---|---|
| `wallpaper` | Rain on the desktop, above the wallpaper and below every window. Clicks go through it, and Omarchy's own background is not touched. On mains it always rains; on battery, only while no window is on the active workspace. |
| `screensaver` | Rain when you go idle, on your `shell.json` idle timing. It behaves like Omarchy's own: the pointer is hidden, the mouse does not dismiss it, any key does. |
| `lock` | Rain behind the password field. |
| `boot` | The screen before login, typing out the four lines from the film — and two more on the way out, different for a shutdown and for a reboot. Needs your password and rebuilds the initramfs, so it never applies on its own. |
| `widget` | The Matrix icon on the bar: the four switches above with a ✓ each, plus Repair and Uninstall. |

The desktop rain is one more background in the carousel, `1-live-rain`.
`omarchy-matrix wallpaper on` selects it for you.

The first three are the same shader, drawn three times. That is the point: the
screensaver used to be a different program drawing a different rain, and there
was no way to make all three match. The last two are the two pieces Omarchy
gives no way to configure, and both are handled by **deriving** its code rather
than shipping a frozen copy of it — the lock starts from your machine's
`LockView.qml`, the splash from your machine's `omarchy.script`, and a
`post-update.d` hook derives both again after every `omarchy update`, so
Omarchy's fixes keep arriving. [DESIGN.md](DESIGN.md) explains why, at length.

Try the lock without locking yourself out: `omarchy-shell lock preview`. See the
boot splash without rebooting: `bin/preview-plymouth.sh`, and the shutdown one
without shutting down: `bin/preview-plymouth.sh <scenario> --mode shutdown`.

> **If your disk is encrypted**, Plymouth is also what asks for your passphrase.
> The pack adds a callback rather than editing one, and falls back to Omarchy's
> own dialog rather than to no dialog. If anything goes wrong:
> `omarchy plymouth reset` from a running system, or `plymouth.enable=0` on the
> kernel line from your boot loader.

## The palette

No void black: the film never shows one. Surfaces sit where its dark scenes
actually sit (the pills scene averages `#171716`, Neo's sleep `#0E170C`,
Morpheus in warm ambers), the green is the monitor's own yellow-leaning
phosphor, red is the signal red (pill, dress, alarms) and blue the real
world's steel — each lightened only as far as legibility demands
(`#C8102E` at 3.3:1 cannot carry text). Same green hero, same ice-blue
prompt. The rain is untouched.

## Worth knowing

> **`omarchy theme set` rotates to the *next* background**, so re-applying the
> theme takes you off the rain. Come back with `omarchy-matrix wallpaper on`, or
> from the bar.

> **With "stay awake" on, the screensaver never comes up.** The pack respects the
> same switch Omarchy's idle service does
> (`~/.local/state/omarchy/indicators/stay-awake`): with it set there is no
> screensaver, neither ours nor theirs.

> **Careful with Omarchy's own toggle.** The `screensaver` piece uses the native
> `screensaver-off` flag, so `omarchy toggle screensaver` (SUPER → Toggle →
> Screensaver) turns it off underneath while `enter-the-matrix.json` still says
> yes. `omarchy-matrix doctor` puts them back in agreement.

> **`omarchy refresh shell` turns the rain off.** That command rewrites
> `shell.json` wholesale, and that is where Omarchy records which plugins are
> enabled and what sits on your bar. There is no hook to attach to afterwards.
> Recover with `omarchy-matrix doctor`. It brings back the rain plugin, the lock
> clone and the bar icon — not the rest of your `shell.json`; your other plugins
> and your bar layout come back from Omarchy's own backup,
> `~/.config/omarchy/shell.json.bak.<timestamp>`.

## What it touches on your system

Everything the pack installs is either its own file or a file Omarchy leaves for
extending. **Nothing** under `/usr/share/omarchy/`, nor `hyprland.lua`, nor the
background, nor the bar:

```
~/.config/omarchy/plugins/matrix.rain/       the plugin
~/.config/omarchy/plugins/matrix.control/    the bar widget
~/.config/omarchy/enter-the-matrix.json      which pieces are on
~/.config/omarchy/hooks/{theme-set,post-update}.d/enter-the-matrix
~/.config/omarchy/shell.json                 one entry in the bar layout
~/.local/bin/{omarchy-matrix,derive-lock.py,derive-plymouth.py,provider.py}
~/.local/share/omarchy-matrix/provider.json
~/.config/omarchy/plugins/<username>.lock    only while `lock` is on
/usr/share/plymouth/themes/omarchy-matrix/   only while `boot` is on
```

The last two are the derived pieces, and neither overwrites the original:
`omarchy.lock` and Plymouth's `omarchy` theme stay where they were.

"Only while it is on" is meant literally, including for the one path outside your
home directory: `omarchy-matrix boot off` hands the splash back **and** removes
that directory. Turning a piece off leaves nothing behind, whether or not you
ever run `uninstall.sh`.

## Automatic

| When | What happens |
|---|---|
| `omarchy theme set enter-the-matrix` | Whatever you had on comes back |
| `omarchy theme set <other>` | The pack stands down, keeping your settings |
| `omarchy update` | The lock and the boot splash are derived again from the updated sources |

Standing down means: the plugin is disabled, the bar icon goes, Omarchy's
screensaver returns, and **the lock clone is deleted** — with
`omarchy plugin remove`, which is what re-enables Omarchy's own; merely disabling
it would leave you with no lock enabled at all. Your settings are untouched:
going back restores exactly what you had.

`boot` is the exception and does not stand down: the Plymouth splash belongs to
the system, not to the theme. Its ✓ asks the system which theme is really
installed, so it never lies either.

While the pack is stood down the widget **ticks nothing** and
`omarchy-matrix status` says why. The ✓ means "this is happening now", not "you
have it configured" — which is why the Background tick goes out the moment you
pick another background from the carousel.

## Uninstall

**Uninstall**, at the bottom of the bar widget's panel, or `./uninstall.sh`. It
takes all of it back — both plugins, the lock clone, the CLI, the hooks, the boot
splash and the theme directory itself — and leaves Omarchy's own lock,
screensaver and splash in charge again.

The theme has to go somewhere, and it goes back to **the one you were using
before you picked this one**. The `theme-set` hook writes that down every time you
leave, because Omarchy overwrites `current/theme.name` before any hook runs and
afterwards nobody knows. If there is nothing recorded, it asks.

Pass `--keep-theme` if you want the colours and backgrounds to stay behind as an
ordinary Omarchy theme.

> **Do not use Omarchy's `Remove → Theme` on its own.** That command deletes the
> theme folder and nothing else, which would leave the plugin, the lock clone,
> the CLI and the hooks installed and pointing at a theme that is gone — and it
> deletes `uninstall.sh` along with the folder. Uninstall first, remove the theme
> after. If you already did it the other way round, `install.sh` leaves a copy of
> the uninstaller on your PATH as `omarchy-matrix-uninstall` for exactly this.

## The backgrounds

```
0-pills.jpg        the default: what you get with the theme alone
1-live-rain.png    the live one — selecting it turns the desktop rain on
2-neo-sleep.jpg
3-morpheus.jpg
4-sunglasses.jpg
5-hotel-corridor.jpg
6-green-street.jpg
7-the-office.jpg
8-helicopter.png   daylight raid, pale green sky
9-neo-white.jpg    Neo on white — the bright one, for when the rain is off
10-trinity-neo.jpg  Trinity and Neo, warm and dark
```

The rain has an entry of its own, and it is the only one with `-live-` in its
name: that substring, not a fixed filename or a position in the list, is what the
shader watches for. Everything else is an ordinary wallpaper and stays one when
you pick it.

The default is a photograph rather than the rain frame, so installing the theme
without the pack leaves you with a wallpaper instead of a frozen picture of the
one thing the theme is about making move.

> `0-pills.jpg`, `2-neo-sleep.jpg`, `3-morpheus.jpg`, `4-sunglasses.jpg`,
> `8-helicopter.png`, `9-neo-white.jpg` and `10-trinity-neo.jpg` are frames
> from *The Matrix* (1999), © Warner Bros. They are here because this is a
> fan theme and they are what the theme is about. They are not covered by this
> repository's MIT licence, which applies to the code. If you would rather not
> carry them, delete those seven and pick your own — any file with `-live-` in its
> name becomes the rain's marker.

## More

- **[DESIGN.md](DESIGN.md)** — why the lock and the boot splash are derived
  rather than copied, what is in each file, the palette, and how to regenerate
  the assets.
- **[CLAUDE.md](CLAUDE.md)** — the working agreement for this repo: the rules,
  the two-clone workflow, and a list of traps that each cost real debugging time.
  Read it before changing anything. `AGENTS.md` is a short pointer to it.

## Credits

The rain shader started from [`matrix.frag` in
bjarneo/quickshell](https://github.com/bjarneo/quickshell) (MIT). It swaps the
original's procedural blocks for an atlas of the real halfwidth katakana — the
very ones `ttfx matrix` uses, the effect behind Omarchy's screensaver — and keeps
its colours.

## Licence

MIT.
