#!/usr/bin/env python3
"""Lightweight classifiers for known hyptest failure patterns.

These classifiers are intentionally conservative. They are used by eval
fixtures to keep known official-Spike model gaps from drifting back into the
"unknown failure" bucket after future skill edits.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass


@dataclass
class PatternClassification:
    bucket: str
    confidence: str
    reason: str
    tags: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _blob(text: str, case_name: str = "") -> str:
    return f"{case_name}\n{text}".lower().replace("-", "_")


def _has_any(blob: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, blob, re.I | re.S) for pattern in patterns)


def classify_official_spike_pattern(
    text: str,
    case_name: str = "",
) -> PatternClassification:
    blob = _blob(text, case_name)

    if _has_any(
        blob,
        [
            r"\bnmi\b",
            r"double[_\s]?trap",
            r"\brnmi\b",
            r"\bmnepc\b",
            r"\bmncause\b",
            r"\bmnstatus\b",
            r"\bmdt\b",
        ],
    ):
        return PatternClassification(
            "out_of_scope_nhv5_1ap_nmi_double_trap",
            "high",
            "NMI/double-trap behavior is outside the current NHV5.1AP active validation scope.",
            ["official-spike", "scope-exclusion", "nmi-double-trap"],
        )

    if _has_any(blob, [r"cbo\.?zero", r"cbozero", r"\bcbo\b"]) and _has_any(
        blob,
        [
            r"no[_\s]?a",
            r"a[_\s]?bit",
            r"missing\s+a",
            r"permission",
            r"fault\s+classification",
            r"store\s+pf",
        ],
    ):
        return PatternClassification(
            "official_spike_cbo_permission_model_gap",
            "high",
            "Official Spike does not match the project CBO permission/A-bit fault classification expectation.",
            ["official-spike", "model-gap", "cbo", "permission"],
        )

    if _has_any(
        blob,
        [
            r"\blr/?sc\b",
            r"\blrsc\b",
            r"reservation\s+timeout",
            r"reservation\s+expiry",
            r"store[_\s]?conditional",
            r"\bsc\.[wd]\b",
        ],
    ):
        return PatternClassification(
            "official_spike_lrsc_reservation_timeout_model_gap",
            "high",
            "Official Spike does not model the project-specific LR/SC reservation timeout policy.",
            ["official-spike", "model-gap", "lrsc", "reservation-timeout"],
        )

    if _has_any(
        blob,
        [
            r"\bpbmt\b",
            r"\bpma\b",
            r"\bmmio\b",
            r"cacheability",
            r"cacheable",
            r"uncache",
            r"\bio\s+(?:region|range|pma|pbmt|memory)",
            r"device\s+(?:region|memory|responder)",
        ],
    ):
        return PatternClassification(
            "official_spike_pma_pbmt_mmio_cacheability_model_gap",
            "medium",
            "The failure depends on PMA/PBMT/MMIO/cacheability behavior that official Spike models incompletely.",
            ["official-spike", "model-gap", "pma-pbmt-mmio"],
        )

    if _has_any(
        blob,
        [
            r"custom\s+csr",
            r"unknown\s+csr",
            r"unimplemented\s+csr",
            r"unsupported\s+csr",
            r"csr\s+.*(?:not\s+implemented|unsupported)",
        ],
    ):
        return PatternClassification(
            "official_spike_missing_custom_csr_model_gap",
            "high",
            "Official Spike lacks the custom CSR model required by this case.",
            ["official-spike", "model-gap", "custom-csr"],
        )

    if _has_any(
        blob,
        [
            r"custom\s+priv",
            r"custom\s+privilege",
            r"privilege\s+model",
            r"platform\s+priv",
            r"implementation[_\s]?specific\s+priv",
            r"\bsmstateen\b",
            r"\bstateen\b",
        ],
    ):
        return PatternClassification(
            "official_spike_missing_custom_or_priv_model_gap",
            "medium",
            "Official Spike lacks the custom/platform privilege model required by this case.",
            ["official-spike", "model-gap", "custom-priv"],
        )

    if _has_any(blob, [r"illegal\s+instruction", r"illegal_instruction", r"cause\s*=\s*0x?2"]):
        return PatternClassification(
            "official_spike_illegal_instruction_model_gap",
            "medium",
            "Official Spike reports an illegal instruction for an implementation/project-specific instruction path.",
            ["official-spike", "model-gap", "illegal-instruction"],
        )

    return PatternClassification(
        "unknown_official_spike_failure",
        "low",
        "No known official-Spike model-gap pattern matched; inspect manually.",
        ["official-spike", "unknown"],
    )
