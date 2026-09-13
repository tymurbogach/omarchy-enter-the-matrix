# CONTRIBUTING — omarchy-enter-the-matrix

English everywhere: code, docs, comments, commit messages. The repo is public
and Omarchy's world is English.

Run `./tools/check.sh` before pushing. It covers what needs no Omarchy
session. The clean-room test at the end decides whether a change ships.

## Rules

Five rules decide every change. Each one is written down because breaking it
cost real time.

### 1. Omarchy is the source of truth, and it moves

Read Omarchy's own source instead of guessing. It is readable:

```bash
cat $(which omarchy-theme-set)          # how a theme is staged
cat /usr/share/omarchy/shell/plugins/lock/LockView.qml
cat /usr/share/omarchy/default/plymouth/omarchy.script
omarchy commands --json                 # every command, machine-readable
```

Never edit anything under `/usr/share/omarchy/`. The package owns it, and
`omarchy update` overwrites it. Reading it is safe.

Pin what you tested against. `install.sh` carries `TESTED_ON`, and the derivers
abort when a patch no longer fits. Update those values. Do not silence the
aborts.

### 2. Verify what you changed, as the user sees it

Check the result on screen, not only the code path. A menu row that launches
the right program can still render with no icon and a raw id as its label. If
you cannot verify something, say so. Then verify what you can: syntax,
generated output, cross-references.

`tools/preview-plymouth.sh` runs the real boot splash in a window, and `grim`
photographs it. Only two things still need a reboot. One is whether
`mkinitcpio` carried the theme in. The other is whether the DRM renderer agrees
with the X11 renderer about the panel.

### 3. Additive only. Derive, never freeze

The pack must not overwrite Omarchy's originals. Two pieces cannot work any
other way, and both are derived from this machine's source:

- The lock, because a `WlSessionLock` is exclusive by protocol.
  `lib/derive-lock.py` starts from the installed `LockView.qml`.
- The boot splash, because a Plymouth theme takes colours and one still image.
  `lib/derive-plymouth.py` starts from the installed `omarchy.script`.

Each deriver applies a minimal patch and asserts that its anchor appears
exactly once. If the anchor does not fit, the deriver aborts with a clear
message. The `post-update` hook derives both again after every `omarchy update`.

If a feature seems to need a frozen copy of Omarchy code, look for the
extension point you have not found yet. The desktop rain looked like it needed
a clone of `omarchy.background` for weeks. It did not.

### 4. Never leave the machine unable to lock or boot

The two derived pieces are the two that can lock someone out.

- Lock: hand it back with `omarchy plugin remove <clone>`. That command
  re-enables `omarchy.lock`. Disabling the clone leaves zero locks enabled.
  Test with `omarchy-shell lock preview`, never by locking.
- Boot: on an encrypted disk, Plymouth also asks for the passphrase. The patch
  touches no password callback, and the theme installs beside Omarchy's. The
  escape hatches are `omarchy plymouth reset`, and `plymouth.enable=0` on the
  kernel line from the boot loader.

### 5. Everything is a layer. Off must mean gone

- Each piece (`wallpaper`, `screensaver`, `lock`, `boot`) switches on and off
  alone, with no side effect on the other three.
- Another theme stands everything down: nothing rains, nothing is ticked, and
  no plugin stays enabled. `enter-the-matrix.json` stays, so coming back
  restores the same state. `boot` is the one exception, because Plymouth
  belongs to the system and not to the theme.
- Off removes what the piece wrote, including files outside `$HOME`. A user who
  never uninstalls must still end up with a clean machine.
- Nothing of Omarchy's stays disabled.

### Open work

The widget's panel does not say what a stood-down piece would do. It ticks
nothing and explains why at the top. A switch that is on but stood down reads
exactly like a switch that is off.

## Workflow

There are two clones with different jobs:

| Where | For what |
|---|---|
| `~/Projects/omarchy-enter-the-matrix` | The working copy. **Edit and commit here.** |
| `~/.config/omarchy/themes/enter-the-matrix` | What `omarchy theme install` puts there. It gets regenerated — editing here loses the change. |

```bash
cd ~/Projects/omarchy-enter-the-matrix && git commit && git push
cd ~/.config/omarchy/themes/enter-the-matrix && git pull && ./install.sh
```

### Commit messages explain the WHY

