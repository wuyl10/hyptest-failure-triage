---
name: hyptest-failure-triage
description: 专门分析 riscv-hyp-tests / LinkNan hyptest 失败闭环。凡是用户要求分析单个 case FAILED/selfcheck error/timeout/stuck、run.log/assert.log/get_result batch log、Spike/LinkNan difftest mismatch、50000 cycles no commit、HIT GOOD TRAP 但 FAILED、FSDB 波形定位、selfcheck/stuck/mismatch 失败列表、删除已修复失败列表项、修复 ai_test_cases/manual_test_cases 自校验或判断 suspected RTL bug 时，都必须使用本技能。也用于区分 golden/model limitation、用例断言写错、环境限制、真实 RTL bug，并给出修复、manual/blocked 分层和验证证据。凡涉及 PMA/PBMT/MMIO/Device/responder/no-response/stuck 的失败定位，必须同时查当前 hyptest-workflow spec_profile 的 PMA/PBMT/MMIO matrix 和当前平台源码/波形 responder 证据，分别给出规格允许性和当前 testbench 是否有返回路径。
---

# Hyptest Failure Triage

该技能用于把 hyptest 失败从“有失败现象、日志或列表”推进到可执行结论：

- 修正用例自校验或测试环境使用错误。
- 识别 Spike/model limitation 或 LinkNan 环境限制，并给出 manual/RTL-only/blocked 结论。
- 标明 suspected RTL bug，并给出日志、源码、波形证据。
- 验证修复后 PASS，并安全更新用户明确指定的 selfcheck/stuck/mismatch 失败列表或 triage 报告。

## Coordinate With Other Skills

本技能负责失败归因、列表清理安全性和最终报告。需要改 case/注册、
编译/重跑、分层、profile guard 时按下方 router 使用 `$hyptest-workflow`；
需要 FSDB/VCD/FST first-bad-cycle、握手、协议或 X-state 证据时使用
`$waveform-debug`，再回到本技能收口分类。

## Failure Model

Use the "three entry symptoms, six final classifications" model. Entry symptoms
are only how the failure appears; they are not root-cause conclusions.

Common entry symptoms:

- `selfcheck fail`: `FAILED`, failed `TEST_ASSERT`/`AI_ASSERT`, or `HIT GOOD TRAP` with failed selfcheck.
- `stuck/no-forward-progress`: `50000 cycles no commit`, watchdog/no-forward-progress, or timeout that needs stuck judgment.
- `difftest mismatch`: Spike/golden/reference-model disagreement with the DUT or LinkNan platform run.

Final classifications:

- `selfcheck_bug`: the case/assert/setup is wrong; fix the test without weakening intent.
- `spike_or_model_limitation`: the golden/model lacks the required architecture, microarchitecture, or platform behavior.
- `environment_blocked`: the current platform/testbench lacks a required responder, device, config, runtime capability, or the active profile says the targeted RTL capability is not implemented.
- `suspected_rtl_bug`: source intent is valid and log/waveform evidence points to RTL behavior.
- `true_stuck`: internal no-commit/watchdog or waveform/log evidence proves no forward progress.
- `inconclusive`: evidence is insufficient, such as wall-clock timeout only.

Do not equate the entry symptom with the final classification. A case from
a user-provided selfcheck failure list is not automatically `selfcheck_bug`; a
case from a user-provided stuck list is not automatically `true_stuck`; a
difftest mismatch is not automatically an RTL bug.

## Input Modes

Use the most specific evidence the user provided. A failure-list file is required
only for list-level triage or list cleanup. Do not ask for a selfcheck/stuck
list path when the user provided a single case, a log path, or pasted output that
is sufficient for single-case/log triage.

```text
Single-case mode   case_name, optional run.log/assert.log, optional platform
Log mode           run.log/assert.log/get_result batch log path, or pasted output
List mode          explicit selfcheck/stuck/mismatch list path
Cleanup mode       explicit or verified list path plus trusted rerun/snapshot evidence
Workflow handoff   case_name/platform/spec_profile/log_paths from hyptest-workflow
```

