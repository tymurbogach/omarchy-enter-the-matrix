# CLAUDE.md — omarchy-matrix

A theme **and** a shell plugin for Omarchy 4, published from one repo. This file
is the working agreement for anyone — human or agent — changing it.

Everything here is in English because the repo is public and Omarchy's world is
English. Keep it that way: comments, messages, filenames, commit messages.

---

## Rule 0 — Omarchy is the source of truth, and it moves

**Invoke the `/omarchy` skill before touching anything under `~/.config/omarchy`,
`~/.config/hypr`, the bar, the lock, themes or backgrounds.** It carries the
current layout, the command surface and the safe extension points.

**Read Omarchy's own source instead of guessing.** It is right there and it is
readable:

```bash
cat $(which omarchy-theme-set)              # how a theme is actually staged
cat /usr/share/omarchy/shell/plugins/lock/LockView.qml
cat /usr/share/omarchy/default/plymouth/omarchy.script
omarchy commands --json                     # every command, machine-readable
```

Half the design decisions in this repo came from reading that source and finding
the ceiling. None came from assuming.

**Never edit anything under `/usr/share/omarchy/`.** It belongs to the package
and `omarchy update` overwrites it. Reading is safe and encouraged.

**Pin what you tested against.** `install.sh` carries `TESTED_ON`, and the
derivers abort loudly when a patch no longer fits. Update those, don't silence
them.

---

## Rule 1 — A request to review is not a request to change

"Have a look at X", "why does Y happen", "check Z" means: investigate, measure,
**report**. Propose the fix and wait. It does not authorise editing, committing
or pushing.

This is written down because it went wrong. Asked to *look into* why the
screensaver was showing Omarchy's default, the diagnosis was right — and then a
menu file was edited, committed and pushed unasked, breaking a row the user
looks at every day.

**If the fix looks obvious and one line long, it is still not yours.** Say so and
wait.

---

## Rule 2 — Verify what you changed, not what you were thinking about

Before claiming something works, check **the artefact as the user sees it**.

- ❌ "the menu action launches the right program"
- ✅ "the menu row renders with its icon and its label **and** launches the right
  program"

That same session shipped a menu row with no icon and the raw id as its label,
because only the action was tested.

If you genuinely cannot verify it from here — a boot splash, for one — **say so**
instead of assuming. Then verify everything you *can*: syntax, generated output,
cross-references, a simulation of the merge.

Verifications that actually caught bugs in this repo, worth repeating:

```bash
# Regenerate and prove nothing moved: these must come out byte-identical
md5sum glyphs.png backgrounds/*.png
./rain/generate-atlas.py && ./generate-backgrounds.py
md5sum glyphs.png backgrounds/*.png

# The lock patch still applies to the installed Omarchy
python3 -c "import importlib.util as u; s=u.spec_from_file_location('d','bin/derive-lock.py'); \
m=u.module_from_spec(s); s.loader.exec_module(m); m.patch((m.SOURCE/'LockView.qml').read_text())"

# The pack installs from a clean clone, the way a stranger gets it
git clone https://github.com/tymurbogach/omarchy-matrix /tmp/check
omarchy-plugin-validate /tmp/check
```

---

## Rule 3 — Additive only. Derive, never freeze.

The pack must not overwrite Omarchy's originals, and must not leave the system
worse than it found it.

Two pieces genuinely cannot be done any other way — the lock, because a
`WlSessionLock` is exclusive by protocol, and the boot splash, because Plymouth
themes only take colours and one still PNG. **Both are derived, never shipped as
a copy:**

- `bin/derive-lock.py` starts from *this machine's* `LockView.qml`
- `bin/derive-plymouth.py` starts from *this machine's* `omarchy.script`

Both apply a minimal patch, assert the anchor appears exactly once, and **abort
with a clear message** rather than half-patching. A `post-update.d` hook re-runs
them after every `omarchy update`, so Omarchy's fixes keep flowing through.

