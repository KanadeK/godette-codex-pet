"""Strict JSONL parsing and deterministic frame-plan compilation for PetTrace."""

from __future__ import annotations

import json
import math
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

from .contract import (
    ANIMATIONS,
    LOOK_DIRECTIONS,
    TRACE_STATES,
    animation_frame,
    direction_cell,
    direction_label,
)


class TraceError(ValueError):
    """A trace cannot be interpreted without guessing."""


@dataclass(frozen=True, slots=True)
class TraceEvent:
    at_ms: int
    state: str
    duration_ms: int | None = None
    direction_deg: float | None = None
    label: str | None = None
    line: int = 0


@dataclass(frozen=True, slots=True)
class TraceSegment:
    start_ms: int
    end_ms: int
    state: str
    direction_deg: float | None
    label: str | None

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


@dataclass(frozen=True, slots=True)
class FramePlanItem:
    at_ms: int
    duration_ms: int
    state: str
    row: int
    column: int
    direction: str | None
    label: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _require_int(value: object, field: str, line: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TraceError(f"line {line}: {field} must be an integer")
    return value


def _parse_event(raw: object, line: int) -> TraceEvent:
    if not isinstance(raw, dict):
        raise TraceError(f"line {line}: each JSONL record must be an object")
    allowed = {"at_ms", "state", "duration_ms", "direction_deg", "label"}
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise TraceError(f"line {line}: unknown fields: {', '.join(unknown)}")
    if "at_ms" not in raw or "state" not in raw:
        raise TraceError(f"line {line}: at_ms and state are required")

    at_ms = _require_int(raw["at_ms"], "at_ms", line)
    if at_ms < 0:
        raise TraceError(f"line {line}: at_ms must be non-negative")
    state = raw["state"]
    if not isinstance(state, str) or state not in TRACE_STATES:
        choices = ", ".join(sorted(TRACE_STATES))
        raise TraceError(f"line {line}: state must be one of {choices}")

    duration = raw.get("duration_ms")
    if duration is not None:
        duration = _require_int(duration, "duration_ms", line)
        if duration <= 0:
            raise TraceError(f"line {line}: duration_ms must be positive")

    direction = raw.get("direction_deg")
    if direction is not None:
        if isinstance(direction, bool) or not isinstance(direction, (int, float)):
            raise TraceError(f"line {line}: direction_deg must be numeric")
        direction = float(direction)
        if not math.isfinite(direction):
            raise TraceError(f"line {line}: direction_deg must be finite")
    if state == "look" and direction is None:
        raise TraceError(f"line {line}: look events require direction_deg")
    if state != "look" and direction is not None:
        raise TraceError(f"line {line}: direction_deg is only valid for look events")

    label = raw.get("label")
    if label is not None:
        if not isinstance(label, str):
            raise TraceError(f"line {line}: label must be a string")
        if len(label) > 200:
            raise TraceError(f"line {line}: label must be 200 characters or fewer")

    return TraceEvent(at_ms, state, duration, direction, label, line)


def parse_trace_lines(lines: Iterable[str]) -> list[TraceEvent]:
    """Parse strict JSONL records and validate timeline invariants."""

    events: list[TraceEvent] = []
    for line_number, text in enumerate(lines, 1):
        stripped = text.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            raw = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise TraceError(f"line {line_number}: invalid JSON: {exc.msg}") from exc
        events.append(_parse_event(raw, line_number))

    if not events:
        raise TraceError("trace contains no events")
    if events[0].at_ms != 0:
        raise TraceError(f"line {events[0].line}: first event must start at 0 ms")

    for previous, current in pairwise(events):
        if current.at_ms <= previous.at_ms:
            raise TraceError(
                f"line {current.line}: at_ms must be strictly greater than the previous event"
            )
        gap = current.at_ms - previous.at_ms
        if previous.duration_ms is not None and previous.duration_ms != gap:
            raise TraceError(
                f"line {previous.line}: duration_ms {previous.duration_ms} "
                f"does not match next-event gap {gap}"
            )
    if events[-1].duration_ms is None:
        raise TraceError(f"line {events[-1].line}: final event requires duration_ms")
    return events


def load_trace(path: str | Path) -> list[TraceEvent]:
    trace_path = Path(path)
    try:
        return parse_trace_lines(trace_path.read_text(encoding="utf-8").splitlines())
    except OSError as exc:
        raise TraceError(f"cannot read trace {trace_path}: {exc}") from exc


def compile_segments(events: list[TraceEvent]) -> list[TraceSegment]:
    segments: list[TraceSegment] = []
    for index, event in enumerate(events):
        end_ms = (
            events[index + 1].at_ms
            if index + 1 < len(events)
            else event.at_ms + (event.duration_ms or 0)
        )
        segments.append(
            TraceSegment(event.at_ms, end_ms, event.state, event.direction_deg, event.label)
        )
    return segments


def compile_frame_plan(events: list[TraceEvent], fps: int = 10) -> list[FramePlanItem]:
    """Compile events into exact atlas cells and integer millisecond durations."""

    if isinstance(fps, bool) or not isinstance(fps, int) or not 1 <= fps <= 50:
        raise TraceError("fps must be an integer between 1 and 50")
    if 1000 % fps:
        raise TraceError("fps must divide 1000 exactly for a drift-free millisecond timeline")
    step_ms = 1000 // fps
    plan: list[FramePlanItem] = []

    for segment in compile_segments(events):
        cursor = segment.start_ms
        while cursor < segment.end_ms:
            duration = min(step_ms, segment.end_ms - cursor)
            if segment.state == "look":
                assert segment.direction_deg is not None
                row, column, canonical = direction_cell(segment.direction_deg)
                direction = direction_label(canonical)
            else:
                row, column = animation_frame(segment.state, cursor - segment.start_ms)
                direction = None
            plan.append(
                FramePlanItem(
                    cursor,
                    duration,
                    segment.state,
                    row,
                    column,
                    direction,
                    segment.label,
                )
            )
            cursor += duration
    return plan


def coverage_report(events: list[TraceEvent]) -> dict[str, Any]:
    states = {event.state for event in events if event.state != "look"}
    directions = {
        direction_label(event.direction_deg)
        for event in events
        if event.state == "look" and event.direction_deg is not None
    }
    expected_directions = {direction_label(value) for value in LOOK_DIRECTIONS}
    return {
        "ok": True,
        "duration_ms": compile_segments(events)[-1].end_ms,
        "event_count": len(events),
        "states": sorted(states),
        "directions": sorted(directions, key=lambda item: float(item)),
        "missing_states": sorted(set(ANIMATIONS) - states),
        "missing_directions": sorted(
            expected_directions - directions, key=lambda item: float(item)
        ),
    }
