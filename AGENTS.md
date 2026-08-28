# AGENTS.md

**The working agreement for this repo lives in [`CLAUDE.md`](CLAUDE.md). Read it
before changing anything.**

This file is deliberately a pointer and not a copy. Two copies of the same rules
drift apart in silence, and the one you happened to read is never the one that
was updated. `CLAUDE.md` is the single source.

It cannot be a symlink either: `omarchy plugin validate` refuses symlinks
anywhere inside a plugin folder, so a linked `AGENTS.md` would make the pack
impossible to install.

---

What follows is the short version — enough that an agent reading only this file
does not do damage. Everything below is expanded in `CLAUDE.md`, along with a
list of traps that each cost real debugging time and are invisible from the code.

**Omarchy is the source of truth, and it moves.** Invoke the `/omarchy` skill
before touching config. Read `/usr/share/omarchy/` instead of guessing — it is
readable and it is right there. Never edit anything inside it.

**A request to review is not a request to change.** "Have a look at X", "why does
Y happen" means investigate and *report*. Propose the fix and wait. If it looks
obvious and one line long, it is still not yours.

**Verify what you changed, not what you were thinking about.** Check the artefact
as the user sees it. Testing that a menu action launches the right program is not
testing that the menu row renders. If you cannot verify something from here, say
so rather than assume.

**Additive only. Derive, never freeze.** Two pieces genuinely cannot be done
another way — the lock and the boot splash — and both are derived from the source
on the machine, abort when their anchor no longer matches, and are re-derived
after every `omarchy update`. If a new feature seems to need a frozen copy of
Omarchy code, that is the signal to keep looking for the extension point.

**Never leave the machine unable to lock or boot.** Hand the lock back with
`omarchy plugin remove <clone>`, never by disabling it — that leaves zero locks
enabled. Test with `omarchy-shell lock preview`, never by locking. On an
encrypted disk Plymouth is also the passphrase prompt.

**Everything is a layer. Off must mean gone.** Each of the four pieces —
wallpaper, screensaver, lock, boot — switches on its own, with no side effect on
the other three. Picking another theme stands them all down. And `off` must
*remove* what a piece wrote, including outside `$HOME`: it is not enough for
`uninstall.sh` to clean up, because most people never uninstall.

**Screenshot the lock, never trust its status.** Swapping the lock plugin leaves
both loaded and Quickshell picks which one paints. Every status check passed
while the machine locked to Omarchy's blurred wallpaper; `grim` over
`omarchy-shell lock preview` was the only thing that caught it.

**Before publishing, run the clean-room test.** Strip the machine, install from
the published URL the way a stranger does, verify the four pieces on screen,
toggle each one alone, switch theme away and back, uninstall and compare against
the stripped state. `bash -n` and `omarchy-plugin-validate` are the cheap part,
not the test. The six phases are in `CLAUDE.md`.

**Where this is heading:** one bar widget (`kinds: ["bar-widget", "service"]`
plus a `panel`) owning the four switches, instead of a block spliced into the
user's `omarchy-menu.jsonc` under Style — and the machinery kept generic, with
matrix as one provider of the set rather than a hard-coded string.

**English, and commit messages that explain the why.** The repo is public. `git
diff` already says what changed.

Before shipping:

```bash
bash -n install.sh uninstall.sh bin/omarchy-matrix hooks/*
python3 -m py_compile bin/*.py *.py rain/*.py
omarchy-plugin-validate .
```

And then the clean-room test above, which is the one that decides it.
