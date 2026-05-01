# Hyptest Failure Triage Decision Rules

Load this reference when classification is nontrivial, when editing tests, when
writing a `report.md`, or when deciding whether a case can be removed from
`selfcheck_fail.txt` / `stuck.txt` / mismatch lists.

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

The failure is expected because Spike/golden model lacks a microarchitectural
feature or platform model needed by the case.

Common causes:

- Spike has no cache/TLB timing model for cache-residency, CBO side effects, refill ordering, replay queues, sbuffer, uncache buffer, or response-context binding.
- Spike/PMA model differs from LinkNan PMA/PBMT/MMIO routing.
- The case intentionally observes RTL-only behavior such as cacheline dirty preservation, MMIO response timing, internal watchdog, or replay escape.

Action:

- Do not call it RTL bug solely from mismatch.
- Mark `RTL-only`, `manual`, or `blocked` as appropriate.
- If a responder exists and preserves intent, reroute only to an equivalent responder. Otherwise leave blocked/manual.

### `suspected_rtl_bug`

The test expectation matches ISA/platform intent, the setup is coherent, and
RTL/log/waveform evidence shows incorrect behavior.

Action:

- Write a focused `report.md` under `regress_logs/<topic>/`.
- Include scene, expected behavior, actual behavior, first bad point, why it is not a test/Spike limitation, and likely RTL owner area.
- Do not edit RTL unless explicitly asked.

### `environment_blocked`

The case needs a platform responder or memory-like region that the current
LinkNan testbench does not provide.

Typical examples:

- PMA/PBMT IO good path requires byte/half/word lane + whole-line readback, but available UART/IntrGen responders are only register-like.
- Address range is legal PMA/peripheral range but current `SimMMIO` has no response path.

Action:

- Do not fake pass by moving to DRAM/dcache if PMA/PBMT/IO is the test target.
- Mark blocked/manual and state exactly what responder is missing.

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
- Does the case access PMA/PBMT/MMIO/device regions where Spike and LinkNan may route differently?
- Does LinkNan provide a real responder for the target PA? A legal PMA/peripheral range is not enough; no responder can cause no response/stuck.
- Does difftest compare memory that was updated through a path the golden memory does not observe?

Do not use “Spike also behaves the same” as proof of RTL bug for
microarchitectural behavior. Conversely, do not dismiss mismatches as Spike
limitation when the source/log shows ordinary architectural DRAM behavior.

## Reproduce With The Right Runner

Use the smallest batch that answers the question. Keep concurrency high but
bounded:

```bash
cd <hyptest-repo>
test -n "${LINKNAN_HOME:-}" || { echo "missing LINKNAN_HOME"; exit 2; }
test -n "${DIFFTEST_REF_SO:-}" || { echo "missing DIFFTEST_REF_SO"; exit 2; }
python3 compile_elf.py --plat linknan --include-commented --name <case>
python3 get_result.py --platform linknan --case <case> --jobs <1..20> --timeout 900
```

Rules:

- Use `--jobs` up to 20 when running multiple independent cases.
- Use at least `--timeout 900` for LinkNan runs unless the user explicitly requests otherwise.
- For Spike-only triage, compile/run Spike separately and compare logs.
- A timeout result is “inconclusive long run” unless internal stuck/watchdog/no-commit evidence appears in `run.log`.

## Waveform Evidence

Trigger waveform analysis when:

- The first bad point is unclear.
- A suspected RTL bug requires signal-level evidence.
- A 50000-cycle stuck needs no-response vs deadlock vs progress classification.
- The user asks to “看波形” or “具体定位”.

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

Spike mismatch explained by missing cache/TLB/PMA/PBMT/MMIO model, RTL-only passes or target is inherently RTL-only
=> spike_or_model_limitation, mark RTL-only/manual; do not call RTL bug

PMA/PBMT/IO case needs a memory-like responder and none exists
=> environment_blocked, keep/manual; do not reroute to DRAM/dcache

