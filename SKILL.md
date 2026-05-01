---
name: hyptest-failure-triage
description: 专门分析 riscv-hyp-tests-nhv5.1 / LinkNan hyptest 失败闭环。凡是用户要求处理 selfcheck_fail.txt、stuck.txt、run.log、Spike/LinkNan difftest mismatch、50000 cycles no commit/stuck、HIT GOOD TRAP 但 FAILED、FSDB 波形定位、删除已修复失败列表、修复 ai_test_cases/manual_test_cases 自校验或判断 suspected RTL bug 时，都必须使用本技能。也用于区分 Spike 缺少 cache/TLB/PMA/PBMT/MMIO 模型导致的 mismatch、用例断言写错、环境限制、真实 RTL bug，并给出修复、manual/blocked 分层和验证证据。
---

# Hyptest Failure Triage

该技能用于把 hyptest 失败从“列表里有 case”推进到可执行结论：

- 修正用例自校验或测试环境使用错误。
- 识别 Spike/model limitation 或 LinkNan 环境限制，并给出 manual/RTL-only/blocked 结论。
- 标明 suspected RTL bug，并给出日志、源码、波形证据。
- 验证修复后 PASS，并安全更新 `selfcheck_fail.txt` / `stuck.txt` / triage 报告。

## Coordinate With Other Skills

- 若要新增/修改 `ai_test_cases/*.c` / `manual_test_cases/**/*.c`、`test_register.c`、编译/批跑、分层决策，也使用 `$hyptest-workflow`。
- 若需要 FSDB/VCD/FST 波形定位、first-bad-cycle、信号握手或协议证据，也使用 `$waveform-debug`。
- 本技能负责失败归因和闭环规则；其它技能负责对应领域的细节。

## Default Inputs

优先使用显式参数或环境变量，不依赖个人绝对路径：

```text
HYPTEST_REPO or RVH_HYPTEST_REPO  riscv-hyp-tests-nhv5.1 repo root
LINKNAN_HOME                      LinkNan repo root
DIFFTEST_REF_SO                   difftest reference shared object for LinkNan reruns
SPIKE_BIN                         official Spike executable when Spike reruns are needed
selfcheck list                    $LINKNAN_HOME/regress_logs/selfcheck_fail.txt
stuck list                        $LINKNAN_HOME/regress_logs/stuck.txt
triage reports                    $LINKNAN_HOME/regress_logs/
sim run dirs                      $LINKNAN_HOME/sim/simv/
```

If a required repo path is not provided, the bundled scripts should fail with a
clear message instead of silently falling back to another user's workspace.

For the current source/artifact layout and platform environment variables, use
`references/repo_layout.md`.

## Workflow Handoff

当 `hyptest-workflow` 已经生成交接卡片时，优先读取这些稳定字段，再进入本技能的 snapshot / source / waveform 流程：

```text
case_name
platform
spec_profile
scenario
assert_site
assert_expr
exception_observed
excpt_dump
log_markers
error_points
reason_code_candidates
reason_code_details
next_single_run
waveform_needed
log_paths
```

这些字段只是 workflow 初判证据，不是最终 RTL 结论。若 `waveform_needed=true`，或存在 stuck/difftest mismatch/FSDB 需求，继续按本技能规则收集 run.log、assert.log、source 和波形证据。

## Task Router

Use this table to choose the first deterministic action. It keeps the triage
flow from jumping straight to source edits or RTL conclusions before the run
evidence is organized.

| User input / symptom | First action | Then read / run | Stop condition |
| --- | --- | --- | --- |
| `selfcheck_fail.txt` / many failed cases | Generate a fresh snapshot | `cluster_failures.py`, `triage_plan.py` when the list is nontrivial | Do not patch or remove until source + rerun evidence confirms the class |
| `stuck.txt`, `50000 cycles no commit`, no-forward-progress | Snapshot, then isolate true stuck vs long run | `references/decision_rules.md`, waveform if first bad point is unclear | Wall-clock timeout alone is inconclusive |
| Difftest mismatch / Spike vs LinkNan mismatch | Snapshot latest run and inspect source intent | `references/known_patterns.md` for PMA/PBMT/cache/TLB/CBO patterns | Difftest-disabled GOOD TRAP cannot clear a mismatch list |
| `HIT GOOD TRAP` but `FAILED` | Treat as selfcheck/assertion failure first | Source function, assert text, latest run log | Remove from list only after clean rerun |
| FSDB / waveform request | Gather run dir, log, source intent first | Use `$waveform-debug` for signal-level first-bad-cycle work | Report waveform evidence; do not edit RTL unless asked |
| Request to delete fixed failures | Snapshot from trusted run artifacts first | `update_failure_list.py --dry-run --verbose-skips` | Edit list only after reviewing removable cases and list kind |
| Suspected RTL bug | Reconstruct test intent and disprove selfcheck/model/env causes | `decision_rules.md`, `known_patterns.md`, waveform/source report | Write report with evidence and owner area; do not modify RTL by default |

## Evidence Ladder

Prefer conclusions that are backed by the highest available evidence level:

1. Fresh source review of the exact case and helpers.
2. Latest relevant `run.log` / `assert.log` from the intended platform and
   difftest mode.
3. Clean rerun evidence for list cleanup: GOOD TRAP/PASS with no failure,
   mismatch, fatal assertion, or internal watchdog.
4. Waveform evidence for first-bad-cycle, no-response, or RTL owner claims.
5. Known-pattern match only as a hypothesis, never as final proof.

If these evidence levels disagree, keep the case in the failure list and report
the conflict instead of forcing a classification.

## Bundled Tool

Use the bundled script for the first pass whenever the input is a case list such as
`selfcheck_fail.txt` or `stuck.txt`. It finds the source function, extracts relevant
PMA/PBMT/CBO/PMP/assert keywords, locates recent LinkNan run directories, parses
`run.log` key lines, and emits a conservative preliminary bucket.

```bash
python3 <skill-dir>/scripts/triage_snapshot.py \
  --list <failure-list> \
  --hyptest-repo "$HYPTEST_REPO" \
  --linknan-repo "$LINKNAN_HOME" \
  --md-out "$LINKNAN_HOME/regress_logs/<topic>_snapshot.md" \
  --json-out "$LINKNAN_HOME/regress_logs/<topic>_snapshot.json"
```

Treat the script output as triage input, not as final proof. A preliminary bucket
must still be confirmed by source review, rerun evidence, or waveform evidence
before modifying cases or deleting list entries.

Use the list updater only after generating a fresh snapshot from the run results
you intend to trust:

```bash
python3 <skill-dir>/scripts/update_failure_list.py \
  --list <failure-list> \
  --snapshot-json <topic>_snapshot.json \
  --dry-run
```

Then inspect the removable cases. Re-run without `--dry-run` only when each
removal is acceptable. The updater only removes cases whose latest indexed run is
classified as a clean `passed_good_trap`; it creates `<failure-list>.bak` before
editing. For mismatch lists, pass `--list-kind mismatch` so a difftest-disabled
wave/RTL-only GOOD TRAP is not treated as enough evidence to clear a difftest
mismatch.
Do not run the updater in parallel with snapshot generation; wait until the JSON
snapshot exists and corresponds to the exact run artifacts you want to trust.

Use the clustering script after snapshot generation when the list has many cases.
It groups cases by conservative observable features. Default `coarse` mode groups
by latest run status, source module, and PBMT presence. Use `theme` when you want
failure-theme separation, and `strict` only when exact failed assert text matters.

```bash
python3 <skill-dir>/scripts/cluster_failures.py \
  --snapshot-json <topic>_snapshot.json \
  --mode coarse \
  --md-out <topic>_clusters.md \
  --json-out <topic>_clusters.json
```

Use clusters to choose representative cases for waveform/debug. Do not treat a
cluster as final root cause; it is a work queue optimizer.

Use the action-plan script when you want a compact “what should I do next?”
view after snapshot generation. It groups cases into remove candidates,
source/rerun work, waveform-report updates, mismatch model checks, true-stuck
debug, and inconclusive long runs.

```bash
python3 <skill-dir>/scripts/triage_plan.py \
  --snapshot-json <topic>_snapshot.json \
  --md-out <topic>_plan.md \
  --json-out <topic>_plan.json
```

Use the report-template script for nontrivial classes or representative cases
before deep waveform/source write-up. It creates an editable `report.md` skeleton
pre-filled with selected cases, latest run evidence, source keyword lines, and
the required sections for final classification.

```bash
python3 <skill-dir>/scripts/triage_report_template.py \
  --snapshot-json <topic>_snapshot.json \
  --case <case> \
  --max-cases 5 \
  --title "<topic> triage report" \
  --out <report-dir>/<topic>/report.md
```

Use `--action selfcheck_fail`, `--action waveform_report_update`,
`--action mismatch`, or `--action stuck` when you want a class-level skeleton
instead of a single-case report.

Use the comparison script after LinkNan/dependencies updates or after rerunning
a batch. It highlights new failures, resolved/removed cases, status changes,
evidence-tag changes, and latest-run changes between two snapshots.

```bash
python3 <skill-dir>/scripts/compare_snapshots.py \
  --old <old_topic>_snapshot.json \
  --new <new_topic>_snapshot.json \
  --md-out <topic>_compare.md \
  --json-out <topic>_compare.json
```

Treat `status_changed` as the highest-priority review queue. A case moving from
`selfcheck_fail` to `passed_good_trap` is a removal candidate only after applying
the same trust policy as `update_failure_list.py`; a case moving into
`difftest_mismatch` or `true_stuck_evidence` needs fresh root-cause triage.

Use the command-suggester script after snapshot/plan when the next execution
steps are repetitive. It emits conservative compile/rerun/report/update commands
without executing them.

```bash
python3 <skill-dir>/scripts/command_suggester.py \
  --snapshot-json <topic>_snapshot.json \
  --limit 5 \
  --jobs 20 \
  --timeout 900 \
  --md-out <topic>_commands.md \
  --json-out <topic>_commands.json
```