Not what changed — `git diff` says that. Why it changed, what was tried, what the
constraint was. Several commits here are the only record of a limitation that
would otherwise be rediscovered the hard way. No credit lines for any AI
assistant, ever — neither in commits, nor in PR descriptions.

---

## Traps already paid for

Each of these cost real debugging time. None is obvious from the code.

**For a `bar-widget`, "enabled" means "present in `bar.layout`".**
`PluginRegistry.setEnabled` inserts the layout entry when you enable it and
removes it when you disable it (`PluginRegistry.qml:498-520`); `isEnabled` then
answers from wherever the entry is found. So a plugin that is both a widget and
something else cannot be switched off without taking its icon off the bar --
which is why the rain and the switchboard are two plugins, not one.

**A bar widget with no `implicitWidth` paints nothing, silently.** The bar sizes
each slot from `activeItem.implicitWidth` (`Bar.qml:1565`), and a plain `Item`
has none, so every bar widget sets `implicitWidth: button.implicitWidth` on its
root. Without it the plugin loads, answers IPC and opens its panel while
occupying zero pixels -- and every non-visual check passes. Only a screenshot
says otherwise.

**Hyprland 0.56 took its dispatchers to a Lua API, and a stale selector fails
SILENTLY.** `hyprctl dispatch focuswindow class:Plymouthd` is a Lua syntax
error, `hl.dsp.focus` wants a direction rather than a window, and
`hl.dsp.window.fullscreen()` acts on whatever *is* focused. That last one
matters: a preview script that assumed focus had moved then drove `wtype`, and
typed a test passphrase and its Return into the terminal the user was working
in. **Never aim `wtype` at a window you have not confirmed is focused** — it has
no target, it types wherever the compositor is pointing. `tools/preview-plymouth.sh`
sends keys down plymouthd's own pty instead, which nothing else can receive.

**A summoned panel only takes the keyboard on the first summon after the shell
starts.** `omarchy-shell shell summon <id>` maps the panel, but a later summon
in the same shell process leaves the keys going to whatever had focus -- Escape
does not even close it. Omarchy's own `omarchy.bluetooth` behaves identically,
so this is the environment, not the pack. It matters when testing: drive the
widget's cursor with `wtype` right after `omarchy-restart-shell`, or the panel
will sit there ignoring you and look like a bug of ours.

**Hot-reloading does not resize a bar widget's slot.** After adding those two
lines to a live widget the slot stayed 0 px wide across several reloads and only
took its size after `omarchy-restart-shell`. install.sh ends with one restart
for this reason.

**`omarchy theme update` fires no hooks at all** -- it is `git pull` per theme,
nothing more (`cat $(which omarchy-theme-update)`) -- and `omarchy update` never
calls it. Nothing the pack installs outside the theme directory can be refreshed
by a hook after a pull, which is why `doctor` compares files itself and calls
`install.sh --sync`.

**"Different" is not "outdated".** That comparison first ran with `cmp`, and a
working copy installed over an older theme directory looks exactly as different
as a pulled theme looks over an older install -- so it dutifully copied the old
files over the new ones. It asks `-nt` now: a `git pull` gives every file it
touches a fresh mtime, which is the event this is actually for.

**Hot-reloading plugin QML can leave two instances alive.** The old one keeps
answering IPC while the new one paints. Symptom: the IPC reports `false` for a
property you just set to `true`, and the journal shows errors on a line that no
longer exists in the file. Fix: `omarchy restart shell`. `rescanPlugins` is not
always enough.

