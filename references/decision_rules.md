# Hyptest Failure Triage Decision Rules

Load this reference when classification is nontrivial, when editing tests, when
writing a `report.md`, or when deciding whether a case can be removed from a
user-provided selfcheck/stuck/mismatch failure list.

## Failure Model

Use "three entry symptoms, six final classifications" during triage.

Entry symptoms are the observable way a case appears in logs or lists:

- `selfcheck fail`: failed assertion/selfcheck, including `HIT GOOD TRAP` with `FAILED`.
- `stuck/no-forward-progress`: internal `50000 cycles no commit`, watchdog/no-forward-progress, or timeout that needs stuck judgment.
- `difftest mismatch`: DUT and Spike/golden/reference model disagree.

These entry symptoms do not decide root cause by themselves. After source review,
latest run evidence, rerun, and waveform if needed, classify into exactly one of
the final taxonomy labels below. A selfcheck-list entry can become
`selfcheck_bug`, `environment_blocked`, `spike_or_model_limitation`, or
`suspected_rtl_bug`; a stuck-list entry can become `true_stuck` or
`inconclusive`; a mismatch can become model limitation, environment issue,
selfcheck bug, or suspected RTL bug.

## Failure Taxonomy

Use these labels consistently in notes and final answers.

### `selfcheck_bug`

The RTL behavior is plausible or verified correct, but the test assertion/setup
is wrong.

Typical examples:

- The test seeds one backing address but checks another backing address.
- A PBMT alias handler access and final check do not use the same alias/backing semantics.
- The test uses a fixed `sd` on a non-8B-aligned or width-specific scenario where `sb/sh/sw` is required.
- The expected exception cause/tval is impossible under the configured PTE/PMP/PMA/PBMT attributes.

Action:

- Fix the case without weakening the test target.
- Compile and rerun the affected case.
- Remove it from failure lists only after PASS + GOOD TRAP + no error.

### `spike_or_model_limitation`

The failure is expected because the selected gate/model lacks a
microarchitectural feature or platform model needed by the case. Most entries in
this bucket are official Spike gate gaps; do not apply this label to a LinkNan
difftest REF-DUT mismatch until the runner and reference path have been
identified.

Common causes:

- Official/community Spike (`HYPTEST_SPIKE_BIN`) has no cache/TLB timing model
  for cache-residency, CBO side effects, refill ordering, replay queues,
  sbuffer, uncache buffer, or response-context binding.
- Official/community Spike lacks or differs from the current platform's
  PMA/PBMT/MMIO routing model.
- The case intentionally observes RTL-only behavior such as cacheline dirty preservation, MMIO response timing, internal watchdog, or replay escape.
- A LinkNan difftest reference (`HYPTEST_DIFFTEST_REF_SO`) has a confirmed,
  runner-specific modeling/alignment gap after REF-DUT first-divergence analysis.

Action:

- Do not call it RTL bug solely from mismatch.
- Mark `RTL-only`, `manual`, or `blocked` as appropriate.
- If a responder exists and preserves intent, reroute only to an equivalent responder. Otherwise leave blocked/manual.
- When this label is used for `HYPTEST_DIFFTEST_REF_SO`, the report text must
  say "LinkNan difftest REF/model alignment gap" or equivalent runner-specific
  wording, not "official Spike gap".
- For LinkNan difftest PMA/PBMT/MMIO mismatches, first keep the case on the
  `linknan-difftest` path and analyze REF-DUT PMA/PA/responder evidence. Do not
  shortcut to "official Spike lacks PMA."

### `suspected_rtl_bug`

The test expectation matches ISA/platform intent, the setup is coherent, and
RTL/log/waveform evidence shows incorrect behavior.

Action:

- Write a focused `report.md` under `regress_logs/<topic>/`.
- Include scene, expected behavior, actual behavior, first bad point, why it is not a test/Spike limitation, and likely RTL owner area.
- Do not edit RTL unless explicitly asked.

### `environment_blocked`

The case needs a platform responder or memory-like region that the current
platform/testbench does not provide, or it targets a feature/corner that the
active `hyptest-workflow` profile says the current RTL/Nanhu implementation does
not support.

Typical examples:

- PMA/PBMT IO good path requires byte/half/word lane + whole-line readback, but the available responders are only register-like.
- Address range is legal in the active spec profile, but the current platform profile or testbench evidence says no response path exists.
- The active profile or `query_spec_profile.py` classifies the target as
  `nanhu_not_impl`, unimplemented, unsupported, or outside the current RTL
  implementation scope.

