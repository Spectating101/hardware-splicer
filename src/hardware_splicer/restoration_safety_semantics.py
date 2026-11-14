"""Bounded semantic guard for hazards quoted as prohibitions vs instructions.

This is an auxiliary text filter, not a safety certification, machine
authorization system or comprehensive electrical standard. It is intended
to prevent the regex rule treating "Never probe live mains" as an
instruction to DO so. Potentially unsafe positive proposals still fail.

A negation covers only its own clause. A prohibition earlier in the text
never masks a later hazardous command: every hazardous verb occurrence is
judged separately, and a negator only protects an occurrence when nothing
that ends or redirects a clause (punctuation, "but", "then", "instead",
"unless", a double negative such as "do not hesitate to", ...) sits between
the two. The check is fail-closed: when in doubt the action is reported.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterator, Mapping, Pattern

NEGATED = re.compile(
    r"(?i)\b(?:do\s+not|don't|never|avoid|must\s+not|should\s+not|"
    r"not\s+safe\s+to|refrain\s+from|not\s+recommended\s+to)\b"
)
# Hard clause boundaries: a negation never crosses these.
CLAUSE_BREAK = re.compile(r"[.;!?:\n\r—–|•(){}\[\]\"]|\s-+\s")
CHANGE_OF_DIRECTION = re.compile(
    r"(?i)\b(?:but|instead|however|then|next|rather|otherwise|afterwards?|"
    r"alternatively|unless|except|although|though|yet|still|whereas|while|"
    r"also|later|before|after|once|when|whenever|if|because|since|until|"
    r"first|finally|meanwhile|besides|additionally|furthermore|moreover|plus|"
    r"and\s+then|or\s+else|only)\b"
)
# "do not hesitate/forget/fail to X" is an instruction to do X.
DOUBLE_NEGATION = re.compile(
    r"(?i)\b(?:forget|forgetting|hesitate|hesitating|fail|failing|neglect|"
    r"neglecting|refuse|refusing|omit|omitting|skip|skipping|no\s+need|"
    r"not\s+only|wait|waiting|stop|cease|ever\s+fail)\b"
)
WORD = re.compile(r"\b[\w]+(?:'[\w]+)?\b")
# A comma ends the negated clause, except in a plain list of verbs
# ("never probe, measure or touch live mains").
_LIST_WORDS = frozenset({
    "or", "and", "nor", "to", "attempt", "ever", "try", "even", "bypass",
    "bypassing", "short", "shorting", "jump", "jumper", "jumping", "bridge",
    "bridging", "probe", "probing", "measure", "measuring", "touch",
    "touching", "test", "testing", "charge", "charging", "recharge",
    "recharging", "jumpstart", "defeat", "defeating", "disable", "disabling",
    "override", "overriding", "circumvent", "circumventing", "out",
})
_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿­"))


def normalise(text: str) -> str:
    """Fold look-alike spellings so a matcher sees one canonical form."""
    text = unicodedata.normalize("NFKC", text).translate(_ZERO_WIDTH)
    text = text.replace("’", "'").replace("‘", "'").replace("`", "'")
    text = re.sub(r"(?<=\w)[-_/‐‑](?=\w)", " ", text)
    return text


def iter_plan_text(plan: Mapping[str, Any]) -> Iterator[tuple[str, str]]:
    """Yield (field path, text) for every free-text string in a plan.

    Walks the whole structure, not a fixed field list, so an extra or
    renamed key cannot hide text from a gate. Evidence ID lists are
    identifiers, not prose, and are skipped.
    """
    def walk(path: str, node: Any) -> Iterator[tuple[str, str]]:
        if isinstance(node, str):
            yield path, node
        elif isinstance(node, Mapping):
            for key, value in node.items():
                if key == "evidence_ids":
                    continue
                yield from walk(f"{path}.{key}" if path else str(key), value)
        elif isinstance(node, (list, tuple)):
            for index, value in enumerate(node, 1):
                yield from walk(f"{path}[{index}]", value)
    yield from walk("", plan)


def _negation_covers(text: str, start: int) -> bool:
    """True only if a negator in the SAME clause governs the verb at start."""
    before = text[:start]
    clause = CLAUSE_BREAK.split(before)[-1]
    matches = list(NEGATED.finditer(clause))
    if not matches:
        return False
    tail = clause[matches[-1].end():]
    if CHANGE_OF_DIRECTION.search(tail) or DOUBLE_NEGATION.search(tail):
        return False
    words = [w.lower() for w in WORD.findall(tail)]
    if "," in tail and not all(w in _LIST_WORDS for w in words):
        return False
    # A local prohibition can have a short "attempt to", "ever", "the"
    # interposition before the prohibited verb phrase.
    return len(words) <= 6


def _clearly_negated(text: str, match_start: int) -> bool:
    return _negation_covers(text, match_start)


def _all_matches(matcher: Pattern[str], text: str) -> Iterator[re.Match[str]]:
    """Every match start, including ones a longer match would swallow."""
    for pos in range(len(text)):
        m = matcher.match(text, pos)
        if m:
            yield m


def unsafe_action_findings(
    plan: Mapping[str, Any], matcher: Pattern[str]
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for field, raw in iter_plan_text(plan):
        text = normalise(raw)
        seen: set[int] = set()
        for m in _all_matches(matcher, text):
            if m.start() in seen or _negation_covers(text, m.start()):
                continue
            seen.add(m.start())
            findings.append({
                "field": field,
                "matched_action_class": m.group(0)[:100],
                "reason": "Positive or unqualified hazardous action proposal: fail closed.",
            })
    return findings
