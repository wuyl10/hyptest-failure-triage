#!/usr/bin/env python3
"""Shared path helpers for hyptest failure-triage scripts."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


def env_path(*names: str) -> Path | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return Path(value).expanduser()
    return None


def require_path(
    value: Path | None,
    option_name: str,
    env_names: Iterable[str],
    description: str,
) -> Path:
    if value is not None:
        return value.expanduser().resolve()
    env_text = " or ".join(env_names)
    raise SystemExit(
        f"missing {description}: pass {option_name} or set {env_text}"
    )


def default_skill_dir(current_file: str) -> Path:
    return Path(current_file).resolve().parents[1]
