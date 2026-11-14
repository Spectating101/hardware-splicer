"""Authority gate: reference schematic pins != verified physical test points.

A matching revision CLAIM from a video/article is never equivalent to
independently inspecting the actual board marking. We permit a model to
discuss the reference pin topology but fail closed on proposed pin-specific
physical checks while its applicability is unverified.

Every free-text field of the plan (and every mapping key) is scanned, and
so is reference-topology prose: a pin reference in a rationale field is
withheld too. The check is pattern based and deliberately broad. It flags a
numbered pin, pad, terminal or contact with or without a designator, a
designator joined to a number ("DC1-4", "DC1.4"), a designator near a
pin-like word, and "the centre pin of the barrel jack". It also flags
harmless text such as "C10 pin 1 convention"; false rejections are
accepted. Pins named rather than numbered ("the VIN pin") are not caught.
"""
from __future__ import annotations
import re
from typing import Any, Collection, Mapping

from .restoration_safety_semantics import (
    disallowed_text_reasons, fold, iter_plan_text,
)

_DES = r"[A-Z]{1,3}\d{1,4}"
_PIN = r"(?:pins?|pads?|terminals?|contacts?|leads?|legs?|balls?|poles?)"
_NUM = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|[a-z]{1,2}\d{1,2})"
_ORD = r"(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|last|\d+(?:st|nd|rd|th))"
_PART = (r"(?:jack|connector|header|socket|port|ic|chip|switch|regulator|diode|fuse|"
         r"battery|cell|transistor|mosfet|capacitor|resistor|inductor|relay|module|"
         r"cartridge|slot)")

_COMPONENT_PIN = re.compile(
    r"(?i)\b(?:[A-Z]{1,3}\d{1,4})\s*(?:pin\s*#?\s*\d+|[.]\d+|pins\s*\d+\s*(?:and|to|-)\s*\d+)\b"
    r"|\bpin\s*#?\s*\d+\s+(?:on|of|at)\s+[A-Z]{1,3}\d{1,4}\b"
)
# Run on the text as written (the original pattern is always among them).
PATTERNS = [
    _COMPONENT_PIN,
    re.compile(rf"\b{_PIN}\s*(?:(?:no|num|number)\b\.?)?\s*[:#]?\s*{_NUM}\b", re.I),
    re.compile(rf"\b{_ORD}\s+{_PIN}\b", re.I),
    re.compile(rf"\bpins?\b(?:\W+\w+){{0,3}}?\W+(?:of|on|at|in)\W+(?:the\W+)?(?:\w+\W+){{0,2}}?{_PART}\b", re.I),
]
# Designator-proximity patterns. These run on text in which tokens that are
# real evidence IDs of this plan ("E1") have been masked, because an evidence
# citation next to the word "pins" is not a part reference. Only IDs actually
# supplied by the caller are masked; the shape "E<digit>" is never exempt.
PROXIMITY_PATTERNS = [
    re.compile(rf"\b{_DES}\s*[-\u2013./:_#]\s*\d{{1,3}}\b", re.I),
    re.compile(rf"\b{_DES}\b(?:\W+\w+){{0,3}}?\W+{_PIN}\b", re.I),
    re.compile(rf"\b{_PIN}\b(?:\W+\w+){{0,3}}?\W+(?:of|on|at|in|from)\W+(?:the\W+)?{_DES}\b", re.I),
]


class UnverifiedBoardPinAction(ValueError):
    """An exact component-pin test was proposed without board identification."""


def _mask_evidence_ids(text: str, evidence_ids: Collection[str] | None) -> str:
    for ident in sorted({i for i in (evidence_ids or ()) if isinstance(i, str) and i}, key=len, reverse=True):
        text = re.sub(rf"(?<!\w){re.escape(ident)}(?!\w)", "\x01" * len(ident), text)
    return text


def _spans(text: str, evidence_ids: Collection[str] | None) -> list[tuple[int, int]]:
    masked = _mask_evidence_ids(text, evidence_ids)
    found = sorted(
        [(m.start(), m.end()) for p in PATTERNS for m in p.finditer(text)]
        + [(m.start(), m.end()) for p in PROXIMITY_PATTERNS for m in p.finditer(masked)]
    )
    merged: list[tuple[int, int]] = []
    for start, end in found:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def unsafe_pin_actions(
    plan: Mapping[str, Any], reference: Mapping[str, Any] | None,
    evidence_ids: Collection[str] | None = None,
) -> list[dict[str, str]]:
    if not reference or reference.get("target_board_physically_verified") is not False:
        return []
    issues=[]
    for field,raw in iter_plan_text(plan, evidence_ids):
        for reason,chars in disallowed_text_reasons(raw):
            issues.append({"field":field,"pin_reference":chars,"reason":reason})
        text=fold(raw)
        for start,end in _spans(text,evidence_ids):
            issues.append({
                "field":field,"pin_reference":text[start:end].strip(),
                "reason":"The cited schematic is revision-specific; target board identity is only publisher-reported, not physically verified.",
            })
    return issues


def reject_unverified_board_pin_actions(
    plan:Mapping[str,Any],reference:Mapping[str,Any]|None,
    evidence_ids:Collection[str]|None=None,
)->None:
    issues=unsafe_pin_actions(plan,reference,evidence_ids)
    if issues:
        raise UnverifiedBoardPinAction(
            "board revision not independently verified; pin-specific action withheld: "+
            ", ".join(x["pin_reference"] for x in issues)
        )