Everything else is additive: the plugin draws on its own layer-shell surfaces and
`omarchy.background` is never cloned or disabled.

**If a new feature seems to need a frozen copy of Omarchy code, that is the
signal to look for the extension point you have not found yet.** The desktop
rain looked like it needed a clone of `omarchy.background` for weeks. It did not.

---

## Rule 4 — Never leave the machine unable to lock or boot

The two derived pieces are the two that can lock someone out.

- **Lock:** hand it back with `omarchy plugin remove <clone>`, which re-enables
  `omarchy.lock` through `cloneSourceRestores`. *Disabling* the clone leaves
  **zero** locks enabled, because cloning put Omarchy's own into
  `disabledPlugins`. Test with `omarchy-shell lock preview` — never by locking.
- **Boot:** on an encrypted disk, Plymouth is also what asks for the passphrase.
  The patch touches no password callback, and the theme installs *alongside*
  Omarchy's rather than over it. Escape hatches: `omarchy plymouth reset`, or
  `plymouth.enable=0` on the kernel line from the boot loader.

---

## Rule 5 — Everything is a layer. Off must mean gone.

The pack is a **layer over Omarchy**, not a fork of it. Four things follow, and
none of them is negotiable.

**Every piece switches on its own.** `wallpaper`, `screensaver`, `lock`, `boot` —
each one off, on and back with no side effect on the other three, and with no
step in the middle that says "now re-apply the theme". A piece that only works
while the others are on is not a layer, it is a fork.

**Picking another theme stands everything down.** Nothing rains, nothing is
ticked, no plugin is left enabled. `matrix.json` is kept, so coming back to
matrix restores exactly what was there. `boot` is the one documented exception:
Plymouth belongs to the system, not to the theme.

**Off must remove, not merely deactivate.** If a piece wrote something, its `off`
takes it back — including anything outside `$HOME`. It is not enough for
`uninstall.sh` to clean up: someone who never uninstalls, and only turns a piece
off, must still end up with a clean machine.

> Written down because it was broken, and in the one place hardest to notice:
> `boot off` called `omarchy-plymouth-reset` and left
> `/usr/share/plymouth/themes/omarchy-matrix/` on disk forever, while
> `uninstall.sh` deleted it only when it happened to be the active theme. Turning
> the piece off was the exact case both missed.

**Nothing of Omarchy's may be left disabled.** The lock is the sharp edge:
handing it back always goes through `omarchy plugin remove`, never
`plugin disable`. See Rule 4.

---

## Where this is going

The pack is a **theme plus a layer**, and the layer is now two shell plugins:
`matrix.rain` draws, `matrix.control` is one icon on the bar that owns the
switches. Nothing of the pack is written into a file that is not its own any
more -- the block that used to be spliced into `omarchy-menu.jsonc` is gone, and
the only shared file it touches is `shell.json`, through Omarchy's own
`omarchy plugin enable`, which is what that command is for.

The four pieces are not matrix-specific: they are *wallpaper, screensaver, lock
and boot as a set*, and matrix is one provider of that set. `provider.json` is
the seam -- the only file that names the provider. Keep it that way: new work
adds to the machinery and asks the descriptor, rather than writing `matrix` down
one more time.

### The list, in the order it is worth doing

The nine seams the 2026-08-28 clean-room test turned up are closed. What is
below came out of closing them.

1. **`widget/Panel.qml` still writes the CLI's name down.** Every other file
   asks `provider.json`; the widget cannot, because it would need the CLI to
   find it. Either it reads `~/.local/share/omarchy-matrix/provider.json`
   directly with a `FileView`, or that stays the provider's one line -- decide,
   and write down which.
2. **`~/.local/share/omarchy-matrix/` is a bootstrap constant in three files**
   (the CLI, `bin/provider.py`, `uninstall.sh`). It cannot come from the file it
   is used to find, but three copies of it is two too many.