Review the generated commands before running them. The suggester intentionally
does not launch RTL or edit lists; it preserves the rule that wall-clock timeout
alone is inconclusive and that difftest mismatch cleanup needs difftest-enabled
evidence.

After editing any bundled script, run the self-test:

```bash
python3 <skill-dir>/scripts/selftest.py
```

The self-test uses synthetic cases to check selfcheck-fail classification,
`passed_good_trap` detection, difftest-enabled vs difftest-disabled trust,
true stuck detection, FSDB tool-error filtering, PBMT keyword extraction,
clustering, action-plan grouping, report-template generation, and safe list
update behavior. It also checks snapshot comparison for added cases and status
changes, command suggestion generation, realistic log fixtures, and official
Spike known-pattern fixtures.

For faster focused checks, run:

```bash
python3 <skill-dir>/scripts/eval_log_patterns.py
python3 <skill-dir>/scripts/eval_official_spike_patterns.py
```

The log-pattern eval checks realistic `run.log`/Spike snippets such as FSDB
version banners, `HIT GOOD TRAP` with `FAILED`, difftest mismatch, internal
`50000 cycles no commit`, wall-clock timeout-only, untested exception, BAD TRAP,
and plain `50000` parameter PASS.

The official-Spike eval checks known model-gap/scope-exclusion buckets such as
CBO no-A fault classification, PMA/PBMT/MMIO/cacheability, NMI/double trap
outside NHV5.1AP scope, LR/SC reservation timeout, missing custom CSR, and
illegal instruction on official Spike.

## Non-Negotiable Rules

- Do not modify RTL unless the user explicitly requests RTL changes. For RTL suspected bugs, write evidence and suggested owner check points instead.
- Do not classify a case as stuck from wall-clock timeout alone. A real stuck conclusion needs internal `50000 cycles no commit`, internal watchdog, or waveform/log evidence of no forward progress.
- Do not use a short timeout such as 300s for LinkNan triage. Use at least 15 minutes by default for long RTL runs, but still do not treat timeout alone as stuck.
- Do not remove a case from a failure list unless the rerun shows `PASSED` / `HIT GOOD TRAP` and no `FAILED`, `ERROR`, fatal assertion, mismatch, or internal watchdog.
- Do not use a difftest-disabled waveform/RTL-only PASS to clear a difftest mismatch list. It can support selfcheck or waveform conclusions, but mismatch cleanup needs difftest-enabled PASS unless the user explicitly accepts RTL-only evidence.
- Do not weaken the validation intent to make a case pass. In particular, do not move PMA/PBMT/IO tests to DRAM/dcache unless the original test target is not PMA/PBMT/IO.
- Do not convert byte/half/word coverage into only 8B access coverage unless the original test naturally has 8B register semantics.
- Preserve dirty worktree changes. Never revert user or generated changes that are unrelated to the current failure.

## Detailed Rules

For nontrivial classification, test edits, report writing, stuck/mismatch
judgment, PMA/PBMT/IO decisions, or final list removal decisions, load:

```text
references/decision_rules.md
```

That reference contains the full taxonomy, evidence trust levels, Spike/platform
limitation checks, waveform requirements, patch policy, safe-list-update rules,
report template, final-answer format, and quick examples. Keep this main file as
the fast path; use the reference whenever a decision can affect test intent,
failure-list cleanup, or RTL bug labeling.

For source path, generated artifact, LinkNan run directory, and environment
variable questions, load:

```text
references/repo_layout.md
```

For failures resembling prior LinkNan patterns such as Class 1-5 CBO/refill
line-image failures, Class 6 PBMT=NC trap-entry observers, PMA/PBMT IO
no-response/stuck cases, difftest-disabled waveform runs, or long-run vs true
stuck ambiguity, load:

```text
references/known_patterns.md
```

Use known patterns as starting hypotheses only; still confirm with current
source, run.log, and waveform evidence before changing tests or labeling RTL.

## Fast Workflow

1. Generate a fresh snapshot with `triage_snapshot.py`.
2. For more than a few cases, run `cluster_failures.py` and `triage_plan.py`.
3. Use `command_suggester.py` to produce conservative next commands when useful.
4. If a report is needed, seed it with `triage_report_template.py`.
5. If comparing reruns or LinkNan updates, use `compare_snapshots.py`.
6. Before deleting from any failure list, run `update_failure_list.py --dry-run --verbose-skips` with the correct `--list-kind`.
7. Load `references/decision_rules.md` before patching tests, labeling suspected RTL bugs, or making any PMA/PBMT/IO/mismatch/stuck decision.
8. Load `references/known_patterns.md` when current symptoms resemble a prior pattern, but verify before acting.

## Final Answer Expectations

Answer in Chinese by default and be concrete:

- State the current classification and confidence.
- Say what changed, if anything.
- Say which cases were removed from lists, if any.
- Say which cases remain and why.
- Provide exact report/log/snapshot paths.
- Mention whether waveform or RTL owner confirmation is still needed.

Do not give vague conclusions such as “可能是 bug” without saying which evidence
supports it and what would disprove it. Avoid dumping whole script outputs; link
the generated paths and summarize the decisions.
