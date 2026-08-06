from __future__ import annotations

from godette_pet.contract import (
    ANIMATIONS,
    LOOK_DIRECTIONS,
    animation_frame,
    direction_cell,
    direction_label,
    normalize_direction,
    used_cells,
)


def test_contract_has_74_required_cells_and_16_directions() -> None:
    # 57 state frames + 16 direction frames + V2 neutral look fallback.
    assert len(used_cells()) == 74
    assert len(LOOK_DIRECTIONS) == 16
    assert sum(spec.frame_count for spec in ANIMATIONS.values()) == 57


def test_animation_frame_uses_exact_duration_boundaries() -> None:
    assert animation_frame("idle", 0) == (0, 0)
    assert animation_frame("idle", 279) == (0, 0)
    assert animation_frame("idle", 280) == (0, 1)
    assert animation_frame("idle", ANIMATIONS["idle"].cycle_ms) == (0, 0)


def test_direction_quantization_and_cells_wrap_clockwise() -> None:
    assert normalize_direction(-1) == 0
    assert normalize_direction(11.3) == 22.5
    assert direction_cell(90) == (9, 4, 90)
    assert direction_cell(180) == (10, 0, 180)
    assert direction_cell(359) == (9, 0, 0)
    assert direction_label(22.5) == "022.5"
    assert direction_label(90) == "090"
