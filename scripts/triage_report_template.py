#!/usr/bin/env python3
"""Create an editable Chinese report.md skeleton from a hyptest triage snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_snapshot(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(errors="ignore"))
    if not isinstance(data, list):
        raise SystemExit(f"snapshot JSON must contain a list: {path}")
    return data


def latest_run(item: dict[str, Any]) -> dict[str, Any]:
    runs = item.get("runs") or []
    return runs[0] if runs else {}


def has_waveform_evidence(item: dict[str, Any]) -> bool:
    tags = set(latest_run(item).get("evidence_tags") or [])
    return bool(tags & {"wave-run", "fsdb", "waveform"})


def select_cases(snapshot: list[dict[str, Any]], cases: list[str], action: str | None) -> list[dict[str, Any]]:
    if cases:
        wanted = set(cases)
        selected = [item for item in snapshot if item.get("case") in wanted]
        missing = sorted(wanted - {item.get("case") for item in selected})
        if missing:
            raise SystemExit(f"case(s) not found in snapshot: {', '.join(missing)}")
        return selected
    if action:
        selected = []
        for item in snapshot:
            status = latest_run(item).get("status", "no_run")
            tags = set(latest_run(item).get("evidence_tags") or [])
            if action == "selfcheck_fail" and status == "selfcheck_fail":
                selected.append(item)
            elif action in {"waveform", "waveform_report_update"} and has_waveform_evidence(item):
                selected.append(item)
            elif action == "mismatch" and status == "difftest_mismatch":
                selected.append(item)
            elif action == "stuck" and status == "true_stuck_evidence":
                selected.append(item)
            elif action == "passed" and status == "passed_good_trap":
                selected.append(item)
        return selected
    return snapshot[:1]


def md_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def source_ref(source: dict[str, Any]) -> str:
    if not source:
        return "NOT FOUND"
    return f"{source.get('path')}:{source.get('start_line')}-{source.get('end_line')}"


def write_report(
    path: Path,
    snapshot_path: Path,
    selected: list[dict[str, Any]],
    title: str,
    max_cases: int,
    waveform_reports: list[Path],
) -> None:
    if path.name != "report.md":
        raise SystemExit(f"triage report output must be named report.md: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append("## 总结")
    lines.append("")
    lines.append("待填写：用一段中文给出最终结论。分类必须选择一个：`selfcheck_bug`、`spike_or_model_limitation`、`suspected_rtl_bug`、`environment_blocked`、`true_stuck` 或 `inconclusive`。")
    lines.append("")
    lines.append("## Case 列表")
    lines.append("")
    lines.append(f"- snapshot: `{snapshot_path}`")
    lines.append(f"- selected_cases: `{len(selected)}`")
    lines.append("")
    lines.append("| Case | 最新状态 | 证据标签 | 源码位置 | 最新运行 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for item in selected:
        run = latest_run(item)
        source = item.get("source") or {}
        lines.append(
            "| "
            + " | ".join(
                md_escape(str(x))
                for x in [
                    item.get("case"),
                    run.get("status", "no_run"),
                    ",".join(run.get("evidence_tags") or []),
                    source_ref(source),
                    run.get("path", "NOT FOUND"),
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## 错误分类与代表用例")
    lines.append("")
    lines.append("待填写：按错误簇/错误分类挑代表用例展开。每个错误簇至少写一个代表 case；同类剩余 case 可列在“涉及 case”。不要把 cluster 当最终 root cause，必须结合源码、日志、profile 和必要时波形证据判断。")
    lines.append("")
    lines.append("### <错误簇或分类名称>")
    lines.append("")
    lines.append("- representative_case: `TBD`")
    lines.append("- 涉及 case: `TBD`")
    lines.append("- 初步分类: `selfcheck_bug | spike_or_model_limitation | suspected_rtl_bug | environment_blocked | true_stuck | inconclusive`")
    lines.append("- 置信度: `high | medium | low`")
    lines.append("")
    lines.append("#### 场景")
    lines.append("")
    lines.append("待填写：代表用例测什么；包括特权级、地址类型、PMA/PBMT/MMIO/DRAM/cacheability、访问宽度、异常/handler/check 路径。")
    lines.append("")
    lines.append("#### 本来预期")
    lines.append("")
    lines.append("待填写：按 spec/profile/test intent，本来应该发生什么。")
    lines.append("")
    lines.append("#### 错误情况")
    lines.append("")
    lines.append("待填写：run.log/assert.log/mismatch/waveform 观察到的实际错误。")
    lines.append("")
    lines.append("#### 初步判断")
    lines.append("")
    lines.append("待填写：说明当前更像 Spike/model limitation、RTL bug、selfcheck bug、environment blocked 还是 true stuck/inconclusive；若偏 RTL，写具体怀疑模块/路径/信号/响应/数据错误；若偏 Spike/model，写缺失模型或与 LinkNan 平台行为不一致的位置。")
    lines.append("")
    lines.append("## 场景与验证意图")
    lines.append("")
    lines.append("待填写：说明特权级、地址类型、访问宽度/对齐、seed 路径、执行路径、异常 handler 路径和最终检查路径。必须保留原始验证目标，不能为了通过而弱化 PMA/PBMT/IO/窄宽度等意图。")
    lines.append("")
    lines.append("## 失败现象")
    lines.append("")
    visible = selected[:max_cases]
    if len(selected) > max_cases:
        lines.append(f"待填写：还有 `{len(selected) - max_cases}` 个 case 只在上表汇总；如果证据与代表 case 不同，需要展开补充。")
        lines.append("")
    for item in visible:
        run = latest_run(item)
        lines.append(f"### {item.get('case')}")
        lines.append("")
        lines.append(f"- latest_status: `{run.get('status', 'no_run')}`")
        lines.append(f"- evidence_tags: `{', '.join(run.get('evidence_tags') or [])}`")
        if run.get("key_lines"):
            lines.append("- run.log 关键行:")
            for key_line in run.get("key_lines", [])[:20]:
                lines.append(f"  - `{key_line}`")
        else:
            lines.append("- run.log 关键行: `none captured`")
        lines.append("")
    lines.append("## 源码分析")
    lines.append("")
    if len(selected) > max_cases:
        lines.append(f"待填写：下面源码细节只展开 `{max_cases}` 个代表 case；如果剩余 case 不走同一 helper/path，需要继续补充。")
        lines.append("")
    for item in visible:
        source = item.get("source") or {}
        lines.append(f"### {item.get('case')}")
        lines.append("")
        lines.append(f"- source: `{source_ref(source)}`")
        lines.append(f"- exact_pbmt_hits: `{source.get('exact_pbmt_hits', 0)}`")
        if source.get("keyword_lines"):
            lines.append("- 源码关键行:")
            for line in source.get("keyword_lines", [])[:20]:
                lines.append(f"  - `{line}`")
        else:
            lines.append("- 源码关键行: `none captured`")
        lines.append("")
    lines.append("## Profile Guard")
    lines.append("")
    lines.append("待填写：PMA/PBMT/MMIO/Device/responder/no-response 或 profile 实现范围相关 case 必填；无关时写 `not-applicable`。")
    lines.append("")
    lines.append("- spec_profile: `TBD`")
    lines.append("- pa/window: `TBD`")
    lines.append("- pma: `TBD`")
    lines.append("- pbmt: `TBD`")
    lines.append("- spec_allowed: `TBD`")
    lines.append("- responder_required: `TBD`")
    lines.append("- spike_gate_applicable: `TBD`")
    lines.append("- rtl_implemented: `TBD`")
    lines.append("- profile_not_impl_reason: `TBD`")
    lines.append("- testbench_responder_confirmed: `TBD`")
    lines.append("- platform/source evidence: `TBD`")
    lines.append("- wave/log evidence: `TBD`")
    lines.append("- classification: `TBD`")
    lines.append("")
    lines.append("## 波形报告")
    lines.append("")
    if waveform_reports:
        lines.append("本 triage 使用了 waveform-debug 的信号级报告；主报告只摘要关键结论，完整波形证据以以下 `report.md` 为准：")
        lines.append("")
        for report in waveform_reports:
            lines.append(f"- waveform_report: `{report}`")
    else:
        lines.append("未使用波形；如果后续调用 `$waveform-debug`，必须在这里填写 waveform-debug 产出的 `report.md` 路径，并摘要 first-bad-cycle/关键信号结论。")
    lines.append("")
    lines.append("待填写：若有波形，摘要 first bad time/cycle、关键信号、期望 vs 实际数据/控制流，以及为什么后续症状只是结果。")
    lines.append("")
    lines.append("## 待人工审核问题")
    lines.append("")
    lines.append("待填写：记录修改用例或重跑过程中发现的疑似 RTL bug、未决环境问题或需要 owner 判断的问题。每项写清 source/log/run-dir/waveform report 路径；没有则写 `none`。不要为了清表而把这些疑点改没。")
    lines.append("")
    lines.append("## 分类")
    lines.append("")
    lines.append("待填写：写明最终 taxonomy label，并说明为什么排除其它分类。必须明确区分 Spike/model limitation、测试自校验错误、环境限制和 suspected RTL bug。")
    lines.append("")
    lines.append("## 处理动作")
    lines.append("")
    lines.append("待填写：说明已做 patch、仅写 bug report、manual/blocked 决策，或仍需要平台/RTL 支持。不得弱化 PMA/PBMT/IO/窄宽度验证意图。")
    lines.append("")
    lines.append("## 验证")
    lines.append("")
    lines.append("待填写：列出执行命令、结果日志路径、PASS/FAIL/GOOD TRAP 证据和失败列表更新。没有可信 clean rerun 证据时，不得从失败列表删除。")
    lines.append("")
    path.write_text("\n".join(lines))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an editable Chinese report.md template from snapshot JSON."
    )
    parser.add_argument("--snapshot-json", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--title", default="Hyptest 失败分析报告")
    parser.add_argument(
        "--waveform-report",
        action="append",
        type=Path,
        default=[],
        help="Path to waveform-debug report.md; repeatable when multiple waveform reports are used",
    )
    parser.add_argument("--case", action="append", default=[], help="Specific case to include; repeatable")
    parser.add_argument(
        "--max-cases",
        type=int,
        default=5,
        help="Maximum selected cases to expand with detailed run/source evidence",
    )
    parser.add_argument(
        "--action",
        choices=["selfcheck_fail", "waveform", "waveform_report_update", "mismatch", "stuck", "passed"],
        help="Select cases by broad latest status/action when --case is not used",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snapshot = load_snapshot(args.snapshot_json)
    selected = select_cases(snapshot, args.case, args.action)
    if not selected:
        raise SystemExit("no cases selected for report")
    write_report(
        args.out,
        args.snapshot_json,
        selected,
        args.title,
        max(args.max_cases, 1),
        args.waveform_report,
    )
    print(f"report={args.out}")
    print(f"cases={len(selected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
