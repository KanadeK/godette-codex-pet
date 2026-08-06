from __future__ import annotations

import zipfile
from pathlib import Path
from stat import S_IFLNK

import pytest

import godette_pet.install as install_module
from godette_pet.atlas import PetValidationError
from godette_pet.install import (
    InstallError,
    PetLock,
    doctor,
    install_pet,
    resolve_codex_home,
    resolved_pet_source,
    rollback_pet,
    uninstall_pet,
)

from .conftest import make_pet


def test_install_replace_uninstall_and_rollback(tmp_path: Path) -> None:
    source = make_pet(tmp_path / "source")
    home = tmp_path / "codex"
    dry = install_pet(source, codex_home=home, dry_run=True)
    assert dry["dry_run"] and not (home / "pets" / "godette").exists()

    installed = install_pet(source, codex_home=home)
    assert installed["ok"]
    assert (home / "pets" / "godette" / "pet.json").is_file()

    replaced = install_pet(source, codex_home=home)
    assert replaced["backup"]
    assert Path(replaced["backup"]).is_dir()

    removed = uninstall_pet(codex_home=home)
    assert removed["status"] == "moved-to-backup"
    assert not (home / "pets" / "godette").exists()

    restored = rollback_pet(codex_home=home)
    assert restored["ok"]
    assert (home / "pets" / "godette" / "pet.json").is_file()


def test_doctor_reports_missing_then_healthy(tmp_path: Path) -> None:
    source = make_pet(tmp_path / "source")
    home = tmp_path / "codex"
    missing = doctor(source, codex_home=home)
    assert not missing["ok"]
    assert "not installed" in missing["repairs"][0]
    install_pet(source, codex_home=home)
    assert doctor(source, codex_home=home)["ok"]


def test_zip_source_and_zip_slip_defense(tmp_path: Path) -> None:
    source = make_pet(tmp_path / "source")
    safe_zip = tmp_path / "safe.zip"
    with zipfile.ZipFile(safe_zip, "w") as archive:
        archive.write(source / "pet.json", "pet/pet.json")
        archive.write(source / "spritesheet.webp", "pet/spritesheet.webp")
    with resolved_pet_source(safe_zip) as extracted:
        assert (extracted / "pet.json").is_file()

    unsafe_zip = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(unsafe_zip, "w") as archive:
        archive.writestr("../escape.txt", "no")
    with pytest.raises(InstallError, match="unsafe archive"), resolved_pet_source(unsafe_zip):
        pass


@pytest.mark.parametrize(
    "member_name",
    ["..\\escape.txt", "C:/escape.txt", "/absolute.txt"],
)
def test_zip_rejects_cross_platform_escape_names(tmp_path: Path, member_name: str) -> None:
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(member_name, "no")
    with pytest.raises(InstallError, match="unsafe archive"), resolved_pet_source(archive_path):
        pass


def test_zip_rejects_symlink_and_corruption(tmp_path: Path) -> None:
    symlink_zip = tmp_path / "symlink.zip"
    link = zipfile.ZipInfo("pet/link")
    link.create_system = 3
    link.external_attr = (S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(symlink_zip, "w") as archive:
        archive.writestr(link, "target")
    with pytest.raises(InstallError, match="unsafe archive"), resolved_pet_source(symlink_zip):
        pass

    corrupt = tmp_path / "corrupt.zip"
    corrupt.write_bytes(b"not a zip")
    with pytest.raises(InstallError, match="cannot read pet archive"), resolved_pet_source(corrupt):
        pass


def test_zip_rejects_duplicate_portable_names_and_entry_flood(tmp_path: Path) -> None:
    duplicate_zip = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(duplicate_zip, "w") as archive:
        archive.writestr("pet/README.txt", "one")
        archive.writestr("PET/readme.TXT", "two")
    with pytest.raises(InstallError, match="duplicate archive"), resolved_pet_source(duplicate_zip):
        pass

    crowded_zip = tmp_path / "crowded.zip"
    with zipfile.ZipFile(crowded_zip, "w") as archive:
        for index in range(257):
            archive.writestr(f"pet/entry-{index}.txt", "")
    with pytest.raises(InstallError, match="limit is 256"), resolved_pet_source(crowded_zip):
        pass


@pytest.mark.parametrize("failure_call", [2, 3])
def test_install_preserves_previous_pet_after_staged_or_final_validation_failure(
    tmp_path: Path, monkeypatch, failure_call: int
) -> None:
    previous = make_pet(tmp_path / "previous")
    candidate = make_pet(tmp_path / "candidate")
    previous_manifest = (previous / "pet.json").read_bytes()
    candidate_manifest = (candidate / "pet.json").read_text(encoding="utf-8")
    (candidate / "pet.json").write_text(
        candidate_manifest.replace('"displayName": "Test Pet"', '"displayName": "Candidate Pet"'),
        encoding="utf-8",
    )
    home = tmp_path / "codex"
    install_pet(previous, codex_home=home)

    real_require = install_module.require_valid_pet
    validation_calls = 0

    def fail_final_validation(path: str | Path, *, strict: bool = True):
        nonlocal validation_calls
        validation_calls += 1
        if validation_calls == failure_call:
            raise PetValidationError("injected validation failure")
        return real_require(path, strict=strict)

    monkeypatch.setattr(install_module, "require_valid_pet", fail_final_validation)
    with pytest.raises(PetValidationError, match="injected validation failure"):
        install_pet(candidate, codex_home=home)

    target = home / "pets" / "godette"
    assert (target / "pet.json").read_bytes() == previous_manifest
    assert real_require(target)["ok"]


def test_rollback_without_backup_fails(tmp_path: Path) -> None:
    with pytest.raises(InstallError, match="no Godette backup"):
        rollback_pet(codex_home=tmp_path / "empty")


def test_source_lock_dry_run_and_doctor_edge_cases(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "codex"
    source = make_pet(tmp_path / "source")
    with (
        pytest.raises(InstallError, match="source must"),
        resolved_pet_source(tmp_path / "missing"),
    ):
        pass

    empty_zip = tmp_path / "empty.zip"
    with zipfile.ZipFile(empty_zip, "w"):
        pass
    with pytest.raises(InstallError, match="does not contain"), resolved_pet_source(empty_zip):
        pass

    lock = PetLock(home)
    with lock:
        with pytest.raises(InstallError, match="active lock"), PetLock(home):
            pass
        locked = doctor(source, codex_home=home)
        assert locked["lock"]

    monkeypatch.setenv("CODEX_HOME", str(home))
    assert resolve_codex_home() == home.resolve()
    monkeypatch.delenv("CODEX_HOME")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert resolve_codex_home() == tmp_path / ".codex"

    assert uninstall_pet(codex_home=home)["status"] == "not-installed"
    install_pet(source, codex_home=home)
    dry = uninstall_pet(codex_home=home, dry_run=True)
    assert dry["dry_run"]
    assert not (home / "pet-backups").exists()

    uninstall_pet(codex_home=home)
    install_pet(source, codex_home=home)
    rolled = rollback_pet(codex_home=home, dry_run=True)
    assert rolled["dry_run"] and rolled["displaced"]

    (home / "pets" / "godette" / "pet.json").write_text("{", encoding="utf-8")
    invalid_source = tmp_path / "invalid-source"
    invalid_source.mkdir()
    (invalid_source / "pet.json").write_text("{", encoding="utf-8")
    broken = doctor(invalid_source, codex_home=home)
    assert not broken["ok"]
    assert len(broken["repairs"]) >= 2
