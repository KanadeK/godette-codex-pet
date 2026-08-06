# Contributing

## Before opening a pull request

1. Explain the user-visible problem.
2. Add or update tests for the behavior and failure path.
3. Keep installer changes validate-first and backup-preserving.
4. Keep PetDiff budgets explicit and serialized into reports.
5. Do not add raw Codex logs, prompts, tool payloads, user paths, or account
   identifiers to fixtures.
6. Do not replace generated art without provenance and the complete hatch-pet
   QA evidence.

Run:

```bash
python -m pip install -e ".[dev]"
python -m ruff format .
python -m ruff check .
python -m pytest --cov=godette_pet --cov-report=term-missing
node --test web/tests/*.test.mjs
python scripts/release_check.py --json
```

Coverage must remain at least 90 percent. New commands need exit-code tests and
actionable repair output.

## Artwork

Godette derivative artwork is CC BY 4.0. Preserve attribution, reference hashes,
and QA artifacts. Standard-row repairs replace a complete row; look repairs
replace one complete coherent look row. Do not paste an isolated generated cell
into the final atlas.

## Commit hygiene

Use focused commits and describe why a policy or safety invariant changed. Do
not add `Co-authored-by` trailers unless every named person actually authored
the contribution and has agreed to the attribution.
