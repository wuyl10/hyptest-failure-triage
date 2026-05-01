#!/usr/bin/env python3
"""Evaluate official-Spike known-pattern fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from known_pattern_classifier import classify_official_spike_pattern


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    default_manifest = script_dir.parent / "fixtures" / "official_spike" / "manifest.json"
    parser = argparse.ArgumentParser(description="Evaluate official-Spike known-pattern fixtures.")
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
        result = classify_official_spike_pattern(text, case_name=str(item.get("case_name", "")))
        failures: list[str] = []

        expected_bucket = str(item["expected_bucket"])
        if result.bucket != expected_bucket:
            failures.append(f"expected bucket {expected_bucket}, got {result.bucket}")

        expected_tags = set(item.get("expected_tags", []))
        missing_tags = sorted(expected_tags - set(result.tags))
        if missing_tags:
            failures.append(f"missing expected tags: {', '.join(missing_tags)}")

        if failures:
            print(f"FAIL [{index}/{len(cases)}] {label}")
            for failure in failures:
                print(f"  - {failure}")
            print(f"  reason: {result.reason}")
            if args.fail_fast:
                return 1
            continue

        passed += 1
        print(f"PASS [{index}/{len(cases)}] {label} -> {result.bucket}")

    print(f"summary: {passed}/{len(cases)} passed")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
