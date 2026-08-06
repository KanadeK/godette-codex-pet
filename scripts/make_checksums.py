"""Write deterministic SHA-256 sums for release files."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    directory = args.directory.resolve()
    files = sorted(
        path for path in directory.iterdir() if path.is_file() and path.name != "SHA256SUMS.txt"
    )
    if not files:
        raise SystemExit(f"no release files found in {directory}")
    output = directory / "SHA256SUMS.txt"
    output.write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in files),
        encoding="utf-8",
        newline="\n",
    )
    print(output)
