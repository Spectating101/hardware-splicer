"""Fail-closed quantitative evidence gate for HS repair advice.

A video-only reported observation does not justify prescribing an exact
numeric diagnostic threshold. This is a GENERIC provenance constraint,
not a hardcoded repair case, part taxonomy or a claim of engineering truth.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

# Detect directional limits with engineering units in action advice.
# Examples: >0.4A, <0.05A, below 10 ohms, above 12V, at least 15W.
BOUND = re.compile(
    r"(?i)(?:"
    r"(?:[<>≤≥])\s*"
    r"|(?:above|below|greater\s+than|less\s+than|under|over|at\s+least|at\s+most)\s+"
    r")"
    r"(?P<value>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>mA|A|mV|V|mW|W|mΩ|Ω|ohms?|°C|C)\b"
)


class UnsupportedQuantitativeThreshold(ValueError):
    """A proposed engineering measurement cutoff lacks a sourced basis."""


def unsourced_thresholds(
    plan: Mapping[str, Any], ledger: Mapping[str, Any] | None
) -> list[dict[str, str]]:
    """Return unsupported numeric *cutoffs*, not all quoted measurements.

    The ledger currently has no verified specification claims. Future
    technical documents may explicitly support one calibrated threshold,
    but this gate intentionally does not infer that from video narration.
    """
    if not ledger:
        return []
    unresolved = set(ledger.get("unresolved_source_ids") or [])
    if not unresolved.intersection({
        "no_component_datasheet_provided",
        "no_schematic_or_boardview_provided",
        "no_verified_meter_observations",
    }):
        return []
    segments=[("next_safe_check",plan.get("next_safe_check",""))]
    for i,h in enumerate(plan.get("hypotheses") or [],1):
        segments.append((f"hypotheses[{i}].safe_test",h.get("safe_test","")))
        segments.append((f"hypotheses[{i}].why",h.get("why","")))
    findings=[]
    for source,text in segments:
        if not isinstance(text,str):
            continue
        for m in BOUND.finditer(text):
            findings.append({
                "field":source,
                "limit":m.group(0).strip(),
                "explanation":"No authenticated reference curve, manufacturer specification or verified baseline authorizes this numeric diagnostic cutoff.",
            })
    return findings


def reject_unsourced_thresholds(
    plan: Mapping[str, Any], ledger: Mapping[str, Any] | None
) -> None:
    findings=unsourced_thresholds(plan,ledger)
    if findings:
        limits=", ".join(row["limit"] for row in findings)
        raise UnsupportedQuantitativeThreshold(
            "unsupported quantitative cutoff(s) in repair test: "+limits
        )
