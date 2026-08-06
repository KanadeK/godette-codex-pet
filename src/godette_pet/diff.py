"""Deterministic visual-regression reports for Codex v2 pet atlases."""

from __future__ import annotations

import hashlib
import html
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw

from .atlas import require_valid_pet
from .contract import (
    ANIMATIONS,
    CELL_HEIGHT,
    CELL_WIDTH,
    LOOK_DIRECTIONS,
    used_cells,
)


class DiffError(ValueError):
    """A visual comparison policy or output request is invalid."""


@dataclass(frozen=True, slots=True)
class DiffPolicy:
    """Machine-enforced visual change budget."""

    channel_tolerance: int = 0
    max_changed_cells: int = 0
    max_cell_change_ratio: float = 0.0
    max_bbox_shift_px: float = 0.0

    def validate(self) -> None:
        if (
            isinstance(self.channel_tolerance, bool)
            or not isinstance(self.channel_tolerance, int)
            or not 0 <= self.channel_tolerance <= 255
        ):
            raise DiffError("channel_tolerance must be an integer between 0 and 255")
        if (
            isinstance(self.max_changed_cells, bool)
            or not isinstance(self.max_changed_cells, int)
            or self.max_changed_cells < 0
        ):
            raise DiffError("max_changed_cells must be a non-negative integer")
        if (
            isinstance(self.max_cell_change_ratio, bool)
            or not isinstance(self.max_cell_change_ratio, (int, float))
            or not math.isfinite(self.max_cell_change_ratio)
            or not 0.0 <= self.max_cell_change_ratio <= 1.0
        ):
            raise DiffError("max_cell_change_ratio must be between 0 and 1")
        if (
            isinstance(self.max_bbox_shift_px, bool)
            or not isinstance(self.max_bbox_shift_px, (int, float))
            or not math.isfinite(self.max_bbox_shift_px)
            or self.max_bbox_shift_px < 0
        ):
            raise DiffError("max_bbox_shift_px must be non-negative")


def _cell(image: Image.Image, row: int, column: int) -> Image.Image:
    left = column * CELL_WIDTH
    top = row * CELL_HEIGHT
    return image.crop((left, top, left + CELL_WIDTH, top + CELL_HEIGHT))


def _cell_label(row: int, column: int) -> str:
    if row < 9:
        state = next(name for name, spec in ANIMATIONS.items() if spec.row == row)
        return f"{state}:{column}"
    direction = LOOK_DIRECTIONS[(row - 9) * 8 + column]
    formatted = f"{direction:05.1f}" if not direction.is_integer() else f"{int(direction):03d}"
    return f"look:{formatted}"


def _binary_delta(delta: Image.Image, tolerance: int) -> Image.Image:
    channels = [
        channel.point(lambda value: 255 if value > tolerance else 0) for channel in delta.split()
    ]
    mask = channels[0]
    for channel in channels[1:]:
        mask = ImageChops.lighter(mask, channel)
    return mask


def _bbox_center(alpha: Image.Image) -> tuple[float, float]:
    box = alpha.getbbox()
    if box is None:
        return 0.0, 0.0
    left, top, right, bottom = box
    return (left + right) / 2.0, (top + bottom) / 2.0


def _image_digest(image: Image.Image) -> str:
    return hashlib.sha256(image.tobytes()).hexdigest()


