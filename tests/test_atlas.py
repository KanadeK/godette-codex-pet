from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

import godette_pet.atlas as atlas_module
from godette_pet.atlas import PetValidationError, require_valid_pet, validate_pet_dir
from godette_pet.contract import ATLAS_SIZE, CELL_HEIGHT, CELL_WIDTH


def test_valid_pet_reports_exact_contract(valid_pet: Path) -> None:
    report = require_valid_pet(valid_pet)
    assert report["ok"]
    assert report["metrics"]["size"] == [1536, 2288]
    assert report["metrics"]["populated_required_cells"] == 74
    assert report["metrics"]["empty_unused_cells"] == 14
    assert report["metrics"]["hidden_rgb_pixels"] == 0


def test_missing_and_invalid_manifest_fail(tmp_path: Path) -> None:
    report = validate_pet_dir(tmp_path)
    assert report["errors"][0]["code"] == "manifest_missing"
    (tmp_path / "pet.json").write_text("{", encoding="utf-8")
    report = validate_pet_dir(tmp_path)
    assert report["errors"][0]["code"] == "manifest_invalid"


def test_manifest_escape_and_wrong_version_fail(valid_pet: Path) -> None:
    manifest_path = valid_pet / "pet.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["spriteVersionNumber"] = 1
    manifest["spritesheetPath"] = "../outside.webp"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    report = validate_pet_dir(valid_pet)
    assert {item["code"] for item in report["errors"]} == {"manifest_invalid"}


def test_blank_required_and_nonblank_unused_cells_fail(valid_pet: Path) -> None:
    atlas_path = valid_pet / "spritesheet.webp"
    with Image.open(atlas_path) as opened:
        atlas = opened.convert("RGBA")
    draw = ImageDraw.Draw(atlas)
    draw.rectangle((0, 0, CELL_WIDTH - 1, CELL_HEIGHT - 1), fill=(0, 0, 0, 0))
    # Idle uses columns 0-5 and the V2 neutral fallback uses column 6;
    # column 7 must remain blank.
    draw.rectangle(
        (7 * CELL_WIDTH + 30, 30, 7 * CELL_WIDTH + 50, 60),
        fill=(10, 20, 30, 255),
    )
    atlas.save(atlas_path, "WEBP", lossless=True, exact=True)
    report = validate_pet_dir(valid_pet)
    codes = {item["code"] for item in report["errors"]}
    assert {"used_blank", "unused_nonblank"} <= codes


def test_edge_clipping_is_warning_or_strict_error(valid_pet: Path) -> None:
    atlas_path = valid_pet / "spritesheet.webp"
    with Image.open(atlas_path) as opened:
        atlas = opened.convert("RGBA")
    ImageDraw.Draw(atlas).point((0, 0), fill=(20, 20, 20, 255))
    atlas.save(atlas_path, "WEBP", lossless=True, exact=True)
    relaxed = validate_pet_dir(valid_pet, strict=False)
    strict = validate_pet_dir(valid_pet, strict=True)
    assert any(item["code"] == "edge_clipped" for item in relaxed["warnings"])
    assert any(item["code"] == "edge_clipped" for item in strict["errors"])


def test_manifest_and_atlas_failure_modes(valid_pet: Path, tmp_path: Path) -> None:
    manifest_path = valid_pet / "pet.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_path.write_text("[]", encoding="utf-8")
    assert validate_pet_dir(valid_pet)["errors"][0]["code"] == "manifest_invalid"

    manifest["displayName"] = ""
    manifest["spritesheetPath"] = str((tmp_path / "absolute.webp").resolve())
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    report = validate_pet_dir(valid_pet)
    assert {item["code"] for item in report["errors"]} == {"manifest_invalid"}

    manifest["displayName"] = "Godette"
    manifest["spritesheetPath"] = "missing.webp"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert validate_pet_dir(valid_pet)["errors"][0]["code"] == "atlas_missing"

    atlas_path = valid_pet / "broken.webp"
    atlas_path.write_bytes(b"not an image")
    manifest["spritesheetPath"] = "broken.webp"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert validate_pet_dir(valid_pet)["errors"][0]["code"] == "atlas_invalid"


def test_windows_style_escape_and_non_contract_format_fail(valid_pet: Path) -> None:
    manifest_path = valid_pet / "pet.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["spritesheetPath"] = "C:/outside.webp"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert validate_pet_dir(valid_pet)["errors"][0]["code"] == "manifest_invalid"

    original_atlas = valid_pet / "spritesheet.webp"
    with Image.open(original_atlas) as opened:
        atlas = opened.convert("RGBA")
    tiff_path = valid_pet / "spritesheet.tiff"
    atlas.save(tiff_path, "TIFF")
    manifest["spritesheetPath"] = "spritesheet.tiff"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    report = validate_pet_dir(valid_pet)
    assert any("expected PNG or WEBP" in item["message"] for item in report["errors"])


def test_wrong_atlas_contract_and_pixel_hygiene(valid_pet: Path, monkeypatch) -> None:
    atlas_path = valid_pet / "spritesheet.webp"
    small = Image.new("RGB", (20, 20), (255, 0, 255))
    small.save(atlas_path, "WEBP", lossless=True)
    wrong = validate_pet_dir(valid_pet)
    assert {item["code"] for item in wrong["errors"]} == {"atlas_invalid"}

    image = Image.new("RGBA", ATLAS_SIZE, (1, 2, 3, 0))
    draw = ImageDraw.Draw(image)
    for row in range(11):
        for column in range(8):
            draw.rectangle(
                (
                    column * CELL_WIDTH + 20,
                    row * CELL_HEIGHT + 20,
                    column * CELL_WIDTH + 40,
                    row * CELL_HEIGHT + 50,
                ),
                fill=(255, 0, 255, 255),
            )
    image.save(atlas_path, "WEBP", lossless=True, exact=True)
    monkeypatch.setattr(atlas_module, "MAX_ATLAS_BYTES", 1)
    dirty = validate_pet_dir(valid_pet)
    codes = {item["code"] for item in dirty["errors"]}
    assert {"size_limit", "unused_nonblank", "hidden_rgb", "chroma_residue"} <= codes
    with pytest.raises(PetValidationError):
        require_valid_pet(valid_pet)
