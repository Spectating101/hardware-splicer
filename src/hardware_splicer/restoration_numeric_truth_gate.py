"""Fail-closed quantitative evidence gate for HS repair advice.

A video-only reported observation does not justify prescribing an exact
numeric diagnostic threshold. This is a GENERIC provenance constraint,
not a hardcoded repair case, part taxonomy or a claim of engineering truth.

There is deliberately NO allow path. The gate reads only the ledger's
``unresolved_source_ids``; it never consults the source claims registered by
restoration_source_numeric_ledger, so a figure that appears verbatim in a
cited source is still rejected when used as a diagnostic cutoff. Do not add
one without an authenticated, unit-and-condition-matched source record.

Detection is pattern based and cannot be complete. It recognises a number
with an electrical or thermal unit (symbol or word, SI prefixes) that is
tied to a comparator word or symbol, an approximation marker, a range, a
trailing "or more/less", or a cutoff/threshold word, in every free-text
field of the plan. Numbers written out in words are not recognised.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from .restoration_safety_semantics import fold, iter_plan_text, mixed_script_words

_NUM = r"[-+]?(?:\d+(?:[.,]\d+)?|\.\d+)"
_PFX = r"(?:kilo|mega|giga|milli|micro|nano|[kmgµμunp])"
_LONG = r"(?:volts?|amps?|amperes?|watts?|(?:kil|meg|gig)?ohms?|hertz)"
_SHORT = r"(?:v|a|w|hz|ω)"
_UNIT = (
    r"(?:[°º]\s*[cf]|degrees?\s*(?:celsius|fahrenheit|[cf])|celsius|fahrenheit"
    rf"|(?:{_PFX}[\s-]*)?{_LONG}|{_PFX}?{_SHORT}|c)(?!\w)"
)
_QTY = rf"(?<![\w.]){_NUM}\s*{_UNIT}"
_QTY_NO_UNIT = rf"(?<![\w.]){_NUM}"

_COMP_SYMBOL = r"(?:[<>≤≥≈~≲≳]|[<>=]=|=<|=>)"
_COMP_WORD = (
    r"\b(?:above|below|under|over|beneath|beyond|exceed(?:s|ed|ing)?|"
    r"greater\s+than|less\s+than|lower\s+than|higher\s+than|more\s+than|"
    r"fewer\s+than|smaller\s+than|larger\s+than|bigger\s+than|at\s+least|"
    r"at\s+most|at\s+or\s+(?:above|below)|up\s+to|down\s+to|"
    r"(?:no|not)\s+(?:more|less|greater|lower|higher|fewer)\s+than|"
    r"minimum|maximum|min|max|upper|lower|equal\s+to|equals?|exactly|"
    r"approximately|approx\.?|about|around|roughly|circa|nearly|almost|"
    r"close\s+to|near|between|from)\b"
)
_FILL = r"[^\d.;:!?\n]{0,20}?"
_TRAIL = (
    r"(?:\s*(?:or|and|and/or|/)?\s*(?:more|less|greater|lower|higher|fewer|"
    r"above|below|over|under|up|down|upwards?|downwards?|bigger|smaller|"
    r"larger|max(?:imum)?|min(?:imum)?|at\s+(?:most|least)|tops|plus|minus|"
    r"or\s+so)\b|\+)"
)
_CUT = (
    r"(?:cut-?\s?off|threshold|trip\s*(?:point|level)|pass\s*/?\s*fail|"
    r"go\s*/?\s*no\s*/?\s*go|limit|set\s*point|healthy\s+(?:range|value|reading))"
)
_NEAR = r"[^;:!?\n\d]{0,30}?"

PATTERNS = [
    re.compile(rf"(?:{_COMP_SYMBOL}|{_COMP_WORD}){_FILL}{_QTY}", re.I),
    re.compile(rf"{_QTY}{_TRAIL}", re.I),
    re.compile(rf"{_QTY_NO_UNIT}\s*(?:{_UNIT})?\s*(?:-|–|—|\bto\b|\bthrough\b)\s*{_QTY}", re.I),
    re.compile(rf"\bbetween\s+{_QTY_NO_UNIT}\s*(?:{_UNIT})?\s*(?:and|&)\s*{_QTY}", re.I),
    re.compile(rf"\b{_CUT}\b{_NEAR}{_QTY}", re.I),
    re.compile(rf"{_QTY}{_NEAR}\b{_CUT}\b", re.I),
]


class UnsupportedQuantitativeThreshold(ValueError):
    """A proposed engineering measurement cutoff lacks a sourced basis."""


def _spans(text: str) -> list[tuple[int, int]]:
    found = sorted(
        (m.start(), m.end()) for pattern in PATTERNS for m in pattern.finditer(text)
    )
    merged: list[tuple[int, int]] = []
    for start, end in found:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


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
    findings = []
    for source, raw in iter_plan_text(plan):
        for word in mixed_script_words(raw):
            findings.append({
                "field": source,
                "limit": word,
                "explanation": "Word mixes ASCII and non-ASCII letters (possible look-alike spelling): fail closed.",
            })
        text = fold(raw)
        for start, end in _spans(text):
            findings.append({
                "field": source,
                "limit": text[start:end].strip(),
                "explanation": "No authenticated reference curve, manufacturer specification or verified baseline authorizes this numeric diagnostic cutoff.",
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
