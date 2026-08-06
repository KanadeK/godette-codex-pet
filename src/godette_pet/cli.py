"""Command-line interface for Godette and PetDiff CI."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .atlas import PetValidationError, validate_pet_dir
from .diff import DiffError, DiffPolicy, compare_pets
from .install import InstallError, doctor, install_pet, rollback_pet, uninstall_pet
from .package import PackageError, build_release_archive
from .render import RenderError, render_plan
from .trace import (
    TraceError,
    compile_frame_plan,
    coverage_report,
    load_trace,
)


def _write(payload: Any, *, json_output: bool = False) -> None:
    if json_output or isinstance(payload, (dict, list)):
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(payload)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="godette-pet",
        description="Godette pet management and deterministic PetDiff CI regression tooling.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate a Codex v2 pet directory")
    validate.add_argument("pet_dir", nargs="?", default="pet")
    validate.add_argument("--strict", action="store_true")
    validate.add_argument("--json", action="store_true")

    check = sub.add_parser("trace-check", help="validate a PetTrace JSONL file")
    check.add_argument("trace")
    check.add_argument("--require-all-states", action="store_true")
    check.add_argument("--require-all-directions", action="store_true")
    check.add_argument("--json", action="store_true")

    plan = sub.add_parser("plan", help="compile a trace to an exact atlas frame plan")
    plan.add_argument("trace")
    plan.add_argument("--fps", type=int, default=10)
    plan.add_argument("--output")
    plan.add_argument("--json", action="store_true")

    render = sub.add_parser("render", help="render a trace to animated GIF or WebP")
    render.add_argument("trace")
    render.add_argument("--pet-dir", default="pet")
    render.add_argument("--output", required=True)
    render.add_argument("--fps", type=int, default=10)
    render.add_argument("--background", default="#0d1117")
    render.add_argument("--scale", type=int, default=1)
    render.add_argument("--json", action="store_true")

    diff = sub.add_parser("diff", help="compare two Codex v2 pets under a visual change budget")
    diff.add_argument("baseline")
    diff.add_argument("candidate")
    diff.add_argument("--output-dir", required=True)
    diff.add_argument("--channel-tolerance", type=int, default=0)
    diff.add_argument("--max-changed-cells", type=int, default=0)
    diff.add_argument("--max-cell-change-ratio", type=float, default=0.0)
    diff.add_argument("--max-bbox-shift-px", type=float, default=0.0)
    diff.add_argument("--json", action="store_true")

    install = sub.add_parser("install", help="transactionally install a validated pet")
    install.add_argument("--source", default="pet")
    install.add_argument("--codex-home")
    install.add_argument("--dry-run", action="store_true")
    install.add_argument("--json", action="store_true")

    uninstall = sub.add_parser("uninstall", help="move the installed pet into backups")
    uninstall.add_argument("--codex-home")
    uninstall.add_argument("--dry-run", action="store_true")
    uninstall.add_argument("--json", action="store_true")

    rollback = sub.add_parser("rollback", help="restore the most recent valid backup")
    rollback.add_argument("--codex-home")
    rollback.add_argument("--dry-run", action="store_true")
    rollback.add_argument("--json", action="store_true")

    diagnose = sub.add_parser("doctor", help="diagnose source and installed state")
    diagnose.add_argument("--source")
    diagnose.add_argument("--codex-home")
    diagnose.add_argument("--json", action="store_true")

    package = sub.add_parser("package", help="build a byte-reproducible release archive")
    package.add_argument("--repo-root", default=".")
    package.add_argument("--output", required=True)
    package.add_argument("--version", required=True)
    package.add_argument("--json", action="store_true")
    return parser


def _trace_check(args: argparse.Namespace) -> tuple[dict[str, Any], bool]:
    events = load_trace(args.trace)
    report = coverage_report(events)
    failures: list[str] = []
    if args.require_all_states and report["missing_states"]:
        failures.append("missing states: " + ", ".join(report["missing_states"]))
    if args.require_all_directions and report["missing_directions"]:
        failures.append("missing directions: " + ", ".join(report["missing_directions"]))
    report["errors"] = failures
    report["ok"] = not failures
    return report, not failures


def run(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            report = validate_pet_dir(args.pet_dir, strict=args.strict)
            _write(report, json_output=args.json)
            return 0 if report["ok"] else 1
        if args.command == "trace-check":
            report, ok = _trace_check(args)
            _write(report, json_output=args.json)
            return 0 if ok else 1
        if args.command == "plan":
            items = compile_frame_plan(load_trace(args.trace), args.fps)
            payload = {
                "ok": True,
                "fps": args.fps,
                "frames": [item.to_dict() for item in items],
            }
            if args.output:
                output_path = Path(args.output)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(
                    json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                payload["output"] = str(output_path.resolve())
            _write(payload, json_output=args.json)
            return 0
        if args.command == "render":
            plan = compile_frame_plan(load_trace(args.trace), args.fps)
            report = render_plan(
                args.pet_dir,
                plan,
                args.output,
                background=args.background,
                scale=args.scale,
            )
            _write(report, json_output=args.json)
            return 0
        if args.command == "diff":
            report = compare_pets(
                args.baseline,
                args.candidate,
                args.output_dir,
                policy=DiffPolicy(
                    channel_tolerance=args.channel_tolerance,
                    max_changed_cells=args.max_changed_cells,
                    max_cell_change_ratio=args.max_cell_change_ratio,
                    max_bbox_shift_px=args.max_bbox_shift_px,
                ),
            )
            _write(report, json_output=args.json)
            return 0 if report["ok"] else 1
        if args.command == "install":
            report = install_pet(args.source, codex_home=args.codex_home, dry_run=args.dry_run)
            _write(report, json_output=args.json)
            return 0
        if args.command == "uninstall":
            report = uninstall_pet(codex_home=args.codex_home, dry_run=args.dry_run)
            _write(report, json_output=args.json)
            return 0
        if args.command == "rollback":
            report = rollback_pet(codex_home=args.codex_home, dry_run=args.dry_run)
            _write(report, json_output=args.json)
            return 0
        if args.command == "doctor":
            report = doctor(args.source, codex_home=args.codex_home)
            _write(report, json_output=args.json)
            return 0 if report["ok"] else 1
        if args.command == "package":
            report = build_release_archive(args.repo_root, args.output, version=args.version)
            _write(report, json_output=args.json)
            return 0
    except (
        DiffError,
        TraceError,
        PetValidationError,
        RenderError,
        InstallError,
        PackageError,
        OSError,
    ) as exc:
        _write({"ok": False, "error": str(exc)}, json_output=True)
        return 2
    return 2


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
