# Known Hyptest Failure Patterns

Load this reference when a new failure resembles one of the patterns below.
These notes are distilled from prior LinkNan / riscv-hyp-tests-nhv5.1 triage in
this workspace. Treat them as starting hypotheses, not final proof.

## Class 1-5: CBO / Refill / Line Image Selfcheck Failures

Typical observable shape:

- `selfcheck_fail.txt` contains many HS cache/CBO/prefetch/sbuffer/AMO cases.
- Latest runs may be `difftest-disabled`; some have `fsdb,wave-run`.
- Source has `exact_pbmt_hits=0`, so do not explain these as PBMT=NC or PBMT=IO behavior without new evidence.
- Failures mention preserved adjacent word, old image, refill image, zero line, overlay, prefetch, AMO replay, or trap-entry same-block `cbo.inval`.

Useful first checks:

- Run `triage_snapshot.py`, `cluster_failures.py --mode coarse`, and `triage_plan.py`.
- Confirm the representative source really uses cacheable DRAM-like pages, not PBMT/PMA IO.
- Check whether latest evidence is difftest-disabled waveform evidence before using it for mismatch cleanup.
- If writing a report, start from `triage_report_template.py --action waveform_report_update` for wave-backed representatives.

Prior working hypothesis:

- Representative waveforms pointed at a common CBO/refill line-image preservation issue: after `cbo.inval` implemented as flush, the expected dirty/seeded line image was not preserved in the later refill/final memory image.
- This should be treated as `suspected_rtl_bug` only after source/waveform confirms the test expectation is valid and the first bad point is in RTL line-image/refill behavior.

Avoid these mistakes:

- Do not classify as PBMT=NC/IO just because some other failures involved PBMT.
- Do not clear difftest mismatch lists using difftest-disabled waveform PASS.
- Do not rewrite tests to avoid CBO/refill behavior if that is the verification target.

## Class 6: PBMT=NC Trap-Entry Same-Address Observer

Typical observable shape:

- PBMT=NC misaligned trap-entry observer tests may fail selfcheck around handler byte load/store visibility.
- Difftest may not report mismatch even when selfcheck fails, because the test is checking a microarchitectural/alias/backing-memory observation that difftest may not compare at the exact path or time.

Useful first checks:

- Inspect the test source to ensure seed path, faulting path, handler path, and final check observe the same intended alias/backing semantics.
- Confirm whether the handler operation is byte/half/word/narrow and whether final check uses the same intended address semantics.
- If the source has already been patched to make alias/backing semantics consistent, require a clean rerun before deleting from `selfcheck_fail.txt`.

Prior fix pattern:

- If the selfcheck bug is alias/backing inconsistency, fix the test so the seed, handler, execution, and final check paths observe the same intended backing semantics.
- Do not simply change the expected value to match the observed failure.

Avoid these mistakes:

- Do not assume “no difftest mismatch” means the selfcheck is wrong.
- Do not assume PBMT=NC always makes the assertion invalid; first prove whether the case intended cache-bypass/backing observation.

## PMA / PBMT IO Good-Path Stuck Or No-Response Cases

Typical observable shape:

- Case accesses PMA/PBMT IO/device-like physical ranges.
- Run may hit internal `50000 cycles no commit` or no-response behavior.
- The case may require byte/half/word lane merges and whole-line readback.

Useful first checks:

- Determine whether the original verification target is PMA/PBMT/IO behavior.
- Check whether LinkNan testbench has a real responder for the target PA. A legal peripheral/PMA range is not enough.
- Distinguish real internal no-commit/watchdog evidence from wall-clock timeout.

Prior environment conclusion:

- UART/IntrGen register responders are not equivalent to a memory-like MMIO scratch region if the test needs arbitrary byte-lane merge and whole-line readback.
- In that situation classify as `environment_blocked` or manual unless a memory-like responder exists.

Avoid these mistakes:

- Do not reroute PMA/PBMT/IO validation to DRAM/dcache to make it pass.
- Do not convert narrow byte/half/word matrix coverage to only 8B access coverage unless the original case naturally has 8B register semantics.
- Do not classify `900s` wall timeout alone as stuck; require internal no-commit/watchdog or waveform no-forward-progress evidence.

