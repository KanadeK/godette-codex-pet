from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from godette_pet.render import RenderError, render_plan
from godette_pet.trace import compile_frame_plan, parse_trace_lines


def _plan() -> list:
    events = parse_trace_lines(
        [
            json.dumps({"at_ms": 0, "state": "idle"}),
            json.dumps(
                {
                    "at_ms": 300,
                    "state": "look",
                    "direction_deg": 270,
                    "duration_ms": 300,
                }
            ),
        ]
    )
    return compile_frame_plan(events, fps=10)


@pytest.mark.parametrize("suffix", [".gif", ".webp"])
def test_replay_render_is_byte_deterministic(valid_pet: Path, tmp_path: Path, suffix: str) -> None:
    first = render_plan(valid_pet, _plan(), tmp_path / f"first{suffix}")
    second = render_plan(valid_pet, _plan(), tmp_path / f"second{suffix}")
    assert first["sha256"] == second["sha256"]
    assert first["frames"] == 6
    assert first["duration_ms"] == 600
    with Image.open(first["output"]) as rendered:
        assert rendered.size == (192, 208)
        assert getattr(rendered, "n_frames", 1) >= 2


def test_render_rejects_bad_output_and_scale(valid_pet: Path, tmp_path: Path) -> None:
    with pytest.raises(RenderError, match="empty"):
        render_plan(valid_pet, [], tmp_path / "output.gif")
    with pytest.raises(RenderError, match="must end"):
        render_plan(valid_pet, _plan(), tmp_path / "output.png")
    with pytest.raises(RenderError, match="scale"):
        render_plan(valid_pet, _plan(), tmp_path / "output.gif", scale=0)
    with pytest.raises(RenderError, match="background"):
        render_plan(
            valid_pet,
            _plan(),
            tmp_path / "output.gif",
            background="not-a-color",
        )
