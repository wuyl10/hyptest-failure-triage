#!/usr/bin/env python3
"""Create a first-pass hyptest failure triage snapshot.

This script is intentionally conservative: it does not decide final root cause.
It collects source/run-log evidence that the agent should inspect before
classifying selfcheck failures, difftest mismatches, or stuck cases.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from env_paths import env_path, require_path

DEFAULT_HYPTEST_REPO = env_path("HYPTEST_REPO", "RVH_HYPTEST_REPO")
DEFAULT_LINKNAN_REPO = env_path("LINKNAN_HOME")

SOURCE_KEYWORD_RE = re.compile(
    r"PBMT|Pbmt|\bpbmt\b|VSRWXPbmt|PTE_Pbmt|pbmt_hspt_to_x|"
    r"PMA|PMP|MMIO|\bIO\b|\bNC\b|cbo_|prefetch|sfence|fence|"
    r"phys_page_base|hs_page_base|vs_page_base|TEST_ASSERT|AI_ASSERT|"
    r"EXCEPT|excpt|cause|tval|sb\(|sh\(|sw\(|sd\(|lb\(|lbu\(|lh\(|lhu\(|lw\(|lwu\(|ld\("
)
EXACT_PBMT_RE = re.compile(
    r"PBMT|Pbmt|\bpbmt\b|VSRWXPbmt|PTE_Pbmt|pbmt_hspt_to_x|prepare_pbmt"
)
LOG_KEY_RE = re.compile(
    r"FAILED|ERROR|MISMATCH|mismatch|HIT GOOD TRAP|BAD TRAP|"
    r"50000|no commit|No commit|watchdog|Watchdog|assert|ASSERT|timeout|TIMEOUT|Fatal|FATAL|"
    r"disable diff-test|disable difftest|diff-test ref|reference model|Dumping FSDB|FSDB Waveform"
)
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
DIFFTEST_DISABLED_RE = re.compile(r"\bdisable[sd]?\s+diff-?test\b|\bdiff-?test\s+disabled\b", re.I)
DIFFTEST_ENABLED_RE = re.compile(
    r"diff-?test\s+ref\s+so|the reference model is|riscv64-spike-so|difftest.*spike",
    re.I,
)
FSDB_ENABLED_RE = re.compile(r"Dumping FSDB Waveform|FSDB Dumper|Create FSDB file|tb_top.*\.fsdb", re.I)
INTERNAL_STUCK_RE = re.compile(
    r"50000.*(?:no[- ]?commit|no forward progress)|(?:no[- ]?commit|no forward progress).*50000|watchdog",
    re.I,
)
MISMATCH_RE = re.compile(r"\b(?:MISMATCH|mismatch)\b")
NEGATED_MISMATCH_RE = re.compile(r"\b(?:no|without)\s+mismatch(?:es)?\b", re.I)
FAILED_RE = re.compile(r"\bFAILED\b")
NEGATED_FAILED_RE = re.compile(r"\b(?:no|without|zero)\s+failed\b|\bfailed\s*[:=]\s*0\b|\b0\s+failed\b", re.I)
BAD_TRAP_RE = re.compile(r"\bBAD\s+TRAP\b", re.I)
NEGATED_BAD_TRAP_RE = re.compile(r"\b(?:no|without)\s+bad\s+trap\b|\bbad\s+trap\s*[:=]\s*0\b|\b0\s+bad\s+traps?\b", re.I)


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def is_ignorable_error_line(line: str) -> bool:
    """Filter simulator/tool warnings that contain ERROR but are not test failure."""
    lowered = line.lower()
    return (
        "fsdb dumper" in lowered
        or "the simulator version is newer than the fsdb dumper version" in lowered
        or ("verdi" in lowered and "error" in lowered)
    )


def is_ignorable_error_at(lines: list[str], index: int) -> bool:
    """Filter single-line and multi-line tool banners that include ERROR.

    Some FSDB versions print a standalone "* ERROR -" line, then put the real
    "simulator version is newer than the FSDB dumper version" explanation on
    following lines. Treat that banner as a waveform tool warning, not a test
    failure.
    """
    line = lines[index]
    if is_ignorable_error_line(line):
        return True
    window = "\n".join(lines[max(0, index - 2) : min(len(lines), index + 6)]).lower()
    return (
        "fsdb dumper" in window
        and "simulator version is newer" in window
        and "error" in line.lower()
    )


def has_real_mismatch_line(line: str) -> bool:
    if not MISMATCH_RE.search(line):
        return False
    return NEGATED_MISMATCH_RE.search(line) is None


def has_real_failed_line(line: str) -> bool:
    if not FAILED_RE.search(line):
        return False
    return NEGATED_FAILED_RE.search(line) is None


def has_real_bad_trap_line(line: str) -> bool:
    if not BAD_TRAP_RE.search(line):
        return False
    return NEGATED_BAD_TRAP_RE.search(line) is None


@dataclass
class SourceHit:
    path: str
    start_line: int
    end_line: int
    exact_pbmt_hits: int
    keyword_lines: list[str]


@dataclass
class RunHit:
    path: str
    mtime: float
    has_run_log: bool
    status: str
    difftest_enabled: bool
    difftest_disabled: bool
    fsdb_enabled: bool
    wave_run: bool
    has_good_trap: bool
    has_bad_trap: bool
    has_failed_assert: bool
    has_mismatch: bool
    has_non_ignorable_error: bool
    has_internal_stuck: bool
    has_timeout: bool
    evidence_tags: list[str]
    key_lines: list[str]


@dataclass
class CaseSnapshot:
    case: str
    source: SourceHit | None
    runs: list[RunHit]
    preliminary_bucket: str
    notes: list[str]


@dataclass
class FunctionCandidate:
    path: Path
    match_start: int
    match_end: int


def read_cases(path: Path) -> list[str]:
    cases: list[str] = []
    for line in path.read_text(errors="ignore").splitlines():
        item = line.strip()
        if not item or item.startswith("#"):
            continue
        cases.append(item.split()[0])
    return cases


def source_files(repo: Path) -> list[Path]:
    files: list[Path] = []
    source_roots = [
        repo / "ai_test_cases",
        repo / "manual_test_cases",
    ]
    for root in source_roots:
        if root.exists():
            files.extend(sorted(root.rglob("*.c")))
    for root_file in sorted(repo.glob("*.c")):
        if root_file.name == "test_register.c":
            continue
        files.append(root_file)
    return files


def build_function_index(files: Iterable[Path]) -> dict[str, FunctionCandidate]:
    """Index bool test functions once instead of re-reading every source per case."""
    index: dict[str, FunctionCandidate] = {}
    pat = re.compile(r"\bbool\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
    for path in files:
        text = path.read_text(errors="ignore")
        for match in pat.finditer(text):
            name = match.group(1)
            # Keep the first definition if duplicate declarations exist.
            index.setdefault(name, FunctionCandidate(path, match.start(), match.end()))
    return index


def find_function(
    case: str,
    function_index: dict[str, FunctionCandidate],
    repo: Path,
) -> SourceHit | None:
    candidate = function_index.get(case)
    if not candidate:
        return None
    path = candidate.path
    text = path.read_text(errors="ignore")
    body_start = text.find("{", candidate.match_end)
    if body_start < 0:
        start_line = text[: candidate.match_start].count("\n") + 1
        return SourceHit(str(path.relative_to(repo)), start_line, start_line, 0, [])

    depth = 0
    body_end = len(text)
    for idx, ch in enumerate(text[body_start:], body_start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                body_end = idx + 1
                break

    start_line = text[: candidate.match_start].count("\n") + 1
    end_line = text[:body_end].count("\n") + 1
    body = text[candidate.match_start : body_end]
    keyword_lines: list[str] = []
    exact_pbmt_hits = 0
    for lineno, line in enumerate(body.splitlines(), start_line):
        stripped = line.strip()
        if EXACT_PBMT_RE.search(stripped):
            exact_pbmt_hits += 1
        if SOURCE_KEYWORD_RE.search(stripped):
            if len(stripped) > 180:
                stripped = stripped[:177] + "..."
            keyword_lines.append(f"L{lineno}: {stripped}")
    return SourceHit(
        str(path.relative_to(repo)),
        start_line,
        end_line,
        exact_pbmt_hits,
        keyword_lines[:40],
    )


def classify_log(text: str) -> str:
    clean_lines = [strip_ansi(line) for line in text.splitlines()]
    lower = "\n".join(clean_lines).lower()
    has_good = "hit good trap" in lower
    has_bad = any(has_real_bad_trap_line(line) for line in clean_lines)
    has_failed = any(has_real_failed_line(line) for line in clean_lines)
    has_mismatch = any(has_real_mismatch_line(line) for line in clean_lines)
    has_error = any(
        (re.search(r"\b(ERROR|FATAL|Fatal)\b", line) is not None)
        and not is_ignorable_error_at(clean_lines, index)
        for index, line in enumerate(clean_lines)
    )
    has_stuck = INTERNAL_STUCK_RE.search("\n".join(clean_lines)) is not None
    has_timeout = "timeout" in lower or "timed out" in lower

    if has_stuck:
        return "true_stuck_evidence"
    if has_mismatch:
        return "difftest_mismatch"
    if has_bad:
        return "bad_trap"
    if has_good and has_failed:
        return "selfcheck_fail"
    if has_good and not has_failed and not has_error:
        return "passed_good_trap"
    if has_timeout:
        return "timeout_inconclusive"
    if has_failed or has_error:
        return "failed_or_error"
    return "unknown"


def extract_run_metadata(run_dir: Path, text: str) -> dict[str, object]:
    clean = "\n".join(strip_ansi(line) for line in text.splitlines())
    lower = clean.lower()
    difftest_disabled = DIFFTEST_DISABLED_RE.search(clean) is not None
    difftest_enabled = (DIFFTEST_ENABLED_RE.search(clean) is not None) and not difftest_disabled
    fsdb_enabled = FSDB_ENABLED_RE.search(clean) is not None
    wave_run = run_dir.name.startswith("wave_") or fsdb_enabled
    has_good_trap = "hit good trap" in lower
    clean_lines = clean.splitlines()
    has_bad_trap = any(has_real_bad_trap_line(line) for line in clean_lines)
    has_failed_assert = any(has_real_failed_line(line) for line in clean_lines)
    has_mismatch = any(has_real_mismatch_line(line) for line in clean_lines)
    has_non_ignorable_error = any(
        (re.search(r"\b(ERROR|FATAL|Fatal)\b", line) is not None)
        and not is_ignorable_error_at(clean_lines, index)
        for index, line in enumerate(clean_lines)
    )
    has_internal_stuck = INTERNAL_STUCK_RE.search(clean) is not None
    has_timeout = "timeout" in lower or "timed out" in lower

    evidence_tags: list[str] = []
    if difftest_enabled:
        evidence_tags.append("difftest-enabled")
    elif difftest_disabled:
        evidence_tags.append("difftest-disabled")
    else:
        evidence_tags.append("difftest-unknown")
    if fsdb_enabled:
        evidence_tags.append("fsdb")
    if wave_run:
        evidence_tags.append("wave-run")
    if has_internal_stuck:
        evidence_tags.append("internal-stuck")
    if has_timeout and not has_internal_stuck:
        evidence_tags.append("timeout-only")
    if has_good_trap and not any([has_failed_assert, has_mismatch, has_non_ignorable_error, has_internal_stuck]):
        evidence_tags.append("clean-good-trap")

    return {
        "difftest_enabled": difftest_enabled,
        "difftest_disabled": difftest_disabled,
        "fsdb_enabled": fsdb_enabled,
        "wave_run": wave_run,
        "has_good_trap": has_good_trap,
        "has_bad_trap": has_bad_trap,
        "has_failed_assert": has_failed_assert,
        "has_mismatch": has_mismatch,
        "has_non_ignorable_error": has_non_ignorable_error,
        "has_internal_stuck": has_internal_stuck,
        "has_timeout": has_timeout,
        "evidence_tags": evidence_tags,
    }


def parse_run_log(run_dir: Path) -> RunHit:
    run_log = run_dir / "run.log"
    if not run_log.exists():
        return RunHit(
            str(run_dir),
            run_dir.stat().st_mtime,
            False,
            "no_run_log",
            False,
            False,
            False,
            run_dir.name.startswith("wave_"),
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            ["no-run-log"],
            [],
        )

    text = run_log.read_text(errors="ignore")
    metadata = extract_run_metadata(run_dir, text)
    clean_log_lines = [strip_ansi(line).strip() for line in text.splitlines()]
    key_lines: list[str] = []
    for lineno, stripped_clean in enumerate(clean_log_lines, 1):
        if LOG_KEY_RE.search(stripped_clean):
            if is_ignorable_error_at(clean_log_lines, lineno - 1):
                continue
            if MISMATCH_RE.search(stripped_clean) and not has_real_mismatch_line(stripped_clean):
                continue
            if FAILED_RE.search(stripped_clean) and not has_real_failed_line(stripped_clean):
                continue
            if BAD_TRAP_RE.search(stripped_clean) and not has_real_bad_trap_line(stripped_clean):
                continue
            stripped = stripped_clean
            if len(stripped) > 220:
                stripped = stripped[:217] + "..."
            key_lines.append(f"L{lineno}: {stripped}")
            if len(key_lines) >= 60:
                break

    return RunHit(
        str(run_dir),
        run_dir.stat().st_mtime,
        True,
        classify_log(text),
        bool(metadata["difftest_enabled"]),
        bool(metadata["difftest_disabled"]),
        bool(metadata["fsdb_enabled"]),
        bool(metadata["wave_run"]),
        bool(metadata["has_good_trap"]),
        bool(metadata["has_bad_trap"]),
        bool(metadata["has_failed_assert"]),
        bool(metadata["has_mismatch"]),
        bool(metadata["has_non_ignorable_error"]),
        bool(metadata["has_internal_stuck"]),
        bool(metadata["has_timeout"]),
        list(metadata["evidence_tags"]),
        key_lines,
    )


def build_run_index(cases: list[str], simv_dir: Path) -> dict[str, list[Path]]:
    """Index run directories by exact case name in dir name or run.log header.

    LinkNan/get_result may truncate long directory names and append a hash, so
    exact directory substring matching misses many valid artifacts. Reading a
    small run.log prefix is usually enough because the test harness prints the
    case name near the beginning.
    """
    index: dict[str, list[Path]] = {case: [] for case in cases}
    if not simv_dir.exists():
        return index

    def dir_name_matches_case(name: str, case: str) -> bool:
        # Common LinkNan dirs are either exactly the case name or have a
        # runner/wave prefix ending with "_<case>". Avoid generic substring
        # matches so short case names do not consume longer case artifacts.
        return name == case or name.endswith("_" + case)

    def log_prefix_matches_case(prefix: str, case: str) -> bool:
        # The harness normally prints the case name on its own line. Prefer this
        # exact-line match over substring matching because test names are long
        # identifiers and often share prefixes.
        for line in prefix.splitlines():
            if strip_ansi(line).strip() == case:
                return True
        return False

    dirs = [p for p in simv_dir.iterdir() if p.is_dir()]
    for run_dir in dirs:
        matched: set[str] = {
            case for case in cases if dir_name_matches_case(run_dir.name, case)
        }
        if not matched:
            run_log = run_dir / "run.log"
            if run_log.exists():
                try:
                    prefix = run_log.read_text(errors="ignore")[:65536]
                except OSError:
                    prefix = ""
                matched = {
                    case for case in cases if log_prefix_matches_case(prefix, case)
                }
        for case in matched:
            index[case].append(run_dir)

    for case in cases:
        index[case].sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return index


def find_runs(case: str, run_index: dict[str, list[Path]], max_runs: int) -> list[RunHit]:
    return [parse_run_log(p) for p in run_index.get(case, [])[:max_runs]]


def choose_bucket(source: SourceHit | None, runs: list[RunHit]) -> tuple[str, list[str]]:
    notes: list[str] = []
    if not source:
        notes.append("source function not found")
    elif source.exact_pbmt_hits:
        notes.append(f"source has {source.exact_pbmt_hits} exact PBMT keyword hits")

    if not runs:
        notes.append("no LinkNan simv run directory found")
        return "no_run_artifact", notes

    latest = runs[0]
    status = latest.status
    if latest.difftest_disabled:
        notes.append("latest run has difftest disabled; good for RTL-only/selfcheck evidence, not mismatch cleanup")
    elif latest.difftest_enabled:
        notes.append("latest run has difftest enabled")
    elif latest.has_run_log:
        notes.append("latest run difftest mode unknown")
    if latest.fsdb_enabled:
        notes.append("latest run has FSDB/waveform enabled")
    if status == "true_stuck_evidence":
        return "true_stuck_candidate", notes
    if status == "difftest_mismatch":
        return "mismatch_needs_model_check", notes
    if status == "selfcheck_fail":
        return "selfcheck_needs_source_or_wave_check", notes
    if status == "passed_good_trap":
        return "already_passed_candidate_remove_if_listed", notes
    if status == "timeout_inconclusive":
        return "timeout_not_stuck_without_internal_evidence", notes
    return status, notes


def build_snapshots(args: argparse.Namespace) -> list[CaseSnapshot]:
    cases = read_cases(args.list)
    files = source_files(args.hyptest_repo)
    function_index = build_function_index(files)
    run_index = build_run_index(cases, args.simv_dir)
    snapshots: list[CaseSnapshot] = []
    for case in cases:
        source = find_function(case, function_index, args.hyptest_repo)
        runs = find_runs(case, run_index, args.max_runs)
        bucket, notes = choose_bucket(source, runs)
        snapshots.append(CaseSnapshot(case, source, runs, bucket, notes))
    return snapshots


def write_json(path: Path, snapshots: list[CaseSnapshot]) -> None:
    data = [asdict(s) for s in snapshots]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def md_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def write_markdown(path: Path, snapshots: list[CaseSnapshot], args: argparse.Namespace) -> None:
    lines: list[str] = []
    lines.append("# Hyptest Failure Triage Snapshot")
    lines.append("")
    lines.append("## Inputs")
    lines.append("")
    lines.append(f"- list: `{args.list}`")
    lines.append(f"- hyptest_repo: `{args.hyptest_repo}`")
    lines.append(f"- simv_dir: `{args.simv_dir}`")
    lines.append(f"- cases: `{len(snapshots)}`")
    lines.append("")
    lines.append("## Summary Table")
    lines.append("")
    lines.append("| Case | Source | Latest status | Evidence tags | Preliminary bucket | PBMT hits | Notes |")
    lines.append("| --- | --- | --- | --- | --- | ---: | --- |")
    for snap in snapshots:
        if snap.source:
            source = f"{snap.source.path}:{snap.source.start_line}"
            pbmt_hits = snap.source.exact_pbmt_hits
        else:
            source = "NOT FOUND"
            pbmt_hits = 0
        latest_status = snap.runs[0].status if snap.runs else "no_run"
        evidence_tags = ",".join(snap.runs[0].evidence_tags) if snap.runs else "no-run"
        notes = "; ".join(snap.notes)
        lines.append(
            "| "
            + " | ".join(
                md_escape(str(x))
                for x in [
                    snap.case,
                    source,
                    latest_status,
                    evidence_tags,
                    snap.preliminary_bucket,
                    pbmt_hits,
                    notes,
                ]
            )
            + " |"
        )
    lines.append("")

    lines.append("## Per-Case Evidence")
    lines.append("")
    for snap in snapshots:
        lines.append(f"### {snap.case}")
        lines.append("")
        lines.append(f"- preliminary_bucket: `{snap.preliminary_bucket}`")
        if snap.source:
            lines.append(
                f"- source: `{snap.source.path}:{snap.source.start_line}-{snap.source.end_line}`"
            )
            lines.append(f"- exact_pbmt_hits: `{snap.source.exact_pbmt_hits}`")
            if snap.source.keyword_lines:
                lines.append("- source keyword lines:")
                for item in snap.source.keyword_lines[:20]:
                    lines.append(f"  - `{item}`")
        else:
            lines.append("- source: `NOT FOUND`")
        if snap.runs:
            latest = snap.runs[0]
            lines.append(f"- latest_run: `{latest.path}`")
            lines.append(f"- latest_status: `{latest.status}`")
            lines.append(f"- evidence_tags: `{', '.join(latest.evidence_tags)}`")
            lines.append(
                "- run_flags: "
                f"`difftest_enabled={latest.difftest_enabled}`, "
                f"`difftest_disabled={latest.difftest_disabled}`, "
                f"`fsdb_enabled={latest.fsdb_enabled}`, "
                f"`wave_run={latest.wave_run}`, "
                f"`has_good_trap={latest.has_good_trap}`, "
                f"`has_failed_assert={latest.has_failed_assert}`, "
                f"`has_mismatch={latest.has_mismatch}`, "
                f"`has_internal_stuck={latest.has_internal_stuck}`, "
                f"`has_timeout={latest.has_timeout}`"
            )
            if latest.key_lines:
                lines.append("- run.log key lines:")
                for item in latest.key_lines[:20]:
                    lines.append(f"  - `{item}`")
            if len(snap.runs) > 1:
                lines.append("- recent_runs:")
                for idx, run in enumerate(snap.runs[:3], 1):
                    lines.append(
                        f"  - `{idx}` `{run.status}` `{', '.join(run.evidence_tags)}` `{run.path}`"
                    )
                    for item in run.key_lines[:5]:
                        lines.append(f"    - `{item}`")
        else:
            lines.append("- latest_run: `NOT FOUND`")
        if snap.notes:
            lines.append("- notes:")
            for note in snap.notes:
                lines.append(f"  - {note}")
        lines.append("")

    path.write_text("\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a conservative first-pass snapshot for hyptest failure triage."
    )
    parser.add_argument("--list", type=Path, required=True, help="Failure list file")
    parser.add_argument(
        "--hyptest-repo",
        type=Path,
        default=DEFAULT_HYPTEST_REPO,
        help="riscv-hyp-tests-nhv5.1 repo path; defaults to HYPTEST_REPO or RVH_HYPTEST_REPO",
    )
    parser.add_argument(
        "--linknan-repo",
        type=Path,
        default=DEFAULT_LINKNAN_REPO,
        help="LinkNan repo path; defaults to LINKNAN_HOME",
    )
    parser.add_argument(
        "--simv-dir",
        type=Path,
        default=None,
        help="LinkNan simv directory; defaults to <linknan-repo>/sim/simv",
    )
    parser.add_argument(
        "--max-runs",
        type=int,
        default=3,
        help="Maximum matching run directories to inspect per case",
    )
    parser.add_argument("--json-out", type=Path, help="Optional JSON output")
    parser.add_argument("--md-out", type=Path, help="Optional Markdown output")
    args = parser.parse_args()
    args.hyptest_repo = require_path(
        args.hyptest_repo,
        "--hyptest-repo",
        ("HYPTEST_REPO", "RVH_HYPTEST_REPO"),
        "hyptest repo",
    )
    if args.simv_dir is None:
        args.linknan_repo = require_path(
            args.linknan_repo,
            "--linknan-repo",
            ("LINKNAN_HOME",),
            "LinkNan repo",
        )
        args.simv_dir = args.linknan_repo / "sim" / "simv"
    else:
        args.simv_dir = args.simv_dir.expanduser().resolve()
        if args.linknan_repo is not None:
            args.linknan_repo = args.linknan_repo.expanduser().resolve()
    return args


def main() -> int:
    args = parse_args()
    snapshots = build_snapshots(args)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.json_out, snapshots)
    if args.md_out:
        args.md_out.parent.mkdir(parents=True, exist_ok=True)
        write_markdown(args.md_out, snapshots, args)
    if not args.json_out and not args.md_out:
        print(json.dumps([asdict(s) for s in snapshots], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
