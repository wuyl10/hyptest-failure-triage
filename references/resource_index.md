# Resource Index

本文是 `hyptest-failure-triage` 的资源索引，用于人工维护和快速定位。`SKILL.md` 保留执行入口和硬规则；具体分类、布局、模式、脚本和 fixtures 放在这里集中说明。

## Rule References

| 文件 | 用途 |
| --- | --- |
| `references/decision_rules.md` | 失败分类、证据等级、source intent 重建、Spike/平台模型边界、重跑规则、波形要求、patch policy、安全删表、报告模板 |
| `references/known_patterns.md` | 已知 LinkNan / official Spike 失败模式：CBO/refill、PBMT=NC trap-entry、PMA/PBMT IO stuck、difftest-disabled wave、official Spike model gaps、true stuck vs long run |
| `references/repo_layout.md` | hyptest 源码布局、生成物、LinkNan run artifacts、平台名和环境变量 |
| `references/resource_index.md` | 当前索引文件 |

## Public Scripts

| 脚本 | 用途 |
| --- | --- |
| `scripts/triage_snapshot.py` | 对 `selfcheck_fail.txt` / `stuck.txt` 等失败列表做第一轮快照，索引源码、关键词、最新 run 目录和 run.log 特征 |
| `scripts/cluster_failures.py` | 对 snapshot JSON 做保守聚类，支持 `coarse` / `theme` / `strict` |
| `scripts/triage_plan.py` | 从 snapshot JSON 生成 action-oriented plan，划分删除候选、source/rerun、waveform/report、mismatch、stuck、inconclusive 等工作队列 |
| `scripts/command_suggester.py` | 从 snapshot 生成保守的下一步命令建议，不自动执行 |
| `scripts/triage_report_template.py` | 从 snapshot 生成可编辑 `report.md` 骨架，预填 case、run/source 证据和必要章节 |
| `scripts/update_failure_list.py` | 只删除最新 clean `passed_good_trap` 的失败列表项；支持 `--dry-run`、`--list-kind` 和 `.bak` |
| `scripts/compare_snapshots.py` | 对比两份 snapshot，找新增、已解决、状态变化、evidence tag 变化和 latest-run 变化 |
| `scripts/known_pattern_classifier.py` | 已知模式分类辅助，被 snapshot/评估脚本复用 |
| `scripts/env_paths.py` | 环境变量和路径解析辅助 |
| `scripts/list_skill_commands.py` | 打印常用 triage 命令，支持 text / Markdown / JSON 输出 |
| `scripts/update_readme_commands.py` | 从 `list_skill_commands.py --markdown` 刷新 README 生成命令块 |
| `scripts/check_readme_commands.py` | 检查 README 生成命令块是否与 `list_skill_commands.py --markdown` 一致 |
| `scripts/check_resource_index.py` | 检查 resource index 是否覆盖 public scripts、references 和 fixtures，并检查 README 关键入口 |
| `scripts/check_fixture_manifests.py` | 检查 fixture manifest 是否和磁盘上的 `.log` 文件一致 |
| `scripts/selftest.py` | 综合自测，覆盖分类、list update、聚类、plan、report、compare、command suggestion 和 fixtures |
| `scripts/eval_log_patterns.py` | realistic run.log / Spike snippet 模式评估 |
| `scripts/eval_official_spike_patterns.py` | official Spike known model-gap 模式评估 |

## Fixtures

### `fixtures/logs/`

| fixture | 覆盖现象 |
| --- | --- |
| `hit_good_trap_but_failed.log` | GOOD TRAP 但 selfcheck FAILED |
| `difftest_mismatch.log` | difftest mismatch |
| `internal_50000_no_commit.log` | 内部 50000 cycles no commit |
| `timeout_only.log` | 仅 wall-clock timeout，不足以判 stuck |
| `fsdb_version_warning_pass.log` | FSDB/Verdi banner 但测试通过 |
| `untested_exception_error.log` | untested exception |
| `bad_trap.log` | BAD TRAP |
| `plain_50000_parameter_pass.log` | 普通 50000 参数或消息，不能误判 no-commit |
| `manifest.json` | fixture manifest |

### `fixtures/official_spike/`

| fixture | 覆盖现象 |
| --- | --- |
| `cbo_no_a_fault_classification.log` | CBO permission / A-bit 分类差异 |
| `pma_pbmt_mmio_cacheability.log` | PMA/PBMT/MMIO/cacheability model gap |
| `missing_custom_csr.log` | custom CSR / custom privilege model gap |
| `nmi_double_trap_scope_excluded.log` | NMI / double trap scope exclusion |
| `lrsc_reservation_timeout.log` | LR/SC reservation timeout model gap |
| `illegal_instruction_model_gap.log` | official Spike illegal instruction model gap |
| `manifest.json` | fixture manifest |

## Recommended Maintenance Checks

修改 skill 文档后至少运行：

```bash
python3 scripts/selftest.py
python3 scripts/check_readme_commands.py
python3 scripts/check_resource_index.py
python3 scripts/check_fixture_manifests.py
```

修改 run.log 模式识别时运行：

```bash
python3 scripts/eval_log_patterns.py
```

修改 official Spike 模式识别时运行：

```bash
python3 scripts/eval_official_spike_patterns.py
```

新增脚本或 fixture 后，更新本索引并确认 `README.md` 和 `SKILL.md` 中的命令仍然准确。

## Cross-Skill Boundary

| 任务 | 主要 skill | 说明 |
| --- | --- | --- |
| 新增/修改 case、注册、编译、运行、分层、回填 `test_point` | `hyptest-workflow` | failure triage 可以给出修复方向，但落地 workflow 规则仍由 workflow skill 负责 |
| selfcheck/stuck/mismatch/run.log 归因、失败列表更新、suspected RTL bug 报告 | `hyptest-failure-triage` | 当前 skill 的主职责 |
| FSDB/VCD/FST waveform first-bad-cycle、握手、协议、X-state 定位 | `waveform-debug` | 当前 skill 负责准备源意图和 run 证据，波形细节交给 waveform skill |
