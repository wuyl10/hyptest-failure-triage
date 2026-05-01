#!/usr/bin/env python3
"""Safely remove resolved cases from a hyptest failure list.

Input is the JSON produced by triage_snapshot.py. A case is removable only when
its latest run is classified as passed_good_trap and satisfies the requested
trust policy. The script preserves comments, blank lines, and unknown lines.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def trusted_pass(run: dict, list_kind: str, allow_difftest_disabled: bool) -> tuple[bool, str]:
    if run.get("status") != "passed_good_trap":
        return False, "latest status is not passed_good_trap"
    bad_flags = [
        "has_failed_assert",
        "has_mismatch",
        "has_non_ignorable_error",
        "has_internal_stuck",
        "has_bad_trap",
    ]
    for flag in bad_flags:
        if run.get(flag):
            return False, f"latest run has {flag}"
    if list_kind == "mismatch" and not run.get("difftest_enabled"):
        if not allow_difftest_disabled:
            return False, "mismatch cleanup requires difftest-enabled evidence"
    return True, "trusted pass"


def load_passed_cases(
    snapshot: Path,
    list_kind: str,
    allow_difftest_disabled: bool,
) -> tuple[set[str], dict[str, str], dict[str, str]]:
    if not snapshot.exists():
        raise SystemExit(f"snapshot JSON not found: {snapshot}")
    data = json.loads(snapshot.read_text(errors="ignore"))
    passed: set[str] = set()
    skipped: dict[str, str] = {}
    pass_reasons: dict[str, str] = {}
    for item in data:
        runs = item.get("runs") or []
        if not runs:
            skipped[item["case"]] = "no run in snapshot"
            continue
        ok, reason = trusted_pass(runs[0], list_kind, allow_difftest_disabled)
        if ok:
            passed.add(item["case"])
            pass_reasons[item["case"]] = reason
        else:
            skipped[item["case"]] = reason
    return passed, skipped, pass_reasons


def update_list(path: Path, passed: set[str], dry_run: bool) -> tuple[list[str], list[str]]:
    if not path.exists():
        raise SystemExit(f"failure list not found: {path}")
    original = path.read_text(errors="ignore").splitlines(keepends=True)
    kept: list[str] = []
    removed: list[str] = []

    for line in original:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            case = stripped.split()[0]
            if case in passed:
                removed.append(case)
                continue
        kept.append(line)

    if not dry_run and removed:
        backup = path.with_suffix(path.suffix + ".bak")
        backup.write_text("".join(original))
        path.write_text("".join(kept))

    return removed, kept


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remove only latest passed_good_trap cases from a failure list."
    )
    parser.add_argument("--list", type=Path, required=True, help="Failure list to update")
    parser.add_argument(
        "--snapshot-json",
        type=Path,
        required=True,
        help="JSON produced by triage_snapshot.py",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show removable cases without editing the list",
    )
    parser.add_argument(
        "--list-kind",
        choices=["selfcheck", "stuck", "mismatch", "generic"],
        default="generic",
        help=(
            "Trust policy for removal. mismatch requires difftest-enabled latest pass; "
            "selfcheck/stuck/generic require a clean GOOD TRAP without failure flags."
        ),
    )
    parser.add_argument(
        "--allow-difftest-disabled",
        action="store_true",
        help="Allow difftest-disabled GOOD TRAP evidence even for --list-kind mismatch.",
    )
    parser.add_argument(
        "--verbose-skips",
        action="store_true",
        help="Print non-removable cases and the reason each one was skipped.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    passed, skipped, pass_reasons = load_passed_cases(
        args.snapshot_json,
        args.list_kind,
        args.allow_difftest_disabled,
    )
    removed, kept = update_list(args.list, passed, args.dry_run)
    print(f"list_kind={args.list_kind}")
    print(f"trusted_pass_in_snapshot={len(passed)}")
    print(f"skipped_in_snapshot={len(skipped)}")
    print(f"removed_from_list={len(removed)}")
    for case in removed:
        print(f"{case} # {pass_reasons.get(case, 'trusted pass')}")
    if args.verbose_skips and skipped:
        print("skipped_cases:")
        for case, reason in sorted(skipped.items()):
            print(f"{case} # {reason}")
    if args.dry_run:
        print("dry_run=true; list not modified")
    elif removed:
        print(f"backup={args.list.with_suffix(args.list.suffix + '.bak')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
