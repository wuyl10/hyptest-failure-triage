# hyptest-failure-triage

`hyptest-failure-triage` 用于 `riscv-hyp-tests-nhv5.1` / LinkNan hyptest 失败闭环。它面向的不是“新增测试点”，而是把已经失败的 case 从失败列表、日志、源码、波形和重跑证据推进到可执行结论。

典型目标：

- 修正 selfcheck / case 断言或测试环境使用错误。
- 区分 Spike / golden model limitation、LinkNan 环境限制、测试自校验错误和真实 RTL 可疑 bug。
- 判断 stuck 是否有内部 no-commit / watchdog / waveform no-forward-progress 证据，而不是只看 wall-clock timeout。
- 为 suspected RTL bug 写出可审查的 `report.md`。
- 在验证通过后安全更新 `selfcheck_fail.txt`、`stuck.txt` 或 mismatch 列表。

## 入口文件

| 文件 | 作用 |
| --- | --- |
| `SKILL.md` | Codex 触发和执行入口，包含硬规则、任务路由、脚本顺序和最终答复要求 |
| `references/decision_rules.md` | 失败分类、证据等级、patch policy、安全删表规则、报告模板 |
| `references/known_patterns.md` | 已知 LinkNan / official Spike 失败模式，用作假设起点 |
| `references/repo_layout.md` | hyptest、LinkNan、日志和环境变量布局 |
| `references/resource_index.md` | 本 skill 的资源索引，列出 references、scripts、fixtures |

## 什么时候使用

看到这些输入或症状时应使用本 skill：

- `selfcheck_fail.txt`
- `stuck.txt`
- `run.log` / `assert.log`
- Spike / LinkNan difftest mismatch
- `HIT GOOD TRAP` 但仍 `FAILED`
- `50000 cycles no commit`
- wall-clock timeout 需要判断是不是 stuck
- FSDB / waveform 定位请求
- 请求删除已修复失败列表项
- 判断 suspected RTL bug
- 修复 `ai_test_cases/` / `manual_test_cases/` 的自校验错误

如果任务变成新增/修改 hyptest case、调整 `test_register.c`、编译批跑、回填 `test_point` 或分层落位，同时使用 `hyptest-workflow`。如果任务需要波形 first-bad-cycle、握手、协议或 X-state 分析，同时使用 `waveform-debug`。

## 环境变量

优先使用环境变量，不依赖个人绝对路径：

```text
HYPTEST_REPO or RVH_HYPTEST_REPO  riscv-hyp-tests-nhv5.1 repo root
LINKNAN_HOME                      LinkNan repo root
DIFFTEST_REF_SO                   difftest reference shared object
SPIKE_BIN                         official Spike executable when Spike reruns are needed
```

常见路径：

```text
selfcheck list   $LINKNAN_HOME/regress_logs/selfcheck_fail.txt
stuck list       $LINKNAN_HOME/regress_logs/stuck.txt
triage reports   $LINKNAN_HOME/regress_logs/
sim run dirs     $LINKNAN_HOME/sim/simv/
```

## 标准流程

常用命令可以直接列出：

```bash
python3 scripts/list_skill_commands.py
```

也可以生成 Markdown 或 JSON：

```bash
python3 scripts/list_skill_commands.py --markdown
python3 scripts/list_skill_commands.py --json
```

snapshot 是 triage 输入，不是最终证明。它帮助汇总 case 源码位置、关键词、最新 run 目录、run.log 特征和初步 bucket。聚类和计划是工作队列优化，不是最终 root cause。生成的命令不会自动执行，先人工检查，再决定是否运行。删除失败列表前必须先 dry-run；对 mismatch 列表必须使用 `--list-kind mismatch`，除非用户明确接受，否则不要用 difftest-disabled GOOD TRAP 清理 difftest mismatch。

下面这段命令由 `python3 scripts/update_readme_commands.py` 从 `scripts/list_skill_commands.py --markdown` 生成。

<!-- BEGIN GENERATED COMMANDS -->
### snapshot

- `selfcheck-snapshot`: Create a conservative first-pass snapshot from selfcheck_fail.txt.

  ```bash
  python3 scripts/triage_snapshot.py --list "$LINKNAN_HOME/regress_logs/selfcheck_fail.txt" --hyptest-repo "$HYPTEST_REPO" --linknan-repo "$LINKNAN_HOME" --md-out "$LINKNAN_HOME/regress_logs/selfcheck_snapshot.md" --json-out "$LINKNAN_HOME/regress_logs/selfcheck_snapshot.json"
  ```

- `stuck-snapshot`: Create a conservative first-pass snapshot from stuck.txt.

  ```bash
  python3 scripts/triage_snapshot.py --list "$LINKNAN_HOME/regress_logs/stuck.txt" --hyptest-repo "$HYPTEST_REPO" --linknan-repo "$LINKNAN_HOME" --md-out "$LINKNAN_HOME/regress_logs/stuck_snapshot.md" --json-out "$LINKNAN_HOME/regress_logs/stuck_snapshot.json"
  ```

### planning

- `cluster`: Cluster snapshot cases by conservative observable features.

  ```bash
  python3 scripts/cluster_failures.py --snapshot-json <topic>_snapshot.json --mode coarse --md-out <topic>_clusters.md --json-out <topic>_clusters.json
  ```

- `plan`: Create an action-oriented triage plan from a snapshot.

  ```bash
  python3 scripts/triage_plan.py --snapshot-json <topic>_snapshot.json --md-out <topic>_plan.md --json-out <topic>_plan.json
  ```

