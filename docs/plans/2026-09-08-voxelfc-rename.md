# VOXEL FC Rename Implementation Plan

> **For Hermes:** Use the `subagent-driven-development` skill to implement this plan task-by-task. Do not begin implementation until the existing local changes are checkpointed or explicitly excluded by Fabiano.

**Goal:** Replace the public and technical identity `SuperTranscriptFC` with `VOXEL FC` / `voxelfc`, including the Python package, CLI, persistent configuration, scripts, documentation, tests, local installation paths, and the GitHub repository, without breaking existing transcript files or installed machines.

**Architecture:** `VOXEL FC` is the human-facing product name and means “VOXEL — File Companion”. `voxelfc` is the canonical lowercase technical identifier for the Python distribution, import package, CLI, repository, environment variable, and new state directory. Existing `.transcriptFC.txt`, `.transcriptFC.srt`, `.transcriptFC.vtt`, and `.transcriptFC.lock` files remain the stable Dropbox data contract in the first migration; changing those extensions is a separate, explicit migration and must not be hidden inside a code rename.

**Tech Stack:** Python 3.10+, setuptools/PEP 621, pytest, Dropbox SDK, faster-whisper, pyannote.audio, Bash, Windows batch/PowerShell, GitHub CLI.

---

## 1. Current state and findings

### Repository and working tree

- Local repository: `/home/fcastell/DropboxMainFC@Leno18/_2026Products/2026-09 SuperTranscriptFC`
- Current branch: `main`, tracking `origin/main`.
- Current remote: `https://github.com/fabianocastello/supertranscriptfc.git`.
- GitHub repository: public, default branch `main`, no existing `.github/` workflow files, no topics.
- `fabianocastello/voxelfc` was checked and is not currently present, so the desired GitHub name appears available for this owner.
- The working tree is **not clean** before this rename:
  - `quickInstall.md` is modified locally.
  - `tools/` contains untracked operational scripts and generated audit reports.
- These changes must be reviewed and checkpointed separately before implementation. The rename must not overwrite, stage, or discard them implicitly.

### Existing technical identity to change

| Layer | Current | Target |
|---|---|---|
| Human brand | `SuperTranscriptFC` | `VOXEL FC` |
| Product description | implicit | `VOXEL — File Companion` |
| Distribution | `supertranscriptfc` | `voxelfc` |
| Python package | `src/supertranscriptfc` | `src/voxelfc` |
| Python imports | `from supertranscriptfc...` | `from voxelfc...` |
| CLI | `supertranscriptfc` | `voxelfc` |
| Compatibility CLI | absent | `supertranscriptfc` alias, deprecated |
| Config environment variable | `SUPERTRANSCRIPTFC_HOME` | `VOXELFC_HOME` |
| Default state directory | `~/.supertranscriptfc` | `~/.voxelfc` for new installs |
| Git ignore entry | `.supertranscriptfc/` | `.voxelfc/` plus legacy entry during transition |
| Logger name/file | `supertranscriptfc` / `supertranscriptfc.log` | `voxelfc` / `voxelfc.log` |
| GitHub repository | `supertranscriptfc` | `voxelfc` |
| GitHub URL | `/fabianocastello/supertranscriptfc` | `/fabianocastello/voxelfc` |
| Transcript output suffix | `.transcriptFC.*` | **keep unchanged in phase 1** |
| Existing transcript front matter | old historical values | **do not rewrite existing files** |
| New transcript front matter | `system: "SuperTranscriptFC"` | `system: "VOXEL FC"` |

### Why `VOXEL FC` is a good name, with caveats

- `VOXEL` is short, memorable, pronounceable, and visually strong. `FC` gives the name a project-specific differentiator and can be explained as **File Companion**.
- `VOXEL` is not a natural acronym. Do not force an awkward backronym merely to make every letter stand for a word; use the brand plus the descriptor instead: **VOXEL FC — File Companion for audio intelligence**.
- “Voxel” is an established technical term (a volumetric pixel) and is already used by software companies, libraries, and trademarks. This is not a blocker for an internal/open-source project, but it means the name is not globally unique and should not be treated as legally cleared.
- The more distinctive technical/public handle is `voxelfc`, which was not found as the owner’s GitHub repository during this audit. Before commercial launch, separately check domain, package-index, social-handle, and trademark availability.

---

## 2. Compatibility policy

Adopt this policy before editing code:

1. **Canonical new identity:** `VOXEL FC` in user-facing text; `voxelfc` in code and URLs.
2. **CLI compatibility:** publish both entry points for one deprecation cycle:
   - `voxelfc` is documented and canonical.
   - `supertranscriptfc` invokes the same `voxelfc.cli:main` and prints/logs a deprecation warning.