Action:

- Do not fake pass by moving to DRAM/dcache if PMA/PBMT/IO is the test target.
- Do not fake pass by weakening or retargeting an unimplemented RTL feature into
  an implemented neighboring scenario unless the user explicitly changes the test
  intent.
- Mark blocked/manual and state exactly what responder, device, runtime support,
  or RTL implementation support is missing.

## Evidence Trust Levels

Before deleting list entries or making a final mismatch/stuck conclusion, record
what kind of run produced the evidence:

```text
difftest-enabled run
=> acceptable evidence for clearing selfcheck, stuck, and difftest mismatch lists if it is a clean GOOD TRAP

difftest-disabled / RTL-only / waveform run
=> acceptable evidence for selfcheck behavior and waveform debug, but not enough to clear difftest mismatch

FSDB/wave run with Verdi/FSDB "ERROR" banner only
=> do not count the tool banner as test failure; still check FAILED/mismatch/watchdog lines

wall-clock timeout only
=> inconclusive; never count as true stuck without internal no-commit/watchdog/no-forward-progress evidence
```

`triage_snapshot.py` emits `evidence_tags` and run flags for this reason. Use
them as a guardrail, not as a replacement for reading the relevant log/source.

## Runner And Difftest Mode Handoff

When triage needs a rerun, hand the request to `hyptest-workflow` with exactly
one of these runner modes. This skill decides why the run is needed; workflow
executes the compile/run command and records artifacts.

```text
spike-gate
=> compile_elf.py --plat spike
=> get_result.py --platform spike
Use for ordinary architecture/default gate evidence when the active profile says
`spike_gate_applicable=true`.

linknan-difftest
=> compile_elf.py --plat linknan
=> get_result.py --platform linknan
=> difftest enabled
Use for difftest mismatch reproduction, mismatch cleanup, or DUT/reference
alignment evidence.

linknan-no-diff
=> compile_elf.py --plat linknan
=> get_result.py --platform linknan
=> difftest disabled / no-diff per current LinkNan runner support
Use for RTL-only selfcheck, waveform/FSDB, no-response/stuck, responder evidence,
or model-gap observation where Spike/golden would block the target observation.
```

The only platform choices for this skill are Spike and LinkNan.

Use `linknan-no-diff` when the question is "what does the RTL/test selfcheck do
without the reference model stopping the run?" Examples include CBO/refill line
image, cache/TLB/sbuffer/replay/MSHR state, PMA/PBMT/MMIO responder behavior,
FSDB first-bad-cycle work, and no-response/stuck triage.

Use `linknan-difftest` when the question is "does the DUT still disagree with
the reference model?" This is mandatory for clearing difftest mismatch lists.

Never use `linknan-no-diff` evidence to clear a mismatch list, prove a mismatch
is fixed, or convert a profile-marked unimplemented target into a PASS.

PMA/PBMT/MMIO difftest logs use the same generic difftest triage flow as other
mismatch logs: find the first divergent committed instruction or trap state,
record REF-vs-DUT deltas, then decide whether the mismatch is selfcheck, model,
environment, or RTL. The PMA/PBMT/MMIO fields below are required add-ons, not a
separate shortcut or special PMA-only flow.

Minimum PMA/PBMT/MMIO difftest add-ons:

- First divergent PC, instruction, access width, and whether the access is setup
  traffic or the target observation.
- VA/PA when available, `mtval`/`stval`, `mcause`/`scause`, `mepc`/`sepc`, and
  REF trap vs DUT trap/no-trap direction.
- Decoded PMA/PBMT/MMIO row from the active profile, including `spec_allowed`,
  `responder_required`, and `spike_gate_applicable`.
- PMA CSR/config evidence when present: `pmaaddr*`, `pmacfg*`, TOR/NAPOT/entry
  priority, reset/default entry, and physical map window.
- Current platform responder evidence from source, log, or waveform.

## Reconstruct Test Intent From Source

Open the full function and helper definitions. Extract:

- Target privilege mode and helper convention (`HS` may be project S-semantics alias under this repo).
- Address classes: DRAM/cacheable, PBMT=NC, PBMT=IO, PMA IO/device, PMP denied/restored, bad PA, MMIO responder.
- Width and alignment coverage: byte/half/word/doubleword/vector/misaligned/cross-line.
- Seed path, execution path, handler path, final check path.
- Expected exception cause/tval/data image.
- Whether the case requires cache/TLB/CBO/sbuffer/replay/MSHR behavior that Spike cannot model.

Use exact-source proof, not case name alone:

```bash
rg -n "PBMT|Pbmt|pbmt|VSRWXPbmt|PTE_Pbmt|pbmt_hspt_to_x|PMA|PMP|cbo_|prefetch|sfence|fence|mmio|IO|NC|phys_page_base|hs_page_base|vs_page_base|TEST_ASSERT|AI_ASSERT" <source-file>
```

## Spike And Platform Limitation Checks

For mismatch cases, ask:

- Does the case depend on cache/TLB state, CBO implementation choice, dirty line preservation, replay queue, ROB head, sbuffer, uncache buffer, or response-context binding? Spike usually cannot model these microarchitectural states.
- Does the case access PMA/PBMT/MMIO/device regions where Spike and the current platform may route differently?
- Does the current platform provide a real responder for the target PA? A legal PMA/peripheral range is not enough; no responder can cause no response/stuck.
- Does difftest compare memory that was updated through a path the golden memory does not observe?

Do not use “Spike also behaves the same” as proof of RTL bug for
microarchitectural behavior. Conversely, do not dismiss mismatches as Spike
limitation when the source/log shows ordinary architectural DRAM behavior.

For PMA/PBMT/MMIO/device/no-response cases, do the profile guard before using
waveform or platform code to classify the failure:

- Determine `spec_profile` from the workflow input or the hyptest-workflow
  profile registry default.
- Query/read `references/spec_profiles/<spec_profile>.md` and record the
  PMA/PBMT/window row: `spec_allowed`, `responder_required`,
  `spike_gate_applicable`, and default decision.
- Also record whether the target feature/corner is within current RTL/Nanhu
  implemented scope. If the profile or query output marks it as `nanhu_not_impl`,
  unimplemented, unsupported, or outside implementation scope, the case cannot be
  declared resolved by changing expectations or avoiding the feature.
- Treat the profile row as the only source for legality. Platform no-response
  evidence can prove `testbench_responder_confirmed=false`, but it must not be
  rephrased as "the PMA/PBMT combination is not allowed" unless the profile row
  says so.
- Then inspect the active spec profile's project-specific responder/source
  evidence section and the current waveform/log for the response path. Exact
  file/line checks, address windows, and known responder semantics belong in
  `references/spec_profiles/<spec_profile>.md`, not in this generic triage rule.
- If the profile says allowed but platform evidence shows no responder or an
  insufficient register-like responder, classify as `environment_blocked` or
  manual. If a concrete responder exists and supports the access semantics, keep
  investigating selfcheck vs RTL behavior.
- If the profile says the targeted RTL capability is not implemented, classify as
  `environment_blocked` / manual implementation gap, keep the original intent
  visible, and do not remove the case from failure/mismatch/stuck lists as a
  fixed case unless the user explicitly retargets it and the new implemented
  target has its own clean evidence.

## Reproduce With The Right Runner

Use the smallest batch that answers the question. Keep concurrency high but
bounded. For LinkNan evidence, choose `linknan-difftest` or `linknan-no-diff`
according to the handoff rules above:

```text
runner_mode: spike-gate | linknan-difftest | linknan-no-diff
compile_plat: spike | linknan
run_platform: spike | linknan
difftest_mode: not-applicable | enabled | disabled
include_commented: true | false
purpose:
cleanup_allowed: true | false
```

Rules:

- Use `--jobs` up to 20 when running multiple independent cases.
- Use at least `--timeout 900` for LinkNan runs unless the user explicitly requests otherwise.
- For Spike gate triage, compile/run Spike separately and compare logs.
- For `linknan-difftest`, the workflow runner must use difftest-enabled
  evidence; `HYPTEST_DIFFTEST_REF_SO` is required.
- For PMA/PBMT/MMIO mismatch, `official_spike_has_pma_csr=false` in the active
  profile only describes official/community Spike (`HYPTEST_SPIKE_BIN`). It does
  not prove that LinkNan difftest reference (`HYPTEST_DIFFTEST_REF_SO`) lacks
  PMA; keep REF-DUT PMA evidence on the `linknan-difftest` path unless triage
  explicitly needs a no-diff supplemental run.
- For `linknan-no-diff`, do not invent or hardcode a no-diff CLI flag in this
  skill. Tell `$hyptest-workflow` `runner_mode=linknan-no-diff` and
  `difftest_mode=disabled`; workflow chooses the current supported runner
  mechanism and records the artifacts.
- A timeout result is “inconclusive long run” unless internal stuck/watchdog/no-commit evidence appears in `run.log`.

## Waveform Evidence