**A plugin rescan still in flight when the shell is restarted SEGFAULTS
quickshell.** The scan finishes mid-teardown, builds the plugin services, and
their `IpcHandler` asks the engine generation for an IPC registry the teardown
has already freed — `__dynamic_cast` on a dead `EngineGenerationExt`,
`ipchandler.cpp:318`, reached from `Process::onFinished` (the scanner exiting)
through `shell.qml:300`'s `createObject`. It is
[quickshell#972](https://github.com/quickshell-mirror/quickshell/issues/972),
open, and **not fixable from here**; it is present in 0.3.0 and 0.3.1 alike, so
do not go looking for the package that "broke" it.

What made it ours is the workload: `suspend` disables two plugins, removes the
lock clone, prunes its backup and restarts the shell, all inside one second.
Fifteen coredumps in three days, every one a `theme set` away from matrix.
`settle_plugin_scan` now waits for `listPlugins` to answer the same thing three
times before any lock restart. That NARROWS the race — it does not close it, and
nothing here can. The shell was going to restart anyway, so the visible symptom
was only a dirty exit and a crash notification; do not mistake that for it being
harmless to leave, because a segfault during teardown bites differently on a
different day.

The cheap way to keep the window shut: **never write into a live plugin folder.**
Omarchy watches `~/.config/omarchy/plugins` with `inotifywait -m -r`
(`PluginRegistry.qml:636`) and ignores dot-prefixed entries
(`localPluginIdForPath`, `:707`), so staging in `.<id>.staging` and renaming into
place is invisible until it is complete. `rm -rf` on the live folder is the same
burst in reverse — rename it to `.<id>.retired` first and delete that.

**`omarchy refresh shell` rewrites `shell.json` wholesale**, and that is where
enabled plugins and the bar layout are recorded. There is no post-refresh hook.
Recovery is `omarchy-matrix doctor`, or re-applying the theme. Verified on this
machine: after a refresh, `doctor` restored `matrix.rain`, the lock clone (with
`omarchy.lock` disabled again) and the widget entry in the bar. It
restores the pack and nothing else -- the user's own plugins and bar order come
back from Omarchy's own `shell.json.bak.<timestamp>`.

**A tick has to ask the machinery, not the settings.** Found by running that
same refresh: with `shell.json` wiped, `status` printed `✓ lock` and
`✓ wallpaper` while the rain plugin was disabled and Omarchy's own lock was the
one in charge. The settings were true, the theme was ours, and nothing was
happening. `is_active` now asks whether the plugin is enabled, whether the lock
clone is the enabled lock, and whether the screensaver flag is set.

**There are TWO background directories and only one is the theme's.**
`~/.config/omarchy/themes/<theme>/backgrounds/` is the carousel the theme ships.
`~/.config/omarchy/backgrounds/<theme>/` is where the *user* drops extras, and it
does not exist until they do. `omarchy-theme-set:78` searches both, which is why
the second one looks authoritative when you go hunting and is in fact usually
absent. Verifying "did my new backgrounds land?" against the second path reports
a failure that is not there.

**A theme installed from git may not ship any `.lua`** — nor `alacritty.toml`,
`foot.ini`, `ghostty.conf`, `kitty.conf` or `vscode.json`
(`omarchy-theme-set:142`). Lua runs code inside the compositor. That is why this
theme sets border *colours* but not thickness or rounding.

**Overriding a menu row means repeating `icon` and `label`.** `normalizeItem`
(`MenuModel.js:13`) fills in every key *before* `mergeMenuSources` merges, with
`icon: value.icon || ""` and `label: value.label || id`. A row carrying only
`action` overwrites the good icon and label with blanks — whatever the comment in
the extensions file claims.

**In jq, `(.[$k] // true)` returns `true` when the value is `false`.** Ask
`if has($k) then .[$k] else true end` instead.

**Plymouth draws at the panel's NATIVE resolution**, not the logical one. A point
size chosen for 1080p is tiny on a 3072 px panel. `derive-plymouth.py` used to
work the size out at derive time from `hyprctl`; it does not any more. The
script measures its own text at boot — render a probe, read `GetWidth()` back,
scale from there — which is right on every panel, survives docking, and needs no
calibration constant. `Window.GetWidth()` in the X11 preview is half the panel's,
so a baked size would also have made every preview a lie.

**A derive-time aspect ratio can run the panel off the bottom of a real
screen, and BOX_ASPECT alone cannot know that.** It is baked from this
machine's font metrics; the panel's vertical anchor (`entry.y`, Omarchy's own
idea of where its dialog goes) is boot-time and can sit low enough that there
is not BOX_ASPECT's worth of room under it. Caught by photographing the real
render at this panel's own resolution with `tools/preview-plymouth.sh`, not by
the math -- the box simply had no bottom border in the shot. Two fixes, not
one: the panel is lifted a fixed fraction of the screen height off `entry.y`
rather than sitting exactly on it, AND the height is clamped against
`Window.GetHeight()` at boot, because the lift is still a guess about a
screen the deriver has never seen.

**In the initramfs, `Image.Text`'s font FAMILY is ignored. Only the size
survives.** The mkinitcpio hook copies exactly three font files, under fixed
names, and `label-freetype` resolves a family by shelling out to
`/usr/bin/fc-match` — which is not in the initramfs. So `"DejaVu Serif 30"`
renders as a serif on your desktop and as `/usr/share/fonts/Plymouth.ttf` at
boot, with nothing to warn you. Anything whose exact shape matters must arrive
as a PNG. `tools/preview-plymouth.sh` reproduces all three restrictions, which is
the only reason this was found before shipping.

**But `Font=` in the .plymouth DOES decide which TTF that is**, and the note
above used to obscure it by saying a family "comes out as the theme's mono
font". That was only true because `stage()` writes the same family into both
`Font=` and `MonospaceFont=`, making the two files identical. The hook resolves
`Font=` with `fc-match` and copies that one file in as `Plymouth.ttf`
(`/usr/lib/initcpio/install/plymouth`), which is exactly what `label-freetype`
falls back to. So the boot has one text face and the theme chooses it — it just
cannot choose a SECOND one, or vary it per call.

**A font family named at derive time is a silent dependency.** `fc-match` does
not fail when it misses; it returns `monospace`. Name a family the installing
machine does not have and the splash is baked in the wrong face with nothing
anywhere to say so. That is why the splash's own face ships in `fonts/` as a
file, and why `available_font()`'s fallback is only ever allowed to affect the
disk's prompt, never a picture.

**plymouthd SEGFAULTS when it can resolve no font at all.** Nothing checks that
`FT_New_Face` found a file. That is why `derive-plymouth.py` asserts the family
resolves, and why the preview has to populate `/usr/share/fonts/Plymouth*.ttf`
rather than merely hiding fc-match.

**A number and a sprite object cannot share a name in a Plymouth script.**
`global.mx_caps = -1` early in the file, then `mx_caps.image = Image.Text(...)`
later: the second assignment goes to a number, does nothing, and the sprite
draws nothing — no error, no log line, no clue. Cost an hour. Suffix the state
(`mx_caps_state`) or rename the object.

**`Image()` on a file that is not there still tests as true**, and Plymouth does
NOT abort the script when you then `Scale()` it — it carries on. So a guard has
to ask `Image("x.png").GetWidth() > 0`, and a missing asset otherwise gives you
a password prompt with nothing to type into.

**plymouthd blocks on a pty nobody drains.** It announces "redirecting debug
output to /dev/pts/N" and does that even with `--debug-file`; if the master end
is not being read, the daemon stops part way through with no error anywhere.
That trace is also the only place a `.script` syntax error is ever reported.

**A block glyph for the passphrase reads as a progress bar, however much air
you put between the blocks.** The mask was `▊` and not `█` for exactly that
reason -- seven-eighths of a cell, so the characters would not butt together --
and it did not work, because the progress readout lives in the SAME row and was
also made of blocks. A boot went `solid bar` (typing) -> `[░░░░] 0%` -> `[███░]
42%`, and the eye read all three as one meter behaving oddly. What separates the
two is the GLYPH, not the spacing: dots for the passphrase, blocks for the
track. And `░` beside `█` is its own version of the same mistake -- one is a
dither pattern and the other is solid ink, so an empty bar and a half-full one
do not look like the same object. The track is now one image drawn twice, at two
opacities.

**A missing glyph draws NOTHING -- not `.notdef`, not a box.** True of every
piece of text this splash still typesets (the boot lines, the captions, the
CAPS LOCK label): freetype does not give back a hollow rectangle for a glyph
the font lacks, it inks zero pixels and advances the cell. On the passphrase
mask specifically this is no longer a live risk -- see the next trap, it is
DRAWN rather than typeset now -- but the guard pattern is worth keeping for
everything that still is: ask the PICTURE, not the font (`magick ... -alpha
extract -format "%[fx:mean]"`), and die below 1% ink (nothing drawn) or above
60% (block-shaped, reads as the progress track). The old table this held was
wrong for more than one glyph -- re-measured in Terminus, which is the face
that ships: `-` 4.1 %, `·` 1.4 %, `•` 5.6 %, `▪` 0 % (missing in this font),
`*` 13.6 %, `●` 5.6 %, `■` 18.7 %, `▊` 73 %, `█` 94.6 %.

**A font can render `●` as a blocky octagon, not a disc, and its ink share
will not tell you.** TerminessNerdFont is a Terminus derivative, and Terminus
is a bitmap face at heart -- its `●` measures barely more ink than a plain
`•` (see the table above) and is visibly NOT round: a stepped, roughly-square
blob, even at pointsize 120 with no antialiasing to blame. Only visible by
rendering the one glyph alone and looking at it -- every measurement this file
takes of MASK is about coverage, none of them are about shape. Cost real time:
`kerning` and a faux-bold `-strokewidth` were tuned against this glyph first,
on the reasonable-sounding theory that bigger and bolder would eventually read
as round. It does not; dilating a blocky octagon draws a bigger blocky octagon.
The passphrase mask is drawn with ImageMagick's own `circle` primitive now,
one per cell, rather than typeset at all -- the one piece of text in this file
that stopped being text, specifically because no glyph in the shipped font
could deliver the shape asked for.

The same trap bites the typed LINES, and the mask's guard does not cover them: a
whole line inks plenty with one character missing from the middle, so it comes
out spelt wrong and passes every check. An accent is the realistic way to hit it
-- a face that has `e` says nothing about whether it has an accented one, and
the reboot lines open with a deja vu. `splash_assets()` therefore renders every
character in use as ONE strip and measures the ink per cell (`-crop {cell}x{h}
+repage -format "%[fx:mean] "` gives all of them in a single magick call, which
the monospace assertion above makes safe).

That guard is also what rejected a candidate face while choosing one. Cascadia
Code's dashes touch each other, so a row of them draws a continuous rule rather
than a row of characters — and it is not monospace either, which the cell-drift
check catches. Neither is visible in a font sample; both are obvious in a
picture of the actual line.

**`-draw` takes its colour from `-fill`, so `-fill none` draws NOTHING rather
than erasing.** The panel's top rule is broken where its caption sits, and the
first version knocked that hole through with `-compose clear` over a
`-draw rectangle`. It silently did nothing: the rule came out straight through
the letters. `-compose` governs `-draw image`, not `-draw rectangle`. The frame
is five `line` strokes now, with the gap simply not drawn — and painting the gap
in the background colour would have been its own bug, since the background
belongs to Omarchy's theme and our guess at it would show as a patch on any
other.

**A preview scenario cannot reach the bullets or the progress bar.** Three
separate things get in the way, and all three were hit here:
`send` goes down plymouthd's pty, but the daemon counts passphrase keystrokes
from the RENDERER, so nothing ever becomes a bullet; `display_normal_callback`
starts Omarchy's fake progress the moment `password_shown` is set, which
repaints over the dialog at 50 fps; and in `--mode=boot` plymouthd feeds real
boot progress into `Plymouth.SetBootProgressFunction` whether or not anything is
booting, which overwrites any percent you set. What works is a **doctored copy
of the staged theme** -- `preview-plymouth.sh --stage DIR` takes any directory --
with a probe appended that calls `mx_password_callback` and `mx_progress`
directly from `refresh_callback`, re-asserting on every frame, and out-registers
the boot progress callback with a no-op. The probe only CALLS the drawing code,
so the pictures are still of the real thing.

**The preview probe bypasses the asset guard, so it cannot test the fallback.**
The doctored stage calls `mx_password_callback` straight from `refresh_callback`,
which is the whole point of it -- but the `if (... GetWidth() > 0)` that decides
whether to register that callback never runs. Delete an asset and preview with
the probe and you get a half-drawn dialog of ours, which looks exactly like the
fallback being broken. It is not: use `plymouth ask-for-password` in the
scenario, with NO probe, and Omarchy's own dialog comes up whole. Photographed
both ways.

**There are only TWO Plymouth exits, and `halt` is not one of them.**
`plymouth-halt.service`, `plymouth-poweroff.service` and
`plymouth-kexec.service` all run `plymouthd --mode=shutdown`; only
`plymouth-reboot.service` differs (`grep ExecStart
/usr/lib/systemd/system/plymouth-*.service`). `script.so` knows `shutdown`,
`reboot`, `updates`, `system-upgrade` and `firmware-upgrade` -- there is no
`halt` string in it to match. So a halt cannot be told apart from a power off
from inside a `.script`, and a `halt` key in `provider.json` would be
configuration that never runs.

**plymouthd feeds boot progress on the way OUT too, and a sprite that turns
itself on will draw on an empty screen.** `Plymouth.SetBootProgressFunction` is
called in `--mode=shutdown` and `--mode=reboot` exactly as in `--mode=boot`, so
`update_progress_bar` -> `mx_progress` runs at shutdown. Nothing on an exit ever
asks for a passphrase, so `mx_bar_show(1)` is never reached and the panel is
never shown -- but `mx_progress` owned the fill's opacity (it is the only thing
that knows how wide the crop should be) and lit it anyway. The result,
photographed: ONE cyan cell floating in the middle of a black screen with no
panel and no track behind it. It had been there since before the exit lines
existed and nobody had looked, because every earlier shot was cropped to the
typed line at the top.

