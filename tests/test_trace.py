from __future__ import annotations

import json

import pytest

from godette_pet.trace import (
    TraceError,
    compile_frame_plan,
    compile_segments,
    coverage_report,
    load_trace,
    parse_trace_lines,
)


def _lines(records: list[dict[str, object]]) -> list[str]:
    return [json.dumps(record) for record in records]


def test_parse_compile_and_cover_a_trace() -> None:
    events = parse_trace_lines(
        _lines(
            [
                {"at_ms": 0, "state": "idle"},
                {"at_ms": 300, "state": "look", "direction_deg": 89},
                {"at_ms": 500, "state": "review", "duration_ms": 250},
            ]
        )
    )
    assert [segment.duration_ms for segment in compile_segments(events)] == [300, 200, 250]
    plan = compile_frame_plan(events, fps=10)
    assert sum(item.duration_ms for item in plan) == 750
    look = [item for item in plan if item.state == "look"]
    assert {(item.row, item.column, item.direction) for item in look} == {(9, 4, "090")}
    report = coverage_report(events)
    assert report["duration_ms"] == 750
    assert "idle" in report["states"]
    assert "090" in report["directions"]


@pytest.mark.parametrize(
    ("records", "message"),
    [
        ([], "no events"),
        ([{"at_ms": 1, "state": "idle", "duration_ms": 10}], "start at 0"),
        (
            [
                {"at_ms": 0, "state": "idle"},
                {"at_ms": 0, "state": "review", "duration_ms": 10},
            ],
            "strictly greater",
        ),
        ([{"at_ms": 0, "state": "look", "duration_ms": 10}], "require direction"),
        (
            [{"at_ms": 0, "state": "idle", "direction_deg": 90, "duration_ms": 10}],
            "only valid",
        ),
        ([{"at_ms": 0, "state": "idle"}], "final event"),
        ([{"at_ms": 0, "state": "unknown", "duration_ms": 10}], "state must"),
    ],
)
def test_trace_rejects_ambiguous_or_invalid_input(
    records: list[dict[str, object]], message: str
) -> None:
    with pytest.raises(TraceError, match=message):
        parse_trace_lines(_lines(records))


def test_trace_rejects_unknown_fields_and_drift() -> None:
    with pytest.raises(TraceError, match="unknown fields"):
        parse_trace_lines(_lines([{"at_ms": 0, "state": "idle", "duration_ms": 10, "oops": True}]))
    with pytest.raises(TraceError, match="does not match"):
        parse_trace_lines(
            _lines(
                [
                    {"at_ms": 0, "state": "idle", "duration_ms": 99},
                    {"at_ms": 100, "state": "review", "duration_ms": 20},
                ]
            )
        )


def test_frame_plan_requires_drift_free_fps() -> None:
    events = parse_trace_lines(_lines([{"at_ms": 0, "state": "idle", "duration_ms": 1000}]))
    with pytest.raises(TraceError, match="divide 1000"):
        compile_frame_plan(events, fps=12)
    with pytest.raises(TraceError, match="between 1 and 50"):
        compile_frame_plan(events, fps=0)


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ("[]", "must be an object"),
        ('{"state":"idle"}', "required"),
        ('{"at_ms":true,"state":"idle"}', "must be an integer"),
        ('{"at_ms":-1,"state":"idle"}', "non-negative"),
        ('{"at_ms":0,"state":"idle","duration_ms":0}', "positive"),
        (
            '{"at_ms":0,"state":"look","direction_deg":true,"duration_ms":10}',
            "numeric",
        ),
        (
            '{"at_ms":0,"state":"look","direction_deg":1e999,"duration_ms":10}',
            "finite",
        ),
        ('{"at_ms":0,"state":"idle","duration_ms":10,"label":1}', "must be a string"),
        (
            '{"at_ms":0,"state":"idle","duration_ms":10,"label":"' + "x" * 201 + '"}',
            "200 characters",
        ),
    ],
)
def test_trace_field_validation(line: str, message: str) -> None:
    with pytest.raises(TraceError, match=message):
        parse_trace_lines([line])


def test_comments_invalid_json_missing_file_and_fps_types(tmp_path) -> None:
    events = parse_trace_lines(
        ["# captured by PetTrace", "", '{"at_ms":0,"state":"idle","duration_ms":10}']
    )
    with pytest.raises(TraceError, match="invalid JSON"):
        parse_trace_lines(["{"])
    with pytest.raises(TraceError, match="cannot read trace"):
        load_trace(tmp_path / "missing.jsonl")
    for fps in (True, 51, "10"):
        with pytest.raises(TraceError, match="between 1 and 50"):
            compile_frame_plan(events, fps=fps)
