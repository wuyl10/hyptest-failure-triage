#!/usr/bin/env python3
"""Cluster hyptest failure snapshots by conservative observable features."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def clean_line(line: str) -> str:
    line = ANSI_RE.sub("", line)
    line = re.sub(r"\s+", " ", line).strip()
    line = re.sub(r"^\s*L\d+:\s*", "", line)
    return line


def module_group(source_path: str | None) -> str:
    if not source_path:
        return "unknown_source"
    name = Path(source_path).name
    mapping = [
        ("amo", "amo"),
        ("prefetch", "prefetch"),
        ("cmo", "cmo_sbuffer_cbo"),
        ("difftest_cboinvalid", "cboinvalid_sync"),
        ("trap_entry", "trap_entry"),
        ("pbmt", "pbmt"),
        ("misaligned", "misaligned"),
    ]
    for token, group in mapping:
        if token in name:
            return group
    return name.removesuffix(".c")


def source_tags(keyword_lines: list[str]) -> tuple[str, ...]:
    joined = "\n".join(keyword_lines)
    checks = [
        ("pbmt", r"PBMT|Pbmt|\bpbmt\b|VSRWXPbmt|PTE_Pbmt"),
        ("pma_pmp", r"\bPMA\b|\bPMP\b|pmp|PMP"),
        ("cbo", r"cbo_"),
        ("prefetch", r"prefetch"),
        ("fence", r"fence|sfence"),
        ("exception", r"EXCEPT|excpt|cause|tval|SAF|LAF|page fault|access fault"),
        ("byte_width", r"\bsb\(|\blb\(|\blbu\("),
        ("half_width", r"\bsh\(|\blh\(|\blhu\("),
        ("word_width", r"\bsw\(|\blw\(|\blwu\("),
        ("dword_width", r"\bsd\(|\bld\("),
        ("assert", r"TEST_ASSERT|AI_ASSERT"),
    ]
    tags = [name for name, pattern in checks if re.search(pattern, joined)]
    return tuple(tags) if tags else ("no_source_tags",)


def failed_messages(run_lines: list[str], limit: int = 3) -> tuple[str, ...]:
    msgs: list[str] = []
    for raw in run_lines:
        line = clean_line(raw)
        if "FAILED" not in line:
            continue
        msg = line.replace("FAILED", "").strip()
        msg = re.sub(r"\(\)\s*$", "", msg).strip()
        if msg and msg not in msgs:
            msgs.append(msg)
        if len(msgs) >= limit:
            break
    return tuple(msgs) if msgs else ("no_failed_message",)


def failure_themes(messages: tuple[str, ...]) -> tuple[str, ...]:
    joined = "\n".join(messages).lower()
    checks = [
        ("amo", r"\bamo\b"),
        ("sbuffer", r"sbuffer|store queue|same-entry|evict|refill-to-misspipe"),
        ("prefetch", r"prefetch|mshr"),
        ("cbo", r"cbo|invalid|inval|zero"),
        ("overlay", r"overlay|overlapped|cross-16b|split|mask"),
        ("adjacent_preserve", r"adjacent|preserv"),
        ("fault_trap", r"fault|trap|exception|tval|cause|vstart"),
        ("old_image", r"old image|older|unchanged|payload"),
        ("zero_line", r"zero"),
        ("line_image", r"block|line|image|payload|word"),
    ]
    themes = [name for name, pattern in checks if re.search(pattern, joined)]
    return tuple(themes) if themes else ("generic_failed_assert",)


def cluster_key(item: dict[str, Any], mode: str) -> tuple[Any, ...]:
    source = item.get("source") or {}
    runs = item.get("runs") or []
    latest = runs[0] if runs else {}
    messages = failed_messages(latest.get("key_lines") or [])
    base = (
        item.get("preliminary_bucket", "unknown_bucket"),
        latest.get("status", "no_run"),
        module_group(source.get("path")),
        source_tags(source.get("keyword_lines") or []),
        bool(source.get("exact_pbmt_hits")),
    )
    if mode == "strict":
        return base + (messages,)
    if mode == "theme":
        return base + (failure_themes(messages),)
    return (
        item.get("preliminary_bucket", "unknown_bucket"),
        latest.get("status", "no_run"),
        module_group(source.get("path")),
        bool(source.get("exact_pbmt_hits")),
    )


def load_snapshot(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(errors="ignore"))
    if not isinstance(data, list):
        raise SystemExit(f"snapshot JSON must contain a list: {path}")
    return data


def summarize_cluster(key: tuple[Any, ...], items: list[dict[str, Any]]) -> dict[str, Any]:
    first = items[0]
    source = first.get("source") or {}
    runs = first.get("runs") or []
    latest = runs[0] if runs else {}
    bucket = first.get("preliminary_bucket", "unknown_bucket")
    status = latest.get("status", "no_run")
    module = module_group(source.get("path"))
    tags = sorted({tag for item in items for tag in source_tags((item.get("source") or {}).get("keyword_lines") or [])})
    failures = failed_messages(latest.get("key_lines") or [])
    themes = sorted({theme for item in items for theme in failure_themes(failed_messages(((item.get("runs") or [{}])[0]).get("key_lines") or []))})
    has_pbmt = any((item.get("source") or {}).get("exact_pbmt_hits") for item in items)
    return {
        "size": len(items),
        "bucket": bucket,
        "status": status,
        "module": module,
        "tags": tags,
        "themes": themes,
        "failed_messages": list(failures),
        "has_pbmt": has_pbmt,
        "cases": [item["case"] for item in items],
        "representative": items[0]["case"],
    }


def build_clusters(snapshot: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for item in snapshot:
        grouped[cluster_key(item, mode)].append(item)
    clusters = [summarize_cluster(key, items) for key, items in grouped.items()]
    clusters.sort(key=lambda c: (-c["size"], c["module"], c["representative"]))
    return clusters


def write_json(path: Path, clusters: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clusters, indent=2, ensure_ascii=False) + "\n")


def md_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def write_markdown(path: Path, snapshot_path: Path, mode: str, clusters: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# Hyptest Failure Cluster Report")
    lines.append("")
    lines.append(f"- snapshot: `{snapshot_path}`")
    lines.append(f"- mode: `{mode}`")
    lines.append(f"- clusters: `{len(clusters)}`")
    lines.append(f"- cases: `{sum(c['size'] for c in clusters)}`")
    lines.append("")
    lines.append("## Cluster Summary")
    lines.append("")
    lines.append("| ID | Size | Bucket | Status | Module | Tags | Themes | Representative | First failed messages |")
    lines.append("| ---: | ---: | --- | --- | --- | --- | --- | --- | --- |")
    for idx, cluster in enumerate(clusters, 1):
        lines.append(
            "| "
            + " | ".join(
                md_escape(str(x))
                for x in [
                    idx,
                    cluster["size"],
                    cluster["bucket"],
                    cluster["status"],
                    cluster["module"],
                    ",".join(cluster["tags"]),
                    ",".join(cluster["themes"]),
                    cluster["representative"],
                    "<br>".join(cluster["failed_messages"]),
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Clusters")
    lines.append("")
    for idx, cluster in enumerate(clusters, 1):
        lines.append(f"### Cluster {idx}: {cluster['module']} / {cluster['status']}")
        lines.append("")
        lines.append(f"- size: `{cluster['size']}`")
        lines.append(f"- bucket: `{cluster['bucket']}`")
        lines.append(f"- tags: `{', '.join(cluster['tags'])}`")
        lines.append(f"- themes: `{', '.join(cluster['themes'])}`")
        lines.append(f"- representative: `{cluster['representative']}`")
        lines.append("- failed messages:")
        for msg in cluster["failed_messages"]:
            lines.append(f"  - `{msg}`")
        lines.append("- cases:")
        for case in cluster["cases"]:
            lines.append(f"  - `{case}`")
        lines.append("")
    path.write_text("\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cluster triage_snapshot.py JSON output by conservative features."
    )
    parser.add_argument("--snapshot-json", type=Path, required=True)
    parser.add_argument(
        "--mode",
        choices=["coarse", "theme", "strict"],
        default="coarse",
        help="coarse groups by status/module/PBMT; theme adds failure themes; strict also keys on exact failed messages",
    )
    parser.add_argument("--md-out", type=Path)
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snapshot = load_snapshot(args.snapshot_json)
    clusters = build_clusters(snapshot, args.mode)
    if args.json_out:
        write_json(args.json_out, clusters)
    if args.md_out:
        write_markdown(args.md_out, args.snapshot_json, args.mode, clusters)
    if not args.json_out and not args.md_out:
        print(json.dumps(clusters, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
