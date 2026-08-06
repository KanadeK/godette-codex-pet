"""Strict structural validation for Codex v2 pet packages."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from PIL import Image, ImageChops

from .contract import (
    ATLAS_COLUMNS,
    ATLAS_ROWS,
    ATLAS_SIZE,
    CELL_HEIGHT,
    CELL_WIDTH,
    MAX_ATLAS_BYTES,
    SPRITE_VERSION,
    used_cells,
)


class PetValidationError(ValueError):
    """Raised when a command requires a valid pet package."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hidden_rgb_count(image: Image.Image) -> int:
    red, green, blue, alpha = image.split()
    rgb_nonzero = ImageChops.lighter(red, ImageChops.lighter(green, blue)).point(
        lambda value: 255 if value else 0
    )
    alpha_zero = alpha.point(lambda value: 255 if value == 0 else 0)
    return ImageChops.multiply(rgb_nonzero, alpha_zero).histogram()[255]


def _magenta_residue_count(image: Image.Image) -> int:
    count = 0
    pixels = image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()
    # Match the hatch validator's visible-pixel threshold. Very low-alpha
    # edge antialiasing is not an opaque chroma-key leak and must not make a
    # correctly despilled WebP package impossible to validate.
    for red, green, blue, alpha in pixels:
        if alpha > 16 and red >= 245 and green <= 20 and blue >= 245:
            count += 1
    return count


def _repair(code: str) -> str:
    repairs = {
        "manifest_missing": "Restore pet/pet.json from the release or run the package build.",
        "manifest_invalid": "Fix pet.json as UTF-8 JSON and rerun validate.",
        "atlas_missing": "Restore the spritesheet named by spritesheetPath.",
        "atlas_invalid": "Rebuild the atlas from validated hatch-pet output.",
        "used_blank": (
            "Regenerate or restore the named animation row; required cells cannot be blank."
        ),
        "unused_nonblank": "Clear every pixel in unused cells to transparent RGBA.",
        "edge_clipped": "Repair the source row and reassemble with safe cell padding.",
        "hidden_rgb": "Run the single approved despill/hidden-RGB cleanup during v2 assembly.",
        "chroma_residue": "Re-run the approved v2 chroma despill and atlas validator.",
        "size_limit": "Re-encode the atlas as lossless WebP without changing dimensions.",
    }
    return repairs[code]


