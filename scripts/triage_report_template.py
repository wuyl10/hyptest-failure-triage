#!/usr/bin/env python3
"""Create an editable report.md skeleton from a hyptest triage snapshot."""

from __future__ import annotations

import argparse
import json
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


def select_cases(snapshot: list[dict[str, Any]], cases: list[str], action: str | None) -> list[dict[str, Any]]:
    if cases:
        wanted = set(cases)
        selected = [item for item in snapshot if item.get("case") in wanted]
        missing = sorted(wanted - {item.get("case") for item in selected})
        if missing:
            raise SystemExit(f"case(s) not found in snapshot: {', '.join(missing)}")
        return selected
    if action:
        selected = []
        for item in snapshot:
            status = latest_run(item).get("status", "no_run")
            tags = set(latest_run(item).get("evidence_tags") or [])
            if action == "selfcheck_fail" and status == "selfcheck_fail":
                selected.append(item)
            elif action == "waveform_report_update" and status == "selfcheck_fail" and "wave-run" in tags:
                selected.append(item)
            elif action == "mismatch" and status == "difftest_mismatch":
                selected.append(item)
            elif action == "stuck" and status == "true_stuck_evidence":
                selected.append(item)
            elif action == "passed" and status == "passed_good_trap":
                selected.append(item)
        return selected
    return snapshot[:1]


def md_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def source_ref(source: dict[str, Any]) -> str:
    if not source:
        return "NOT FOUND"
    return f"{source.get('path')}:{source.get('start_line')}-{source.get('end_line')}"


def write_report(
    path: Path,
    snapshot_path: Path,
    selected: list[dict[str, Any]],
    title: str,
    max_cases: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("TBD: one-paragraph conclusion. Choose one label: `selfcheck_bug`, `spike_or_model_limitation`, `suspected_rtl_bug`, `environment_blocked`, `true_stuck`, or `inconclusive`.")
    lines.append("")
    lines.append("## Cases")
    lines.append("")
    lines.append(f"- snapshot: `{snapshot_path}`")
    lines.append(f"- selected_cases: `{len(selected)}`")
    lines.append("")
    lines.append("| Case | Latest status | Evidence tags | Source | Latest run |")
    lines.append("| --- | --- | --- | --- | --- |")
    for item in selected:
        run = latest_run(item)
        source = item.get("source") or {}
        lines.append(
            "| "
            + " | ".join(
                md_escape(str(x))
                for x in [
                    item.get("case"),
                    run.get("status", "no_run"),
                    ",".join(run.get("evidence_tags") or []),
                    source_ref(source),
                    run.get("path", "NOT FOUND"),
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Scene And Intent")
    lines.append("")
    lines.append("TBD: explain privilege mode, address type, access width/alignment, seed path, execution path, handler path, and final check path. Preserve the original verification target.")
    lines.append("")
    lines.append("## Observed Failure")
    lines.append("")
    visible = selected[:max_cases]
    if len(selected) > max_cases:
        lines.append(f"TBD: `{len(selected) - max_cases}` additional selected cases are summarized in the table above; expand them if their evidence differs from the representative set.")
        lines.append("")
    for item in visible:
        run = latest_run(item)
        lines.append(f"### {item.get('case')}")
        lines.append("")
        lines.append(f"- latest_status: `{run.get('status', 'no_run')}`")
        lines.append(f"- evidence_tags: `{', '.join(run.get('evidence_tags') or [])}`")
        if run.get("key_lines"):
            lines.append("- run.log key lines:")
            for key_line in run.get("key_lines", [])[:20]:
                lines.append(f"  - `{key_line}`")
        else:
            lines.append("- run.log key lines: `none captured`")
        lines.append("")
    lines.append("## Source Analysis")
    lines.append("")
    if len(selected) > max_cases:
        lines.append(f"TBD: source details below are limited to `{max_cases}` representative cases; expand if remaining cases are not covered by the same helper/path.")
        lines.append("")
    for item in visible:
        source = item.get("source") or {}
        lines.append(f"### {item.get('case')}")
        lines.append("")
        lines.append(f"- source: `{source_ref(source)}`")
        lines.append(f"- exact_pbmt_hits: `{source.get('exact_pbmt_hits', 0)}`")
        if source.get("keyword_lines"):
            lines.append("- source keyword lines:")
            for line in source.get("keyword_lines", [])[:20]:
                lines.append(f"  - `{line}`")
        else:
            lines.append("- source keyword lines: `none captured`")
        lines.append("")
    lines.append("## Waveform Evidence")
    lines.append("")
    lines.append("TBD if waveform was used: include first useful bad cycle/time, key signals, expected vs actual data/control flow, and why later symptoms are secondary.")
    lines.append("")
    lines.append("## Classification")
    lines.append("")
    lines.append("TBD: state the selected taxonomy label and why alternatives were rejected. Be explicit about Spike/model limitation vs test selfcheck bug vs suspected RTL bug.")
    lines.append("")
    lines.append("## Action")
    lines.append("")
    lines.append("TBD: patch performed, report-only bug, manual/blocked decision, or required platform support. Do not weaken PMA/PBMT/IO/narrow-width intent.")
    lines.append("")
    lines.append("## Verification")
    lines.append("")
    lines.append("TBD: commands run, result log paths, PASS/FAIL/GOOD TRAP evidence, and list updates. Do not delete from failure lists without clean trusted evidence.")
    lines.append("")
    path.write_text("\n".join(lines))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an editable triage report template from snapshot JSON."
    )
    parser.add_argument("--snapshot-json", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--title", default="Hyptest triage report")
    parser.add_argument("--case", action="append", default=[], help="Specific case to include; repeatable")
    parser.add_argument(
        "--max-cases",
        type=int,
        default=5,
        help="Maximum selected cases to expand with detailed run/source evidence",
    )
    parser.add_argument(
        "--action",
        choices=["selfcheck_fail", "waveform_report_update", "mismatch", "stuck", "passed"],
        help="Select cases by broad latest status/action when --case is not used",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snapshot = load_snapshot(args.snapshot_json)
    selected = select_cases(snapshot, args.case, args.action)
    if not selected:
        raise SystemExit("no cases selected for report")
    write_report(args.out, args.snapshot_json, selected, args.title, max(args.max_cases, 1))
    print(f"report={args.out}")
    print(f"cases={len(selected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
