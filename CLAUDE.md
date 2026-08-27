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

---

## Before you ship

```bash
bash -n install.sh uninstall.sh bin/omarchy-matrix hooks/*
python3 -m py_compile bin/*.py *.py rain/*.py
omarchy-plugin-validate .                  # must pass, or nobody can install it
```

Then install from a clean clone and confirm the four pieces really work — the
menu row renders, the rain animates, `omarchy-shell lock status` still reports
`passwordPam` and `fingerprint`.
