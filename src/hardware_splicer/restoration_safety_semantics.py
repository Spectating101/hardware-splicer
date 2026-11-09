"""Bounded semantic guard for hazards quoted as prohibitions vs instructions.

This is an auxiliary text filter, not a safety certification, machine
authorization system or comprehensive electrical standard. It is intended
to prevent the regex rule treating "Never probe live mains" as an
instruction to DO so. Potentially unsafe positive proposals still fail.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Pattern

NEGATED = re.compile(
    r"(?i)\b(?:do\s+not|don't|never|avoid|must\s+not|should\s+not|"
    r"not\s+safe\s+to|refrain\s+from|not\s+recommended\s+to)\b"
)
CLAUSE_BREAK = re.compile(r"[.;!?\n]")
CHANGE_OF_DIRECTION = re.compile(
    r"(?i)\b(?:but|instead|however|then|next|rather|otherwise|afterwards)\b"
)
WORD = re.compile(r"\b[\w]+(?:'[\w]+)?\b")

def _clearly_negated(text:str,match_start:int)->bool:
    """Protect explicit local prohibitions, not remote 'do not ... but DO'."""
    before=text[:match_start]
    # Restrict the scope to this clause rather than an entire paragraph.
    clause=CLAUSE_BREAK.split(before)[-1]
    matches=list(NEGATED.finditer(clause))
    if not matches:
        return False
    neg=matches[-1]
    tail=clause[neg.end():]
    if CHANGE_OF_DIRECTION.search(tail):
        return False
    # A local prohibition can have a short "attempt to", "ever", "the"
    # interposition before the prohibited verb phrase.
    return len(WORD.findall(tail))<=6

def unsafe_action_findings(
    plan:Mapping[str,Any], matcher:Pattern[str]
)->list[dict[str,str]]:
    fields=[
        ("summary",plan.get("summary","")),
        ("next_safe_check",plan.get("next_safe_check","")),
        ("uncertainty",plan.get("uncertainty","")),
    ]
    for i,h in enumerate(plan.get("hypotheses") or [],1):
        for k in ("mechanism","why","safe_test"):
            fields.append((f"hypotheses[{i}].{k}",h.get(k,"")))
    findings=[]
    for field,text in fields:
        if not isinstance(text,str):
            continue
        for m in matcher.finditer(text):
            if _clearly_negated(text,m.start()):
                continue
            findings.append({
                "field":field,
                "matched_action_class":m.group(0)[:100],
                "reason":"Positive or unqualified hazardous action proposal: fail closed.",
            })
    return findings
