"""Render deterministic animated session replays from PetTrace frame plans."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from PIL import Image, ImageColor

from .atlas import require_valid_pet
from .contract import CELL_HEIGHT, CELL_WIDTH
from .trace import FramePlanItem


class RenderError(ValueError):
    """A replay output cannot be produced safely."""


def _cell(image: Image.Image, item: FramePlanItem) -> Image.Image:
    left = item.column * CELL_WIDTH
    top = item.row * CELL_HEIGHT
    return image.crop((left, top, left + CELL_WIDTH, top + CELL_HEIGHT))


def _parse_background(value: str) -> tuple[int, int, int, int]:
    try:
        red, green, blue = ImageColor.getrgb(value)
    except ValueError as exc:
        raise RenderError(f"invalid background color {value!r}") from exc
    return red, green, blue, 255


def render_plan(
    pet_dir: str | Path,
    plan: list[FramePlanItem],
    output: str | Path,
    *,
    background: str = "#0d1117",
    scale: int = 1,
) -> dict[str, Any]:
    """Render a frame plan to deterministic animated GIF or lossless WebP."""

    if not plan:
        raise RenderError("frame plan is empty")
    if isinstance(scale, bool) or not isinstance(scale, int) or not 1 <= scale <= 4:
        raise RenderError("scale must be an integer between 1 and 4")

    pet_path = Path(pet_dir)
    report = require_valid_pet(pet_path, strict=False)
    atlas_path = pet_path / report["manifest"]["spritesheetPath"]
    with Image.open(atlas_path) as opened:
        atlas = opened.convert("RGBA")

    rgba = _parse_background(background)
    frames: list[Image.Image] = []
    durations: list[int] = []
    for item in plan:
        sprite = _cell(atlas, item)
        canvas = Image.new("RGBA", (CELL_WIDTH, CELL_HEIGHT), rgba)
        canvas.alpha_composite(sprite)
        if scale != 1:
            canvas = canvas.resize(
                (CELL_WIDTH * scale, CELL_HEIGHT * scale), Image.Resampling.NEAREST
            )
        frames.append(canvas)
        durations.append(item.duration_ms)

    output_path = Path(output)
    suffix = output_path.suffix.lower()
    if suffix not in {".gif", ".webp"}:
        raise RenderError("output must end in .gif or .webp")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if suffix == ".gif":
        converted = [
            frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=255) for frame in frames
        ]
        converted[0].save(
            output_path,
            save_all=True,
            append_images=converted[1:],
            duration=durations,
            loop=0,
            disposal=2,
            optimize=False,
            comment=b"PetTrace deterministic replay",
        )
    elif suffix == ".webp":
        frames[0].save(
            output_path,
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=0,
            lossless=True,
            quality=100,
            method=6,
            exact=True,
            minimize_size=False,
        )
    payload = output_path.read_bytes()
    return {
        "ok": True,
        "output": str(output_path.resolve()),
        "format": suffix.removeprefix("."),
        "frames": len(frames),
        "duration_ms": sum(durations),
        "size": [CELL_WIDTH * scale, CELL_HEIGHT * scale],
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