`global.mx_bar_on` now gates `mx_progress`, and it clears the fill rather than
merely skipping it, so a percent arriving after the readout is hidden cannot
leave the last crop lit. **Judge an exit from the WHOLE frame**: the interesting
failure is in the middle of the screen, not where the words are.

**`Plymouth.GetMode()` is already right at the TOP of the script**, not only
inside a callback. `omarchy.script` asks it in `display_normal_callback`, which
makes it look like something only a callback can know; it is not. plymouthd sets
the mode before it loads the theme, so the whole storyboard can be *selected* at
load time rather than swapped mid-flight. Proven rather than assumed: probes at
the first and last line of the file both read `shutdown` under
`--mode=shutdown`. `tools/preview-plymouth.sh --mode NAME` exists for exactly this
-- it is how the exit splashes are photographed without turning the machine off.

**`omarchy plymouth current` cannot see our boot theme.** It identifies a theme
by comparing `logo.png` inside Omarchy's *own* folder, and ours installs
separately. Use `plymouth-set-default-theme` with no arguments.

**A repair command that does not check the theme re-creates the state it
exists to fix.** The pack was found raining under everforest: `theme set` had
stood it down correctly at 14:52, and a manual `git pull && ./install.sh` that
evening stood it back up, because `install.sh` ends in `doctor` and `doctor`
applied every setting without asking which theme was current. The hook never
failed -- the recovery path undid it. Now, under another theme, `doctor` only
syncs files (and stands down anything still up), piece commands write the
setting and defer the apply to the next `theme set`, and `status` says so when
pieces are up while stood down. `boot` is exempt: it belongs to the system.

