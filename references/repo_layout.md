# Current Hyptest / LinkNan Layout

Use this reference when triage depends on source location, generated artifacts,
platform environment variables, or where to look for logs. List-level triage and
list cleanup require a user-provided or trusted workflow-provided list path;
single-case or log-only triage does not require any failure-list file.

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
$HYPTEST_LINKNAN_HOME/regress_logs/
$HYPTEST_LINKNAN_HOME/sim/simv/
$HYPTEST_LINKNAN_HOME/sim/simv/<case-or-run-name>/run.log
$HYPTEST_LINKNAN_HOME/sim/simv/<case-or-run-name>/assert.log
```

Run directory names may be truncated or prefixed. Prefer exact `case.name` /
`run.log` evidence over substring matching.

Do not infer failure-list paths from default names under `regress_logs/`. If a
user provides a single case, a Spike/LinkNan log, or pasted output, triage that
evidence directly. If the user asks for list-level analysis or list cleanup
without a list path, ask for the explicit path.

## Platform Names And Environment

Use current hyptest platform names:

```text
spike
linknan
```

Environment variables follow the `hyptest-workflow` public contract. Reusable
commands must emit `HYPTEST_*` names.

```text
HYPTEST_HOME            hyptest repo root
HYPTEST_LINKNAN_HOME    LinkNan repo root when LinkNan artifacts are needed
HYPTEST_DIFFTEST_REF_SO difftest reference shared object when LinkNan difftest reruns are needed
HYPTEST_SPIKE_BIN       official/community Spike executable when Spike reruns are needed
HYPTEST_CROSS_COMPILE   toolchain prefix only when workflow compile/rerun needs it
HYPTEST_TMPDIR          temporary directory when needed
HYPTEST_FAILURE_TRIAGE_SKILL_HOME failure-triage skill directory when manually running bundled scripts
```

Use dedicated skill-home variables for bundled scripts:

```text
HYPTEST_FAILURE_TRIAGE_SKILL_HOME  hyptest-failure-triage bundled scripts
HYPTEST_WORKFLOW_SKILL_HOME        hyptest-workflow bundled scripts
WAVEFORM_DEBUG                     waveform-debug bundled scripts
```

Do not emit `--plat xiangshan` or `--platform xiangshan`; LinkNan is the
hyptest platform name. RTL source paths may still contain `xiangshan` as a Scala
package path.
