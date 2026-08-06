from __future__ import annotations

from pathlib import Path

import pytest

from scripts.build_site import STATIC_FILES, build_site

from .conftest import make_pet


def _site_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    make_pet(root / "pet")
    (root / "web").mkdir()
    for relative in STATIC_FILES:
        (root / "web" / relative).write_text(relative, encoding="utf-8")
    (root / "examples").mkdir()
    for name in ("bugfix-session.jsonl", "direction-tour.jsonl"):
        (root / "examples" / name).write_text(
            '{"at_ms":0,"state":"idle","duration_ms":10}\n',
            encoding="utf-8",
        )
    return root


def test_site_build_copies_validated_assets_and_is_repeatable(tmp_path: Path) -> None:
    root = _site_root(tmp_path)
    output = root / "dist" / "site"
    first = build_site(root, output)
    second = build_site(root, output)
    assert first["ok"] and second["ok"]
    assert (output / "assets" / "spritesheet.webp").is_file()
    assert (output / "assets" / "build-metadata.json").is_file()
    assert (output / "examples" / "direction-tour.jsonl").is_file()


def test_site_build_refuses_unsafe_or_unmarked_output(tmp_path: Path) -> None:
    root = _site_root(tmp_path)
    with pytest.raises(ValueError, match="root"):
        build_site(root, root)

    output = root / "dist" / "existing"
    output.mkdir(parents=True)
    (output / "user-file.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError, match="unmarked"):
        build_site(root, output)
    assert (output / "user-file.txt").read_text(encoding="utf-8") == "keep"
