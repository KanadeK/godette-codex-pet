# Architecture

## Product boundary

The repository ships two connected but independently testable products:

1. a complete Codex v2 Godette pet package;
2. PetDiff CI, a generic visual-regression engine for Codex v2 pets.

The browser lab demonstrates the same comparison rules, but the Python CLI is
the release authority. A web result can never override a failed CLI report.

## Python layers

`godette_pet.contract`

- Owns the 192 x 208 cell, 8 x 11 atlas, nine standard rows, sixteen look
  directions, timing table, and 74-cell used set (including the neutral fallback).
- Has no file-system or Pillow dependency.

`godette_pet.atlas`

- Loads `pet.json` and the referenced atlas.
- Rejects path escape, wrong v2 metadata, wrong dimensions/mode, blank required
  cells, nonblank unused cells, hidden RGB, opaque chroma, and oversize output.
- Emits a repair string with every finding.

`godette_pet.diff`

- Validates both inputs before comparing them.
- Compares decoded RGBA pixels for every required cell.
- Computes all-pixel and visible-pixel change ratios plus alpha-bounds center
  movement.
- Writes `report.json`, `report.html`, and `diff-sheet.png`.
- Applies only caller-declared budgets. Defaults are strict identity.

`godette_pet.trace` and `godette_pet.render`

- Define synthetic state fixtures, not a Codex log ingestion product.
- Compile integer-millisecond frame plans with no clock drift.
- Render deterministic GIF and lossless WebP evidence from real atlas cells.

`godette_pet.install`

- Resolves every path before mutation.
- Rejects ZIP traversal, absolute entries, and symlink metadata.
- Validates source and stage before replacement.
- Uses an exclusive lock, preserves the old pet as a backup, and restores it
  after a failed replacement.

`godette_pet.package`

- Requires all release-critical files.
- Stores fixed timestamps, permissions, ordering, compression settings, and a
  per-file SHA-256 manifest.

`godette_pet.cli`

- Maps commands to the layers above and preserves exit-code semantics:
  `0` pass, `1` valid comparison/check that fails policy, `2` invalid request.

## Static web layers

`web/petdiff-core.mjs` is a DOM-free implementation of required-cell comparison
and has Node tests. `web/app.mjs` handles browser decoding, upload, status,
canvas rendering, and accessible controls. `scripts/build_site.py` copies only
the static sources and validated production assets into a deterministic output
directory.

## Data flow

```text
baseline pet ─┐
              ├─ validate ─ decode RGBA ─ compare 74 cells ─ apply policy
candidate pet ┘                                              │
                                                             ├─ report.json
                                                             ├─ report.html
                                                             └─ diff-sheet.png
```

No network request or telemetry is needed after installation. PetDiff never
reads Codex messages, prompts, tool payloads, account identifiers, or workspace
files outside the two pet directories and its output directory.

## Mutation invariants

- Validation precedes install, replacement, packaging, rendering, and diff.
- A dry run does not create a backup directory or lock.
- Uninstall is a move to backup, not deletion.
- Rollback validates the backup before moving the active package.
- Output ZIP metadata is fixed and source files are sorted.
- PetDiff policy is serialized into the report so a reviewer can reproduce the
  exact decision.
