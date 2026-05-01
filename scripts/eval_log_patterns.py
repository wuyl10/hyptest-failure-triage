#!/usr/bin/env python3
"""Evaluate log classification fixtures against triage_snapshot parsers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from triage_snapshot import classify_log, extract_run_metadata


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    default_manifest = script_dir.parent / "fixtures" / "logs" / "manifest.json"
    parser = argparse.ArgumentParser(description="Evaluate realistic log classification fixtures.")
    parser.add_argument("--manifest", type=Path, default=default_manifest)
    parser.add_argument("--fail-fast", action="store_true")
    return parser.parse_args()


def load_manifest(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit(f"manifest must be a JSON list: {path}")
    return data


def main() -> int:
    args = parse_args()
    manifest = args.manifest.expanduser().resolve()
    base_dir = manifest.parent
    cases = load_manifest(manifest)
    passed = 0

    for index, item in enumerate(cases, 1):
        label = str(item["id"])
        log_path = base_dir / str(item["file"])
        text = log_path.read_text(encoding="utf-8", errors="ignore")
        status = classify_log(text)
        metadata = extract_run_metadata(log_path.parent, text)
        failures: list[str] = []

        expected_status = str(item["expected_status"])
        if status != expected_status:
            failures.append(f"expected status {expected_status}, got {status}")

        for key, expected_value in dict(item.get("expected_metadata", {})).items():
            actual_value = metadata.get(key)
            if actual_value != expected_value:
                failures.append(f"expected metadata {key}={expected_value!r}, got {actual_value!r}")

        expected_tags = set(item.get("expected_tags", []))
        actual_tags = set(metadata.get("evidence_tags", []))
        missing_tags = sorted(expected_tags - actual_tags)
        if missing_tags:
            failures.append(f"missing expected tags: {', '.join(missing_tags)}")

        if failures:
            print(f"FAIL [{index}/{len(cases)}] {label}")
            for failure in failures:
                print(f"  - {failure}")
            if args.fail_fast:
                return 1
            continue

        passed += 1
        print(f"PASS [{index}/{len(cases)}] {label} -> {status}")

    print(f"summary: {passed}/{len(cases)} passed")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