For list-level triage and cleanup, use only the list path explicitly provided by
the user or by a trusted workflow handoff. Do not infer or probe default
failure-list names under `regress_logs/`; if the task requires a list and no list
path is provided, ask for the path.

环境变量口径与 `hyptest-workflow` 对齐：对外统一使用 `HYPTEST_*`
变量，不依赖个人绝对路径。

```text
HYPTEST_HOME            hyptest repo root
HYPTEST_LINKNAN_HOME    LinkNan repo root when LinkNan artifacts are needed
HYPTEST_DIFFTEST_REF_SO difftest reference shared object for LinkNan difftest reruns
HYPTEST_SPIKE_BIN       official/community Spike executable when Spike reruns are needed
HYPTEST_CROSS_COMPILE   toolchain prefix only when workflow compile/rerun needs it
HYPTEST_TMPDIR          temporary directory when needed
HYPTEST_FAILURE_TRIAGE_SKILL_HOME failure-triage skill directory when manually running bundled scripts
triage reports          preferably next to the relevant logs or under regress_logs/
sim run dirs            $HYPTEST_LINKNAN_HOME/sim/simv/ when using LinkNan artifacts
```

Use separate skill-home variables for cross-skill handoff:

```text
HYPTEST_FAILURE_TRIAGE_SKILL_HOME  hyptest-failure-triage bundled scripts
HYPTEST_WORKFLOW_SKILL_HOME        hyptest-workflow bundled scripts
WAVEFORM_DEBUG                     waveform-debug bundled scripts
```

If a required repo path for the chosen mode is not provided, the bundled scripts
should fail with a clear message instead of silently falling back to another
user's workspace.

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
waveform_context
  waveform_path
  rtl_root
  top_module
  debug_target
  time_window
  expected_behavior
  observed_behavior
  suggested_waveform_report
