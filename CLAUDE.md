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

Today the pack is a theme plus a block spliced into the user's menu under
**Style** — one level deeper than it should be, and it only knows about matrix.

The direction is a single **bar widget**: `kinds: ["bar-widget", "service"]` with
a `panel` entry point, the way Omarchy's own built-ins do it. One item on the
bar owns the four switches, and the pack stops writing into
`omarchy-menu.jsonc` at all — which is the most invasive thing it currently does
to a file that is not its own.

Beyond that, the four pieces are not really matrix-specific: they are
*wallpaper, screensaver, lock and boot as a set*, and matrix is one provider of
that set. New work should keep the seam visible — a provider contributes a
shader and its assets, the machinery around it stays generic — rather than
hard-coding one more `matrix` string.

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

**Hot-reloading plugin QML can leave two instances alive.** The old one keeps
answering IPC while the new one paints. Symptom: the IPC reports `false` for a
property you just set to `true`, and the journal shows errors on a line that no
longer exists in the file. Fix: `omarchy restart shell`. `rescanPlugins` is not
always enough.

**`omarchy refresh shell` rewrites `shell.json` wholesale**, and that is where
enabled plugins are recorded. There is no post-refresh hook. Recovery is
`omarchy-matrix doctor`, or re-applying the theme.

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
   in `~/.local/bin`, `/usr/share/plymouth/themes/omarchy-matrix/`, the marker
   block inside `omarchy-menu.jsonc`, `~/.config/omarchy/matrix.json`, the theme
   directory, and the `~/.local/state/omarchy/toggles/screensaver-off` flag.
   Prove it is gone before going on: `omarchy-matrix` must be *command not
   found*. Leave the user's own hooks alone — `theme-set.d` holds more than ours.
2. **Install from the published URL**, never from the working copy, following the
   README literally and doing nothing it does not say. What the README omits, the
   stranger does not know.
3. **Verify the four pieces are on and on screen** — not merely configured.
4. **Toggle each piece off and back on, one at a time**, checking each time that
   the other three did not move.
5. **Switch to another theme and back.** Away: nothing rains, nothing is ticked,
   Omarchy's own lock and screensaver answer again, and nothing of Omarchy's is
   left disabled. Back: exactly what was on before is on again.
6. **Uninstall, and compare the machine against phase 1.** Anything still there
   is a bug, not a detail.

Whatever this turns up belongs in the repo — as a fix, or as a written-down
limitation. Rediscovering it on someone else's machine costs far more.