def _compare_cell(
    baseline: Image.Image,
    candidate: Image.Image,
    row: int,
    column: int,
    tolerance: int,
) -> tuple[dict[str, Any], Image.Image]:
    before = _cell(baseline, row, column)
    after = _cell(candidate, row, column)
    delta = ImageChops.difference(before, after)
    changed_mask = _binary_delta(delta, tolerance)
    changed_pixels = changed_mask.histogram()[255]
    total_pixels = CELL_WIDTH * CELL_HEIGHT

    visible_union = ImageChops.lighter(before.getchannel("A"), after.getchannel("A"))
    visible_mask = visible_union.point(lambda value: 255 if value else 0)
    visible_pixels = visible_mask.histogram()[255]
    changed_visible = ImageChops.multiply(changed_mask, visible_mask).histogram()[255]

    before_center = _bbox_center(before.getchannel("A"))
    after_center = _bbox_center(after.getchannel("A"))
    bbox_shift = (
        (after_center[0] - before_center[0]) ** 2 + (after_center[1] - before_center[1]) ** 2
    ) ** 0.5

    highlight = Image.new("RGBA", before.size, (0, 0, 0, 0))
    highlight.paste((226, 74, 61, 255), mask=changed_mask)
    result = {
        "label": _cell_label(row, column),
        "row": row,
        "column": column,
        "changed": bool(changed_pixels),
        "changed_pixels": changed_pixels,
        "changed_ratio": round(changed_pixels / total_pixels, 8),
        "visible_changed_pixels": changed_visible,
        "visible_changed_ratio": round(changed_visible / max(1, visible_pixels), 8),
        "bbox_shift_px": round(bbox_shift, 4),
        "baseline_sha256": _image_digest(before),
        "candidate_sha256": _image_digest(after),
    }
    return result, highlight


def _make_diff_sheet(
    baseline: Image.Image,
    candidate: Image.Image,
    changed: list[dict[str, Any]],
    highlights: dict[tuple[int, int], Image.Image],
    output: Path,
) -> None:
    scale = 0.5
    preview_size = (int(CELL_WIDTH * scale), int(CELL_HEIGHT * scale))
    gutter = 12
    label_height = 24
    rows = max(1, len(changed))
    width = gutter * 4 + preview_size[0] * 3
    height = gutter + rows * (preview_size[1] + label_height + gutter)
    sheet = Image.new("RGB", (width, height), (24, 31, 36))
    draw = ImageDraw.Draw(sheet)

    if not changed:
        draw.text((gutter, gutter), "No changed v2 cells.", fill=(223, 231, 235))
    for index, item in enumerate(changed):
        row = item["row"]
        column = item["column"]
        top = gutter + index * (preview_size[1] + label_height + gutter)
        draw.text(
            (gutter, top),
            f"{item['label']}  changed {item['changed_ratio']:.4f}",
            fill=(223, 231, 235),
        )
        image_top = top + label_height
        previews = (
            _cell(baseline, row, column),
            _cell(candidate, row, column),
            highlights[(row, column)],
        )
        for preview_index, preview in enumerate(previews):
            resized = preview.resize(preview_size, Image.Resampling.NEAREST)
            left = gutter + preview_index * (preview_size[0] + gutter)
            sheet.paste(resized, (left, image_top), resized if resized.mode == "RGBA" else None)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, "PNG", optimize=False)


def _write_html(report: dict[str, Any], output: Path) -> None:
    rows = "\n".join(
        (
            "<tr>"
            f"<td>{html.escape(item['label'])}</td>"
            f"<td>{item['changed_pixels']}</td>"
            f"<td>{item['changed_ratio']:.6f}</td>"
            f"<td>{item['visible_changed_ratio']:.6f}</td>"
            f"<td>{item['bbox_shift_px']:.2f}px</td>"
            "</tr>"
        )
        for item in report["cells"]
        if item["changed"]
    )
    if not rows:
        rows = '<tr><td colspan="5">No changed v2 cells.</td></tr>'
    status = "PASS" if report["ok"] else "FAIL"
    violations = "".join(f"<li>{html.escape(item)}</li>" for item in report["violations"])
    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PetDiff CI report</title>