## Difftest-Disabled / Waveform Runs

Typical observable shape:

- `run.log` contains `disable diff-test`.
- `run.log` contains FSDB/Verdi banners, sometimes with a standalone `ERROR -` line.
- The run may still end in `HIT GOOD TRAP` or selfcheck `FAILED`.

Rules:

- FSDB/Verdi dumper version banners are not test failures by themselves.
- Difftest-disabled PASS is useful for selfcheck or waveform conclusions.
- Difftest-disabled PASS is not enough to clear a difftest mismatch list.

Recommended tool behavior:

- Use `triage_snapshot.py` evidence tags: `difftest-disabled`, `fsdb`, `wave-run`, `clean-good-trap`.
- Use `update_failure_list.py --list-kind mismatch` for mismatch cleanup so difftest-disabled evidence is rejected unless explicitly overridden.

## Official Spike Model Gaps

These patterns explain failures seen only on official Spike. They are not enough
to label LinkNan as wrong unless LinkNan/RTL evidence independently disagrees
with the architectural intent.

### CBO permission / A-bit classification

Observable shape:

- `cbo.zero` on a page missing A may report Store Page Fault on official Spike.
- Some project expectations distinguish no-A classification or preserve CBO
  target-block side effects more strictly than official Spike models.

Recommended action:

- Record as official Spike model gap when the case is meant to validate the RTL
  behavior and official Spike lacks the same CBO permission classification.
- Keep the test only if the assertion is still valid for NHV5.1AP RTL; otherwise
  move it to manual/compile-only instead of changing the architectural target.

### PMA / PBMT / MMIO / cacheability model gap

Observable shape:

- Case depends on PMA regions, PBMT cacheability, MMIO responder semantics, or
  cache-vs-uncache side effects.
- Official Spike either treats the memory as a flat model or lacks the same PMA,
  PBMT, device-response, cache/TLB timing, or line-state behavior.

Recommended action:

- Do not use official Spike as the default pass/fail gate for these cases.
- Classify as official Spike model gap or manual/RTL-only after confirming the
  source intentionally targets PMA/PBMT/MMIO/cacheability behavior.
- Do not rewrite the target address back to normal DRAM only to satisfy Spike.

### Missing custom CSR / custom privilege model

Observable shape:

- Official Spike traps on a custom CSR, custom instruction, platform-specific
  privilege hook, or implementation-specific state that LinkNan supports.

Recommended action:

- Record as official Spike model gap and delete from official-Spike failure
  noise when the case is outside the official model.
- Preserve the case for LinkNan/manual validation if it is in project scope.

### NMI / double trap outside NHV5.1AP project scope

Observable shape:

- Cases cover NMI or double-trap behavior that is not required by the current
  NHV5.1AP core verification scope.

Recommended action:

- Remove these cases from the active official-Spike triage list.
- Record the removal as project-scope exclusion, not as an RTL bug.

### LR/SC reservation timeout model gap

Observable shape:

- Case expects microarchitectural reservation timeout/expiry behavior.
- Official Spike models architectural LR/SC success/failure at a much simpler
  level and may not implement the same timeout policy.

Recommended action:

- Treat as official Spike model gap for official-Spike cleanup.
- Keep only as manual/RTL-focused coverage when the timeout policy is an
  intended LinkNan verification target.

## True Stuck Versus Long Run

Real stuck evidence:

- Internal `50000 cycles no commit`.
- Internal watchdog/no-forward-progress message.
- Waveform/log evidence that commits stop and the request cannot receive a response.

Inconclusive evidence:

- Wall-clock timeout only.
- Long-running tests that continue to print assertions or commit/progress information.
- A bare numeric `50000` in parameters or messages without no-commit/watchdog context.

Recommended action:

- For inconclusive long runs, rerun longer or inspect progress signals/logs.
- For true stuck, write a focused stuck report with request path, target address class, responder availability, and first no-forward-progress point.
