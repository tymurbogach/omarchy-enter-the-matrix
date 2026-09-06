# Matrix Widget Extraction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the bar-widget plugin (currently `widget/manifest.json` + `widget/Panel.qml` in this repo) into its own standalone public repo, `omarchy-matrix-widget`, so it can be submitted to `plugins.omarchy.org` as a clean, single-manifest-at-root plugin — without changing what an end user gets when they run this repo's existing `install.sh`, and without merging it back into the rain plugin (which would reintroduce the independent-toggle bug this pack already paid to fix once).

**Architecture:** The widget's plugin id, manifest contents, and `Panel.qml` code do not change. What moves is *where the source of truth lives*: a new repo (`omarchy-matrix-widget`) becomes the canonical home, and this repo's `install.sh` fetches it at install time (a persistent, cached git clone under `~/.local/share/omarchy-matrix/`, refreshed on every run) instead of copying from a `widget/` subdirectory it ships itself. A `MATRIX_WIDGET_SRC` environment override lets local development point `install.sh` at an uncommitted local checkout instead of the network, preserving the existing edit → `install.sh` → observe loop from CLAUDE.md's "How to work on this repo" table.

**Tech Stack:** bash (`install.sh`), jq, git, QML (Quickshell plugin, unchanged), `omarchy-plugin-validate`.

**Spec:** No separate spec document — requirements were established via conversation with the repo owner and are captured in the Context section below, cross-checked against this repo's `CLAUDE.md` (the project's own working agreement) and against the real `plugins.omarchy.org` submission process (fetched and confirmed directly: `publish.html`, and the `submit-plugin.yml` GitHub issue template in `omacom/omarchy-plugin-marketplace`).

## Context (why this plan exists)

- `plugins.omarchy.org` submissions are a manually-reviewed GitHub issue (`submit-plugin.yml`), not an automated bot — confirmed by fetching the real template. It asks for a repo URL, category, tags, and a checklist. The convention stated in the publish guide is "valid `manifest.json` in the repository root" — one plugin per repo.
- This repo currently ships **two** plugins with two manifests: `manifest.json` at the root (the rain `service`, id `io.github.tymurbogach.enter-the-matrix`) and `widget/manifest.json` (the bar widget, id `io.github.tymurbogach.enter-the-matrix.widget`). The README already documents that `omarchy plugin add <this repo>` does **not** work correctly today — it installs the whole repo as the rain plugin and silently skips the CLI, hooks, and widget. Marketplace submission of this repo as-is was never viable.
- Per repo-owner decision: only the **widget** goes to the marketplace. The rain plugin and the rest of the pack (CLI, hooks, lock/boot derivation) keep working exactly as they do today, installed via `omarchy theme install` + `install.sh` — untouched by this plan.
- **Non-negotiable constraint, from this repo's own `CLAUDE.md`:** the rain and the widget must stay two separate plugins. `PluginRegistry.setEnabled` treats a `bar-widget`'s "enabled" as "present in `bar.layout`" — folding widget + service into one manifest (`kinds: ["service", "bar-widget"]`) would mean disabling one disables the other, which is the exact bug the two-plugin split was already built to avoid. This plan does not touch that split; it only moves the widget's *source location*.
- **Clean-room constraint, also from `CLAUDE.md`:** the documented verification clones the repo with plain `git clone` (no `--recurse-submodules`). A git submodule for the widget would silently leave an empty directory on that exact command and break `install.sh`. This plan therefore uses an **install-time git clone**, not a submodule.

## File Structure

**New repo — `omarchy-matrix-widget`** (scaffolded locally first, pushed only in Task 6):
```
manifest.json   # moved verbatim from widget/manifest.json (id unchanged)
Panel.qml       # moved verbatim from widget/Panel.qml
LICENSE         # MIT, matching this repo's LICENSE
README.md       # what it is, standalone install/removal, degrade-gracefully note
```

**This repo (`omarchy-enter-the-matrix`) — modified:**
- `provider.json` — `widget.dir` replaced by `widget.repo` + `widget.ref`
- `install.sh` — `stage_plugin` generalized to take an absolute source dir; new `resolve_widget_src` fetches/caches the widget repo (or honors `MATRIX_WIDGET_SRC` for local dev)
- `widget/` — removed once the migration is verified (Task 5)
- `README.md` — one paragraph updated to mention the widget's standalone install path
- `CLAUDE.md` — one new entry under "Traps already paid for" documenting the install-time-clone-not-submodule decision, so it isn't rediscovered