3. **Environment compatibility:** prefer `VOXELFC_HOME`; accept `SUPERTRANSCRIPTFC_HOME` as a legacy fallback with a warning.
4. **State compatibility:** new installations default to `~/.voxelfc`; if an existing `~/.supertranscriptfc` exists and no explicit home is configured, use it with a migration warning rather than downloading models again or losing `processed_files.json`.
5. **Output compatibility:** retain `.transcriptFC.txt`, `.transcriptFC.srt`, `.transcriptFC.vtt`, and `.transcriptFC.lock` so Dropbox monitors recognize historical and current files. Do not bulk-rename Dropbox outputs in this project rename.
6. **Metadata compatibility:** new output writes identify the system as `VOXEL FC`; historical transcript files remain untouched. Readers/auditors must tolerate old front matter.
7. **Removal timing:** remove the old CLI/env compatibility only in a separately announced breaking release after all machines and scripts have migrated.

This policy prevents the most dangerous failure mode: a name change that causes all existing audio to be reprocessed or makes the folder monitor fail to recognize completed work.

---

# Implementation phases

## Phase 0 — Checkpoint and baseline

### Task 0.1: Protect the current local work

**Files:** no project files; Git metadata only.

1. Inspect the current diff:

```bash
git status --short --untracked-files=all
git diff -- quickInstall.md
gn=$(git ls-files --others --exclude-standard tools | wc -l)
printf 'untracked tools files: %s\n' "$gn"
```

2. Decide explicitly whether the modified `quickInstall.md` and each untracked `tools/` file are:
   - included in the rename branch;
   - committed separately first; or
   - intentionally excluded from the rename.
3. Never use `git add .` during this work. Stage reviewed paths only.
4. Create a dedicated branch from the chosen clean/checkpointed base:

```bash
git switch -c rename/voxelfc
```

The branch isolates the rename so `main` remains stable and makes rollback a branch reset rather than a partial manual reverse rename.

### Task 0.2: Run the baseline test and syntax gate

The project virtual environment currently has Python 3.12.3 and pytest 9.1.1. Run before editing:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q src tests
```

Expected baseline: all existing tests pass and compilation exits 0. Record the result in the implementation commit/PR notes. If the project venv is absent on another machine, create it with `python3 -m venv .venv` and install the project test dependencies before proceeding.

---

## Phase 1 — Rename the Python package and project metadata

### Task 1.1: Move the import package

**Files:**
- Rename: `src/supertranscriptfc/` → `src/voxelfc/`
- Modify: all Python imports in `tests/` and package modules.

Use a filesystem-aware Git rename:

```bash
git mv src/supertranscriptfc src/voxelfc
```

Update every internal import from `supertranscriptfc` to `voxelfc`. Do not change the `.transcriptFC` output suffixes.

Verification:

```bash
.venv/bin/python -c 'import voxelfc; print(voxelfc.__version__)'
.venv/bin/python -m pytest -q
```

### Task 1.2: Change distribution and console entry points

**File:** `pyproject.toml`

Change:

```toml
name = "supertranscriptfc"

[project.scripts]
supertranscriptfc = "supertranscriptfc.cli:main"
```

to:

```toml
name = "voxelfc"

