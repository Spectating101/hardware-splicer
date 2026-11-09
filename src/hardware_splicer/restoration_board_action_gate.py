"""Authority gate: reference schematic pins != verified physical test points.

A matching revision CLAIM from a video/article is never equivalent to
independently inspecting the actual board marking. We permit a model to
discuss the reference pin topology but fail closed on proposed pin-specific
physical checks while its applicability is unverified.
"""
from __future__ import annotations
import re
from typing import Any, Mapping

_COMPONENT_PIN = re.compile(
    r"(?i)\b(?:[A-Z]{1,3}\d{1,4})\s*(?:pin\s*#?\s*\d+|[.]\d+|pins\s*\d+\s*(?:and|to|-)\s*\d+)\b"
    r"|\bpin\s*#?\s*\d+\s+(?:on|of|at)\s+[A-Z]{1,3}\d{1,4}\b"
)


class UnverifiedBoardPinAction(ValueError):
    """An exact component-pin test was proposed without board identification."""


def unsafe_pin_actions(
    plan: Mapping[str, Any], reference: Mapping[str, Any] | None
) -> list[dict[str, str]]:
    if not reference or reference.get("target_board_physically_verified") is not False:
        return []
    issues=[]
    fields=[("next_safe_check",plan.get("next_safe_check",""))]
    for index,hyp in enumerate(plan.get("hypotheses") or [],1):
        fields.append((f"hypotheses[{index}].safe_test",hyp.get("safe_test","")))
    for field,text in fields:
        if not isinstance(text,str):
            continue
        for m in _COMPONENT_PIN.finditer(text):
            issues.append({
                "field":field,"pin_reference":m.group(0).strip(),
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
