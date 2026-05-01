#!/usr/bin/env python3
"""Self-test the hyptest-failure-triage helper scripts with synthetic data."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
TRIAGE = SCRIPT_DIR / "triage_snapshot.py"
CLUSTER = SCRIPT_DIR / "cluster_failures.py"
UPDATE = SCRIPT_DIR / "update_failure_list.py"
PLAN = SCRIPT_DIR / "triage_plan.py"
REPORT_TEMPLATE = SCRIPT_DIR / "triage_report_template.py"
COMPARE = SCRIPT_DIR / "compare_snapshots.py"
SUGGEST = SCRIPT_DIR / "command_suggester.py"
EVAL_LOG_PATTERNS = SCRIPT_DIR / "eval_log_patterns.py"
EVAL_OFFICIAL_SPIKE = SCRIPT_DIR / "eval_official_spike_patterns.py"
CHECK_RESOURCE_INDEX = SCRIPT_DIR / "check_resource_index.py"
CHECK_README_COMMANDS = SCRIPT_DIR / "check_readme_commands.py"
CHECK_FIXTURE_MANIFESTS = SCRIPT_DIR / "check_fixture_manifests.py"


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=True)


def write_case(repo: Path, name: str, body: str, source_dir: str = "ai_test_cases") -> None:
    path = repo / source_dir / f"{name}.c"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "#include <stdint.h>\n"
        f"bool {name}()\n"
        "{\n"
        f"{body}\n"
        "    return true;\n"
        "}\n"
    )


def write_run(simv: Path, dirname: str, log: str) -> None:
    run_dir = simv / dirname
    run_dir.mkdir(parents=True)
    (run_dir / "run.log").write_text(log)


def assert_eq(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected!r}, got {actual!r}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="hyptest_failure_triage_selftest_") as td:
        root = Path(td)
        repo = root / "riscv-hyp-tests-nhv5.1"
        simv = root / "LinkNan" / "sim" / "simv"
        (repo / "ai_test_cases").mkdir(parents=True)
        simv.mkdir(parents=True)

        cases = [
            "case_selfcheck_fail",
            "case_manual_selfcheck_fail",
            "case_passed_good_trap",
            "case_difftest_good_trap",
            "case_real_stuck",
            "case_fsdb_error_but_pass",
            "case_split_fsdb_error_but_pass",
            "case_50000_param_not_stuck",
            "case_overlap",
        ]
        (root / "failures.txt").write_text("\n".join(cases) + "\n")

        write_case(
            repo,
            "case_selfcheck_fail",
            "    uint64_t vaddr = hs_page_base(SWITCH1);\n"
            "    cbo_inval(vaddr);\n"
            "    TEST_ASSERT(\"target word preserves seed image\", false);",
        )
        write_case(
            repo,
            "case_manual_selfcheck_fail",
            "    uint64_t vaddr = hs_page_base(SWITCH_MANUAL);\n"
            "    TEST_SETUP_EXCEPT();\n"
            "    TEST_ASSERT(\"manual source should be indexed\", false);",
            source_dir="manual_test_cases/memory",
        )
        write_case(
            repo,
            "case_passed_good_trap",
            "    uint64_t vaddr = hs_page_base(SWITCH2);\n"
            "    TEST_ASSERT(\"all checks pass\", true);",
        )
        write_case(
            repo,
            "case_difftest_good_trap",
            "    uint64_t vaddr = hs_page_base(SWITCH3);\n"
            "    TEST_ASSERT(\"difftest-enabled checks pass\", true);",
        )
        write_case(
            repo,
            "case_real_stuck",
            "    uint64_t vaddr = hs_page_base(VSRWXPbmt2_GURWXPbmt1);\n"
            "    pbmt_hspt_to_x(VSRWXPbmt2_GURWXPbmt1);\n"
            "    TEST_ASSERT(\"io request should complete\", true);",
        )
        write_case(
            repo,
            "case_fsdb_error_but_pass",
            "    uint64_t vaddr = hs_page_base(SCRATCHPAD);\n"
            "    TEST_ASSERT(\"fsdb warning should not taint pass\", true);",
        )
        write_case(
            repo,
            "case_split_fsdb_error_but_pass",
            "    uint64_t vaddr = hs_page_base(SCRATCHPAD2);\n"
            "    TEST_ASSERT(\"split fsdb warning should not taint pass\", true);",
        )
        write_case(
            repo,
            "case_50000_param_not_stuck",
            "    uint64_t cycles = 50000;\n"
            "    TEST_ASSERT(\"plain 50000 parameter should not imply stuck\", cycles == 50000);",
        )
        write_case(
            repo,
            "case_overlap",
            "    TEST_ASSERT(\"short case must not consume longer case run\", true);",
        )
        write_case(
            repo,
            "case_overlap_extra",
            "    TEST_ASSERT(\"longer case is not listed\", true);",
        )

        write_run(
            simv,
            "selfcheck34_case_selfcheck_fail",
            "risc-v NH-V5 tests\n"
            "case_selfcheck_fail\n"
            "target word preserves seed image FAILED\n"
            "FAILED\n"
            "HIT GOOD TRAP!\n",
        )
        write_run(
            simv,
            "selfcheck34_case_manual_selfcheck_fail",
            "risc-v NH-V5 tests\n"
            "case_manual_selfcheck_fail\n"
            "manual source should be indexed FAILED\n"
            "FAILED\n"
            "HIT GOOD TRAP!\n",
        )
        write_run(
            simv,
            "selfcheck34_case_passed_good_trap",
            "risc-v NH-V5 tests\n"
            "disable diff-test\n"
            "case_passed_good_trap\n"
            "all checks pass PASSED\n"
            "HIT GOOD TRAP!\n",
        )
        write_run(
            simv,
            "selfcheck34_case_difftest_good_trap",
            "risc-v NH-V5 tests\n"
            "diff-test ref so:/path/to/riscv64-spike-so\n"
            "The reference model is /path/to/riscv64-spike-so\n"
            "case_difftest_good_trap\n"
            "difftest-enabled checks pass PASSED\n"
            "HIT GOOD TRAP!\n",
        )
        write_run(
            simv,
            "selfcheck34_case_real_stuck",
            "risc-v NH-V5 tests\n"
            "case_real_stuck\n"
            "50000 cycles no commit\n",
        )
        write_run(
            simv,
            "truncated_case_fsdb",
            "ERROR - The simulator version is newer than the FSDB dumper version\n"
            "risc-v NH-V5 tests\n"
            "case_fsdb_error_but_pass\n"
            "fsdb warning should not taint pass PASSED\n"
            "HIT GOOD TRAP!\n",
        )
        write_run(
            simv,
            "wave_truncated_case_split_fsdb",
            "Dumping FSDB Waveform for DEBUG is active !!!\n"
            "FSDB Dumper for VCS\n"
            "*  ERROR -\n"
            "*  The simulator version is newer than the FSDB dumper version which  *\n"
            "risc-v NH-V5 tests\n"
            "case_split_fsdb_error_but_pass\n"
            "split fsdb warning should not taint pass PASSED\n"
            "HIT GOOD TRAP!\n",
        )
        write_run(
            simv,
            "selfcheck34_case_50000_param_not_stuck",
            "risc-v NH-V5 tests\n"
            "case_50000_param_not_stuck\n"
            "parameter cycles=50000\n"
            "plain 50000 parameter should not imply stuck PASSED\n"
            "HIT GOOD TRAP!\n",
        )
        write_run(
            simv,
            "selfcheck34_case_overlap_extra",
            "risc-v NH-V5 tests\n"
            "case_overlap_extra\n"
            "longer case is not listed PASSED\n"
            "HIT GOOD TRAP!\n",
        )

        snapshot_json = root / "snapshot.json"
        snapshot_md = root / "snapshot.md"
        run(
            [
                sys.executable,
                str(TRIAGE),
                "--list",
                str(root / "failures.txt"),
                "--hyptest-repo",
                str(repo),
                "--simv-dir",
                str(simv),
                "--json-out",
                str(snapshot_json),
                "--md-out",
                str(snapshot_md),
            ]
        )
        data = {item["case"]: item for item in json.loads(snapshot_json.read_text())}
        assert_eq(data["case_selfcheck_fail"]["runs"][0]["status"], "selfcheck_fail", "selfcheck status")
        assert_eq(
            data["case_manual_selfcheck_fail"]["source"]["path"],
            "manual_test_cases/memory/case_manual_selfcheck_fail.c",
            "manual case source path",
        )
        assert_eq(
            data["case_manual_selfcheck_fail"]["runs"][0]["status"],
            "selfcheck_fail",
            "manual selfcheck status",
        )
        assert_eq(data["case_passed_good_trap"]["runs"][0]["status"], "passed_good_trap", "pass status")
        assert_eq(
            data["case_passed_good_trap"]["runs"][0]["difftest_disabled"],
            True,
            "difftest-disabled pass metadata",
        )
        assert_eq(
            data["case_difftest_good_trap"]["runs"][0]["difftest_enabled"],
            True,
            "difftest-enabled pass metadata",
        )
        assert_eq(data["case_real_stuck"]["runs"][0]["status"], "true_stuck_evidence", "stuck status")
        assert_eq(data["case_fsdb_error_but_pass"]["runs"][0]["status"], "passed_good_trap", "ignored FSDB error")
        assert_eq(
            data["case_split_fsdb_error_but_pass"]["runs"][0]["status"],
            "passed_good_trap",
            "ignored split FSDB error banner",
        )
        assert_eq(
            data["case_50000_param_not_stuck"]["runs"][0]["status"],
            "passed_good_trap",
            "plain 50000 should not be stuck",
        )
        assert_eq(
            data["case_overlap"]["runs"],
            [],
            "short case should not match longer run directory or log prefix",
        )
        assert_eq(data["case_real_stuck"]["source"]["exact_pbmt_hits"] > 0, True, "PBMT hit")

        cluster_json = root / "clusters.json"
        run(
            [
                sys.executable,
                str(CLUSTER),
                "--snapshot-json",
                str(snapshot_json),
                "--mode",
                "coarse",
                "--json-out",
                str(cluster_json),
            ]
        )
        clusters = json.loads(cluster_json.read_text())
        assert_eq(sum(c["size"] for c in clusters), 9, "cluster case count")

        plan_json = root / "plan.json"
        run(
            [
                sys.executable,
                str(PLAN),
                "--snapshot-json",
                str(snapshot_json),
                "--json-out",
                str(plan_json),
            ]
        )
        plan = {item["action"]: item for item in json.loads(plan_json.read_text())}
        assert_eq(plan["remove_candidate"]["size"], 5, "plan remove candidates")
        assert_eq(plan["source_or_rerun"]["size"], 2, "plan source/rerun")
        assert_eq(plan["stuck_debug"]["size"], 1, "plan stuck debug")
        assert_eq(plan["needs_run_artifact"]["size"], 1, "plan missing run artifact")

        report_md = root / "report.md"
        run(
            [
                sys.executable,
                str(REPORT_TEMPLATE),
                "--snapshot-json",
                str(snapshot_json),
                "--out",
                str(report_md),
                "--case",
                "case_selfcheck_fail",
                "--title",
                "Synthetic selfcheck report",
            ]
        )
        report_text = report_md.read_text()
        for expected in [
            "# Synthetic selfcheck report",
            "## Scene And Intent",
            "case_selfcheck_fail",
            "target word preserves seed image FAILED",
            "## Classification",
            "## Verification",
        ]:
            if expected not in report_text:
                raise AssertionError(f"report template missing {expected!r}")

        old_snapshot = json.loads(snapshot_json.read_text())
        new_snapshot = json.loads(snapshot_json.read_text())
        by_case = {item["case"]: item for item in new_snapshot}
        by_case["case_selfcheck_fail"]["runs"][0]["status"] = "passed_good_trap"
        by_case["case_selfcheck_fail"]["runs"][0]["has_failed_assert"] = False
        by_case["case_selfcheck_fail"]["runs"][0]["evidence_tags"] = ["difftest-disabled", "clean-good-trap"]
        by_case["case_real_stuck"]["runs"][0]["status"] = "difftest_mismatch"
        by_case["case_real_stuck"]["runs"][0]["has_internal_stuck"] = False
        by_case["case_real_stuck"]["runs"][0]["has_mismatch"] = True
        added = json.loads(json.dumps(by_case["case_passed_good_trap"]))
        added["case"] = "case_new_failure"
        added["runs"][0]["status"] = "selfcheck_fail"
        added["runs"][0]["has_failed_assert"] = True
        new_snapshot.append(added)
        old_compare_json = root / "old_compare.json"
        new_compare_json = root / "new_compare.json"
        old_compare_json.write_text(json.dumps(old_snapshot))
        new_compare_json.write_text(json.dumps(new_snapshot))
        compare_json = root / "compare.json"
        run(
            [
                sys.executable,
                str(COMPARE),
                "--old",
                str(old_compare_json),
                "--new",
                str(new_compare_json),
                "--json-out",
                str(compare_json),
            ]
        )
        compare_data = json.loads(compare_json.read_text())
        assert_eq(compare_data["summary"]["added_case"], 1, "compare added case")
        assert_eq(compare_data["summary"]["status_changed"], 2, "compare status changes")

        suggest_md = root / "suggest.md"
        run(
            [
                sys.executable,
                str(SUGGEST),
                "--snapshot-json",
                str(snapshot_json),
                "--hyptest-repo",
                str(repo),
                "--linknan-repo",
                str(root / "LinkNan"),
                "--md-out",
                str(suggest_md),
                "--limit",
                "2",
            ]
        )
        suggest_text = suggest_md.read_text()
        for expected in [
            "### source_rerun",
            "### stuck_debug",
            "### verify_remove",
            "missing LINKNAN_HOME",
            "missing DIFFTEST_REF_SO",
            "compile_elf.py --plat linknan --include-commented --name case_selfcheck_fail",
            "get_result.py --platform linknan --case case_selfcheck_fail --jobs 20 --timeout 900",
            "update_failure_list.py",
            "timeout 900s or more",
        ]:
            if expected not in suggest_text:
                raise AssertionError(f"command suggestions missing {expected!r}")

        dry = run(
            [
                sys.executable,
                str(UPDATE),
                "--list",
                str(root / "failures.txt"),
                "--snapshot-json",
                str(snapshot_json),
                "--dry-run",
            ]
        )
        if "removed_from_list=5" not in dry.stdout:
            raise AssertionError(f"dry-run should identify five clean listed passed cases, got:\n{dry.stdout}")
        verbose = run(
            [
                sys.executable,
                str(UPDATE),
                "--list",
                str(root / "failures.txt"),
                "--snapshot-json",
                str(snapshot_json),
                "--dry-run",
                "--verbose-skips",
            ]
        )
        if "skipped_cases:" not in verbose.stdout or "case_real_stuck" not in verbose.stdout:
            raise AssertionError(f"verbose dry-run should explain skipped cases, got:\n{verbose.stdout}")

        mismatch_dry = run(
            [
                sys.executable,
                str(UPDATE),
                "--list",
                str(root / "failures.txt"),
                "--snapshot-json",
                str(snapshot_json),
                "--list-kind",
                "mismatch",
                "--dry-run",
            ]
        )
        if "removed_from_list=1" not in mismatch_dry.stdout:
            raise AssertionError(
                "mismatch dry-run should remove only the difftest-enabled clean pass, got:\n"
                f"{mismatch_dry.stdout}"
            )

        run(
            [
                sys.executable,
                str(UPDATE),
                "--list",
                str(root / "failures.txt"),
                "--snapshot-json",
                str(snapshot_json),
            ]
        )
        remaining = (root / "failures.txt").read_text()
        if (
            "case_passed_good_trap" in remaining
            or "case_difftest_good_trap" in remaining
            or "case_fsdb_error_but_pass" in remaining
            or "case_split_fsdb_error_but_pass" in remaining
            or "case_50000_param_not_stuck" in remaining
        ):
            raise AssertionError("passed cases were not removed")
        if (
            "case_selfcheck_fail" not in remaining
            or "case_manual_selfcheck_fail" not in remaining
            or "case_real_stuck" not in remaining
        ):
            raise AssertionError("unresolved cases were removed incorrectly")
        if not (root / "failures.txt.bak").exists():
            raise AssertionError("backup was not created")

        run([sys.executable, str(EVAL_LOG_PATTERNS)])
        run([sys.executable, str(EVAL_OFFICIAL_SPIKE)])
        run([sys.executable, str(CHECK_README_COMMANDS)])
        run([sys.executable, str(CHECK_RESOURCE_INDEX)])
        run([sys.executable, str(CHECK_FIXTURE_MANIFESTS)])

    print("selftest passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