logs/waveform show incorrect RTL behavior under valid test expectation
=> suspected_rtl_bug, write report.md, keep in failure list unless user wants separate bug list

internal 50000 no-commit/watchdog on a valid responsive target
=> true stuck, write root-cause report; keep in stuck.txt

wall timeout only, commits still happening, or assertions still printing
=> long running/inconclusive, do not classify stuck
```

Before patching, state the invariant that must remain true after the fix:

```text
PBMT/PMA IO case: still uses IO/PMA target, same access widths, no DRAM/dcache reroute.
Narrow-width case: still covers byte/half/word and signedness/lane behavior.
CBO/refill case: still performs cbo.inval/refill and checks preserved/zeroed line image per intent.
Trap-entry case: handler path and final check observe the same intended backing semantics.
```

## Patch Policy For Test Fixes

When editing a test case:

- Preserve the original validation axis: same width, same alignment, same PMA/PBMT/cacheability target, same exception intent.
- Fix address/alias consistency instead of changing expected values to match broken setup.
- For PBMT/NC/IO alias cases, align seed path, handler path, execution path, and final check path to the intended alias/backing semantics.
- For PMA IO/device tests, use only responders that preserve required semantics. Do not use UART/IntrGen if the case needs whole-line memory image, byte-lane merges, or arbitrary readback.
- For width tests, use width-correct operations (`sb/sh/sw/sd`, matching load signedness) instead of a fixed wider store.
- After patching, compile and rerun only the affected cases first.

## Safe List Updates

Only remove from `selfcheck_fail.txt` or `stuck.txt` after rerun evidence:

```text
HIT GOOD TRAP
no FAILED
no ERROR
no mismatch
no internal watchdog/no-commit stuck
```

Preferred safe path:

```bash
python3 <skill-dir>/scripts/triage_snapshot.py \
  --list <failure-list> \
  --md-out <report-dir>/<topic>_snapshot.md \
  --json-out <report-dir>/<topic>_snapshot.json

python3 <skill-dir>/scripts/update_failure_list.py \
  --list <failure-list> \
  --snapshot-json <report-dir>/<topic>_snapshot.json \
  --list-kind selfcheck \
  --dry-run
```

If dry-run output is correct, run the same updater without `--dry-run`.
Use `--verbose-skips` when the user asks why a case was not removed.

## Report Template

Use this structure for nontrivial triage:

```markdown
# <case/class/topic> triage report

## Summary
One-paragraph conclusion: selfcheck_bug / spike_or_model_limitation / suspected_rtl_bug / environment_blocked / true_stuck / inconclusive.

## Cases
List affected cases and current status.

## Scene And Intent
What the case is trying to verify, including mode, address type, width/alignment, and expected behavior.

## Observed Failure
Relevant run.log lines, mismatch fields, failed asserts, or stuck evidence.

## Source Analysis
Important source snippets by file:line and helper behavior. Explain seed/execute/handler/check paths.

## Waveform Evidence
Only if used. Include first bad time/cycle, key signals, and why later symptoms are secondary.

## Classification
State the selected taxonomy label and why alternatives were rejected.

## Action
Patch performed, report-only bug, manual/blocked decision, or required platform support.

## Verification
Commands run, result log paths, PASS/FAIL/GOOD TRAP evidence, and list updates.
```

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
Verification: compile linknan, run LinkNan, GOOD TRAP with no FAILED; remove from selfcheck_fail.txt.
```

### Stuck Triage

```text
Finding: run.log has no internal 50000 no-commit; commits continue and assertions print.
Action: do not classify stuck. Continue run or inspect final status.
```

### PMA/PBMT IO Case

```text
Finding: case requires byte/half/word lane and whole-line readback on IO-like memory, but only UART/IntrGen register responders exist.
Action: mark environment_blocked/manual unless a memory-like MMIO scratch responder is available. Do not reroute to DRAM/dcache.
```
