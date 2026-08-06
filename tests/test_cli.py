from __future__ import annotations

import json
from pathlib import Path

import pytest

import godette_pet.cli as cli
from godette_pet.cli import run


def test_validate_and_trace_check_exit_codes(valid_pet: Path, tmp_path: Path, capsys) -> None:
    assert run(["validate", str(valid_pet), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"]

    trace = tmp_path / "trace.jsonl"
    trace.write_text('{"at_ms":0,"state":"idle","duration_ms":100}\n', encoding="utf-8")
    assert run(["trace-check", str(trace), "--require-all-states", "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["errors"]


def test_plan_writes_output_and_reports_errors(tmp_path: Path, capsys) -> None:
    trace = tmp_path / "trace.jsonl"
    trace.write_text('{"at_ms":0,"state":"idle","duration_ms":200}\n', encoding="utf-8")
    output = tmp_path / "nested" / "plan.json"
    assert run(["plan", str(trace), "--output", str(output), "--json"]) == 0
    assert output.is_file()
    capsys.readouterr()

    bad = tmp_path / "bad.jsonl"
    bad.write_text("{}\n", encoding="utf-8")
    assert run(["plan", str(bad), "--json"]) == 2
    assert not json.loads(capsys.readouterr().out)["ok"]


def test_all_management_dispatch_paths(
    valid_pet: Path, tmp_path: Path, capsys, monkeypatch
) -> None:
    trace = tmp_path / "trace.jsonl"
    trace.write_text(
        '{"at_ms":0,"state":"idle","duration_ms":100}\n',
        encoding="utf-8",
    )
    rendered = tmp_path / "replay.gif"
    assert (
        run(
            [
                "render",
                str(trace),
                "--pet-dir",
                str(valid_pet),
                "--output",
                str(rendered),
                "--scale",
                "2",
                "--json",
            ]
        )
        == 0
    )
    assert rendered.is_file()
    capsys.readouterr()

    calls: list[str] = []

    def report(name: str):
        def inner(*_args, **_kwargs):
            calls.append(name)
            return {"ok": True, "command": name}

        return inner

    monkeypatch.setattr(cli, "install_pet", report("install"))
    monkeypatch.setattr(cli, "uninstall_pet", report("uninstall"))
    monkeypatch.setattr(cli, "rollback_pet", report("rollback"))
    monkeypatch.setattr(cli, "doctor", report("doctor"))
    monkeypatch.setattr(cli, "build_release_archive", report("package"))

    assert run(["install", "--source", str(valid_pet), "--dry-run", "--json"]) == 0
    assert run(["uninstall", "--dry-run", "--json"]) == 0
    assert run(["rollback", "--dry-run", "--json"]) == 0
    assert run(["doctor", "--source", str(valid_pet), "--json"]) == 0
    assert run(["package", "--output", str(tmp_path / "pet.zip"), "--version", "0.1.0"]) == 0
    assert calls == ["install", "uninstall", "rollback", "doctor", "package"]
    capsys.readouterr()


def test_cli_invalid_validate_direction_gate_and_main(tmp_path: Path, capsys, monkeypatch) -> None:
    assert run(["validate", str(tmp_path), "--strict", "--json"]) == 1
    capsys.readouterr()

    trace = tmp_path / "trace.jsonl"
    trace.write_text(
        '{"at_ms":0,"state":"idle","duration_ms":100}\n',
        encoding="utf-8",
    )
    assert run(["trace-check", str(trace), "--require-all-directions"]) == 1
    capsys.readouterr()

    monkeypatch.setattr(cli, "run", lambda: 7)
    with pytest.raises(SystemExit) as raised:
        cli.main()
    assert raised.value.code == 7
