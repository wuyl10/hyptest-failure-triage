# Current Hyptest / LinkNan Layout

Use this reference when triage depends on source location, generated artifacts,
or platform environment variables.

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
result_log/
tmp/
```

`case_elf_asm/` is the only current per-case ELF/ASM export directory.
Do not reintroduce removed legacy ELF/ASM output directory names into commands,
docs, or cleanup logic.

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

## Platform Names And Environment

Use current hyptest platform names:

```text
spike
linknan
```

Required environment variables for reusable commands:

```text
HYPTEST_REPO or RVH_HYPTEST_REPO  riscv-hyp-tests-nhv5.1 repo root
LINKNAN_HOME                      LinkNan repo root
DIFFTEST_REF_SO                   difftest reference shared object
SPIKE_BIN                         official Spike executable
```

Do not emit `--plat xiangshan` or `--platform xiangshan`; LinkNan is the
hyptest platform name. RTL source paths may still contain `xiangshan` as a Scala
package path.
