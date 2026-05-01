#!/usr/bin/env python3
"""Check that resource_index.md covers public resources."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
RESOURCE_INDEX = SKILL_DIR / "references" / "resource_index.md"
README = SKILL_DIR / "README.md"


def rel(path: Path) -> str:
    return path.relative_to(SKILL_DIR).as_posix()


def collect_missing(resource_text: str, *, include_fixtures: bool = True) -> list[str]:
    missing: list[str] = []

    for path in sorted((SKILL_DIR / "references").glob("*.md")):
        marker = rel(path)
        if marker not in resource_text:
            missing.append(marker)

    for path in sorted((SKILL_DIR / "scripts").glob("*.py")):
        marker = rel(path)
        if marker not in resource_text:
            missing.append(marker)

    if include_fixtures:
        for path in sorted((SKILL_DIR / "fixtures").glob("*/*")):
            if not path.is_file():
                continue
            marker = path.name
            full_marker = rel(path)
            if marker not in resource_text and full_marker not in resource_text:
                missing.append(full_marker)

    return missing


def collect_readme_issues(readme_text: str) -> list[str]:
    required_markers = [
        "references/resource_index.md",
        "scripts/list_skill_commands.py",
        "scripts/selftest.py",
        "scripts/eval_log_patterns.py",
        "scripts/eval_official_spike_patterns.py",
    ]
    return [marker for marker in required_markers if marker not in readme_text]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-fixtures", action="store_true", help="Skip fixture coverage checks.")
    args = parser.parse_args()

    if not RESOURCE_INDEX.exists():
        print(f"missing {rel(RESOURCE_INDEX)}", file=sys.stderr)
        return 1
    if not README.exists():
        print("missing README.md", file=sys.stderr)
        return 1

    resource_text = RESOURCE_INDEX.read_text()
    readme_text = README.read_text()

    missing = collect_missing(resource_text, include_fixtures=not args.no_fixtures)
    readme_issues = collect_readme_issues(readme_text)

    if missing or readme_issues:
        if missing:
            print("resource_index.md missing entries:", file=sys.stderr)
            for item in missing:
                print(f"  - {item}", file=sys.stderr)
        if readme_issues:
            print("README.md missing expected markers:", file=sys.stderr)
            for item in readme_issues:
                print(f"  - {item}", file=sys.stderr)
        return 1

    print("resource-index-check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
