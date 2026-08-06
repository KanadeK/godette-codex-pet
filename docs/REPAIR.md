# Repair runbook

Preserve the failing command, its JSON output, `report.html`, `diff-sheet.png`,
and any installer backup before changing files.

## Validation failure

Run:

```bash
godette-pet validate pet --strict --json
```

Then repair only the reported scope:

- `manifest_missing` or `manifest_invalid`: restore a UTF-8 `pet.json`, keep
  `spriteVersionNumber: 2`, and use a relative in-directory spritesheet path.
- `atlas_missing` or `atlas_invalid`: restore the release atlas or rebuild it
  from retained hatch QA. Do not resize an 8 x 9 intermediate.
- `used_blank`: regenerate or restore the named complete animation row.
- `unused_nonblank`: clear only cells after each standard row's used count.
- `edge_clipped`: repair the source row with safe padding, then reassemble.
- `hidden_rgb` or `chroma_residue`: rerun the single approved chroma despill
  stage and the v2 validator. Do not repeatedly blur or recolor finished art.
- `size_limit`: encode the unchanged 1536 x 2288 RGBA atlas as lossless WebP.

Re-run strict validation after every repair.

## PetDiff failure

1. Open `report.html`.
2. Confirm which semantic cells changed.
3. Inspect baseline, candidate, and red mask in `diff-sheet.png`.
4. If the change is accidental, restore or repair only the affected complete
   standard row or coherent look row.
5. If intentional, declare the smallest changed-cell, ratio, and bounds budget.
6. Re-run strict comparison before updating the baseline.

Never delete a report and claim the check passed. A policy change belongs in
review alongside the artwork change.

## Installer lock

Run:

```bash
godette-pet doctor --source pet --json
```

If `.godette-pet.lock` is younger than 900 seconds, wait for the active command.
Only after confirming no installation process exists and the lock is older than
900 seconds may it be removed manually.

## Failed install

The installer stages and validates the candidate before replacement. If a later
move or validation fails, it removes the stage and restores the previous target.

1. Do not delete `pet-backups`.
2. Run `doctor`.
3. Validate the source directly.
4. If no active pet remains, run `rollback`.
5. Retry installation from a verified release archive or repository.

```bash
godette-pet validate pet --strict
godette-pet rollback --dry-run --json
godette-pet rollback --json
godette-pet install --source pet --dry-run --json
```

## ZIP safety failure

An archive with absolute paths, `..`, drive prefixes, symlink metadata,
case-insensitive duplicate names, more than 256 entries, a member over 32 MiB,
or more than 64 MiB uncompressed is rejected. Windows device names and alternate
data stream syntax are rejected on every platform. Do not bypass these checks.
Download the official release asset again and verify its SHA-256.

## Reproducibility failure

```bash
godette-pet package --repo-root . --output dist/first.zip --version 0.1.0
godette-pet package --repo-root . --output dist/second.zip --version 0.1.0
```

Compare SHA-256 values. If they differ, inspect archive member order, timestamps,
permissions, compression settings, and generated content. The package builder
fixes metadata; changing source bytes between builds remains a hard failure.

## CI or site failure

Reproduce locally in this order:

```bash
python -m ruff format --check .
python -m ruff check .
python -m pytest --cov=godette_pet --cov-report=term-missing
node --test web/tests/*.test.mjs
python -m build
python scripts/build_site.py --output dist/site
python scripts/release_check.py --json
```

Do not publish from a locally green subset when the full release check or remote
workflow is red.