<style>
:root {{ color-scheme: light dark; font-family: ui-monospace, Consolas, monospace; }}
body {{ max-width: 72rem; margin: auto; padding: 2rem; line-height: 1.5; }}
header {{ display: grid; grid-template-columns: 1fr auto; gap: 1rem; align-items: start; }}
.status {{ padding: .45rem .7rem; border: 2px solid currentColor; font-weight: 800; }}
img {{ max-width: 100%; height: auto; background: #181f24; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: .6rem; text-align: left; border-bottom: 1px solid #77818a; }}
code {{ overflow-wrap: anywhere; }}
</style>
</head>
<body>
<header><div><h1>PetDiff CI</h1><p>Deterministic Codex v2 atlas regression report.</p></div>
<span class="status">{status}</span></header>
<p><strong>{report["summary"]["changed_cells"]}</strong> of
<strong>{report["summary"]["compared_cells"]}</strong> required cells changed.</p>
<ul>{violations or "<li>No policy violations.</li>"}</ul>
<img src="diff-sheet.png" alt="Baseline, candidate, and highlighted changed pixels">
<h2>Changed cells</h2>
<table><thead><tr><th>Cell</th><th>Pixels</th><th>All-pixel ratio</th>
<th>Visible ratio</th><th>Bounds shift</th></tr></thead><tbody>{rows}</tbody></table>
</body>
</html>
"""
    output.write_text(document, encoding="utf-8", newline="\n")


def compare_pets(
    baseline_dir: str | Path,
    candidate_dir: str | Path,
    output_dir: str | Path,
    *,
    policy: DiffPolicy | None = None,
) -> dict[str, Any]:
    """Compare two validated v2 pets and write deterministic CI evidence."""

    selected_policy = policy or DiffPolicy()
    selected_policy.validate()
    baseline_path = Path(baseline_dir).resolve()
    candidate_path = Path(candidate_dir).resolve()
    output_path = Path(output_dir).resolve()

    baseline_report = require_valid_pet(baseline_path, strict=False)
    candidate_report = require_valid_pet(candidate_path, strict=False)
    with Image.open(baseline_path / baseline_report["manifest"]["spritesheetPath"]) as opened:
        baseline = opened.convert("RGBA")
    with Image.open(candidate_path / candidate_report["manifest"]["spritesheetPath"]) as opened:
        candidate = opened.convert("RGBA")

    cells: list[dict[str, Any]] = []
    highlights: dict[tuple[int, int], Image.Image] = {}
    for row, column in sorted(used_cells()):
        result, highlight = _compare_cell(
            baseline,
            candidate,
            row,
            column,
            selected_policy.channel_tolerance,
        )
        cells.append(result)
        highlights[(row, column)] = highlight

    changed = [item for item in cells if item["changed"]]
    worst_ratio = max((item["changed_ratio"] for item in changed), default=0.0)
    worst_shift = max((item["bbox_shift_px"] for item in changed), default=0.0)
    violations: list[str] = []
    if len(changed) > selected_policy.max_changed_cells:
        violations.append(
            f"changed cells {len(changed)} exceed budget {selected_policy.max_changed_cells}"
        )
    if worst_ratio > selected_policy.max_cell_change_ratio:
        violations.append(
            "largest cell change ratio "
            f"{worst_ratio:.8f} exceeds budget {selected_policy.max_cell_change_ratio:.8f}"
        )
    if worst_shift > selected_policy.max_bbox_shift_px:
        violations.append(
            f"largest bounds shift {worst_shift:.4f}px exceeds budget "
            f"{selected_policy.max_bbox_shift_px:.4f}px"
        )

    output_path.mkdir(parents=True, exist_ok=True)
    sheet_path = output_path / "diff-sheet.png"
    json_path = output_path / "report.json"
    html_path = output_path / "report.html"
    _make_diff_sheet(baseline, candidate, changed, highlights, sheet_path)
    report = {
        "schema_version": 1,
        "ok": not violations,
        "baseline": str(baseline_path),
        "candidate": str(candidate_path),
        "policy": asdict(selected_policy),
        "summary": {
            "compared_cells": len(cells),
            "changed_cells": len(changed),
            "changed_pixels": sum(item["changed_pixels"] for item in changed),
            "largest_cell_change_ratio": worst_ratio,
            "largest_bbox_shift_px": worst_shift,
        },
        "violations": violations,
        "cells": cells,
        "artifacts": {
            "json": str(json_path),
            "html": str(html_path),
            "diff_sheet": str(sheet_path),
        },
    }
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _write_html(report, html_path)
    return report