3. **The widget's panel does not say what a stood-down piece would do.** It
   ticks nothing and explains why at the top, which is right, but a switch that
   is on-but-stood-down currently reads exactly like one that is off.

---

## How to work on this repo

There are two clones with different jobs:

| Where | For what |
|---|---|
| `~/dev/omarchy-matrix` | The working copy. **Edit and commit here.** |
| `~/.config/omarchy/themes/matrix` | What `omarchy theme install` puts there. It gets regenerated — editing here loses the change. |

```bash
cd ~/dev/omarchy-matrix && git commit && git push
cd ~/.config/omarchy/themes/matrix && git pull && ./install.sh
```

A detour, deliberately: it is the exact path anyone installing the pack takes, so
mistakes surface here rather than on their machine.

Renaming or adding a background needs `omarchy theme set matrix` afterwards — the
state directory only picks up new filenames when the theme is re-applied.

### Commit messages explain the WHY

Not what changed — `git diff` says that. Why it changed, what was tried, what the
constraint was. Several commits here are the only record of a limitation that
would otherwise be rediscovered the hard way.

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
`omarchy.lock` disabled again) and the `matrix.control` entry in the bar. It
restores the pack and nothing else -- the user's own plugins and bar order come
back from Omarchy's own `shell.json.bak.<timestamp>`.

**A tick has to ask the machinery, not the settings.** Found by running that
same refresh: with `shell.json` wiped, `status` printed `✓ lock` and
`✓ wallpaper` while the rain plugin was disabled and Omarchy's own lock was the
one in charge. The settings were true, the theme was ours, and nothing was
happening. `is_active` now asks whether the plugin is enabled, whether the lock
clone is the enabled lock, and whether the screensaver flag is set.

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
size chosen for 1080p is tiny on a 3072 px panel, which is why
`derive-plymouth.py` computes it at derive time.

**`omarchy plymouth current` cannot see our boot theme.** It identifies a theme
by comparing `logo.png` inside Omarchy's *own* folder, and ours installs
separately. Use `plymouth-set-default-theme` with no arguments.

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

---

## Before you ship — the clean-room test

The cheap checks first:

```bash
bash -n install.sh uninstall.sh bin/omarchy-matrix hooks/*
python3 -m py_compile bin/*.py *.py rain/*.py
omarchy-plugin-validate .                  # must pass, or nobody can install it
```

Then the one that actually decides whether this is publishable: **install the
pack the way a stranger does, on a machine that has never seen it.** Reading the
diff is not this test. Neither is `./install.sh` from the working copy — that
path runs with `~/.local/bin` already warm, the hooks already in place and a
`matrix.json` full of yesterday's answers.

Six phases, in order. Each is verified as the user sees it (Rule 2), and a
failure in any one of them is a failure to ship.

1. **Strip the machine.** `./uninstall.sh` first, then hunt the residue by hand:
   plugin backups matching `~/.config/omarchy/plugins/.*.bak.*`, stale binaries
   in `~/.local/bin`, `~/.local/share/omarchy-matrix/`,
   `/usr/share/plymouth/themes/omarchy-matrix/`, the `matrix.control` entry in
   `shell.json`'s bar layout, any marker block left inside `omarchy-menu.jsonc`
   by an older install, `~/.config/omarchy/matrix.json`, the theme directory, and
   the `~/.local/state/omarchy/toggles/screensaver-off` flag.
   Prove it is gone before going on: `omarchy-matrix` must be *command not
   found*. Leave the user's own hooks alone — `theme-set.d` holds more than ours.
2. **Install from the published URL**, never from the working copy, following the
   README literally and doing nothing it does not say. What the README omits, the
   stranger does not know.
3. **Verify the four pieces are on and on screen** — not merely configured.
   For the lock this means a **screenshot**, not a status query: bring up
   `omarchy-shell lock preview` and `grim` it. For the widget it means a
   screenshot of the bar **and** of the open panel: an icon that occupies zero
   pixels answers every other check correctly. Every non-visual check passed
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
