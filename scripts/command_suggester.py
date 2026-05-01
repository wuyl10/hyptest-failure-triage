#!/usr/bin/env python3
"""Suggest conservative next-step commands from a hyptest triage snapshot."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from env_paths import default_skill_dir, env_path, require_path

DEFAULT_HYPTEST_REPO = env_path("HYPTEST_REPO", "RVH_HYPTEST_REPO")
DEFAULT_LINKNAN_REPO = env_path("LINKNAN_HOME")
DEFAULT_SKILL_DIR = default_skill_dir(__file__)


def linknan_env_prechecks() -> list[str]:
    return [
        'test -n "${LINKNAN_HOME:-}" || { echo "missing LINKNAN_HOME"; exit 2; }',
        'test -n "${DIFFTEST_REF_SO:-}" || { echo "missing DIFFTEST_REF_SO"; exit 2; }',
    ]


def linknan_case_commands(case: str, jobs: int, timeout: int) -> list[str]:
    return [
        f"python3 compile_elf.py --plat linknan --include-commented --name {case}",
        f"python3 get_result.py --platform linknan --case {case} --jobs {jobs} --timeout {timeout}",
    ]


def load_snapshot(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(errors="ignore"))
    if not isinstance(data, list):
        raise SystemExit(f"snapshot JSON must contain a list: {path}")
    return data


def latest_run(item: dict[str, Any]) -> dict[str, Any]:
    runs = item.get("runs") or []
    return runs[0] if runs else {}


def choose_action(item: dict[str, Any]) -> str:
    run = latest_run(item)
    status = run.get("status", "no_run")
    tags = set(run.get("evidence_tags") or [])
    if status == "passed_good_trap":
        return "verify_remove"
    if status == "selfcheck_fail" and "wave-run" in tags:
        return "write_wave_report"
    if status == "selfcheck_fail":
        return "source_rerun"
    if status == "difftest_mismatch":
        return "difftest_debug"
    if status == "true_stuck_evidence":
        return "stuck_debug"
    if status == "timeout_inconclusive":
        return "long_run_check"
    return "inspect_artifacts"


def group_cases(snapshot: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in snapshot:
        groups[choose_action(item)].append(item)
    return groups


def first_cases(items: list[dict[str, Any]], limit: int) -> list[str]:
    return [item["case"] for item in items[:limit]]


def command_block(commands: list[str]) -> str:
    return "\n".join(commands)


def build_suggestions(
    snapshot: list[dict[str, Any]],
    snapshot_path: Path,
    hyptest_repo: Path,
    linknan_repo: Path,
    skill_dir: Path,
    limit: int,
    jobs: int,
    timeout: int,
) -> list[dict[str, Any]]:
    groups = group_cases(snapshot)
    suggestions: list[dict[str, Any]] = []
    report_dir = linknan_repo / "regress_logs"

    if groups.get("source_rerun"):
        cases = first_cases(groups["source_rerun"], limit)
        suggestions.append(
            {
                "action": "source_rerun",
                "reason": "Selfcheck failed without latest waveform evidence; inspect source intent and rerun representatives before patching.",
                "cases": cases,
                "commands": command_block(
                    [
                        f"cd {hyptest_repo}",
                        *linknan_env_prechecks(),
                        *[
                            command
                            for case in cases
                            for command in linknan_case_commands(case, jobs, timeout)
                        ],
                        "# Do not classify wall-time timeout alone as stuck.",
                    ]
                ),
            }
        )

    if groups.get("write_wave_report"):
        cases = first_cases(groups["write_wave_report"], limit)
        topic = "waveform_followup"
        suggestions.append(
            {
                "action": "write_wave_report",
                "reason": "Latest evidence already has FSDB/waveform; seed report.md and fill first-bad waveform conclusion.",
                "cases": cases,
                "commands": command_block(
                    [
                        f"python3 {skill_dir}/scripts/triage_report_template.py \\",
                        f"  --snapshot-json {snapshot_path} \\",
                        "  --action waveform_report_update \\",
                        f"  --max-cases {min(limit, 5)} \\",
                        f"  --title \"{topic} triage report\" \\",
                        f"  --out {report_dir}/{topic}/report.md",
                    ]
                ),
            }
        )

    if groups.get("difftest_debug"):
        cases = first_cases(groups["difftest_debug"], limit)
        suggestions.append(
            {
                "action": "difftest_debug",
                "reason": "Mismatch requires difftest-enabled evidence and model/platform-limitation check before suspected RTL bug.",
                "cases": cases,
                "commands": command_block(
                    [
                        f"cd {hyptest_repo}",
                        *linknan_env_prechecks(),
                        *[
                            command
                            for case in cases
                            for command in linknan_case_commands(case, jobs, timeout)
                        ],
                        "# Re-run with difftest enabled; do not use difftest-disabled waveform PASS to clear mismatch lists.",
                    ]
                ),
            }
        )

    if groups.get("stuck_debug"):
        cases = first_cases(groups["stuck_debug"], limit)
        suggestions.append(
            {
                "action": "stuck_debug",
                "reason": "Internal no-commit/watchdog evidence exists; inspect no-response/deadlock/progress path, not wall-clock timeout.",
                "cases": cases,
                "commands": command_block(
                    [
                        f"cd {hyptest_repo}",
                        *linknan_env_prechecks(),
                        *[
                            command
                            for case in cases
                            for command in linknan_case_commands(case, jobs, timeout)
                        ],
                        f"# Re-run RTL/LinkNan with timeout {timeout}s or more; only internal no-commit/watchdog/waveform evidence counts as stuck.",
                    ]
                ),
            }
        )

    if groups.get("long_run_check"):
        cases = first_cases(groups["long_run_check"], limit)
        suggestions.append(
            {
                "action": "long_run_check",
                "reason": "Timeout-only evidence is inconclusive; rerun longer or inspect progress prints/commit activity.",
                "cases": cases,
                "commands": command_block(
                    [
                        f"# Continue or rerun with timeout {timeout}s+; keep jobs <= {jobs}.",
                        "# Do not remove or classify as stuck until internal 50000 cycles no commit/watchdog appears.",
                    ]
                ),
            }
        )

    if groups.get("verify_remove"):
        suggestions.append(
            {
                "action": "verify_remove",
                "reason": "Clean GOOD TRAP candidates exist; dry-run list update with the correct list-kind before editing.",
                "cases": first_cases(groups["verify_remove"], limit),
                "commands": command_block(
                    [
                        f"python3 {skill_dir}/scripts/update_failure_list.py \\",
                        "  --list <failure-list> \\",
                        f"  --snapshot-json {snapshot_path} \\",
                        "  --list-kind selfcheck \\",
                        "  --dry-run --verbose-skips",
                    ]
                ),
            }
        )

    if groups.get("inspect_artifacts"):
        suggestions.append(
            {
                "action": "inspect_artifacts",
                "reason": "Cases lack a clear latest run status; inspect run artifacts or regenerate snapshot after rerun.",
                "cases": first_cases(groups["inspect_artifacts"], limit),
                "commands": command_block(
                    [
                        f"python3 {skill_dir}/scripts/triage_snapshot.py \\",
                        "  --list <failure-list> \\",
                        f"  --hyptest-repo {hyptest_repo} \\",
                        f"  --linknan-repo {linknan_repo} \\",
                        "  --md-out <topic>_snapshot.md \\",
                        "  --json-out <topic>_snapshot.json",
                    ]
                ),
            }
        )

    return suggestions


def write_json(path: Path, suggestions: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(suggestions, indent=2, ensure_ascii=False) + "\n")


def md_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def write_markdown(path: Path, snapshot_path: Path, suggestions: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# Hyptest Suggested Commands")
    lines.append("")
    lines.append(f"- snapshot: `{snapshot_path}`")
    lines.append(f"- suggestion_groups: `{len(suggestions)}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Action | Cases | Reason |")
    lines.append("| --- | ---: | --- |")
    for item in suggestions:
        lines.append(
            "| "
            + " | ".join(
                md_escape(str(x))
                for x in [item["action"], len(item["cases"]), item["reason"]]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Commands")
    lines.append("")
    for item in suggestions:
        lines.append(f"### {item['action']}")
        lines.append("")
        lines.append(f"- reason: {item['reason']}")
        lines.append(f"- cases: `{', '.join(item['cases'])}`")
        lines.append("")
        lines.append("```bash")
        lines.append(item["commands"])
        lines.append("```")
        lines.append("")
    path.write_text("\n".join(lines))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Suggest next-step commands from triage snapshot JSON.")
    parser.add_argument("--snapshot-json", type=Path, required=True)
    parser.add_argument(
        "--hyptest-repo",
        type=Path,
        default=DEFAULT_HYPTEST_REPO,
        help="riscv-hyp-tests repo path; defaults to HYPTEST_REPO or RVH_HYPTEST_REPO",
    )
    parser.add_argument(
        "--linknan-repo",
        type=Path,
        default=DEFAULT_LINKNAN_REPO,
        help="LinkNan repo path; defaults to LINKNAN_HOME",
    )
    parser.add_argument("--skill-dir", type=Path, default=DEFAULT_SKILL_DIR)
    parser.add_argument("--limit", type=int, default=5, help="Max cases per action group")
    parser.add_argument("--jobs", type=int, default=20, help="Recommended max parallel jobs")
    parser.add_argument("--timeout", type=int, default=900, help="Recommended minimum timeout seconds")
    parser.add_argument("--md-out", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    args.hyptest_repo = require_path(
        args.hyptest_repo,
        "--hyptest-repo",
        ("HYPTEST_REPO", "RVH_HYPTEST_REPO"),
        "hyptest repo",
    )
    args.linknan_repo = require_path(
        args.linknan_repo,
        "--linknan-repo",
        ("LINKNAN_HOME",),
        "LinkNan repo",
    )
    args.skill_dir = args.skill_dir.expanduser().resolve()
    return args


def main() -> int:
    args = parse_args()
    suggestions = build_suggestions(
        load_snapshot(args.snapshot_json),
        args.snapshot_json,
        args.hyptest_repo,
        args.linknan_repo,
        args.skill_dir,
        max(args.limit, 1),
        min(max(args.jobs, 1), 20),
        max(args.timeout, 900),
    )
    if args.json_out:
        write_json(args.json_out, suggestions)
    if args.md_out:
        write_markdown(args.md_out, args.snapshot_json, suggestions)
    if not args.json_out and not args.md_out:
        print(json.dumps(suggestions, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
