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
from typing import Any, Mapping

from .restoration_safety_semantics import (
    disallowed_text_reasons, fold, iter_plan_text,
)

_DES = r"[A-Z]{1,3}\d{1,4}"
# Proximity patterns skip evidence IDs ("E1", "E12"), which are not parts.
_PART_DES = r"(?!E\d)[A-Z]{1,3}\d{1,4}"
# Words allowed between a designator and a pin-like word: no punctuation.
_GAP = r"[\s'\u2019()]+"
_ACT = (r"(?:probe|probing|measure|measuring|check|checking|test|testing|touch|"
        r"meter|multimeter|continuity|voltage|resistance|reading|short|jumper|"
        r"apply|connect|solder|ground)")
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
PATTERNS = [
    _COMPONENT_PIN,
    re.compile(rf"\b{_PIN}\s*(?:(?:no|num|number)\b\.?)?\s*[:#]?\s*{_NUM}\b", re.I),
    re.compile(rf"\b{_ORD}\s+{_PIN}\b", re.I),
    re.compile(rf"\b{_PART_DES}\s*[-\u2013./:_#]\s*\d{{1,3}}\b", re.I),
    re.compile(rf"\b{_PART_DES}\b(?:{_GAP}\w+){{0,3}}?{_GAP}{_PIN}\b", re.I),
    re.compile(rf"\b{_PIN}\b(?:{_GAP}\w+){{0,3}}?{_GAP}(?:of|on|at|in|from){_GAP}(?:the{_GAP})?{_PART_DES}\b", re.I),
    re.compile(rf"\b{_ACT}\b[^.;:!?\n]{{0,60}}?\bpins?\b(?:{_GAP}\w+){{0,3}}?{_GAP}(?:of|on|at|in){_GAP}(?:the{_GAP})?(?:\w+{_GAP}){{0,2}}?{_PART}\b", re.I),
]


class UnverifiedBoardPinAction(ValueError):
    """An exact component-pin test was proposed without board identification."""


def _spans(text: str) -> list[tuple[int, int]]:
    found = sorted((m.start(), m.end()) for p in PATTERNS for m in p.finditer(text))
    merged: list[tuple[int, int]] = []
    for start, end in found:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def unsafe_pin_actions(
    plan: Mapping[str, Any], reference: Mapping[str, Any] | None
) -> list[dict[str, str]]:
    if not reference or reference.get("target_board_physically_verified") is not False:
        return []
    issues=[]
    for field,raw in iter_plan_text(plan):
        for reason,chars in disallowed_text_reasons(raw):
            issues.append({"field":field,"pin_reference":chars,"reason":reason})
        text=fold(raw)
        for start,end in _spans(text):
            issues.append({
                "field":field,"pin_reference":text[start:end].strip(),
                "reason":"The cited schematic is revision-specific; target board identity is only publisher-reported, not physically verified.",
            })
    return issues


def reject_unverified_board_pin_actions(
    plan:Mapping[str,Any],reference:Mapping[str,Any]|None
)->None:
    issues=unsafe_pin_actions(plan,reference)
    if issues:
        raise UnverifiedBoardPinAction(
            "board revision not independently verified; pin-specific action withheld: "+
            ", ".join(x["pin_reference"] for x in issues)
        )
