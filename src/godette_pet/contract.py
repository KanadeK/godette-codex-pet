"""The Codex v2 sprite contract used by validation and replay rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

CELL_WIDTH: Final = 192
CELL_HEIGHT: Final = 208
ATLAS_COLUMNS: Final = 8
ATLAS_ROWS: Final = 11
ATLAS_SIZE: Final = (CELL_WIDTH * ATLAS_COLUMNS, CELL_HEIGHT * ATLAS_ROWS)
SPRITE_VERSION: Final = 2
MAX_ATLAS_BYTES: Final = 20 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class AnimationSpec:
    """One standard Codex animation row."""

    row: int
    frame_count: int
    durations_ms: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.frame_count != len(self.durations_ms):
            raise ValueError("frame_count and durations_ms disagree")

    @property
    def cycle_ms(self) -> int:
        return sum(self.durations_ms)


ANIMATIONS: Final[dict[str, AnimationSpec]] = {
    "idle": AnimationSpec(0, 6, (280, 110, 110, 140, 140, 320)),
    "running-right": AnimationSpec(1, 8, (120, 120, 120, 120, 120, 120, 120, 220)),
    "running-left": AnimationSpec(2, 8, (120, 120, 120, 120, 120, 120, 120, 220)),
    "waving": AnimationSpec(3, 4, (140, 140, 140, 280)),
    "jumping": AnimationSpec(4, 5, (140, 140, 140, 140, 280)),
    "failed": AnimationSpec(5, 8, (140, 140, 140, 140, 140, 140, 140, 240)),
    "waiting": AnimationSpec(6, 6, (150, 150, 150, 150, 150, 260)),
    "running": AnimationSpec(7, 6, (120, 120, 120, 120, 120, 220)),
    "review": AnimationSpec(8, 6, (150, 150, 150, 150, 150, 280)),
}

LOOK_DIRECTIONS: Final[tuple[float, ...]] = tuple(index * 22.5 for index in range(16))
TRACE_STATES: Final[frozenset[str]] = frozenset((*ANIMATIONS, "look"))


def animation_frame(state: str, elapsed_ms: int) -> tuple[int, int]:
    """Return ``(row, column)`` for a standard state at an elapsed time."""

    spec = ANIMATIONS[state]
    cursor = elapsed_ms % spec.cycle_ms
    for column, duration in enumerate(spec.durations_ms):
        if cursor < duration:
            return spec.row, column
        cursor -= duration
    return spec.row, spec.frame_count - 1


def normalize_direction(direction: float) -> float:
    """Quantize any finite degree value to the nearest supported look cell."""

    normalized = direction % 360.0
    index = int(normalized / 22.5 + 0.5) % 16
    return LOOK_DIRECTIONS[index]


def direction_cell(direction: float) -> tuple[int, int, float]:
    """Return ``(row, column, canonical_degree)`` for a look direction."""

    canonical = normalize_direction(direction)
    index = LOOK_DIRECTIONS.index(canonical)
    return 9 + index // 8, index % 8, canonical


def direction_label(direction: float) -> str:
    """Format canonical directions without floating-point noise."""

    canonical = normalize_direction(direction)
    return f"{int(canonical):03d}" if canonical.is_integer() else f"{canonical:05.1f}"


def used_cells() -> frozenset[tuple[int, int]]:
    """Return all cells that must be populated in a v2 atlas."""

    cells = {
        (spec.row, column) for spec in ANIMATIONS.values() for column in range(spec.frame_count)
    }
    # The V2 assembler stores a neutral look fallback in idle row column 6.
    # It is intentionally present even though idle itself uses only columns 0-5.
    cells.add((0, 6))
    cells.update((row, column) for row in (9, 10) for column in range(8))
    return frozenset(cells)