[project.scripts]
voxelfc = "voxelfc.cli:main"
supertranscriptfc = "voxelfc.cli:main"
```

The second entry point is intentional compatibility and must be documented as deprecated. Update the package description to mention VOXEL FC / File Companion.

Verification:

```bash
.venv/bin/python -m pip install -e '.[dropbox,transcribe,diarize]'
.venv/bin/voxelfc --help
.venv/bin/supertranscriptfc --help
```

Both commands must resolve to the same parser and exit successfully without requiring Dropbox or Hugging Face credentials.

### Task 1.3: Rename runtime identity and generated metadata

**Files:**
- `src/voxelfc/cli.py`
- `src/voxelfc/config.py`
- `src/voxelfc/logging_setup.py`
- `src/voxelfc/pipeline.py`
- `src/voxelfc/diarize.py`
- `src/voxelfc/dropbox_client.py`
- `src/voxelfc/transcribe.py`
- `src/voxelfc/outputs.py` if needed by metadata tests
- corresponding tests.

Required behavior:

- CLI `prog` becomes `voxelfc`.
- New user-facing product text becomes `VOXEL FC`.
- Logger name becomes `voxelfc`.
- New log filename becomes `voxelfc.log`.
- New transcript front matter writes `system: "VOXEL FC"`.
- Historical `.transcriptFC.*` filenames and lock detection remain unchanged.
- Avoid changing job IDs, Dropbox paths, output stem naming, or processing stages merely because the brand changed.

Update tests that assert the system front matter. Add a test proving output filenames still use `.transcriptFC.txt/.srt/.vtt`.

---

## Phase 2 — Persistent home and migration-safe configuration

### Task 2.1: Implement canonical and legacy home resolution

**File:** `src/voxelfc/config.py`

Implement a small, testable resolver with this precedence:

1. `VOXELFC_HOME`, if set;
2. `SUPERTRANSCRIPTFC_HOME`, if set, with a deprecation warning;
3. `~/.voxelfc`, if it already exists;
4. `~/.supertranscriptfc`, if it exists, with a migration warning;
5. new default `~/.voxelfc`.

Do not silently use both directories. If both default directories exist and neither variable is set, prefer `~/.voxelfc` and log a clear warning instructing the operator to choose one explicitly and verify state before deleting anything.

The resolver must continue to preserve:

- `tmp/` and `progress.json`;
- `models/` and Hugging Face/Torch cache locations;
- `logs/`;
- `processed_files.json`.

### Task 2.2: Add an explicit state migration utility

**Files:**
- Create: `scripts/migrate_home.py`
- Modify: `README.md` and `quickInstall.md`.

The utility should be safe by default:

```bash
python scripts/migrate_home.py \
  --from ~/.supertranscriptfc \
  --to ~/.voxelfc \
  --dry-run
```

It must:

- refuse to operate if source and destination are the same;
- show the source/destination and estimated contents without secrets;
- support an explicit non-dry-run mode only after the operator stops `voxelfc`/legacy processes;
- preserve file metadata where possible;
- avoid deleting the source by default;
- verify `processed_files.json`, model cache directories, and file counts after copying;
- provide a rollback instruction: point `VOXELFC_HOME` back to the source directory.

Do not copy model caches automatically during a normal installation; the cache can be approximately 20 GB and should be migrated deliberately per machine.

### Task 2.3: Test configuration compatibility

**File:** `tests/test_config.py` (create)

Cover at least:

- explicit `VOXELFC_HOME` wins;
- legacy `SUPERTRANSCRIPTFC_HOME` works;
- existing legacy default is used when no explicit variable exists;
- new installations resolve to `~/.voxelfc`;
- both directories present produces the documented deterministic behavior;
- environment variables are not printed or written to logs.

Run:

```bash
.venv/bin/python -m pytest tests/test_config.py -q
```

---

## Phase 3 — Update installers, updaters, and operational scripts

### Task 3.1: Update Linux/macOS and Windows installers

**Files:**
- `scripts/install.sh`
- `scripts/install.ps1`
- `scripts/install.bat`
- `scripts/install-legacy.bat`

Change user-facing branding, state-directory examples, and executable commands to `VOXEL FC`, `~/.voxelfc`, and `voxelfc`.

Preserve `.env` when it exists. Update installation messages to say that existing `~/.supertranscriptfc` state is detected and not deleted. The scripts must install the new distribution and create the deprecated alias through `pyproject.toml`.

Verification is static and shell-level:

```bash
bash -n scripts/install.sh scripts/update.sh scripts/monitor_folders.sh
.venv/bin/python -m py_compile scripts/dropbox_oauth.py
```

Windows scripts must be reviewed for `%USERPROFILE%\\.voxelfc`, `$HOME\\.voxelfc`, quoting, and the correct new executable.

### Task 3.2: Update update wrappers and folder monitor

**Files:**
- `scripts/update.sh`
- `scripts/update.bat`
- `scripts/update-nogit.bat`
- `scripts/monitor_folders.sh`

Required changes:

- invoke `voxelfc` canonically;
- keep comments/documentation explaining the old alias only as a deprecation fallback;
- change the no-Git ZIP URL to `https://github.com/fabianocastello/voxelfc/archive/refs/heads/main.zip`;
- change temporary ZIP/extraction names to `voxelfc_*`;
- keep monitor completion detection based on `.transcriptFC.txt`;
- do not alter Dropbox folder paths or the `--source`/`--dest` contract.

Add a shell smoke test or a documented manual check that mocks the CLI path and proves `monitor_folders.sh` calls the canonical command without accessing Dropbox.

### Task 3.3: Update operational tools without staging user-generated reports

**Files:**
- `tools/audit.py`
- `tools/status.py`
- `tools/remove_locks.py`
- `tools/dropbox_lock_utils.py`
- generated `tools/*.md` reports.

Review the currently untracked tools before editing. Update code-owned headings and product labels to `VOXEL FC`, but do not rewrite historical generated reports unless explicitly requested. Keep references to `.transcriptFC.*` because they describe the actual Dropbox contract.

