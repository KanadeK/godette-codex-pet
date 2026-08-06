# Release process

## Local gate

Use a clean virtual environment and run:

```bash
python -m pip install -e ".[dev]"
python -m ruff format --check .
python -m ruff check .
python -m pytest --cov=godette_pet --cov-report=term-missing
node --test web/tests/*.test.mjs
python -m build
python scripts/release_check.py --json
```

Run the package step twice and confirm identical SHA-256. Render both example
fixtures and open the resulting animations. Open the extended hatch contact
sheet and direction QA sheet at actual pixel size.

## Source and authorship gate

```bash
git status --short
git diff --check
git log --format=fuller -1
git shortlog -sne HEAD
git log --format=%B | grep -i "Co-authored-by" || true
```

The release commit must use the configured KanadeK noreply identity. No
unintended co-author trailer may be present.

## Online gate

1. Push the exact audited commit.
2. Wait for CI and Pages to complete on that commit.
3. Create annotated tag `v0.1.0`.
4. Build release artifacts from the tagged tree.
5. Publish wheel, sdist, pet ZIP, and `SHA256SUMS.txt`.
6. Download every release asset and verify its hash.
7. Confirm repository visibility, default branch, topics, description, tag,
   Release page, Pages URL, and contributor list.
8. Confirm the public files contain the expected version and provenance.
9. Only then send the completion email.

A local commit, local build, successful push, or green workflow alone is not a
completed public release.
