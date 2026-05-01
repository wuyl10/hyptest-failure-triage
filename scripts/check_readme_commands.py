#!/usr/bin/env python3
"""Check that README.md command block matches list_skill_commands.py."""

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


def expected_block() -> str:
    result = subprocess.run(
        [sys.executable, str(LIST_COMMANDS), "--markdown"],
        text=True,
        capture_output=True,
        check=True,
    )
    return f"{BEGIN}\n{result.stdout.rstrip()}\n{END}"


def actual_block(text: str) -> str:
    if BEGIN not in text or END not in text:
        raise ValueError(f"README.md must contain {BEGIN!r} and {END!r}")
    _, rest = text.split(BEGIN, 1)
    inner, _ = rest.split(END, 1)
    return f"{BEGIN}{inner}{END}"


def main() -> int:
    actual = actual_block(README.read_text())
    expected = expected_block()
    if actual != expected:
        print(
            "README generated command block is out of date; run "
            "python3 scripts/update_readme_commands.py",
            file=sys.stderr,
        )
        return 1
    print("readme-command-check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