The rename branch must stage only reviewed Python tools, not timestamped reports containing historical snapshots, unless Fabiano chooses otherwise.

---

## Phase 4 — Documentation, examples, ignore rules, and tests

### Task 4.1: Rewrite README and quick-install documentation

**Files:**
- `README.md`
- `quickInstall.md`
- `.env.example`
- `SCRATCH_SUPER.txt` if intentionally retained; otherwise leave ignored/untracked and do not publish it.

Update:

- title and product description to `VOXEL FC — File Companion`;
- clone URLs and local directories to `voxelfc`;
- commands to `voxelfc`;
- state/cache examples to `~/.voxelfc`;
- the compatibility section explaining `supertranscriptfc`, `SUPERTRANSCRIPTFC_HOME`, and existing state;
- the explicit statement that `.transcriptFC.*` output names remain stable;
- migration commands and rollback procedure;
- security guidance for `.env`, tokens, and logs.

Do not claim that old Dropbox files were renamed; they were not.

### Task 4.2: Update environment and ignore rules

**Files:**
- `.env.example`
- `.gitignore`

Use:

```dotenv
# Directory for temporary files and state (default: ~/.voxelfc)
VOXELFC_HOME=

# Legacy accepted during migration: SUPERTRANSCRIPTFC_HOME
```

Keep `.supertranscriptfc/` in `.gitignore` during the compatibility window and add `.voxelfc/`. This avoids accidentally exposing old state if an operator runs the new code against a repository containing legacy local artifacts.

### Task 4.3: Rename/update tests and add regression coverage

**Files:**
- `tests/test_merge.py`
- `tests/test_naming.py`
- `tests/test_outputs.py`
- `tests/test_state.py`
- create/update CLI and config tests as needed.

Replace imports with `voxelfc`. Keep the expected stable output suffixes and add regression coverage for:

- `voxelfc --help` and deprecated `supertranscriptfc --help`;
- new front matter `VOXEL FC`;
- old transcript front matter remains readable if a parser/reader consumes it;
- `.transcriptFC.lock` detection remains operational;
- home resolution and legacy state fallback;
- no accidental job-ID or output-stem changes.

Run the full suite:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q src tests tools
```

---

## Phase 5 — Local packaging and machine rollout verification

### Task 5.1: Verify a clean editable installation

Use a temporary venv or a disposable clean checkout, not only the existing editable environment:

```bash
python3 -m venv /tmp/voxelfc-verify-venv
/tmp/voxelfc-verify-venv/bin/python -m pip install --upgrade pip
/tmp/voxelfc-verify-venv/bin/python -m pip install -e .
/tmp/voxelfc-verify-venv/bin/voxelfc --help
/tmp/voxelfc-verify-venv/bin/supertranscriptfc --help
/tmp/voxelfc-verify-venv/bin/python -c 'import voxelfc; print(voxelfc.__version__)'
```

The old package import `supertranscriptfc` should no longer be required internally. If external compatibility imports are intentionally needed, add a deliberate shim and tests rather than leaving a half-renamed package directory.

### Task 5.2: Run a local audio smoke test

With credentials and real audio available, process a short local file using the new command:

```bash
voxelfc --source /caminho/audio_curto.mp3 --local \
  --model-size small --language pt
```

Verify:

- command exits 0;
- output files are generated with the unchanged `.transcriptFC.*` suffixes;
- front matter says `VOXEL FC`;
- state is stored in the selected home directory;
- the log is `voxelfc.log`;
- no token appears in console output, logs, or generated transcript.

Then run the same short input through `supertranscriptfc` and confirm it reaches the same code path. Do not use a production Dropbox folder for the first smoke test.

### Task 5.3: Roll out per machine

For each Linux/macOS/Windows machine (`thor25`, `leno18`, `MacBook Air M1`, `ps20`):

1. stop the monitor/worker;
2. update the checkout and install the new package;
3. choose either the legacy state path fallback or an explicit `migrate_home.py` run;
4. verify model cache and `processed_files.json` before processing;
5. run `voxelfc --help` and one short local test;
6. restart the monitor using the new script;
7. verify that an already completed Dropbox item is skipped based on `.transcriptFC.txt`;
8. verify that one new item produces `VOXEL FC` metadata and stable output suffixes.

Do not remove `~/.supertranscriptfc` until every machine has been verified and the rollback window has expired.

---

## Phase 6 — GitHub repository rename and remote verification

Perform this only after the code branch is tested and committed, and only with explicit authorization because it changes a remote resource.

### Task 6.1: Commit the local rename before changing GitHub

Before each commit:

```bash
git status --short
git diff --check
git diff --stat
git diff --cached --stat
```

Stage exact reviewed paths, never `git add .`. Use coherent commits, for example:

```bash
git add pyproject.toml src/voxelfc tests
 git commit -m "refactor: rename package and cli to voxelfc"

