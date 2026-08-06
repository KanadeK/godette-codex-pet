"""Validation-first, backup-preserving installation and recovery."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import uuid
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from .atlas import PetValidationError, require_valid_pet, validate_pet_dir

MAX_ARCHIVE_MEMBERS = 256
MAX_ARCHIVE_MEMBER_BYTES = 32 * 1024 * 1024
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
WINDOWS_RESERVED_NAMES = {
    "aux",
    "con",
    "nul",
    "prn",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}


class InstallError(RuntimeError):
    """Installation cannot continue without risking user data."""


def resolve_codex_home(value: str | Path | None = None) -> Path:
    if value is not None:
        return Path(value).expanduser().resolve()
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser().resolve() if configured else Path.home() / ".codex"


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _safe_zip_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise InstallError(
            f"archive contains {len(members)} entries; limit is {MAX_ARCHIVE_MEMBERS}"
        )

    safe: list[zipfile.ZipInfo] = []
    seen: set[str] = set()
    total_bytes = 0
    for member in members:
        normalized = member.filename.replace("\\", "/")
        path = PurePosixPath(normalized)
        mode = member.external_attr >> 16
        is_symlink = (mode & 0o170000) == 0o120000
        first_part = path.parts[0] if path.parts else ""
        has_drive = len(first_part) >= 2 and first_part[1] == ":"
        unsafe_windows_part = any(
            ":" in part
            or part.endswith((" ", "."))
            or part.split(".", 1)[0].casefold() in WINDOWS_RESERVED_NAMES
            for part in path.parts
        )
        if (
            not path.parts
            or path.is_absolute()
            or ".." in path.parts
            or has_drive
            or "\x00" in member.filename
            or is_symlink
            or unsafe_windows_part
        ):
            raise InstallError(f"unsafe archive member: {member.filename}")
        normalized_key = path.as_posix().casefold()
        if normalized_key in seen:
            raise InstallError(f"duplicate archive member: {member.filename}")
        seen.add(normalized_key)
        if member.file_size > MAX_ARCHIVE_MEMBER_BYTES:
            raise InstallError(
                f"archive member {member.filename} is {member.file_size} bytes; "
                f"limit is {MAX_ARCHIVE_MEMBER_BYTES}"
            )
        total_bytes += member.file_size
        if total_bytes > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            raise InstallError(
                f"archive uncompressed size exceeds {MAX_ARCHIVE_UNCOMPRESSED_BYTES} bytes"
            )
        safe.append(member)
    return safe


@contextmanager
def resolved_pet_source(source: str | Path) -> Iterator[Path]:
    source_path = Path(source).expanduser().resolve()
    if source_path.is_dir():
        candidate = source_path / "pet" if (source_path / "pet").is_dir() else source_path
        yield candidate
        return
    if not source_path.is_file() or source_path.suffix.lower() != ".zip":
        raise InstallError("source must be a pet directory, repository root, or .zip release")

    with tempfile.TemporaryDirectory(prefix="godette-pet-source-") as temporary:
        root = Path(temporary)
        try:
            with zipfile.ZipFile(source_path) as archive:
                members = _safe_zip_members(archive)
                archive.extractall(root, members=members)
        except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
            raise InstallError(f"cannot read pet archive {source_path}: {exc}") from exc
        candidates = [root / "pet", *root.glob("*/pet"), root]
        for candidate in candidates:
            if (candidate / "pet.json").is_file():
                yield candidate
                return
        raise InstallError("archive does not contain a pet/pet.json package")


class PetLock:
    def __init__(self, codex_home: Path, *, stale_seconds: int = 900) -> None:
        self.path = codex_home / ".godette-pet.lock"
        self.stale_seconds = stale_seconds
        self.acquired = False

    def __enter__(self) -> PetLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            age = time.time() - self.path.stat().st_mtime
            if age <= self.stale_seconds:
                raise InstallError(
                    f"active lock at {self.path}; wait or run doctor before removing it"
                ) from exc
            self.path.unlink()
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"pid": os.getpid(), "created_at": _timestamp()}, stream)
        self.acquired = True
        return self

    def __exit__(self, *_: object) -> None:
        if self.acquired:
            self.path.unlink(missing_ok=True)


def _backup_path(codex_home: Path, *, create_root: bool = True) -> Path:
    root = codex_home / "pet-backups"
    if create_root:
        root.mkdir(parents=True, exist_ok=True)
    return root / f"godette-{_timestamp()}-{uuid.uuid4().hex[:8]}"


def install_pet(
    source: str | Path,
    *,
    codex_home: str | Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    home = resolve_codex_home(codex_home)
    target = home / "pets" / "godette"
    with resolved_pet_source(source) as pet_source:
        source_report = require_valid_pet(pet_source)
        result = {
            "ok": True,
            "dry_run": dry_run,
            "source": str(pet_source),
            "target": str(target),
            "source_sha256": source_report["metrics"]["atlas_sha256"],
            "backup": None,
        }
        if dry_run:
            return result

        with PetLock(home):
            target.parent.mkdir(parents=True, exist_ok=True)
            stage = target.parent / f".godette-stage-{uuid.uuid4().hex}"
            backup: Path | None = None
            candidate_moved = False
            try:
                shutil.copytree(pet_source, stage)
                require_valid_pet(stage)
                if target.exists():
                    backup = _backup_path(home)
                    target.replace(backup)
                    result["backup"] = str(backup)
                stage.replace(target)
                candidate_moved = True
                require_valid_pet(target)
            except Exception as exc:
                if stage.exists():
                    shutil.rmtree(stage)
                try:
                    if backup is not None and backup.exists():
                        failed_target: Path | None = None
                        if target.exists():
                            failed_target = target.parent / f".godette-failed-{uuid.uuid4().hex}"
                            target.replace(failed_target)
                        backup.replace(target)
                        if failed_target is not None:
                            shutil.rmtree(failed_target)
                    elif candidate_moved and target.exists():
                        shutil.rmtree(target)
                except Exception as restore_exc:
                    backup_note = f"; previous pet remains at {backup}" if backup else ""
                    raise InstallError(
                        "install failed and automatic restoration also failed"
                        f"{backup_note}: {restore_exc}"
                    ) from exc
                if isinstance(exc, (InstallError, PetValidationError)):
                    raise
                raise InstallError(f"install failed and previous pet was restored: {exc}") from exc
    return result


def uninstall_pet(*, codex_home: str | Path | None = None, dry_run: bool = False) -> dict[str, Any]:
    home = resolve_codex_home(codex_home)
    target = home / "pets" / "godette"
    if not target.exists():
        return {"ok": True, "dry_run": dry_run, "status": "not-installed", "backup": None}
    backup = _backup_path(home, create_root=not dry_run)
    if not dry_run:
        with PetLock(home):
            target.replace(backup)
    return {
        "ok": True,
        "dry_run": dry_run,
        "status": "moved-to-backup",
        "backup": str(backup),
    }


def rollback_pet(*, codex_home: str | Path | None = None, dry_run: bool = False) -> dict[str, Any]:
    home = resolve_codex_home(codex_home)
    backups_root = home / "pet-backups"
    candidates = sorted(backups_root.glob("godette-*"), key=lambda item: item.stat().st_mtime)
    if not candidates:
        raise InstallError("no Godette backup is available")
    selected = candidates[-1]
    require_valid_pet(selected)
    target = home / "pets" / "godette"
    displaced = _backup_path(home, create_root=not dry_run) if target.exists() else None
    if not dry_run:
        with PetLock(home):
            if target.exists() and displaced is not None:
                target.replace(displaced)
            selected.replace(target)
            require_valid_pet(target)
    return {
        "ok": True,
        "dry_run": dry_run,
        "restored": str(selected),
        "target": str(target),
        "displaced": str(displaced) if displaced else None,
    }


def doctor(
    source: str | Path | None = None, *, codex_home: str | Path | None = None
) -> dict[str, Any]:
    home = resolve_codex_home(codex_home)
    target = home / "pets" / "godette"
    lock = home / ".godette-pet.lock"
    installed = validate_pet_dir(target) if target.exists() else None
    source_report = None
    if source is not None:
        with resolved_pet_source(source) as pet_source:
            source_report = validate_pet_dir(pet_source)
    repairs: list[str] = []
    if installed is None:
        repairs.append("Godette is not installed; run `godette-pet install --source pet`.")
    elif not installed["ok"]:
        repairs.append("Installed files are invalid; run install again from a validated source.")
    if lock.exists():
        age = max(0, int(time.time() - lock.stat().st_mtime))
        repairs.append(
            f"Install lock is {age}s old; if no install is running, remove it after 900s."
        )
    if source_report is not None and not source_report["ok"]:
        repairs.append("The requested repair source is invalid; download the signed release again.")
    return {
        "ok": not repairs,
        "codex_home": str(home),
        "installed": installed,
        "source": source_report,
        "lock": str(lock) if lock.exists() else None,
        "repairs": repairs,
    }
