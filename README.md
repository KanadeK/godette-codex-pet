# Godette Codex Pet and PetDiff CI

[![CI](https://github.com/KanadeK/godette-codex-pet/actions/workflows/ci.yml/badge.svg)](https://github.com/KanadeK/godette-codex-pet/actions/workflows/ci.yml)
[![Pages](https://github.com/KanadeK/godette-codex-pet/actions/workflows/pages.yml/badge.svg)](https://kanadek.github.io/godette-codex-pet/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![Code: MIT](https://img.shields.io/badge/code-MIT-2f855a)](LICENSE)
[![Art: CC BY 4.0](https://img.shields.io/badge/art-CC%20BY%204.0-3f8f83)](ASSET_LICENSE.md)

Godette is a complete Codex v2 animated pet based on the existing
[Godette / Godot-chan character](https://github.com/godotengine/godot-design/tree/7d12f300c377712028e9af6be01511b3e05a534c/godette).
The repository also ships **PetDiff CI**, a deterministic visual-regression
engine for every Codex v2 pet.

This is not a UI shell. The Python package validates the 8 x 11 atlas contract,
compiles and renders deterministic animation fixtures, performs transactional
install/rollback, builds reproducible release archives, and compares all 74
required cells between two real pet packages. PetDiff writes a machine-readable
JSON report, an offline HTML report, and a highlighted PNG difference sheet.

[中文说明](README.zh-CN.md) | [Live PetDiff Lab](https://kanadek.github.io/godette-codex-pet/)

![Godette breathing and blinking in the Codex idle loop](docs/media/godette-idle.gif)

## Why Godette, and why this project

Godette is an established anime-style personification from the official Godot
design repository, not an invented character. The upstream character sheets are
licensed CC BY 4.0 and the character is directly connected to the widely used
[Godot Engine](https://github.com/godotengine/godot).

The repository was deliberately moved away from session-trace replay as its
main product after a same-day local uniqueness audit found that other pet
projects had begun implementing that feature. The remaining GitHub search gap
was pet-specific visual regression: enforcing an explicit pixel and motion
budget across all v2 atlas cells and producing CI evidence. See
[the research record](docs/RESEARCH.md).

## What works

- A Codex v2 package with a 1536 x 2288 lossless WebP atlas, 74 required cells,
  14 transparent unused cells, nine status rows, and sixteen look directions.
- Strict manifest, geometry, alpha, hidden-RGB, chroma, edge, and size checks.
- PetDiff CI with per-channel tolerance, changed-cell budget, per-cell pixel
  ratio budget, and silhouette-center shift budget.
- Deterministic JSON, HTML, and PNG regression artifacts.
- A reusable composite GitHub Action for any public or private v2 pet repo.
- Strict JSONL animation fixtures and deterministic GIF/WebP rendering.
- Cross-platform ZIP traversal, collision, symlink, and expansion-limit defenses.
- Validate-before-write installation, locking, backup, rollback, recoverable
  uninstall, and actionable diagnosis.
- Byte-reproducible release ZIPs with fixed metadata and per-file SHA-256.
- Dependency-free browser PetDiff Lab with loading, empty, pass, and error
  states.

## Quick start

### Install the tool

```bash
git clone https://github.com/KanadeK/godette-codex-pet.git
cd godette-codex-pet
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

On Windows, skip `source` and use `.\.venv\Scripts\python.exe` instead of
`python` after creating the environment.

### Validate and install Godette

```bash
godette-pet validate pet --strict --json
godette-pet install --source pet --dry-run --json
godette-pet install --source pet --json
godette-pet doctor --source pet --json
```

The default target is `${CODEX_HOME:-$HOME/.codex}/pets/godette`. An existing
Godette package is moved to a timestamped backup before replacement.

### Compare a candidate atlas

Keep a known-good pet directory as the baseline:

```bash
godette-pet diff baselines/godette pet \
  --output-dir dist/petdiff \
  --max-changed-cells 0 \
  --max-cell-change-ratio 0 \
  --max-bbox-shift-px 0 \
  --json
```

Exit code `0` means the candidate satisfies the policy, `1` means the visual
budget was exceeded, and `2` means the inputs or policy were invalid. Open
`dist/petdiff/report.html` to inspect baseline, candidate, and changed pixels.

For an intentional one-cell adjustment:

```bash
godette-pet diff baselines/godette pet \
  --output-dir dist/petdiff \
  --max-changed-cells 1 \
  --max-cell-change-ratio 0.03 \
  --max-bbox-shift-px 2
```

Budgets are explicit. PetDiff never silently approves a changed atlas.

## Use PetDiff in GitHub Actions

```yaml
- uses: actions/checkout@v6
  with:
    fetch-depth: 0

- name: Restore baseline pet
  run: git worktree add ../pet-baseline "${{ github.event.pull_request.base.sha }}"

- name: Compare Codex pet
  uses: KanadeK/godette-codex-pet@v0.1.0
  with:
    baseline: ../pet-baseline/pet
    candidate: pet
    output-dir: petdiff-report
    max-changed-cells: "0"

- uses: actions/upload-artifact@v7
  if: always()
  with:
    name: petdiff-report
    path: petdiff-report
```

See [PetDiff CI reference](docs/PETDIFF.md) for policy design and report fields.

## Animation fixtures

The trace tools remain a small, generic test-fixture layer. They accept strict
JSONL records containing only timing, allow-listed state, optional look
direction, and a short label:

```bash
godette-pet trace-check examples/bugfix-session.jsonl \
  --require-all-states --json
godette-pet plan examples/direction-tour.jsonl \
  --fps 10 --output dist/direction-plan.json
godette-pet render examples/bugfix-session.jsonl \
  --pet-dir pet --output dist/bugfix-session.gif
```

They are intentionally not a Codex log scraper. Prompt text, tool arguments,
paths, account values, and other session secrets are never required.

## Safe removal and recovery

```bash
godette-pet uninstall --dry-run --json
godette-pet uninstall --json
godette-pet rollback --json
godette-pet doctor --source pet --json
```

Uninstall moves the active package into `pet-backups`; it does not delete it.
If a command fails, follow [the repair runbook](docs/REPAIR.md) before removing
any lock or backup manually.

## Developer acceptance gate

```bash
python -m pip install -e ".[dev]"
python -m ruff format --check .
python -m ruff check .
python -m pytest --cov=godette_pet --cov-report=term-missing
node --test web/tests/*.test.mjs
python -m build
python scripts/release_check.py --json
```

The final command validates the real pet, both fixtures, deterministic replay,
self-diff, deterministic packaging, required documentation, and site build. A
non-zero exit is a release blocker.

## Failure repair map

| Failure | Meaning | Safe repair |
| --- | --- | --- |
| `manifest_invalid` | v2 metadata is absent or unsafe | restore `pet/pet.json`, then validate |
| `used_blank` | a required animation cell is empty | repair the named complete row and rebuild |
| `unused_nonblank` | unused standard-row cells contain pixels | clear only unused cells and revalidate |
| `hidden_rgb` or `chroma_residue` | transparency cleanup failed | rerun the approved single despill step |
| PetDiff exit `1` | the candidate exceeded its declared budget | inspect `report.html`; fix or explicitly revise policy |
| `active lock` | an install may still be running | wait; only remove a lock older than 900 seconds |
| install exception | staged validation or replacement failed | run `doctor`; the previous package is restored automatically |
| archive hash mismatch | the build is not reproducible | inspect file timestamps/content and build twice again |

Full commands and evidence to preserve are in [docs/REPAIR.md](docs/REPAIR.md).

## Architecture and security

- [Architecture](docs/ARCHITECTURE.md)
- [PetDiff CI](docs/PETDIFF.md)
- [Trace fixture format](docs/TRACE_FORMAT.md)
- [Security policy](SECURITY.md)
- [Contribution guide](CONTRIBUTING.md)
- [Release process](docs/RELEASE.md)

The installer rejects absolute paths, parent traversal, symlink entries,
portable-name collisions, and oversized archives. It validates before moving
the current package and restores the backup if replacement fails. No command
sends telemetry.

## Licensing and attribution

Code is MIT licensed. Godette reference art and the generated derivative pet art
are CC BY 4.0. Character design credit: Andrea Calabró. Reference sheets come
from the `godotengine/godot-design` repository at commit
`7d12f300c377712028e9af6be01511b3e05a534c`.

Read [ASSET_LICENSE.md](ASSET_LICENSE.md) and [NOTICE.md](NOTICE.md) before
redistributing the artwork. This project is unofficial and is not affiliated
with Godot Engine, the Godot Foundation, OpenAI, or Codex.
