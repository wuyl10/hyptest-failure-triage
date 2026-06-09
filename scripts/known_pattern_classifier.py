#!/usr/bin/env python3
"""Lightweight classifiers for known hyptest failure patterns.

These classifiers are intentionally conservative. They are used by eval
fixtures to keep known official-Spike model gaps from drifting back into the
"unknown failure" bucket after future skill edits, and to keep runner-sensitive
PMA/PBMT/MMIO failures from being mislabeled before the runner is known.
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
    return f"{case_name}\n{text}".lower()


def _has_any(blob: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, blob, re.I | re.S) for pattern in patterns)


def _runner_blob(blob: str) -> str:
    return blob.replace("-", "_")


def _has_official_spike_context(blob: str) -> bool:
    normalized = _runner_blob(blob)
    return _has_any(
        f"{blob}\n{normalized}",
        [
            r"official\s+spike",
            r"community\s+spike",
            r"upstream\s+spike",
            r"\bhyptest_spike_bin\b",
            r"\bspike[_\s-]?gate\b",
            r"\bplatform\s*[=:]\s*spike\b",
            r"\b--platform\s+spike\b",
            r"\b--plat\s+spike\b",
            r"\bget_result\.py\b.*\bplatform\s+spike\b",
            r"\bcompile_elf\.py\b.*\bplat\s+spike\b",
        ],
    )


def _has_linknan_difftest_context(blob: str) -> bool:
    normalized = _runner_blob(blob)
    return _has_any(
        f"{blob}\n{normalized}",
        [
            r"\bhyptest_difftest_ref_so\b",
            r"\blinknan[_\s-]?difftest\b",
            r"\bdiff[_\s-]?test\s+ref\s+so\b",
            r"\bdifftest\s+enabled\b",
            r"\bdifftest\s+failed\b",
            r"\bthe\s+reference\s+model\s+is\b",
            r"\briscv64[_\s-]?spike[_\s-]?so\b",
            r"\bref[_\s-]?dut\b",
            r"\bref\s+.*dut\b",
            r"\bdut\s+.*ref\b",
            r"\bref\s+trapped\b",
            r"\bdut\s+continued\b",
        ],
    )


def _runner_guard(blob: str) -> PatternClassification | None:
    has_linknan_difftest = _has_linknan_difftest_context(blob)
    has_official_spike = _has_official_spike_context(blob)
    if has_linknan_difftest and has_official_spike:
        return PatternClassification(
            "runner_conflict_needs_disambiguation",
            "medium",
            (
                "Both official-Spike and LinkNan difftest markers appear; "
                "separate runner evidence before assigning any model gap."
            ),
            ["runner-conflict", "runner-check"],
        )
    if has_linknan_difftest:
        return PatternClassification(
            "linknan_difftest_needs_first_divergence",
            "medium",
            (
                "Known-model-gap keywords appear on a LinkNan difftest path; "
                "keep REF-DUT first-divergence evidence before assigning any model gap."
            ),
            ["linknan-difftest", "runner-check"],
        )
    if not has_official_spike:
        return PatternClassification(
            "runner_disambiguation_needed",
            "low",
            "Known-model-gap keywords need runner context before being labeled as official-Spike gaps.",
            ["runner-check"],
        )
    return None


def classify_known_runner_pattern(
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
        guarded = _runner_guard(blob)
        if guarded:
            return guarded
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
        guarded = _runner_guard(blob)
        if guarded:
            return guarded
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
        guarded = _runner_guard(blob)
        if guarded:
            return guarded
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
        if _has_linknan_difftest_context(blob) and _has_official_spike_context(blob):
            return PatternClassification(
                "pma_pbmt_mmio_runner_conflict_needs_disambiguation",
                "medium",
                (
                    "PMA/PBMT/MMIO keywords appear with both official-Spike and "
                    "LinkNan difftest markers; separate runner evidence before "
                    "assigning a model gap."
                ),
                ["runner-conflict", "runner-check", "pma-pbmt-mmio"],
            )
        if _has_linknan_difftest_context(blob):
            return PatternClassification(
                "pma_pbmt_mmio_linknan_difftest_needs_first_divergence",
                "medium",
                (
                    "PMA/PBMT/MMIO keywords appear on a LinkNan difftest path; "
                    "keep the generic REF-DUT first-divergence flow and check "
                    "PMA CSR/profile/responder evidence before assigning a model gap."
                ),
                ["linknan-difftest", "runner-check", "pma-pbmt-mmio"],
            )
        if not _has_official_spike_context(blob):
            return PatternClassification(
                "pma_pbmt_mmio_runner_disambiguation_needed",
                "low",
                (
                    "PMA/PBMT/MMIO keywords alone do not prove an official-Spike "
                    "model gap; identify the runner, profile, and responder first."
                ),
                ["runner-check", "profile-guard", "pma-pbmt-mmio"],
            )
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
        guarded = _runner_guard(blob)
        if guarded:
            return guarded
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
        guarded = _runner_guard(blob)
        if guarded:
            return guarded
        return PatternClassification(
            "official_spike_missing_custom_or_priv_model_gap",
            "medium",
            "Official Spike lacks the custom/platform privilege model required by this case.",
            ["official-spike", "model-gap", "custom-priv"],
        )

    if _has_any(blob, [r"illegal\s+instruction", r"illegal_instruction", r"cause\s*=\s*0x?2"]):
        guarded = _runner_guard(blob)
        if guarded:
            return guarded
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


def classify_official_spike_pattern(
    text: str,
    case_name: str = "",
) -> PatternClassification:
    """Compatibility wrapper for older eval scripts.

    The implementation is runner-sensitive: LinkNan difftest evidence is not
    classified as an official-Spike model gap until the runner is disambiguated.
    """
    return classify_known_runner_pattern(text, case_name)
