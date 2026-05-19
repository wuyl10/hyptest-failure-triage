# Current Hyptest / LinkNan Layout

Use this reference when triage depends on source location, generated artifacts,
platform environment variables, or where to look for logs/lists. It describes
conventional locations only; single-case or log-only triage does not require
`selfcheck_fail.txt` or `stuck.txt`.

## Hyptest Source Layout

```text
src/                 framework C sources
asm/                 framework assembly entry/handlers
inc/                 public headers and test macros
ai_test_cases/       AI or bulk-generated cases
manual_test_cases/   human-maintained cases, grouped by module
test_register.c      single registration/status source
compile_elf.py       single-case and batch compile entry
get_result.py        Spike/LinkNan run entry
test_point/          test point documents and mapping notes
```

`triage_snapshot.py` indexes both `ai_test_cases/*.c` and
`manual_test_cases/**/*.c`, plus root `.c` files except `test_register.c`.

## Generated Hyptest Artifacts

```text
build/
deploy/
case_elf_asm/
.tmp/
.hyptest_workflow_skill/
```

`case_elf_asm/` is the only current per-case ELF/ASM export directory.
`.tmp/hyptest_compile/` is used by `compile_elf.py` for generated register
sources and compiler temporary files.
`.tmp/result_log/` is used by `get_result.py` for Spike/LinkNan run logs.
`.hyptest_workflow_skill/` holds workflow cache/report/tmp/memory state; triage
may consume reports or handoff JSON from there, but should not treat cache as
source truth.
Do not reintroduce removed legacy ELF/ASM output directory names into commands,
docs, or cleanup logic. Do not write new hyptest run-log references to a root
`result_log/` directory; use `.tmp/result_log/`.

Do not treat generated artifacts as source of test intent. Use them only as run
or compile evidence.

## LinkNan Run Artifacts

```text
$LINKNAN_HOME/regress_logs/
$LINKNAN_HOME/sim/simv/
$LINKNAN_HOME/sim/simv/<case-or-run-name>/run.log
$LINKNAN_HOME/sim/simv/<case-or-run-name>/assert.log
```

Run directory names may be truncated or prefixed. Prefer exact `case.name` /
`run.log` evidence over substring matching.

Conventional list candidates, only for list-mode triage or cleanup:

```text
$LINKNAN_HOME/regress_logs/selfcheck_fail.txt
$LINKNAN_HOME/regress_logs/stuck.txt
```

These files are discovery hints, not mandatory inputs. If a user provides a
single case, a QEMU/Spike/LinkNan log, or pasted output, triage that evidence
directly. Require a list path only when the user asks for list-level analysis or
list cleanup.

## Platform Names And Environment

Use current hyptest platform names:

```text
spike
linknan
qemu     when the target repo supports QEMU in compile_elf.py/get_result.py
```

Required environment variables for reusable commands:

```text
HYPTEST_REPO or RVH_HYPTEST_REPO  hyptest repo root
LINKNAN_HOME                      LinkNan repo root when LinkNan artifacts are needed
DIFFTEST_REF_SO                   difftest reference shared object when LinkNan reruns are needed
SPIKE_BIN                         official Spike executable when Spike reruns are needed
HYPTEST_QEMU_BIN                  QEMU executable when QEMU reruns are needed
```

Do not emit `--plat xiangshan` or `--platform xiangshan`; LinkNan is the
hyptest platform name. RTL source paths may still contain `xiangshan` as a Scala
package path.