log_paths
```

这些字段只是 workflow 初判证据，不是最终 RTL 结论。若 `waveform_needed=true`，或 `waveform_context` 带有 `waveform_path` / `debug_target` / `suggested_waveform_report`，先把这些上下文纳入本技能报告和 waveform-debug 输入；不要重复询问已经存在的 FSDB/top/debug target。若存在 stuck/difftest mismatch/FSDB 需求，继续按本技能规则收集 run.log、assert.log、source 和波形证据。

当本技能需要 `hyptest-workflow` 重新编译或运行时，只使用两个平台：

```text
Spike     compile_elf.py --plat spike    + get_result.py --platform spike
LinkNan   compile_elf.py --plat linknan  + get_result.py --platform linknan
```

本技能的失败闭环只区分 Spike gate 和 LinkNan/RTL 证据。交接给
`hyptest-workflow` 时必须明确 `runner_mode`：

```text
runner_mode: spike-gate | linknan-difftest | linknan-no-diff
compile_plat: spike | linknan
run_platform: spike | linknan
difftest_mode: not-applicable | enabled | disabled
include_commented: true | false
purpose:
cleanup_allowed: true | false
```

- `spike-gate`: 普通架构/default gate，且 active profile 允许 Spike gate。
- `linknan-difftest`: 复现/清理 difftest mismatch，或需要 DUT 与 reference 对齐证据。
- `linknan-no-diff`: RTL-only selfcheck、FSDB/waveform、no-response/stuck、
  PMA/PBMT/MMIO responder、CBO/refill/cache/TLB/sbuffer/replay 等 Spike/golden
  不适合 gate 或 difftest 会挡住观察点的场景。

`linknan-no-diff` 证据可以支持 selfcheck、RTL-only 或波形结论，但不能清理
difftest mismatch 列表，也不能把 profile 标记未实现的目标假装成 PASS。

## Cross-Skill Invocation Router

`hyptest-failure-triage` stays the owning skill for failure classification,
cleanup safety, and final reporting. Call the other skills only for their
execution domain, then return here to classify and close the loop.

Use `$hyptest-workflow` when the next step touches hyptest source/workflow state
or requires a runner:

- Add or edit `ai_test_cases/*.c`, `manual_test_cases/**/*.c`, or
  `test_register.c`.
- Compile or rerun a case, including `spike-gate`, `linknan-difftest`, or
  `linknan-no-diff`.
- Decide or update `default` / `manual` / `compile-only` / `blocked` tiering,
  reason code, or registration status.
- Query `spec_profile`, run profile guard, or decide PMA/PBMT/MMIO/Device
  legality, responder requirement, Spike gate applicability, or RTL/Nanhu
  implementation scope.
- Update `test_point/**/*.md`, test-point to assertion mapping, case uniqueness,
  or repo-wide duplicate/similarity evidence.

Use `$waveform-debug` when signal-level evidence is required:

- The user asks for FSDB/VCD/FST/waveform, first-bad-cycle, handshake/protocol,
  or X-state analysis.
- A suspected RTL bug needs signal evidence before writing the report.
- `50000 cycles no commit`, stuck, no-response, or timeout needs progress vs
  deadlock vs missing-response classification.
- PMA/PBMT/MMIO/Device responder behavior must be proven from request/response
  signals after the profile guard.
- A difftest mismatch needs first-divergence or signal-path evidence beyond the
  final mismatch line.

Do not call `$waveform-debug` for obvious source-level selfcheck bugs,
profile-marked not-implemented cases, pure failure-list cleanup, mismatch cleanup
that only needs a `linknan-difftest` clean rerun, or wall-clock timeout alone
without internal stuck or waveform artifacts.

Use this order for common multi-skill flows:

```text
selfcheck fix:
  failure-triage source/log classification
  -> hyptest-workflow edit/compile/rerun
  -> if a suspected RTL issue appears during the edit/rerun loop, pause cleanup,
     record it in report.md, and either queue manual review or use waveform-debug
  -> failure-triage cleanup/report decision

difftest mismatch cleanup:
  failure-triage source/model check
  -> hyptest-workflow linknan-difftest rerun
  -> failure-triage update_failure_list.py dry-run/final decision
  (no waveform-debug needed for cleanup)

RTL-only stuck/no-response/waveform:
  failure-triage symptom + source intent
  -> hyptest-workflow profile guard and linknan-no-diff/FSDB run if needed
  -> waveform-debug first-bad-cycle/protocol evidence
  -> failure-triage final classification/report

PMA/PBMT/MMIO/Device:
  failure-triage detects address/responder/no-response relevance
  -> hyptest-workflow profile guard
  -> waveform-debug only if current signal evidence is needed
  -> failure-triage separates spec_allowed, responder availability, and RTL bug
