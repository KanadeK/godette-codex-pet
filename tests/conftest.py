from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from godette_pet.contract import (
    ATLAS_COLUMNS,
    ATLAS_ROWS,
    ATLAS_SIZE,
    CELL_HEIGHT,
    CELL_WIDTH,
    used_cells,
)


def make_pet(path: Path, *, pet_id: str = "godette") -> Path:
    path.mkdir(parents=True, exist_ok=True)
    atlas = Image.new("RGBA", ATLAS_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(atlas)
    for row, column in used_cells():
        left = column * CELL_WIDTH + 20
        top = row * CELL_HEIGHT + 20
        color = (
            25 + column * 10,
            80 + row * 5,
            150 + (row + column) % 80,
            255,
        )
        draw.rounded_rectangle(
            (left, top, left + 70, top + 100),
            radius=12,
            fill=color,
        )
    assert len(used_cells()) == 74
    assert ATLAS_COLUMNS * ATLAS_ROWS - len(used_cells()) == 14
    atlas.save(path / "spritesheet.webp", "WEBP", lossless=True, exact=True)
    (path / "pet.json").write_text(
        json.dumps(
            {
                "id": pet_id,
                "displayName": "Godette",
                "description": "Test pet",
                "spriteVersionNumber": 2,
                "spritesheetPath": "spritesheet.webp",
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def valid_pet(tmp_path: Path) -> Path:
    return make_pet(tmp_path / "pet")