Trigger waveform analysis when:

- The first bad point is unclear.
- A suspected RTL bug requires signal-level evidence.
- A 50000-cycle stuck needs no-response vs deadlock vs progress classification.
- The user asks to “看波形” or “具体定位”.
- PMA/PBMT/MMIO/Device responder behavior must be proven from request/response
  signals after the active profile guard.
- A difftest mismatch needs first-divergence or protocol evidence beyond the
  final mismatch line.

Do not trigger waveform analysis when source/log evidence is already sufficient:

- Obvious source-level `selfcheck_bug`, such as wrong seed/check address or
  impossible expected cause.
- Active profile says the target is `nanhu_not_impl` / unsupported /
  unimplemented and no signal evidence is needed to prove that classification.
- Failure-list cleanup where a clean trusted rerun is the only required evidence.
- Difftest mismatch cleanup; use `linknan-difftest` clean rerun evidence instead.
- Wall-clock timeout only, with no internal no-commit/watchdog and no waveform
  artifact to inspect.

Before calling `$waveform-debug`, prepare this handoff so signal-level work does
not lose source/spec context:

```text
case_name:
spec_profile:
runner_mode:
difftest_mode:
run_dir:
run.log:
assert.log:
waveform_path:
source_file:
source_intent:
expected_behavior:
observed_failure:
profile_guard_summary:
  spec_allowed:
  responder_required:
  spike_gate_applicable:
  rtl_implemented:
  testbench_responder_confirmed:
why_waveform_needed:
```

Waveform report must include:

- Target case and run directory.
- Expected behavior from source/spec/platform rules.
- Actual behavior from signal history.
- First useful bad point.
- Why the issue is not just Spike limitation or test selfcheck error.
- Suggested RTL owner area or test fix.

## Decision Table

```text
source assertion/setup wrong + corrected rerun passes
=> selfcheck_bug, patch ai_test_cases/manual_test_cases, remove from failure list

Official Spike gate mismatch explained by missing cache/TLB/PMA/PBMT/MMIO model, RTL-only passes or target is inherently RTL-only
=> spike_or_model_limitation, mark RTL-only/manual; do not call RTL bug

LinkNan difftest PMA/PBMT/MMIO mismatch with REF-DUT trap/data disagreement
=> keep linknan-difftest evidence, analyze first divergence + PMA CSR/profile/responder; do not classify as official Spike gap

PMA/PBMT/IO case needs a memory-like responder and none exists
=> environment_blocked, keep/manual; do not reroute to DRAM/dcache

active profile says target feature/corner is not implemented by current RTL/Nanhu
=> environment_blocked/manual implementation gap; do not fake PASS or clear as fixed

logs/waveform show incorrect RTL behavior under valid test expectation
=> suspected_rtl_bug, write report.md, keep in failure list unless user wants separate bug list

internal 50000 no-commit/watchdog on a valid responsive target
=> true stuck, write root-cause report; keep in the user-provided stuck list

wall timeout only, commits still happening, or assertions still printing
=> long running/inconclusive, do not classify stuck
```

Before patching, state the invariant that must remain true after the fix:

```text
PBMT/PMA IO case: still uses IO/PMA target, same access widths, no DRAM/dcache reroute.
Narrow-width case: still covers byte/half/word and signedness/lane behavior.
CBO/refill case: still performs cbo.inval/refill and checks preserved/zeroed line image per intent.
Trap-entry case: handler path and final check observe the same intended backing semantics.
Profile-not-implemented case: still names the unimplemented target and remains blocked/manual unless explicitly retargeted.
```

## Patch Policy For Test Fixes

When editing a test case:

- Preserve the original validation axis: same width, same alignment, same PMA/PBMT/cacheability target, same exception intent.
- Fix address/alias consistency instead of changing expected values to match broken setup.
- For PBMT/NC/IO alias cases, align seed path, handler path, execution path, and final check path to the intended alias/backing semantics.
- For PMA IO/device tests, use only responders that preserve required semantics. Do not use a profile-marked register-like responder if the case needs whole-line memory image, byte-lane merges, or arbitrary readback.
- For width tests, use width-correct operations (`sb/sh/sw/sd`, matching load signedness) instead of a fixed wider store.
- For profile-not-implemented cases, do not edit the case to avoid the
  unimplemented feature and then claim the original failure is fixed. Either
  preserve the intent and mark blocked/manual, or explicitly retarget the case as
  a different implemented scenario with new source/rerun evidence.