**`qsb` is not on `PATH`** — it is at `/usr/lib/qt6/bin/qsb`. And the shipped
`matrix.frag.qsb` was built with `--glsl 300es,330 --hlsl 50 --msl 12`. Different
targets silently produce a different set of shader variants.

**The Wayland idle protocol resets on *any* input, mouse included.** Dismissing
the screensaver when idle ends is what made it vanish on mouse movement, which
Omarchy's own screensaver does not do — its loop only watches the keyboard.

**A fullscreen overlay maps under the cursor** and gets a pointer event
immediately. Without a short grace period it dismisses itself in the frame it
appears.

**Swapping the lock plugin leaves both loaded, and the loser is chosen for
you.** With `omarchy.lock` and the clone briefly alive at once, Quickshell hands
the `lock` IPC target to one and refuses the other (`Handler was registered but
will not be used because another handler is registered for target lock`). Which
one wins alternated between runs here. When Omarchy's won, the screen locked to
Omarchy's blurred wallpaper while `plugin list` said the clone was enabled,
`lock status` answered, and the patched QML on disk was perfect. `rescanPlugins`
does not unload the loser; `omarchy-restart-shell` does, and `apply_lock` now
calls it whenever the set of enabled locks changes.

**`omarchy plugin remove` renames, it does not delete.** The folder comes back as
`.<id>.bak.<timestamp>` unless it contains a `.git`, in which case it is deleted
outright (`omarchy-plugin-remove:113`). Our lock clone has no `.git` and is
derived, so every `lock off` used to leave a full copy behind — nine of them had
piled up here. Ours are identified by the `MatrixRain.qml` inside; a lock clone
somebody made for their own reasons has the same name shape and must survive.