## Global Constraints

- Plugin ids do not change. Only the widget's *source repo* changes; `io.github.tymurbogach.enter-the-matrix.widget` stays the id everywhere (provider.json, manifest.json, install.sh, uninstall.sh already key off provider.json, so no other file needs literal id changes).
- Nothing under `/usr/share/omarchy/` is touched (unrelated to this change, but this repo's global rule).
- No submodules — install-time `git clone`/`git fetch` only, verified against a plain `git clone` of the parent repo.
- `install.sh --sync` (called by `omarchy-matrix doctor`) must keep working without requiring a fresh network fetch every single time it degrades — cache the clone, refresh it, tolerate a failed refresh with a warning rather than aborting `doctor`.
- Tasks 6 and 7 create a public GitHub repo and file a public marketplace submission issue — both are external, hard-to-fully-reverse actions. **Do not execute Task 6 or Task 7 without the repo owner's explicit go-ahead at that point in the conversation**, even though this plan is approved. Tasks 1–5 are local and reversible (a new local git repo, edits to tracked files in this working copy) and proceed under this plan's approval.

---

### Task 1: Scaffold `omarchy-matrix-widget` locally

**Files:**
- Create: `/tmp/claude-1000/-home-cyberdyne-dev-omarchy-enter-the-matrix/663d49df-1776-4091-9247-aef6662f4a39/scratchpad/omarchy-matrix-widget/manifest.json`
- Create: `/tmp/claude-1000/-home-cyberdyne-dev-omarchy-enter-the-matrix/663d49df-1776-4091-9247-aef6662f4a39/scratchpad/omarchy-matrix-widget/Panel.qml`
- Create: `/tmp/claude-1000/-home-cyberdyne-dev-omarchy-enter-the-matrix/663d49df-1776-4091-9247-aef6662f4a39/scratchpad/omarchy-matrix-widget/LICENSE`
- Create: `/tmp/claude-1000/-home-cyberdyne-dev-omarchy-enter-the-matrix/663d49df-1776-4091-9247-aef6662f4a39/scratchpad/omarchy-matrix-widget/README.md`

**Interfaces:**
- Produces: a directory that is byte-identical to today's `widget/manifest.json` and `widget/Panel.qml` for those two files, plus `LICENSE` and `README.md`. Later tasks reference this directory's absolute path as `$WIDGET_SCRATCH`.

- [ ] **Step 1: Copy the two existing files verbatim**

```bash
WIDGET_SCRATCH=/tmp/claude-1000/-home-cyberdyne-dev-omarchy-enter-the-matrix/663d49df-1776-4091-9247-aef6662f4a39/scratchpad/omarchy-matrix-widget
mkdir -p "$WIDGET_SCRATCH"
cp /home/cyberdyne/dev/omarchy-enter-the-matrix/.claude/worktrees/matrix-widget-extraction/widget/manifest.json "$WIDGET_SCRATCH/manifest.json"
cp /home/cyberdyne/dev/omarchy-enter-the-matrix/.claude/worktrees/matrix-widget-extraction/widget/Panel.qml "$WIDGET_SCRATCH/Panel.qml"
```

- [ ] **Step 2: Verify the copies are identical to the originals**

Run: `diff /home/cyberdyne/dev/omarchy-enter-the-matrix/.claude/worktrees/matrix-widget-extraction/widget/manifest.json "$WIDGET_SCRATCH/manifest.json" && diff /home/cyberdyne/dev/omarchy-enter-the-matrix/.claude/worktrees/matrix-widget-extraction/widget/Panel.qml "$WIDGET_SCRATCH/Panel.qml"`
Expected: no output from either `diff` (files identical).

- [ ] **Step 3: Add `LICENSE`**

```
MIT License

Copyright (c) 2026 tymurbogach

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

Write this to `$WIDGET_SCRATCH/LICENSE` (the shader attribution paragraph from the main repo's `LICENSE` is dropped here — this plugin ships no shader code, only `Panel.qml`).

- [ ] **Step 4: Add `README.md`**

```markdown
# Matrix Widget

The bar widget for the [Matrix pack for Omarchy](https://github.com/tymurbogach/omarchy-enter-the-matrix):
one icon on your bar, and a panel with four switches — desktop rain,
screensaver, lock, and boot splash — plus Repair and Uninstall.

This widget owns no state of its own. Every question it asks goes to the
`omarchy-matrix` CLI (`omarchy-matrix status --json`), which is installed by
the main pack. **Installed alone, without the rest of the pack, the icon
appears dimmed and the panel has nothing to report** — that is expected, not
a bug, and is exactly how it behaves today when the pack is stood down for
another theme.

## Install

The normal way is automatic: installing the
[Matrix pack](https://github.com/tymurbogach/omarchy-enter-the-matrix) via its
own `install.sh` fetches this repo and stages it for you. You do not need to
add it separately.

To add just this widget on its own (for development, or if you already have
the rest of the pack installed some other way):

```bash
omarchy plugin add https://github.com/tymurbogach/omarchy-matrix-widget --enable
```

## Remove

```bash
omarchy plugin remove io.github.tymurbogach.enter-the-matrix.widget
```

If you installed the full pack, use its own uninstaller instead
(`omarchy-matrix-uninstall`), which also hands back the lock, screensaver and
boot splash it took over.

## License

MIT.
```

- [ ] **Step 5: Validate the scaffold as a standalone plugin folder**

Run: `omarchy-plugin-validate "$WIDGET_SCRATCH"`
Expected: exit code 0, no output (the validator is silent on success).

---

### Task 2: Generalize `install.sh` and `provider.json` for a fetched widget source

**Files:**
- Modify: `/home/cyberdyne/dev/omarchy-enter-the-matrix/.claude/worktrees/matrix-widget-extraction/provider.json:37-42`
- Modify: `/home/cyberdyne/dev/omarchy-enter-the-matrix/.claude/worktrees/matrix-widget-extraction/install.sh:37` (the `eval "$(jq -r ...)"` line)
- Modify: `/home/cyberdyne/dev/omarchy-enter-the-matrix/.claude/worktrees/matrix-widget-extraction/install.sh:82-120` (`stage_plugin` and its two call sites)

**Interfaces:**
- Consumes: `$WIDGET_SCRATCH` from Task 1 (used only for local-dev testing in Task 3, not referenced by committed code).
- Produces: `resolve_widget_src()` — a shell function with no arguments, prints an absolute directory path to stdout, used by later tasks and by `install.sh` itself. `stage_plugin()` — now `stage_plugin <id> <absolute-src-dir> <file>...` (previously `<id> <source-subdir-relative-to-$HERE> <file>...`).

- [ ] **Step 1: Update `provider.json`'s widget section**

In `provider.json`, replace:

```json
  "widget": {
    "id": "io.github.tymurbogach.enter-the-matrix.widget",
    "dir": "widget",
    "files": ["manifest.json", "Panel.qml"],
    "section": "right"
  },
```

with:

```json
  "widget": {
    "id": "io.github.tymurbogach.enter-the-matrix.widget",
    "//repo": [
      "The widget lives in its own repo so it can be submitted to",
      "plugins.omarchy.org as a single-manifest-at-root plugin (see",
      "docs/superpowers/plans/2026-09-06-matrix-widget-manager-migration.md).",
      "install.sh fetches and caches it; MATRIX_WIDGET_SRC overrides this for",
      "local development against an uncommitted checkout."
    ],
    "repo": "https://github.com/tymurbogach/omarchy-matrix-widget",
    "ref": "main",
    "files": ["manifest.json", "Panel.qml"],
    "section": "right"
  },
```

- [ ] **Step 2: Update the `jq` read in `install.sh` to pick up the new fields**

Replace line 37:

```bash
eval "$(jq -r '@sh "SLUG=\(.slug) DISPLAY_NAME=\(.displayName) CLI=\(.cli) ACCENT=\(.accent) PLUGIN_ID=\(.plugin.id) PLUGIN_SRC=\(.plugin.dir) WIDGET_ID=\(.widget.id) WIDGET_SRC=\(.widget.dir) RAIN_QML=\(.rainFiles[0])"' "$PROVIDER")"
```

with:

```bash
eval "$(jq -r '@sh "SLUG=\(.slug) DISPLAY_NAME=\(.displayName) CLI=\(.cli) ACCENT=\(.accent) PLUGIN_ID=\(.plugin.id) PLUGIN_SRC=\(.plugin.dir) WIDGET_ID=\(.widget.id) WIDGET_REPO=\(.widget.repo) WIDGET_REF=\(.widget.ref) RAIN_QML=\(.rainFiles[0])"' "$PROVIDER")"
```

(`WIDGET_SRC` is gone — it is now resolved at runtime, not read from the provider.)

- [ ] **Step 3: Generalize `stage_plugin` to take an absolute source directory**

Replace the existing function (currently `install.sh:82-110`):

```bash
stage_plugin() { # <id> <source subdir> <file>...
  local id="$1" src="$2" f
  shift 2
  local dest="$PLUGINS_DIR/$id" staging="$PLUGINS_DIR/.$id.staging"

  rm -rf "$staging"
  mkdir -p "$staging"
  for f in "$@"; do
    cp -f "$HERE/$src/$f" "$staging/$f"
  done
```

with:

```bash
stage_plugin() { # <id> <absolute source dir> <file>...
  local id="$1" src="$2" f
  shift 2
  local dest="$PLUGINS_DIR/$id" staging="$PLUGINS_DIR/.$id.staging"

  rm -rf "$staging"
  mkdir -p "$staging"
  for f in "$@"; do
    cp -f "$src/$f" "$staging/$f"
  done
```

(Everything after the `for` loop — validation, the retire/swap dance — is unchanged.)

- [ ] **Step 4: Add `resolve_widget_src`, right before the plugin-staging section**

Insert this function just above the existing `echo "· plugin $PLUGIN_ID"` line (`install.sh:112`):

```bash
# The widget lives in its own repo (see provider.json's "widget" comment). Fetch
# it once into a persistent, non-plugins-dir cache and refresh it on every run,
# rather than re-cloning from scratch every time -- this also runs from
# `omarchy-matrix doctor` (via --sync), which should not need the network to
# notice nothing changed. MATRIX_WIDGET_SRC bypasses all of this for local
# development against an uncommitted checkout of the widget repo.
WIDGET_CLONE="$SHARE_DIR/widget-src"

resolve_widget_src() {
  if [[ -n ${MATRIX_WIDGET_SRC:-} ]]; then
    echo "$MATRIX_WIDGET_SRC"
    return
  fi

  mkdir -p "$SHARE_DIR"
  if [[ -d "$WIDGET_CLONE/.git" ]]; then
    if ! git -C "$WIDGET_CLONE" fetch --depth 1 origin "$WIDGET_REF" >/dev/null 2>&1 ||
       ! git -C "$WIDGET_CLONE" reset --hard FETCH_HEAD >/dev/null 2>&1; then
      echo "  warning: could not refresh $WIDGET_REPO; using the cached copy" >&2
    fi
  else
    rm -rf "$WIDGET_CLONE"
    git clone --depth 1 --branch "$WIDGET_REF" -- "$WIDGET_REPO" "$WIDGET_CLONE" >/dev/null 2>&1 ||
      { echo "  could not clone $WIDGET_REPO" >&2; exit 1; }
  fi
  echo "$WIDGET_CLONE"
}
```

- [ ] **Step 5: Update the two `stage_plugin` call sites**

Replace (`install.sh:112-120`):

```bash
echo "· plugin $PLUGIN_ID"
stage_plugin "$PLUGIN_ID" "$PLUGIN_SRC" "${PLUGIN_FILES[@]}"

# The switchboard on the bar. A plugin of its own rather than another kind on
# the rain: for a `bar-widget`, enabled means present in bar.layout, so folding
# the two together would take the icon off the bar the moment both rain layers
# were switched off.
echo "· bar widget $WIDGET_ID"
stage_plugin "$WIDGET_ID" "$WIDGET_SRC" "${WIDGET_FILES[@]}"
```

with:

```bash
echo "· plugin $PLUGIN_ID"
stage_plugin "$PLUGIN_ID" "$HERE/$PLUGIN_SRC" "${PLUGIN_FILES[@]}"

# The switchboard on the bar. A plugin of its own rather than another kind on
# the rain: for a `bar-widget`, enabled means present in bar.layout, so folding
# the two together would take the icon off the bar the moment both rain layers
# were switched off. Fetched from its own repo -- see resolve_widget_src above.
echo "· bar widget $WIDGET_ID"
WIDGET_SRC_DIR=$(resolve_widget_src)
stage_plugin "$WIDGET_ID" "$WIDGET_SRC_DIR" "${WIDGET_FILES[@]}"
```

- [ ] **Step 6: Syntax-check**

Run: `bash -n install.sh`
Expected: no output, exit code 0.

- [ ] **Step 7: Commit**

```bash
git add provider.json install.sh
git commit -m "$(cat <<'EOF'
Fetch the bar widget from its own repo instead of shipping widget/

Lets the widget be submitted to plugins.omarchy.org as a single-manifest
plugin without merging it into the rain plugin's manifest, which would
reintroduce the independent on/off toggle bug documented in CLAUDE.md
(PluginRegistry treats a bar-widget's "enabled" as "present in bar.layout").
The rain plugin's manifest stays at this repo's root, unaffected.

install.sh caches the fetch under ~/.local/share/omarchy-matrix/widget-src so
`omarchy-matrix doctor` (which runs install.sh --sync) does not need the
network on every run. MATRIX_WIDGET_SRC overrides it for local development.

Widget code itself (Panel.qml, manifest.json) is unchanged; only its source
location moves, in a follow-up commit once the new repo exists.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Verify the fetch-and-stage logic against a local bare repo (no GitHub yet)

This proves `resolve_widget_src` and the updated `stage_plugin` actually work end-to-end, without depending on a GitHub repo that doesn't exist yet (that's Task 6). A local bare repo stands in for `https://github.com/tymurbogach/omarchy-matrix-widget` for this test only.

**Files:**
- No repo files modified. Uses `$WIDGET_SCRATCH` from Task 1 and a new scratch bare repo.

**Interfaces:**
- Consumes: `resolve_widget_src`, `stage_plugin` from Task 2. `$WIDGET_SCRATCH` from Task 1.

- [ ] **Step 1: Build a local bare repo standing in for the GitHub one**

```bash
BARE=/tmp/claude-1000/-home-cyberdyne-dev-omarchy-enter-the-matrix/663d49df-1776-4091-9247-aef6662f4a39/scratchpad/omarchy-matrix-widget.git
rm -rf "$BARE"
git init --bare "$BARE" >/dev/null
git -C "$WIDGET_SCRATCH" init -q -b main
git -C "$WIDGET_SCRATCH" add manifest.json Panel.qml LICENSE README.md
git -C "$WIDGET_SCRATCH" -c user.email=test@test -c user.name=test commit -q -m "initial"
git -C "$WIDGET_SCRATCH" remote add origin "$BARE"
git -C "$WIDGET_SCRATCH" push -q origin main
```

- [ ] **Step 2: Point `install.sh` at the bare repo instead of the real URL, temporarily, and run `--sync`**

```bash
cd /home/cyberdyne/dev/omarchy-enter-the-matrix/.claude/worktrees/matrix-widget-extraction
cp provider.json /tmp/provider.json.bak
jq --arg repo "$BARE" '.widget.repo = $repo' provider.json > /tmp/provider.json.tmp
mv /tmp/provider.json.tmp provider.json
./install.sh --sync
```

Expected: prints `· plugin ...` then `· bar widget io.github.tymurbogach.enter-the-matrix.widget` with no error, exit code 0.

- [ ] **Step 3: Confirm the staged widget matches the scaffold exactly**

Run:
```bash
diff "$WIDGET_SCRATCH/manifest.json" ~/.config/omarchy/plugins/io.github.tymurbogach.enter-the-matrix.widget/manifest.json
diff "$WIDGET_SCRATCH/Panel.qml" ~/.config/omarchy/plugins/io.github.tymurbogach.enter-the-matrix.widget/Panel.qml
omarchy-plugin-validate ~/.config/omarchy/plugins/io.github.tymurbogach.enter-the-matrix.widget
```
Expected: both `diff`s silent, `omarchy-plugin-validate` exits 0.

- [ ] **Step 4: Confirm the cache is reused on a second run (no re-clone)**

```bash
git -C "$SHARE_DIR/widget-src" log -1 --format=%H > /tmp/before.txt 2>/dev/null || \
  git -C ~/.local/share/omarchy-matrix/widget-src log -1 --format=%H > /tmp/before.txt
./install.sh --sync
git -C ~/.local/share/omarchy-matrix/widget-src log -1 --format=%H > /tmp/after.txt
diff /tmp/before.txt /tmp/after.txt
```
Expected: identical commit hash both times (fetch+reset onto the same `main`, not a fresh clone); no error.

- [ ] **Step 5: Confirm `MATRIX_WIDGET_SRC` override bypasses the network entirely**

```bash
mv "$WIDGET_SCRATCH/Panel.qml" /tmp/Panel.qml.orig
echo "// local override marker" >> "$WIDGET_SCRATCH/Panel.qml"
MATRIX_WIDGET_SRC="$WIDGET_SCRATCH" ./install.sh --sync
grep -q "local override marker" ~/.config/omarchy/plugins/io.github.tymurbogach.enter-the-matrix.widget/Panel.qml && echo OVERRIDE_WORKED
mv /tmp/Panel.qml.orig "$WIDGET_SCRATCH/Panel.qml"
```
Expected: prints `OVERRIDE_WORKED`.

- [ ] **Step 6: Restore `provider.json` to the real URL and re-sync**

```bash
mv /tmp/provider.json.bak provider.json
./install.sh --sync
```

This will fail at this point in the plan (the real `omarchy-matrix-widget` repo doesn't exist yet) — that's expected until Task 6. Confirm the failure is the *loud, clear* one from Task 2 Step 4 (`could not clone https://github.com/tymurbogach/omarchy-matrix-widget`), not a silent skip, then leave `provider.json` on the real URL (do not commit a test URL).

- [ ] **Step 7: Screenshot the widget while it was live in Steps 3–5**

Since the widget staged and enabled correctly during this task, capture the two views Rule 2 of `CLAUDE.md` requires before trusting a bar-widget change: the bar icon, and the open panel with its four switches. Use `omarchy-shell` + `grim` the same way the project's existing widget-verification steps do (see `CLAUDE.md`'s clean-room test, phase 3). This confirms the move did not silently zero out `implicitWidth` or otherwise break rendering.

- [ ] **Step 8: No commit for this task** (it only ran local verification; `provider.json` and the plugins directory are already back to their real, unmodified states).

---

### Task 4: Update this repo's docs

**Files:**
- Modify: `/home/cyberdyne/dev/omarchy-enter-the-matrix/.claude/worktrees/matrix-widget-extraction/README.md` (the "pieces" / widget description area)
- Modify: `/home/cyberdyne/dev/omarchy-enter-the-matrix/.claude/worktrees/matrix-widget-extraction/CLAUDE.md` (append one entry under "Traps already paid for")

**Interfaces:**
- None (documentation only).

- [ ] **Step 1: Add one sentence to `README.md`'s widget row**

In the pieces table, the `widget` row currently reads:

```
| `widget` | The Matrix icon on the bar: the four switches above with a ✓ each, plus Repair and Uninstall. |
```

Change it to:

```
| `widget` | The Matrix icon on the bar: the four switches above with a ✓ each, plus Repair and Uninstall. Lives in its own repo, [omarchy-matrix-widget](https://github.com/tymurbogach/omarchy-matrix-widget), fetched automatically by `install.sh` — see that repo if you want to add just the icon on its own. |
```

- [ ] **Step 2: Append a new trap entry to `CLAUDE.md`**

Add this paragraph at the end of the "Traps already paid for" section (after the `omarchy plugin remove` renames paragraph, before "## Before you ship"):

```markdown
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
```

- [ ] **Step 3: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "$(cat <<'EOF'
Document the widget's move to its own repo

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Remove `widget/` and run the cheap checks

**Files:**
- Delete: `/home/cyberdyne/dev/omarchy-enter-the-matrix/.claude/worktrees/matrix-widget-extraction/widget/manifest.json`
- Delete: `/home/cyberdyne/dev/omarchy-enter-the-matrix/.claude/worktrees/matrix-widget-extraction/widget/Panel.qml`

**Interfaces:**
- None.

- [ ] **Step 1: Confirm Task 1's scratch copy still matches before deleting the originals**

Run: `diff /home/cyberdyne/dev/omarchy-enter-the-matrix/.claude/worktrees/matrix-widget-extraction/widget/manifest.json "$WIDGET_SCRATCH/manifest.json" && diff /home/cyberdyne/dev/omarchy-enter-the-matrix/.claude/worktrees/matrix-widget-extraction/widget/Panel.qml "$WIDGET_SCRATCH/Panel.qml"`
Expected: silent (still identical — nobody edited either copy in between).

- [ ] **Step 2: Remove the directory**

```bash
git rm -r widget/
```

- [ ] **Step 3: Run the cheap checks from `CLAUDE.md`'s "Before you ship" section**

```bash
bash -n install.sh uninstall.sh bin/omarchy-matrix hooks/*
python3 -m py_compile bin/*.py *.py rain/*.py
omarchy-plugin-validate .
```
Expected: all exit 0. The last one validates the root `manifest.json` (the rain plugin) — unaffected by this change, but worth reconfirming since `provider.json` changed.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
Remove widget/, now fetched from omarchy-matrix-widget

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6 — EXTERNAL, requires explicit go-ahead before starting: publish the new repo and run the full clean-room test

**Do not start this task until the repo owner explicitly says to.** It creates a new public GitHub repository and pushes to it.

- [ ] **Step 1: Confirm with the repo owner:** exact GitHub org/user and repo name (this plan assumes `tymurbogach/omarchy-matrix-widget`, matching `provider.json`'s already-written URL — confirm before creating anything under a different name, or update `provider.json` first if the name changes).
- [ ] **Step 2: Create the repo** (via `gh repo create` or the GitHub UI) and push the Task 1 scaffold (`$WIDGET_SCRATCH`, with real git history — not the throwaway commit from Task 3's bare-repo test) as its `main` branch.
- [ ] **Step 3: Run the full clean-room test from `CLAUDE.md`'s "Before you ship" section**, all six phases, on a machine that has never seen either repo — paying particular attention to phase 3 (screenshot the bar icon **and** the open panel) and phase 4 (toggle the widget off and back on from the widget itself, confirm the rain plugin's state is untouched, and vice versa — this is the specific behavior this whole migration exists to preserve).
- [ ] **Step 4: Confirm `install.sh` fetches the real repo correctly with no override set** — this is the first time `resolve_widget_src`'s non-override path runs against the real URL; Task 3 only verified it against a local bare-repo stand-in.

---

### Task 7 — EXTERNAL, requires explicit go-ahead before starting: submit to the marketplace

**Do not start this task until the repo owner explicitly says to**, and not before Task 6 is fully verified. Filing this issue is a public action under the owner's own GitHub identity.

- [ ] **Step 1: Confirm the exact category and tags with the repo owner.** Suggested, based on what the widget actually does: category `Widgets`, tags `Bar` and `Quickshell` (the template caps tags at three; a third could be `System`, owner's call).
- [ ] **Step 2: Open the issue** at `https://github.com/omacom/omarchy-plugin-marketplace/issues/new?template=submit-plugin.yml` (confirmed real URL, fetched directly from `plugins.omarchy.org/develop.html`), filling in:
  - Repository URL: `https://github.com/tymurbogach/omarchy-matrix-widget`
  - Category: as confirmed in Step 1
  - Tags: as confirmed in Step 1
  - Maintainer notes: explain that this is the bar-widget half of a larger theme pack, that it degrades to a dimmed icon when the rest of the pack (`omarchy-enter-the-matrix`) isn't installed, and link to the main repo.
  - Checklist: tick only the boxes that are actually true at submission time (repo public with install/removal docs — done in Task 1; license documented — done in Task 1; ownership confirmed — the repo owner's own call; does not overwrite config without consent — true, it only talks to the CLI; approval is listing-only, not a security review — acknowledgment, not a claim).

## Self-Review

- **Spec coverage:** every requirement from the Context section has a task — single-manifest widget repo (Task 1), no submodules / install-time fetch with local-dev override (Task 2), proof the fetch mechanism works before a real repo exists (Task 3), docs so the decision isn't rediscovered (Task 4), clean removal of the now-redundant local copy with the project's own pre-ship checks (Task 5), the two external actions gated behind explicit go-ahead and the exact clean-room verification CLAUDE.md already prescribes (Task 6), and the actual marketplace submission using the real, fetched issue template (Task 7).
- **Placeholder scan:** no TBD/TODO; every step has literal commands or literal file contents; Task 6/7 steps are deliberately checklist-style because they depend on live decisions (repo name, category) that only the owner can make at that time — this is correctly a gated external action, not a placeholder.
- **Type/name consistency:** `WIDGET_ID`, `WIDGET_REPO`, `WIDGET_REF`, `resolve_widget_src`, `stage_plugin`, `WIDGET_CLONE`, `$WIDGET_SCRATCH` are used the same way across every task that references them.
