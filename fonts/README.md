# fonts/

`TerminessNerdFont-Regular.ttf` — Terminus, as a scalable TTF.

It is here rather than named as a dependency because `derive-plymouth.py` bakes
the boot splash's text into PNGs at derive time, and derive time is on the
machine of whoever installs the pack. Naming a family instead would mean
`fc-match` resolving it there, and when `fc-match` misses it does not say so --
it hands back `monospace` and the splash comes out in the wrong face with
nothing to warn anyone. A file in the repo cannot miss.

Terminus is what the film's terminals look like: a pixel grid, square
terminals, no rounding. Measured against the alternatives before choosing it --
it has `█` for the progress track, its `-` inks 4.4 % of a full block (the mask
guard wants between 1 % and 60 %), and ten dashes measure exactly as wide as ten
`M`s, so the per-cell crops cannot drift.

Copied **unmodified**, which is what OFL 1.1 permits without renaming: the
licence reserves the names "Terminus Font" and "Terminus (TTF)" for the
originals, so any subsetting or editing done here would have to be renamed
first. `LICENSE.txt` is the licence as shipped with it.

Upstream: Terminus by Dimitar Toshkov Zhekov, the TTF conversion by Tilman
Blumenbach, and the Nerd Fonts patch (which is itself the reason it is called
Terminess rather than Terminus).
