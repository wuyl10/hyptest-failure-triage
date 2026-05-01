#!/usr/bin/env python3
"""Refresh the generated command block in README.md."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
README = SKILL_DIR / "README.md"
LIST_COMMANDS = SCRIPT_DIR / "list_skill_commands.py"
BEGIN = "<!-- BEGIN GENERATED COMMANDS -->"
END = "<!-- END GENERATED COMMANDS -->"


def generated_block() -> str:
    result = subprocess.run(
        [sys.executable, str(LIST_COMMANDS), "--markdown"],
        text=True,
        capture_output=True,
        check=True,
    )
    return f"{BEGIN}\n{result.stdout.rstrip()}\n{END}"


def update_text(text: str) -> str:
    if BEGIN not in text or END not in text:
        raise ValueError(f"README.md must contain {BEGIN!r} and {END!r}")
    before, rest = text.split(BEGIN, 1)
    _, after = rest.split(END, 1)
    return before + generated_block() + after


def main() -> int:
    README.write_text(update_text(README.read_text()))
    print("README generated command block updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