**The widget is fetched from its own repo, not shipped in `widget/`.** It moved
to `omarchy-matrix-widget` so it could be submitted to `plugins.omarchy.org`
as a single-manifest-at-root plugin without merging it into the rain plugin's
manifest -- which would have collapsed the independent on/off toggle the
two-plugin split exists for (see the `PluginRegistry.setEnabled` trap above).
`install.sh` fetches and caches it under
`~/.local/share/omarchy-matrix/widget-src`, refreshing on every run rather
than re-cloning, so `omarchy-matrix doctor` (which runs `install.sh --sync`)
degrades to a warning instead of failing outright when offline. A git
submodule was considered and rejected: this repo's own clean-room test clones
with plain `git clone`, no `--recurse-submodules`, and a submodule would
silently leave that directory empty. `MATRIX_WIDGET_SRC=<path>` overrides the
fetch for local development against an uncommitted checkout of the widget
repo.


## Before you ship — the clean-room test

The cheap checks first:

```bash
bash -n install.sh uninstall.sh bin/omarchy-matrix lib/pack.sh tools/*.sh
python3 -m py_compile lib/*.py tools/*.py
./tools/check.sh                          # cheap and coherence checks
omarchy-plugin-validate .                  # must pass, or nobody can install it
```

Then the one that actually decides whether this is publishable: **install the
pack the way a stranger does, on a machine that has never seen it.** Reading the
diff is not this test. Neither is `./install.sh` from the working copy — that
path runs with `~/.local/bin` already warm, the hooks already in place and a
`enter-the-matrix.json` full of yesterday's answers.

