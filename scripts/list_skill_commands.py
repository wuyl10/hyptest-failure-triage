#!/usr/bin/env python3
"""Print common hyptest-failure-triage commands."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Command:
    group: str
    name: str
    description: str
    command: str


COMMANDS = [
    Command(
        "snapshot",
        "list-snapshot",
        "Create a conservative first-pass snapshot from an explicit failure-list file.",
        "python3 $HYPTEST_FAILURE_TRIAGE_SKILL_HOME/scripts/triage_snapshot.py --list <failure-list> "
        "--hyptest-repo \"$HYPTEST_HOME\" --linknan-repo \"$HYPTEST_LINKNAN_HOME\" "
        "--md-out <topic>_snapshot.md --json-out <topic>_snapshot.json",
    ),
    Command(
        "planning",
        "cluster",
        "Cluster snapshot cases by conservative observable features.",
        "python3 $HYPTEST_FAILURE_TRIAGE_SKILL_HOME/scripts/cluster_failures.py --snapshot-json <topic>_snapshot.json "
        "--mode coarse --md-out <topic>_clusters.md --json-out <topic>_clusters.json",
    ),
    Command(
        "planning",
        "plan",
        "Create an action-oriented triage plan from a snapshot.",
        "python3 $HYPTEST_FAILURE_TRIAGE_SKILL_HOME/scripts/triage_plan.py --snapshot-json <topic>_snapshot.json "
        "--md-out <topic>_plan.md --json-out <topic>_plan.json",
    ),
    Command(
        "planning",
        "suggest-commands",
        "Generate conservative next-step commands without executing them.",
        "python3 $HYPTEST_FAILURE_TRIAGE_SKILL_HOME/scripts/command_suggester.py --snapshot-json <topic>_snapshot.json "
        "--limit 5 --jobs 20 --timeout 900 "
        "--md-out <topic>_commands.md --json-out <topic>_commands.json",
    ),
    Command(
        "report",
        "case-report",
        "Generate an editable Chinese report.md skeleton for a representative case.",
        "python3 $HYPTEST_FAILURE_TRIAGE_SKILL_HOME/scripts/triage_report_template.py --snapshot-json <topic>_snapshot.json "
        "--case <case_name> --title '<topic> 失败分析报告' --out <report-dir>/<topic>/report.md",
    ),
    Command(
        "report",
        "action-report",
        "Generate a class-level Chinese report.md skeleton for a broad action group.",
        "python3 $HYPTEST_FAILURE_TRIAGE_SKILL_HOME/scripts/triage_report_template.py --snapshot-json <topic>_snapshot.json "
        "--action selfcheck_fail --max-cases 5 --title '<topic> 失败分析报告' "
        "--out <report-dir>/<topic>/report.md",
    ),
    Command(
        "report",
        "waveform-report-link",
        "Generate a Chinese report.md that cites waveform-debug's report.md.",
        "python3 $HYPTEST_FAILURE_TRIAGE_SKILL_HOME/scripts/triage_report_template.py --snapshot-json <topic>_snapshot.json "
        "--action waveform --title '<topic> 失败分析报告' "
        "--waveform-report <waveform-report-dir>/report.md "
        "--out <report-dir>/<topic>/report.md",
    ),
    Command(
        "list-update",
        "list-update-dry-run",
        "Preview safe removals from an explicit failure list.",
        "python3 $HYPTEST_FAILURE_TRIAGE_SKILL_HOME/scripts/update_failure_list.py --list <failure-list> "
        "--snapshot-json <topic>_snapshot.json --list-kind selfcheck --dry-run --verbose-skips",
    ),
    Command(
        "list-update",
        "mismatch-dry-run",
        "Preview safe removals from a difftest mismatch list; difftest-enabled evidence is required.",
        "python3 $HYPTEST_FAILURE_TRIAGE_SKILL_HOME/scripts/update_failure_list.py --list <mismatch-list> "
        "--snapshot-json <topic>_snapshot.json --list-kind mismatch --dry-run --verbose-skips",
    ),
    Command(
        "compare",
        "compare-snapshots",
        "Compare two snapshots after reruns or LinkNan/dependency updates.",
        "python3 $HYPTEST_FAILURE_TRIAGE_SKILL_HOME/scripts/compare_snapshots.py --old <old>_snapshot.json --new <new>_snapshot.json "
        "--md-out <topic>_compare.md --json-out <topic>_compare.json",
    ),
    Command(
        "validation",
        "selftest",
        "Run the bundled synthetic self-test suite.",
        "python3 $HYPTEST_FAILURE_TRIAGE_SKILL_HOME/scripts/selftest.py",
    ),
    Command(
        "validation",
        "log-pattern-eval",
        "Check realistic run.log / Spike snippet classifications.",
        "python3 $HYPTEST_FAILURE_TRIAGE_SKILL_HOME/scripts/eval_log_patterns.py",
    ),
    Command(
        "validation",
        "official-spike-eval",
        "Check official Spike known model-gap classifications.",
        "python3 $HYPTEST_FAILURE_TRIAGE_SKILL_HOME/scripts/eval_official_spike_patterns.py",
    ),
    Command(
        "maintenance",
        "readme-check",
        "Check README generated commands match list_skill_commands.py.",
        "python3 $HYPTEST_FAILURE_TRIAGE_SKILL_HOME/scripts/check_readme_commands.py",
    ),
    Command(
        "maintenance",
        "readme-update",
        "Refresh README generated command block from list_skill_commands.py.",
        "python3 $HYPTEST_FAILURE_TRIAGE_SKILL_HOME/scripts/update_readme_commands.py",
    ),
    Command(
        "maintenance",
        "resource-index-check",
        "Check resource_index.md covers references, scripts, fixtures, and README anchors.",
        "python3 $HYPTEST_FAILURE_TRIAGE_SKILL_HOME/scripts/check_resource_index.py",
    ),
    Command(
        "maintenance",
        "fixture-manifest-check",
        "Check fixture manifests match the log files on disk.",
        "python3 $HYPTEST_FAILURE_TRIAGE_SKILL_HOME/scripts/check_fixture_manifests.py",
    ),
]


def markdown() -> str:
    lines: list[str] = []
    groups = []
    for cmd in COMMANDS:
        if cmd.group not in groups:
            groups.append(cmd.group)
    for group in groups:
        lines.append(f"### {group}")
        lines.append("")
        for cmd in [c for c in COMMANDS if c.group == group]:
            lines.append(f"- `{cmd.name}`: {cmd.description}")
            lines.append("")
            lines.append("  ```bash")
            lines.append(f"  {cmd.command}")
            lines.append("  ```")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def text() -> str:
    width = max(len(cmd.name) for cmd in COMMANDS)
    lines: list[str] = []
    current_group = None
    for cmd in COMMANDS:
        if cmd.group != current_group:
            current_group = cmd.group
            lines.append(f"\n[{current_group}]")
        lines.append(f"{cmd.name:<{width}}  {cmd.description}")
        lines.append(f"  {cmd.command}")
    return "\n".join(lines).lstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--markdown", action="store_true", help="Emit Markdown command list.")
    args = parser.parse_args()

    if args.json:
        print(json.dumps([asdict(cmd) for cmd in COMMANDS], indent=2, ensure_ascii=False))
    elif args.markdown:
        print(markdown(), end="")
    else:
        print(text(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