git add scripts .env.example .gitignore README.md quickInstall.md
 git commit -m "docs: migrate installers and documentation to VOXEL FC"
```

If the operational `tools/` files are included, commit them separately from generated reports. Explain each Git operation at the time it happens.

### Task 6.2: Rename the remote repository

Preflight:

```bash
gh auth status
gh repo view fabianocastello/supertranscriptfc --json nameWithOwner,url,defaultBranchRef
# Confirm the desired name is not already owned by this account:
gh repo view fabianocastello/voxelfc --json nameWithOwner,url
```

The second command is expected to fail before the rename if the name is available.

Rename:

```bash
gh repo rename voxelfc -R fabianocastello/supertranscriptfc -y
git remote set-url origin https://github.com/fabianocastello/voxelfc.git
```

Verify the remote side effect by reading it back:

```bash
gh repo view fabianocastello/voxelfc --json nameWithOwner,url,defaultBranchRef
 git remote -v
git ls-remote origin HEAD
```

GitHub normally redirects the old repository URL and Git transport location, but all documentation and local remotes must still be updated to the new canonical URL. Check the old URL with a header request and record the result; do not rely only on a local `git remote` update.

### Task 6.3: Push and verify the final branch

Push the tested branch and merge through the project’s chosen policy:

```bash
git push -u origin rename/voxelfc
```

After merge to `main`, verify:

```bash
git fetch origin --prune
git status --short --branch
git log -5 --oneline --decorate
gh repo view fabianocastello/voxelfc --json nameWithOwner,url,defaultBranchRef
```

The final tree must be clean and `origin/main` must point to the merged rename commits.

---

## Phase 7 — Cleanup after the deprecation window

Only after every known machine and automation has migrated:

1. remove the `supertranscriptfc` console alias;
2. stop accepting `SUPERTRANSCRIPTFC_HOME`, or retain it only if operationally justified;
3. remove `.supertranscriptfc/` from `.gitignore` only after confirming no local state is tracked or at risk;
4. delete the old state directories only after independent backups/checksums and a successful rollback window;
5. update the README with the breaking-release note;
6. search the complete repository and operational notes for remaining old-name references.

Final search gate:

```bash
git grep -n -i -E 'supertranscriptfc|SuperTranscriptFC|SUPERTRANSCRIPTFC' -- . ':(exclude).git' || true
```

Any remaining match must be classified as one of:

- intentional compatibility alias/documentation;
- historical report that must remain immutable;
- migration code/warning;
- accidental stale reference that must be removed.

---

# Acceptance criteria

- [ ] `VOXEL FC — File Companion` is the documented product identity.
- [ ] `voxelfc` is the canonical package, import path, CLI, state variable, and GitHub repository name.
- [ ] `voxelfc --help` works in a clean environment.
- [ ] Deprecated `supertranscriptfc --help` still works during the compatibility window.
- [ ] Existing `~/.supertranscriptfc` state is not lost or silently ignored on upgrade.
- [ ] New installs use `~/.voxelfc`.
- [ ] Existing `.transcriptFC.txt/.srt/.vtt/.lock` files remain recognized.
- [ ] New transcript metadata identifies `VOXEL FC`; historical files are not rewritten.
- [ ] Installers, update wrappers, folder monitor, no-Git ZIP URL, and docs use the new canonical name.
- [ ] Current uncommitted/untracked work was explicitly checkpointed and not discarded.
- [ ] Full tests, compilation, packaging smoke test, and one local audio smoke test pass.
- [ ] GitHub repository rename was verified with `gh repo view`, `git remote -v`, and `git ls-remote`.
- [ ] Final Git tree is clean; no secrets, `.env`, model caches, generated reports, or runtime artifacts were staged.

# Rollback

If a machine fails after the rename:

1. stop its worker/monitor;
2. check out the last known-good commit or use the old branch/tag;
3. run the old command or the compatibility alias;
4. set `SUPERTRANSCRIPTFC_HOME` or `VOXELFC_HOME` explicitly to the verified state directory;
5. do not delete either state directory or Dropbox outputs;
6. use the old GitHub URL only as a temporary redirect if necessary, then restore the new `origin` URL after diagnosis.

The repository rename itself is reversible with `gh repo rename supertranscriptfc`, but it should not be used as the first response to a runtime problem; code/state compatibility is the safer rollback boundary.