```

## Task Router

Use this table to choose the first deterministic action. It keeps the triage
flow from jumping straight to source edits or RTL conclusions before the run
evidence is organized.

| User input / symptom | First action | Then read / run | Stop condition |
| --- | --- | --- | --- |
| Single case FAILED/selfcheck error | Locate source and latest available log | Source function, failed assert, run.log/assert.log or get_result log | No failure list required |
| Pasted output or log path | Parse markers first | Classify PASS/FAILED/timeout/untested/mismatch/stuck, then inspect source if needed | Ask for case/source only if the log lacks enough context |
| Explicit selfcheck/stuck/mismatch list path or many failed cases with a provided list | Generate a fresh snapshot from that list | `cluster_failures.py`, `triage_plan.py` when the list is nontrivial | Do not patch or remove until source + rerun evidence confirms the class |
| `50000 cycles no commit`, no-forward-progress, or single stuck case | Inspect the relevant log/run dir first | Source intent, responder availability, waveform if first bad point is unclear | No list path required unless updating a list |
| Difftest mismatch / Spike vs LinkNan mismatch | Inspect source intent and latest run evidence; snapshot only if a list is provided | Use `linknan-difftest` for mismatch reproduction/cleanup; use `linknan-no-diff` only for RTL/waveform observation | Difftest-disabled GOOD TRAP cannot clear a mismatch list |
| `HIT GOOD TRAP` but `FAILED` | Treat as selfcheck/assertion failure first | Source function, assert text, latest run log | Remove from list only after clean rerun |
| Suspected RTL behavior appears while editing/rerunning a test fix | Stop treating the case as simple selfcheck cleanup | Record the suspect in `report.md`; use `$waveform-debug` if signal evidence is needed | Queue manual review or classify after waveform; do not patch around it to get PASS |
| FSDB / waveform request | Gather run dir, log, source intent first | Use `$waveform-debug` for signal-level first-bad-cycle work | Report waveform evidence; do not edit RTL unless asked |
| Request to delete fixed failures | Require an explicit or verified list path, then snapshot trusted run artifacts | `update_failure_list.py --dry-run --verbose-skips` | Edit list only after reviewing removable cases and list kind |
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

## Bundled Tools

Use bundled scripts to make repetitive triage deterministic, but keep their
outputs as evidence organizers rather than final proof. For current command
syntax, run
`python3 $HYPTEST_FAILURE_TRIAGE_SKILL_HOME/scripts/list_skill_commands.py --markdown`
or read `README.md`; `references/resource_index.md` lists every script and
fixture.

- `triage_snapshot.py`: first pass for explicit user/workflow-provided
  selfcheck/stuck/mismatch lists. Do not require it for single-case or log-only
  triage.
- `cluster_failures.py` / `triage_plan.py`: group many list cases and choose
  representative cases. Clusters are work queues, not root cause.
- `triage_report_template.py`: seed the mandatory Chinese `report.md`. The
  template includes `错误分类与代表用例`, full `Profile Guard`, waveform report
  references, manual-review items, final classification, action, and
  verification sections. Use `--action waveform` for wave/fsdb-tagged cases and
  `--waveform-report <waveform-report-dir>/report.md` when waveform-debug was
  used.
- `update_failure_list.py`: only after the user asks to update/clean a list and
  only after a fresh trusted snapshot. Always dry-run first with
  `--verbose-skips` and the correct `--list-kind selfcheck|stuck|mismatch`;
  mismatch cleanup requires difftest-enabled evidence unless explicitly
  overridden by the user. The dangerous difftest-disabled mismatch override
  requires `--difftest-disabled-override-reason`.
- `compare_snapshots.py`: review rerun/dependency-update changes. Treat
  `status_changed` as high priority; new mismatch/stuck status needs fresh
  root-cause triage.
- `command_suggester.py`: generate conservative next-step commands without
  executing them.

After editing bundled scripts, run
`python3 $HYPTEST_FAILURE_TRIAGE_SKILL_HOME/scripts/selftest.py`.
Run `eval_log_patterns.py` for log-pattern changes and
`eval_official_spike_patterns.py` for official Spike model-gap changes.

## Non-Negotiable Rules

- Do not modify RTL unless the user explicitly requests RTL changes. For RTL suspected bugs, write evidence and suggested owner check points instead.
- Do not classify a case as stuck from wall-clock timeout alone. A real stuck conclusion needs internal `50000 cycles no commit`, internal watchdog, or waveform/log evidence of no forward progress.
- Do not use a short timeout such as 300s for LinkNan triage. Use at least 15 minutes by default for long RTL runs, but still do not treat timeout alone as stuck.
- Do not write non-Chinese triage reports or use arbitrary filenames for final triage reports. The failure-triage report filename is exactly `report.md`; when waveform evidence is used, cite the waveform-debug `report.md` path explicitly instead of burying signal evidence without provenance.
- Do not remove a case from a failure list unless the rerun shows `PASSED` / `HIT GOOD TRAP` and no `FAILED`, `ERROR`, fatal assertion, mismatch, or internal watchdog.
- Do not use a difftest-disabled waveform/RTL-only PASS to clear a difftest mismatch list. It can support selfcheck or waveform conclusions, but mismatch cleanup needs difftest-enabled PASS unless the user explicitly accepts RTL-only evidence.
- Do not weaken the validation intent to make a case pass. In particular, do not move PMA/PBMT/IO tests to DRAM/dcache unless the original test target is not PMA/PBMT/IO.
- Do not patch around a suspected RTL behavior discovered while fixing a test. If an edit/rerun loop exposes a new or remaining valid-expectation failure, record it in the Chinese `report.md` under manual-review items, keep it out of cleanup/removal decisions, and either queue it for later human review or call `$waveform-debug` first when signal-level evidence is needed.
- Do not convert byte/half/word coverage into only 8B access coverage unless the original test naturally has 8B register semantics.
- Do not fake a PASS for a case whose target is explicitly outside the active `hyptest-workflow` profile's RTL/Nanhu implemented scope. If the profile says the targeted feature/corner is `nanhu_not_impl`, unimplemented, unsupported, or otherwise outside current RTL implementation, classify/report it as blocked/manual implementation gap and keep it out of resolved/default cleanup unless the user explicitly retargets the case to an implemented scenario with documented intent.
- Do not make PMA/PBMT/MMIO/Device/responder/no-response decisions without a profile-matrix guard. First determine `spec_profile` (default from the hyptest-workflow profile registry if not explicit), then record `spec_allowed`, `responder_required`, and `spike_gate_applicable` from `references/spec_profiles/<spec_profile>.md` or `query_spec_profile.py`. Separately prove `testbench_responder_confirmed` from current platform source, run.log, or waveform. A legal PMA/peripheral PA is not proof of response; a no-response waveform is not proof that the PMA/PBMT combination is spec-disallowed.
- Preserve dirty worktree changes. Never revert user or generated changes that are unrelated to the current failure.

## Detailed Rules

For nontrivial classification, test edits, report writing, stuck/mismatch
judgment, PMA/PBMT/IO decisions, or final list removal decisions, load:

```text
references/decision_rules.md
```

For PMA/PBMT/MMIO/Device/responder/no-response cases, also use the current
`hyptest-workflow` profile as a first-class rule source before deciding whether
the case is invalid, environment-blocked, or suspected RTL. The minimum triage
note is:

```text
spec_profile:
pa/window:
pma:
pbmt:
spec_allowed:
responder_required:
spike_gate_applicable:
rtl_implemented:
profile_not_impl_reason:
testbench_responder_confirmed:
platform/source evidence:
wave/log evidence:
classification:
```

Use the profile for the PMA/PBMT legality question and RTL implementation-scope
question, and use platform source/waveform for the response-path question; do
not collapse those axes into one "valid/invalid" label. A profile-marked
unimplemented RTL feature is not a selfcheck bug and not a pass condition; it is
blocked/manual implementation-gap evidence unless the case is explicitly
retargeted to an implemented scenario.

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

1. Choose input mode first. For single-case/log-only triage, inspect the
   provided log/source directly. For explicit list or many-case triage, generate
   a fresh snapshot with `triage_snapshot.py`.
2. For more than a few list cases, run `cluster_failures.py` and
   `triage_plan.py`; use clusters only to choose representatives.
3. Load `references/decision_rules.md` before patching tests, labeling suspected
   RTL bugs, deleting list entries, or making PMA/PBMT/IO/mismatch/stuck
   decisions.
4. If a report is needed, seed the Chinese `report.md` with
   `triage_report_template.py`.
5. If comparing reruns or LinkNan updates, use `compare_snapshots.py`.
6. Before deleting from any failure list, run
   `update_failure_list.py --dry-run --verbose-skips` with the correct
   `--list-kind selfcheck|stuck|mismatch`.
7. Load `references/known_patterns.md` when current symptoms resemble a prior
   pattern, but verify before acting.

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
