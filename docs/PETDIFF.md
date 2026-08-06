# PetDiff CI reference

PetDiff answers one review question: did a candidate Codex v2 pet change more
than the repository explicitly permits?

## Inputs

Both inputs must be complete pet directories containing `pet.json` and the
referenced v2 atlas. Both packages pass the normal atlas validator before any
comparison. A structurally invalid candidate returns exit code `2`; it is not
treated as an ordinary pixel regression.

## Comparison model

PetDiff decodes both atlases to RGBA and visits the 74 cells required by the v2
contract. Unused cells are already enforced by atlas validation.

For each required cell it records:

- decoded baseline and candidate SHA-256;
- count and ratio of changed RGBA pixels;
- count and ratio of changes inside the visible alpha union;
- Euclidean movement of the alpha-bounds center;
- row, column, and semantic state/direction label.

A channel is changed when its absolute decoded difference is greater than
`channel_tolerance`. The default tolerance is zero.

## Policy

| Option | Default | Meaning |
| --- | ---: | --- |
| `--channel-tolerance` | `0` | ignored per-channel difference, 0-255 |
| `--max-changed-cells` | `0` | maximum required cells with any change |
| `--max-cell-change-ratio` | `0` | maximum full-cell changed-pixel ratio |
| `--max-bbox-shift-px` | `0` | maximum visible bounds-center movement |

All limits apply together. A comparison passes only when every limit passes.
This avoids policies where a large silhouette jump is hidden by a small total
pixel percentage.

## Artifacts

`report.json`

- `schema_version`: currently `1`;
- `ok`: final policy decision;
- `baseline` and `candidate`: resolved inputs;
- `policy`: exact values used;
- `summary`: compared/changed cells, changed pixels, worst ratio and shift;
- `violations`: human-readable policy failures;
- `cells`: all 74 cell measurements;
- `artifacts`: absolute report paths.

`report.html`

An offline technical report with pass/fail state, violations, and changed-cell
table. It has no CDN, analytics, font, script, or network dependency.

`diff-sheet.png`

Each row shows baseline, candidate, and red changed-pixel mask for one changed
cell. An identical comparison produces a small image stating that no required
cell changed.

## Intentional changes

Do not raise every budget globally to make a pull request pass. First run strict
comparison and inspect the changed-cell list. Then set the smallest reviewable
budget matching the intended change. Restore strict budgets after the baseline
is deliberately updated.

Example for one small pose correction:

```bash
godette-pet diff baseline/pet candidate/pet \
  --output-dir petdiff-report \
  --max-changed-cells 1 \
  --max-cell-change-ratio 0.02 \
  --max-bbox-shift-px 1
```

## GitHub Action outputs

The root `action.yml` exposes `report-json`, `report-html`, and `diff-sheet`.
Upload the entire output directory with `actions/upload-artifact@v7` under
`if: always()` so failed comparisons retain their evidence.

## Exit codes

- `0`: valid inputs, policy passed;
- `1`: valid inputs, policy failed;
- `2`: invalid pet, invalid policy, unsafe source, or other request error.
