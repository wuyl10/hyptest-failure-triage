#!/usr/bin/env python3
"""Check fixture manifest files match the log files on disk."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
FIXTURES_DIR = SKILL_DIR / "fixtures"


def rel(path: Path) -> str:
    return path.relative_to(SKILL_DIR).as_posix()


def load_manifest(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{rel(path)} is not valid JSON: {exc}") from exc
    if not isinstance(data, list):
        raise ValueError(f"{rel(path)} must be a JSON list")
    for index, item in enumerate(data, 1):
        if not isinstance(item, dict):
            raise ValueError(f"{rel(path)} entry {index} must be an object")
        for key in ("id", "file"):
            if key not in item or not isinstance(item[key], str) or not item[key]:
                raise ValueError(f"{rel(path)} entry {index} missing non-empty string {key!r}")
    return data


def check_manifest(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        entries = load_manifest(path)
    except ValueError as exc:
        return [str(exc)]

    fixture_dir = path.parent
    ids: set[str] = set()
    files: set[str] = set()

    for item in entries:
        item_id = str(item["id"])
        filename = str(item["file"])
        if item_id in ids:
            errors.append(f"{rel(path)} duplicate id {item_id!r}")
        ids.add(item_id)
        if filename in files:
            errors.append(f"{rel(path)} duplicate file {filename!r}")
        files.add(filename)

        target = fixture_dir / filename
        if not target.exists():
            errors.append(f"{rel(path)} references missing file {filename!r}")
        elif not target.is_file():
            errors.append(f"{rel(path)} references non-file {filename!r}")

    log_files = {p.name for p in fixture_dir.glob("*.log")}
    orphan_logs = sorted(log_files - files)
    for filename in orphan_logs:
        errors.append(f"{rel(path)} does not list log file {filename!r}")

    extra_files = sorted(files - log_files)
    for filename in extra_files:
        errors.append(f"{rel(path)} lists non-log file {filename!r}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        action="append",
        type=Path,
        help="Manifest to check. Defaults to fixtures/*/manifest.json.",
    )
    args = parser.parse_args()

    manifests = args.manifest or sorted(FIXTURES_DIR.glob("*/manifest.json"))
    if not manifests:
        print("no fixture manifests found", file=sys.stderr)
        return 1

    errors: list[str] = []
    for manifest in manifests:
        errors.extend(check_manifest(manifest.expanduser().resolve()))

    if errors:
        print("fixture manifest check failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(f"fixture-manifest-check passed ({len(manifests)} manifests)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