- `suggest-commands`: Generate conservative next-step commands without executing them.

  ```bash
  python3 scripts/command_suggester.py --snapshot-json <topic>_snapshot.json --limit 5 --jobs 20 --timeout 900 --md-out <topic>_commands.md --json-out <topic>_commands.json
  ```

### report

- `case-report`: Generate an editable report.md skeleton for a representative case.

  ```bash
  python3 scripts/triage_report_template.py --snapshot-json <topic>_snapshot.json --case <case_name> --title '<topic> triage report' --out <report-dir>/<topic>/report.md
  ```

- `action-report`: Generate a class-level report skeleton for a broad action group.

  ```bash
  python3 scripts/triage_report_template.py --snapshot-json <topic>_snapshot.json --action selfcheck_fail --max-cases 5 --title '<topic> triage report' --out <report-dir>/<topic>/report.md
  ```

### list-update

- `selfcheck-dry-run`: Preview safe removals from selfcheck_fail.txt.

  ```bash
  python3 scripts/update_failure_list.py --list "$LINKNAN_HOME/regress_logs/selfcheck_fail.txt" --snapshot-json <topic>_snapshot.json --list-kind selfcheck --dry-run --verbose-skips
  ```

- `mismatch-dry-run`: Preview safe removals from a difftest mismatch list; difftest-enabled evidence is required.

  ```bash
  python3 scripts/update_failure_list.py --list <mismatch-list> --snapshot-json <topic>_snapshot.json --list-kind mismatch --dry-run --verbose-skips
  ```

### compare

- `compare-snapshots`: Compare two snapshots after reruns or LinkNan/dependency updates.

  ```bash
  python3 scripts/compare_snapshots.py --old <old>_snapshot.json --new <new>_snapshot.json --md-out <topic>_compare.md --json-out <topic>_compare.json
  ```

### validation

- `selftest`: Run the bundled synthetic self-test suite.

  ```bash
  python3 scripts/selftest.py
  ```

- `log-pattern-eval`: Check realistic run.log / Spike snippet classifications.

  ```bash
  python3 scripts/eval_log_patterns.py
  ```

- `official-spike-eval`: Check official Spike known model-gap classifications.

  ```bash
  python3 scripts/eval_official_spike_patterns.py
  ```

### maintenance

- `readme-check`: Check README generated commands match list_skill_commands.py.

  ```bash
  python3 scripts/check_readme_commands.py
  ```

- `readme-update`: Refresh README generated command block from list_skill_commands.py.

  ```bash
  python3 scripts/update_readme_commands.py
  ```

- `resource-index-check`: Check resource_index.md covers references, scripts, fixtures, and README anchors.

  ```bash
  python3 scripts/check_resource_index.py
  ```

- `fixture-manifest-check`: Check fixture manifests match the log files on disk.

  ```bash
  python3 scripts/check_fixture_manifests.py
  ```
<!-- END GENERATED COMMANDS -->

## 分类口径

| 分类 | 含义 | 动作 |
| --- | --- | --- |
| `selfcheck_bug` | 用例断言、地址别名、seed/check 路径或期望错误 | 修 case，编译和重跑，PASS 后删表 |
| `spike_or_model_limitation` | Spike/golden model 缺少 cache/TLB/PMA/PBMT/MMIO/CBO 等模型 | 标记 RTL-only/manual/blocked，不误判 RTL bug |
| `suspected_rtl_bug` | 测试意图合理，源码和日志/波形指向 RTL 错误 | 写 `report.md`，给出证据和 owner 区域 |
| `environment_blocked` | 当前 testbench 缺少需要的 responder 或环境能力 | 保留 blocked/manual，不改成 DRAM/dcache 逃避 |
| `true_stuck` | 有内部 no-commit/watchdog 或波形无前进证据 | 写 stuck report，保留列表 |
| `inconclusive` | 证据不足，例如 wall-clock timeout only | 不删表，不硬判 stuck 或 RTL bug |

## 硬规则速记

- 不要从 wall-clock timeout alone 判断 stuck。
- 不要用 difftest-disabled PASS 清理 difftest mismatch。
- 不要为了通过而削弱测试意图，例如把 PMA/PBMT/IO 改成 DRAM/dcache。
- 不要把 byte/half/word 覆盖降成只有 8B 访问。
- 不要默认修改 RTL；suspected RTL bug 默认写证据和 owner check points。
- 不要删除失败列表项，除非最新可信 rerun 是 clean GOOD TRAP/PASS 且无 FAILED/ERROR/mismatch/watchdog。
- 保留 dirty worktree 中与当前任务无关的修改，不回滚用户改动。

## 自检

修改本 skill 后运行：

```bash
python3 scripts/selftest.py
python3 scripts/check_readme_commands.py
python3 scripts/check_resource_index.py
python3 scripts/check_fixture_manifests.py
```

更聚焦的模式检查：

```bash
python3 scripts/eval_log_patterns.py
python3 scripts/eval_official_spike_patterns.py
```

## 最终答复要求

默认用中文，结论要具体：

- 当前分类和置信度。
- 改了什么，若有。
- 删除了哪些失败列表项，若有。
- 哪些 case 仍保留，原因是什么。
- 关键 snapshot/report/log 路径。
- 是否仍需要 waveform 或 RTL owner 确认。

不要只说“可能是 bug”。必须说明支持证据，以及什么证据会推翻当前判断。
