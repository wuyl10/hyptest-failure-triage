#!/usr/bin/env python3
"""Generate an action-oriented plan from a hyptest triage snapshot."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_snapshot(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(errors="ignore"))
    if not isinstance(data, list):
        raise SystemExit(f"snapshot JSON must contain a list: {path}")
    return data


def latest_run(item: dict[str, Any]) -> dict[str, Any]:
    runs = item.get("runs") or []
    return runs[0] if runs else {}


def classify_action(item: dict[str, Any]) -> tuple[str, str]:
    run = latest_run(item)
    status = run.get("status", "no_run")
    bucket = item.get("preliminary_bucket", "unknown")
    source = item.get("source") or {}
    has_pbmt = bool(source.get("exact_pbmt_hits"))
    tags = set(run.get("evidence_tags") or [])

    if status == "passed_good_trap":
        if run.get("has_failed_assert") or run.get("has_mismatch") or run.get("has_internal_stuck"):
            return "needs_manual_review", "GOOD TRAP has contradictory failure flags"
        if run.get("difftest_disabled"):
            return "remove_candidate", "clean GOOD TRAP with difftest disabled; OK for selfcheck/stuck cleanup, not mismatch cleanup"
        return "remove_candidate", "clean GOOD TRAP; verify list-kind trust policy before removal"
    if status == "true_stuck_evidence":
        return "stuck_debug", "internal no-commit/watchdog evidence present"
    if status == "difftest_mismatch":
        if has_pbmt:
            return "mismatch_model_check", "PBMT/PMA source tags; check Spike/platform model before RTL bug"
        return "mismatch_debug", "difftest mismatch on latest run"
    if status == "selfcheck_fail":
        if "wave-run" in tags:
            return "waveform_report_update", "latest failing evidence includes waveform/FSDB"
        return "source_or_rerun", "selfcheck failed; inspect source intent and rerun representative"
    if status == "timeout_inconclusive":
        return "long_run_inconclusive", "timeout without internal stuck evidence"
    if bucket == "no_run_artifact" or status in {"no_run", "no_run_log"}:
        return "needs_run_artifact", "no usable latest run.log found"
    return "needs_manual_review", f"unclassified status={status}"


def summarize(snapshot: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    reasons: dict[str, str] = {}
    for item in snapshot:
        action, reason = classify_action(item)
        groups[action].append(item)
        reasons.setdefault(action, reason)

    order = [
        "remove_candidate",
        "source_or_rerun",
        "waveform_report_update",
        "mismatch_model_check",
        "mismatch_debug",
        "stuck_debug",
        "long_run_inconclusive",
        "needs_run_artifact",
        "needs_manual_review",
    ]
    result: list[dict[str, Any]] = []
    for action in order:
        items = groups.get(action, [])
        if not items:
            continue
        result.append(
            {
                "action": action,
                "size": len(items),
                "reason": reasons[action],
                "cases": [item["case"] for item in items],
            }
        )
    return result


def write_json(path: Path, plan: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")


def md_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def write_markdown(path: Path, snapshot_path: Path, plan: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# Hyptest Triage Action Plan")
    lines.append("")
    lines.append(f"- snapshot: `{snapshot_path}`")
    lines.append(f"- groups: `{len(plan)}`")
    lines.append(f"- cases: `{sum(group['size'] for group in plan)}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Action | Size | Reason |")
    lines.append("| --- | ---: | --- |")
    for group in plan:
        lines.append(
            "| "
            + " | ".join(
                md_escape(str(x))
                for x in [group["action"], group["size"], group["reason"]]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Cases")
    lines.append("")
    for group in plan:
        lines.append(f"### {group['action']}")
        lines.append("")
        lines.append(f"- size: `{group['size']}`")
        lines.append(f"- reason: {group['reason']}")
        lines.append("- cases:")
        for case in group["cases"]:
            lines.append(f"  - `{case}`")
        lines.append("")
    path.write_text("\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create an action-oriented plan from triage_snapshot.py JSON output."
    )
    parser.add_argument("--snapshot-json", type=Path, required=True)
    parser.add_argument("--md-out", type=Path)
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = summarize(load_snapshot(args.snapshot_json))
    if args.json_out:
        write_json(args.json_out, plan)
    if args.md_out:
        write_markdown(args.md_out, args.snapshot_json, plan)
    if not args.json_out and not args.md_out:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
