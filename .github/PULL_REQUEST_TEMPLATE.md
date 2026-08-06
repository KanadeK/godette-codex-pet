## Problem

Describe the user-visible or maintenance problem.

## Change

Describe the smallest implemented solution.

## Evidence

- [ ] `python -m ruff format --check .`
- [ ] `python -m ruff check .`
- [ ] `python -m pytest --cov=godette_pet --cov-report=term-missing`
- [ ] `node --test web/tests/*.test.mjs`
- [ ] `python scripts/release_check.py --json` when production assets changed

Attach PetDiff JSON/HTML/PNG evidence for atlas changes. Do not attach private
Codex session content.

## Safety and licensing

- [ ] Installer behavior remains validate-first and backup-preserving.
- [ ] Artwork sources, license, modifications, and attribution are recorded.
- [ ] No unexpected generated, private, or account-specific files are included.
