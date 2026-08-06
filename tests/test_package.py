from __future__ import annotations

from pathlib import Path

import pytest

from godette_pet.package import PACKAGE_PATHS, PackageError, build_release_archive

from .conftest import make_pet


def _package_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    make_pet(root / "pet")
    for relative in PACKAGE_PATHS:
        path = root / relative
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{relative}\n", encoding="utf-8")
    return root


def test_release_archive_is_byte_reproducible(tmp_path: Path) -> None:
    root = _package_root(tmp_path)
    first = build_release_archive(root, tmp_path / "first.zip", version="0.1.0")
    second = build_release_archive(root, tmp_path / "second.zip", version="0.1.0")
    assert first["sha256"] == second["sha256"]
    assert first["files"] == len(PACKAGE_PATHS) + 1


def test_package_requires_all_files_and_sane_version(tmp_path: Path) -> None:
    root = _package_root(tmp_path)
    (root / "NOTICE.md").unlink()
    with pytest.raises(PackageError, match="missing package files"):
        build_release_archive(root, tmp_path / "bad.zip", version="0.1.0")
    (root / "NOTICE.md").write_text("notice", encoding="utf-8")
    with pytest.raises(PackageError, match="version"):
        build_release_archive(root, tmp_path / "bad.zip", version="bad version")
