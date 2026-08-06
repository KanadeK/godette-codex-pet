from __future__ import annotations

from pathlib import Path

import pytest

from scripts.release_check import MARKER, _reset_output


def test_release_check_output_requires_dist_and_preserves_unmarked_data(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    protected = root / "dist" / "protected"
    protected.mkdir(parents=True)
    user_file = protected / "user-file.txt"
    user_file.write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="unmarked"):
        _reset_output(root, protected.resolve())
    assert user_file.read_text(encoding="utf-8") == "keep"

    with pytest.raises(ValueError, match="must stay"):
        _reset_output(root, (tmp_path / "outside").resolve())


def test_release_check_output_reuses_only_its_marked_directory(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    output = (root / "dist" / "preflight").resolve()
    _reset_output(root, output)
    stale = output / "stale.txt"
    stale.write_text("generated", encoding="utf-8")

    _reset_output(root, output)

    assert (output / MARKER).is_file()
    assert not stale.exists()