Six phases, in order. Each is verified as the user sees it -- the artefact on screen, not what the commands say -- and a
failure in any one of them is a failure to ship.

1. **Strip the machine.** `./uninstall.sh` first, then hunt the residue by hand:
   plugin backups matching `~/.config/omarchy/plugins/.*.bak.*`, the `omarchy-matrix` symlink and any stale helpers (`derive-lock.py`, `derive-plymouth.py`, `provider.py`, `omarchy-matrix-uninstall`) in `~/.local/bin`, `~/.local/share/omarchy-matrix/`,
   `/usr/share/plymouth/themes/omarchy-matrix/`, the widget entry in `shell.json`'s bar layout, `~/.config/omarchy/enter-the-matrix.json`, the theme
   directory, and the `~/.local/state/omarchy/toggles/screensaver-off` flag.
   The repo was called `omarchy-matrix` until 2026-08-31, so a machine that saw
   an older install also has `~/.config/omarchy/matrix.json`,
   `~/.config/omarchy/themes/matrix/` and `hooks/*.d/matrix` under the old name.
   Prove it is gone before going on: `omarchy-matrix` must be *command not
   found*. Leave the user's own hooks alone — `theme-set.d` holds more than ours.
2. **Install from the published URL**, never from the working copy, following the
   README literally and doing nothing it does not say. What the README omits, the
   stranger does not know.
3. **Verify the four pieces are on and on screen** — not merely configured.
   For the lock this means a **screenshot**, not a status query: bring up
   `omarchy-shell lock preview` and `grim` it. For the widget it means a
   screenshot of the bar **and** of the open panel: an icon that occupies zero
   pixels answers every other check correctly. For the boot splash it means
   `tools/preview-plymouth.sh` — the typed line, the passphrase dialog with a
   handful of dots in it, and the progress track at 0 %, part way and full, all
   photographed. Neither the bullets nor the track can be reached by a scenario
   on its own: see the trap below for the doctored stage that gets you there. And
   the two exit splashes are `--mode shutdown` and `--mode reboot`, which need
   no reboot either. It used
   to be the one piece that shipped unseen; it no longer has that excuse. Every non-visual check passed
   while the machine was in fact locking to Omarchy's blurred wallpaper, and the
   image was the only thing that said so.
4. **Toggle each piece off and back on, one at a time**, checking each time that
   the others did not move. `lock off` must leave `omarchy.lock` out of
   `disabledPlugins` and no `.bak` behind, and `lock on` is checked by
   screenshot, not by asking. At least one toggle comes from the widget itself,
   not only from the CLI: `wtype -k Down` then `wtype -k Return` drives its
   cursor without a mouse -- **immediately after `omarchy-restart-shell`**, or
   the panel will not have the keyboard (see the traps).
5. **Switch to another theme and back.** Away: nothing rains, nothing is ticked,
   **no Matrix icon is left on the bar**, Omarchy's own lock and screensaver
   answer again, and nothing of Omarchy's is left disabled. Back: exactly what
   was on before is on again.
6. **Uninstall, and compare the machine against phase 1.** Anything still there
   is a bug, not a detail.

Whatever this turns up belongs in the repo — as a fix, or as a written-down
limitation. Rediscovering it on someone else's machine costs far more.
