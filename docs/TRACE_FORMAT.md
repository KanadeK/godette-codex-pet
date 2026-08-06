# Animation fixture format

The trace layer is a deterministic test-fixture format. It does not parse raw
Codex logs and does not need prompt or tool content.

Each non-comment JSONL line contains:

```json
{
  "at_ms": 0,
  "state": "idle",
  "duration_ms": 300,
  "direction_deg": null,
  "label": "optional short test label"
}
```

## Fields

- `at_ms`: non-negative integer offset. The first event must start at `0`; later
  offsets must be strictly increasing.
- `state`: one of `idle`, `running-right`, `running-left`, `waving`, `jumping`,
  `failed`, `waiting`, `running`, `review`, or `look`.
- `duration_ms`: positive integer. It is optional except on the final event. If
  provided before another event, it must exactly equal the gap.
- `direction_deg`: finite number required only for `look`. It is quantized to
  the nearest of sixteen 22.5-degree cells.
- `label`: optional string of at most 200 characters.

Unknown fields are rejected. Blank lines and lines beginning with `#` are
ignored.

## Deterministic frame plans

`--fps` must be an integer from 1 to 50 and divide 1000 exactly. This prevents
fractional-millisecond drift. Each plan item names its exact atlas row, column,
duration, semantic state, direction, and label.

```bash
godette-pet trace-check examples/bugfix-session.jsonl --require-all-states
godette-pet trace-check examples/direction-tour.jsonl --require-all-directions
godette-pet plan examples/bugfix-session.jsonl --fps 10 --output plan.json
godette-pet render examples/bugfix-session.jsonl --pet-dir pet --output replay.gif
```

Use synthetic labels. Do not copy secrets, prompts, tool payloads, paths,
emails, account identifiers, or user content into fixtures.
