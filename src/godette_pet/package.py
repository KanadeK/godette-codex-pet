"""Byte-reproducible release packaging for the Godette pet."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from .atlas import require_valid_pet

FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
PACKAGE_PATHS = (
    "pet/pet.json",
    "pet/spritesheet.webp",
    "pet/provenance.json",
    "LICENSE",
    "LICENSES/CC-BY-4.0.txt",
    "ASSET_LICENSE.md",
    "NOTICE.md",
    "README.md",
    "README.zh-CN.md",
    "CHANGELOG.md",
    "CITATION.cff",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "SUPPORT.md",
    "action.yml",
    "docs/ARCHITECTURE.md",
    "docs/PETDIFF.md",
    "docs/TRACE_FORMAT.md",
    "docs/REPAIR.md",
    "docs/RESEARCH.md",
    "docs/RELEASE.md",
    "docs/media/godette-idle.gif",
    "examples/bugfix-session.jsonl",
    "examples/direction-tour.jsonl",
)


class PackageError(ValueError):
    """The requested package would be incomplete or non-reproducible."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_release_archive(
    repo_root: str | Path, output: str | Path, *, version: str
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    require_valid_pet(root / "pet")
    if not version or any(character.isspace() for character in version):
        raise PackageError("version must be a non-empty token without whitespace")

    entries: dict[str, bytes] = {}
    missing: list[str] = []
    for relative in PACKAGE_PATHS:
        source = root / relative
        if not source.is_file():
            missing.append(relative)
        else:
            entries[PurePosixPath(relative).as_posix()] = source.read_bytes()
    if missing:
        raise PackageError(f"missing package files: {', '.join(missing)}")

    manifest = {
        "schema_version": 1,
        "package": "godette-codex-pet",
        "version": version,
        "files": [
            {"path": path, "bytes": len(data), "sha256": _sha256(data)}
            for path, data in sorted(entries.items())
        ],
    }
    entries["release-manifest.json"] = (
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode()

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path, data in sorted(entries.items()):
            info = zipfile.ZipInfo(path, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.flag_bits |= 0x800
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

    archive_bytes = output_path.read_bytes()
    return {
        "ok": True,
        "output": str(output_path.resolve()),
        "version": version,
        "bytes": len(archive_bytes),
        "sha256": _sha256(archive_bytes),
        "files": len(entries),
        "manifest": manifest,
    }