def validate_pet_dir(path: str | Path, *, strict: bool = False) -> dict[str, Any]:
    """Validate a directory containing ``pet.json`` and its spritesheet."""

    pet_dir = Path(path)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {}

    def issue(code: str, message: str, *, warning: bool = False) -> None:
        target = warnings if warning else errors
        target.append({"code": code, "message": message, "repair": _repair(code)})

    manifest_path = pet_dir / "pet.json"
    if not manifest_path.is_file():
        issue("manifest_missing", f"missing {manifest_path}")
        return {"ok": False, "errors": errors, "warnings": warnings, "metrics": metrics}

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        issue("manifest_invalid", f"cannot parse pet.json: {exc}")
        return {"ok": False, "errors": errors, "warnings": warnings, "metrics": metrics}
    if not isinstance(manifest, dict):
        issue("manifest_invalid", "pet.json must contain a JSON object")
        return {"ok": False, "errors": errors, "warnings": warnings, "metrics": metrics}

    required_strings = ("id", "displayName", "description", "spritesheetPath")
    for field in required_strings:
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            issue("manifest_invalid", f"{field} must be a non-empty string")
    if manifest.get("spriteVersionNumber") != SPRITE_VERSION:
        issue("manifest_invalid", "spriteVersionNumber must be 2")

    relative_sprite = manifest.get("spritesheetPath")
    unsafe_sprite_path = False
    if isinstance(relative_sprite, str):
        posix_sprite = PurePosixPath(relative_sprite)
        first_part = posix_sprite.parts[0] if posix_sprite.parts else ""
        unsafe_sprite_path = (
            not relative_sprite
            or "\\" in relative_sprite
            or "\x00" in relative_sprite
            or posix_sprite.is_absolute()
            or ".." in posix_sprite.parts
            or (len(first_part) >= 2 and first_part[1] == ":")
        )
    if not isinstance(relative_sprite, str) or unsafe_sprite_path:
        issue("manifest_invalid", "spritesheetPath must be a relative path")
        return {"ok": False, "errors": errors, "warnings": warnings, "metrics": metrics}
    atlas_path = (pet_dir / relative_sprite).resolve()
    try:
        atlas_path.relative_to(pet_dir.resolve())
    except ValueError:
        issue("manifest_invalid", "spritesheetPath escapes the pet directory")
        return {"ok": False, "errors": errors, "warnings": warnings, "metrics": metrics}
    if not atlas_path.is_file():
        issue("atlas_missing", f"missing {atlas_path}")
        return {"ok": False, "errors": errors, "warnings": warnings, "metrics": metrics}

    atlas_bytes = atlas_path.stat().st_size
    metrics["atlas_bytes"] = atlas_bytes
    metrics["atlas_sha256"] = sha256_file(atlas_path)
    if atlas_bytes >= MAX_ATLAS_BYTES:
        issue("size_limit", f"atlas is {atlas_bytes} bytes; limit is below {MAX_ATLAS_BYTES}")

    try:
        with Image.open(atlas_path) as opened:
            opened.load()
            image = opened.copy()
            metrics["format"] = opened.format
            metrics["mode"] = opened.mode
    except (OSError, ValueError) as exc:
        issue("atlas_invalid", f"cannot decode atlas: {exc}")
        return {"ok": False, "errors": errors, "warnings": warnings, "metrics": metrics}

    if metrics["format"] not in {"PNG", "WEBP"}:
        issue("atlas_invalid", f"atlas format is {metrics['format']}; expected PNG or WEBP")
    if image.size != ATLAS_SIZE:
        issue("atlas_invalid", f"atlas size is {image.size}; expected {ATLAS_SIZE}")
    if image.mode != "RGBA":
        issue("atlas_invalid", f"atlas mode is {image.mode}; expected RGBA")
    if metrics["format"] not in {"PNG", "WEBP"} or image.size != ATLAS_SIZE or image.mode != "RGBA":
        return {"ok": False, "errors": errors, "warnings": warnings, "metrics": metrics}

    required = used_cells()
    populated = 0
    empty = 0
    edge_cells: list[str] = []
    for row in range(ATLAS_ROWS):
        for column in range(ATLAS_COLUMNS):
            box = (
                column * CELL_WIDTH,
                row * CELL_HEIGHT,
                (column + 1) * CELL_WIDTH,
                (row + 1) * CELL_HEIGHT,
            )
            alpha = image.crop(box).getchannel("A")
            bbox = alpha.getbbox()
            cell_name = f"r{row}c{column}"
            if (row, column) in required:
                if bbox is None:
                    issue("used_blank", f"required cell {cell_name} is blank")
                    continue
                populated += 1
                left, top, right, bottom = bbox
                if left < 2 or top < 2 or right > CELL_WIDTH - 2 or bottom > CELL_HEIGHT - 2:
                    edge_cells.append(cell_name)
            elif bbox is not None:
                issue("unused_nonblank", f"unused cell {cell_name} contains visible pixels")
            else:
                empty += 1

    if edge_cells:
        issue(
            "edge_clipped",
            f"visible pixels approach cell edges in {', '.join(edge_cells)}",
            warning=not strict,
        )
    hidden_rgb = _hidden_rgb_count(image)
    magenta_residue = _magenta_residue_count(image)
    metrics.update(
        {
            "size": list(image.size),
            "required_cells": len(required),
            "populated_required_cells": populated,
            "empty_unused_cells": empty,
            "hidden_rgb_pixels": hidden_rgb,
            "opaque_magenta_pixels": magenta_residue,
        }
    )
    if hidden_rgb:
        issue("hidden_rgb", f"{hidden_rgb} fully transparent pixels retain RGB data")
    if magenta_residue:
        issue("chroma_residue", f"{magenta_residue} visible pixels match the magenta key")

    return {
        "ok": not errors,
        "pet_dir": str(pet_dir.resolve()),
        "manifest": manifest,
        "errors": errors,
        "warnings": warnings,
        "metrics": metrics,
    }


def require_valid_pet(path: str | Path, *, strict: bool = True) -> dict[str, Any]:
    report = validate_pet_dir(path, strict=strict)
    if not report["ok"]:
        summary = "; ".join(item["message"] for item in report["errors"])
        raise PetValidationError(summary)
    return report
