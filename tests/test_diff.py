from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from godette_pet.cli import run
from godette_pet.diff import DiffError, DiffPolicy, compare_pets


def _candidate_from(source: Path, destination: Path) -> Path:
    shutil.copytree(source, destination)
    return destination


def _change_one_cell(pet_dir: Path) -> None:
    atlas_path = pet_dir / "spritesheet.webp"
    with Image.open(atlas_path) as opened:
        atlas = opened.convert("RGBA")
    ImageDraw.Draw(atlas).rectangle((30, 30, 40, 40), fill=(220, 40, 30, 255))
    atlas.save(atlas_path, "WEBP", lossless=True, exact=True)


def test_identical_pets_pass_and_write_complete_report(valid_pet: Path, tmp_path: Path) -> None:
    candidate = _candidate_from(valid_pet, tmp_path / "candidate")
    first = compare_pets(valid_pet, candidate, tmp_path / "report-a")
    second = compare_pets(valid_pet, candidate, tmp_path / "report-b")
    assert first["ok"]
    assert first["summary"]["compared_cells"] == 74
    assert first["summary"]["changed_cells"] == 0
    assert Path(first["artifacts"]["json"]).is_file()
    assert Path(first["artifacts"]["html"]).is_file()
    assert (
        Path(first["artifacts"]["diff_sheet"]).read_bytes()
        == Path(second["artifacts"]["diff_sheet"]).read_bytes()
    )


def test_changed_cell_fails_strict_policy_and_can_use_explicit_budget(
    valid_pet: Path, tmp_path: Path
) -> None:
    candidate = _candidate_from(valid_pet, tmp_path / "candidate")
    _change_one_cell(candidate)
    strict = compare_pets(valid_pet, candidate, tmp_path / "strict")
    assert not strict["ok"]
    assert strict["summary"]["changed_cells"] == 1
    assert strict["violations"]
    report = json.loads(Path(strict["artifacts"]["json"]).read_text(encoding="utf-8"))
    assert report["cells"][0]["label"] == "idle:0"

    budgeted = compare_pets(
        valid_pet,
        candidate,
        tmp_path / "budgeted",
        policy=DiffPolicy(
            max_changed_cells=1,
            max_cell_change_ratio=0.01,
            max_bbox_shift_px=1,
        ),
    )
    assert budgeted["ok"]


@pytest.mark.parametrize(
    "policy",
    [
        DiffPolicy(channel_tolerance=True),
        DiffPolicy(channel_tolerance=256),
        DiffPolicy(channel_tolerance=1.5),
        DiffPolicy(max_changed_cells=-1),
        DiffPolicy(max_changed_cells=0.5),
        DiffPolicy(max_cell_change_ratio=1.1),
        DiffPolicy(max_cell_change_ratio=float("nan")),
        DiffPolicy(max_bbox_shift_px=-0.1),
        DiffPolicy(max_bbox_shift_px=float("inf")),
    ],
)
def test_diff_policy_rejects_invalid_budgets(policy: DiffPolicy) -> None:
    with pytest.raises(DiffError):
        policy.validate()


def test_diff_cli_exit_codes(valid_pet: Path, tmp_path: Path, capsys) -> None:
    candidate = _candidate_from(valid_pet, tmp_path / "candidate")
    assert (
        run(
            [
                "diff",
                str(valid_pet),
                str(candidate),
                "--output-dir",
                str(tmp_path / "same"),
                "--json",
            ]
        )
        == 0
    )
    capsys.readouterr()

    _change_one_cell(candidate)
    assert (
        run(
            [
                "diff",
                str(valid_pet),
                str(candidate),
                "--output-dir",
                str(tmp_path / "changed"),
                "--json",
            ]
        )
        == 1
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["changed_cells"] == 1
