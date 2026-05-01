#!/usr/bin/env python3
"""Compare two hyptest triage snapshots and report status/evidence changes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_snapshot(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(errors="ignore"))
    if not isinstance(data, list):
        raise SystemExit(f"snapshot JSON must contain a list: {path}")
    result: dict[str, dict[str, Any]] = {}
    for item in data:
        case = item.get("case")
        if not case:
            continue
        result[case] = item
    return result


def latest_run(item: dict[str, Any] | None) -> dict[str, Any]:
    if not item:
        return {}
    runs = item.get("runs") or []
    return runs[0] if runs else {}


def source_ref(item: dict[str, Any] | None) -> str:
    source = (item or {}).get("source") or {}
    if not source:
        return "NOT FOUND"
    return f"{source.get('path')}:{source.get('start_line')}"


def run_signature(item: dict[str, Any] | None) -> dict[str, Any]:
    run = latest_run(item)
    return {
        "status": run.get("status", "no_run"),
        "evidence_tags": run.get("evidence_tags") or [],
        "path": run.get("path", "NOT FOUND"),
        "has_failed_assert": bool(run.get("has_failed_assert")),
        "has_mismatch": bool(run.get("has_mismatch")),
        "has_internal_stuck": bool(run.get("has_internal_stuck")),
        "difftest_enabled": bool(run.get("difftest_enabled")),
        "difftest_disabled": bool(run.get("difftest_disabled")),
    }


def change_record(case: str, old: dict[str, Any] | None, new: dict[str, Any] | None, kind: str) -> dict[str, Any]:
    old_sig = run_signature(old)
    new_sig = run_signature(new)
    return {
        "case": case,
        "kind": kind,
        "old_status": old_sig["status"],
        "new_status": new_sig["status"],
        "old_tags": old_sig["evidence_tags"],
        "new_tags": new_sig["evidence_tags"],
        "old_run": old_sig["path"],
        "new_run": new_sig["path"],
        "source": source_ref(new or old),
    }


def compare(old: dict[str, dict[str, Any]], new: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    old_cases = set(old)
    new_cases = set(new)

    for case in sorted(new_cases - old_cases):
        changes.append(change_record(case, None, new[case], "added_case"))
    for case in sorted(old_cases - new_cases):
        changes.append(change_record(case, old[case], None, "removed_case"))

    for case in sorted(old_cases & new_cases):
        old_sig = run_signature(old[case])
        new_sig = run_signature(new[case])
        if old_sig["status"] != new_sig["status"]:
            changes.append(change_record(case, old[case], new[case], "status_changed"))
        elif old_sig["evidence_tags"] != new_sig["evidence_tags"]:
            changes.append(change_record(case, old[case], new[case], "evidence_changed"))
        elif old_sig["path"] != new_sig["path"]:
            changes.append(change_record(case, old[case], new[case], "latest_run_changed"))

    order = {
        "added_case": 0,
        "removed_case": 1,
        "status_changed": 2,
        "evidence_changed": 3,
        "latest_run_changed": 4,
    }
    changes.sort(key=lambda item: (order.get(item["kind"], 99), item["case"]))
    return changes


def summarize(changes: list[dict[str, Any]]) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in changes:
        result[item["kind"]] = result.get(item["kind"], 0) + 1
    return result


def write_json(path: Path, changes: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"summary": summarize(changes), "changes": changes}, indent=2, ensure_ascii=False) + "\n")


def md_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def write_markdown(path: Path, old_path: Path, new_path: Path, changes: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = summarize(changes)
    lines: list[str] = []
    lines.append("# Hyptest Snapshot Comparison")
    lines.append("")
    lines.append(f"- old_snapshot: `{old_path}`")
    lines.append(f"- new_snapshot: `{new_path}`")
    lines.append(f"- total_changes: `{len(changes)}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Kind | Count |")
    lines.append("| --- | ---: |")
    for kind in ["added_case", "removed_case", "status_changed", "evidence_changed", "latest_run_changed"]:
        lines.append(f"| {kind} | {summary.get(kind, 0)} |")
    lines.append("")
    lines.append("## Changes")
    lines.append("")
    if not changes:
        lines.append("No case/status/evidence/latest-run changes detected.")
    else:
        lines.append("| Kind | Case | Old status | New status | Old tags | New tags | Source |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for item in changes:
            lines.append(
                "| "
                + " | ".join(
                    md_escape(str(x))
                    for x in [
                        item["kind"],
                        item["case"],
                        item["old_status"],
                        item["new_status"],
                        ",".join(item["old_tags"]),
                        ",".join(item["new_tags"]),
                        item["source"],
                    ]
                )
                + " |"
            )
    lines.append("")
    path.write_text("\n".join(lines))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two triage_snapshot.py JSON outputs.")
    parser.add_argument("--old", type=Path, required=True, help="Older snapshot JSON")
    parser.add_argument("--new", type=Path, required=True, help="Newer snapshot JSON")
    parser.add_argument("--md-out", type=Path)
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    changes = compare(load_snapshot(args.old), load_snapshot(args.new))
    if args.json_out:
        write_json(args.json_out, changes)
    if args.md_out:
        write_markdown(args.md_out, args.old, args.new, changes)
    if not args.json_out and not args.md_out:
        print(json.dumps({"summary": summarize(changes), "changes": changes}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