- If a patch/rerun exposes a new or remaining behavior that looks like a valid
  test expectation but incorrect RTL behavior, stop treating the work as simple
  selfcheck cleanup. Record a "待人工审核问题" item in the Chinese `report.md`
  with source/log/run-dir evidence, keep the case out of list-removal decisions,
  and either queue it for later human review or call `$waveform-debug` first if
  first-bad-cycle/protocol/no-response evidence is needed.
- Do not hide a suspected RTL behavior by changing the expected value, rerouting
  the address class, disabling the checked path, or converting the case to a
  weaker implemented scenario unless the user explicitly asks for a separate
  retargeted case and the original suspect remains recorded.
- After patching, compile and rerun only the affected cases first.

## Safe List Updates

Only remove from a user-provided selfcheck/stuck/mismatch failure list after rerun evidence:

```text
HIT GOOD TRAP
no FAILED
no ERROR
no mismatch
no internal watchdog/no-commit stuck
```

Preferred safe path:

```bash
python3 $HYPTEST_FAILURE_TRIAGE_SKILL_HOME/scripts/triage_snapshot.py \
  --list <failure-list> \
  --md-out <report-dir>/<topic>_snapshot.md \
  --json-out <report-dir>/<topic>_snapshot.json

python3 $HYPTEST_FAILURE_TRIAGE_SKILL_HOME/scripts/update_failure_list.py \
  --list <failure-list> \
  --snapshot-json <report-dir>/<topic>_snapshot.json \
  --list-kind selfcheck|stuck|mismatch \
  --dry-run
```

If dry-run output is correct, run the same updater without `--dry-run`.
Use `--verbose-skips` when the user asks why a case was not removed.
For `--list-kind mismatch`, do not use difftest-disabled evidence unless the
user explicitly accepts RTL-only cleanup for that list. The compatibility
override requires both `--allow-difftest-disabled` and
`--difftest-disabled-override-reason <reason>` so the report can record why a
normally unsafe cleanup was accepted.

## Report Template

Use `scripts/triage_report_template.py` as the single source of truth for the
editable report skeleton. The final failure-triage report must be a Chinese
Markdown file named exactly `report.md`; the script enforces that filename and
seeds the current required sections.

Required sections in the final report:

- `总结`
- `Case 列表`
- `错误分类与代表用例`
- `场景与验证意图`
- `失败现象`
- `源码分析`
- `Profile Guard`
- `波形报告`
- `待人工审核问题`
- `分类`
- `处理动作`
- `验证`

The `错误分类与代表用例` section must pick representative case(s) per
failure class/cluster and explain scenario, original expectation, observed
failure, and preliminary judgment. Do not treat cluster membership as the final
root cause without source, log, profile, and waveform evidence when needed.

The `Profile Guard` section is mandatory for PMA/PBMT/MMIO/Device/responder,
no-response, or profile implementation-scope cases. It must include at least:

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

If waveform-debug is used, waveform-debug should produce its own `report.md`;
cite that exact path in the triage report's `波形报告` section and summarize
only the key first-bad-cycle evidence.

## Final Answer Format

For the user, answer in Chinese by default and be concrete:

- Current classification and confidence.
- What was changed, if anything.
- Which cases were removed from lists, if any.
- Which cases remain and why.
- Exact report/log paths.
- Whether further waveform/RTL owner confirmation is needed.

Do not give vague conclusions such as “可能是 bug” without saying which
evidence supports it and what would disprove it.

For list triage, include a compact status table when useful:

```text
case | status | classification | action | evidence
```

Avoid dumping the whole script output in the final answer. Link the generated
snapshot/report path and summarize the decisions.

## Quick Examples

### Selfcheck Fix

```text
Finding: handler used PBMT=NC alias, but seed/final check used a different backing PA.
Action: make seed, handler, final check use the same intended alias/backing semantics.
Verification: compile linknan, run LinkNan, GOOD TRAP with no FAILED; remove from the user-provided selfcheck failure list.
```

### Stuck Triage

```text
Finding: run.log has no internal 50000 no-commit; commits continue and assertions print.
Action: do not classify stuck. Continue run or inspect final status.
```

### PMA/PBMT IO Case

```text
Finding: profile row is spec-allowed, but the current target PA has no responder, or only profile-marked register-like responders while the case needs byte/half/word lane merge, arbitrary readback, or whole-line memory image.
Action: mark environment_blocked/manual unless a memory-like MMIO scratch responder is available. Do not reroute to DRAM/dcache, and do not describe the no-response as a spec-disallowed PMA/PBMT combination unless the profile matrix says it is disallowed.
```
