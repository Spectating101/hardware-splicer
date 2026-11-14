"""Bounded semantic guard for hazards quoted as prohibitions vs instructions.

This is an auxiliary text filter, not a safety certification, machine
authorization system or comprehensive electrical standard. It is intended
to prevent the regex rule treating "Never probe live mains" as an
instruction to DO so. Potentially unsafe positive proposals still fail.

Fail-closed rules:

* Every hazardous verb occurrence is judged on its own (overlapping matches
  included), so a prohibition earlier in the text never masks a later one.
* A negator protects a hazardous verb only when it is DIRECTLY followed by it,
  allowing just a fixed set of fillers ("attempt to", "ever", "try to") or a
  list made solely of hazardous verbs ("never probe, measure or touch ...").
  Any other word, punctuation or line/paragraph separator in between means
  the negation does not reach the verb. Double negatives are not prohibitions.
* Every free-text string AND every mapping key of the plan is scanned.
* Suspicious text is REJECTED, never repaired: any control (other than \n and
  \t), format, combining or private-use character, and any letter outside
  ASCII plus a few unit symbols (omega, mu), fails the gate with a distinct
  reason. Known limitation: legitimately accented or non-English text is
  therefore rejected too. Only line separators are mapped (to "\n") and
  compatibility forms are NFKC-folded before matching.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Collection, Iterator, Mapping, Pattern

NEGATED = re.compile(
    r"(?i)\b(?:do\s+not|don't|never|avoid|must\s+not|should\s+not|"
    r"not\s+safe\s+to|refrain\s+from|not\s+recommended\s+to)\b"
)
# Words that may sit between a negator and the hazardous verb it governs.
_FILLERS = frozenset({
    "attempt", "attempting", "to", "ever", "try", "trying", "even", "again",
})
_JOINERS = frozenset({"or", "and", "nor"})
_HAZARD_VERB = re.compile(
    r"(?i)^(?:bypass(?:es|ed|ing)?|shorts?|shorted|shorting|"
    r"jump(?:er|ers|ered|ering|ed|ing|s)?|bridg(?:e|es|ed|ing)|"
    r"defeat(?:s|ed|ing)?|disabl(?:e|es|ed|ing)|overrid(?:e|es|ing)|"
    r"circumvent(?:s|ed|ing)?|prob(?:e|es|ed|ing)|measur(?:e|es|ed|ing)|"
    r"touch(?:es|ed|ing)?|test(?:s|ed|ing)?|charg(?:e|es|ed|ing)|"
    r"recharg(?:e|es|ed|ing)|factory|wip(?:e|es|ing)|eras(?:e|es|ing)|out)$"
)
_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?|\S")
_ID = re.compile(r"^[A-Za-z]{1,2}\d{1,4}$")
# Characters that end a line or paragraph; mapped to "\n" before matching.
_LINE_SEPARATORS = dict.fromkeys(
    map(ord, "\u0085\u2028\u2029\x0b\x0c\x1c\x1d\x1e\x1f\u3002\uff01\uff1f\uff1b\u2026\u2025"),
    "\n",
)
_ALLOWED_NON_ASCII_LETTERS = frozenset("\u03a9\u2126\u03bc\u00b5")  # omega, ohm sign, mu, micro sign
REASON_CONTROL = "disallowed_control_or_format_character"
REASON_LETTER = "disallowed_non_ascii_letter"


def _line_folded(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").translate(_LINE_SEPARATORS)


def fold(text: str) -> str:
    """Canonical text for matching: line separators to "\n", NFKC, unified
    quotes and minus signs. Nothing is deleted; use disallowed_text_reasons()
    first, which rejects what fold() would otherwise have to guess about."""
    text = unicodedata.normalize("NFKC", _line_folded(text))
    text = text.replace("\u2019", "'").replace("\u2018", "'").replace("`", "'")
    text = text.replace("\u2212", "-").replace("\u2010", "-").replace("\u2011", "-")
    return text


def normalise(text: str) -> str:
    """fold() plus hyphen/underscore/slash joins read as spaces ("short-out")."""
    return re.sub(r"(?<=\w)[-_/](?=\w)", " ", fold(text))


def disallowed_text_reasons(text: str) -> list[tuple[str, str]]:
    """(reason, offending characters) for text that must fail the gate outright.

    Checked on the line-folded text before AND after NFKC, so a character
    that only appears after compatibility folding is caught as well.
    """
    folded = _line_folded(text)
    seen: dict[str, list[str]] = {}
    for candidate in (folded, unicodedata.normalize("NFKC", folded)):
        for ch in candidate:
            category = unicodedata.category(ch)
            if ch in "\n\t":
                continue
            if category in ("Cc", "Cf", "Mn", "Me", "Cs", "Co", "Cn"):
                bucket = seen.setdefault(REASON_CONTROL, [])
            elif ord(ch) > 127 and (category[0] == "L" or category == "Nd"
                                    or category in ("Nl", "No")) \
                    and ch not in _ALLOWED_NON_ASCII_LETTERS:
                bucket = seen.setdefault(REASON_LETTER, [])
            else:
                continue
            if ch not in bucket:
                bucket.append(ch)
    return [(reason, "".join(f"U+{ord(c):04X}" + " " for c in chars).strip())
            for reason, chars in seen.items()]


def iter_plan_text(
    plan: Mapping[str, Any], permitted_ids: Collection[str] | None = None
) -> Iterator[tuple[str, str]]:
    """Yield (field path, text) for every string AND mapping key in a plan.

    The walk is structural, not a fixed field list, so an extra or renamed
    key cannot hide text from a gate. The only thing skipped is a hypothesis'
    own ``evidence_ids`` when it is a list of well-formed evidence IDs (members
    of ``permitted_ids`` when given). An ``evidence_ids`` anywhere else, or
    one holding anything else, is scanned like any other text.
    """
    def is_id_list(value: Any) -> bool:
        if not isinstance(value, list) or not value:
            return False
        return all(
            isinstance(v, str) and _ID.fullmatch(v)
            and (permitted_ids is None or v in permitted_ids)
            for v in value
        )

    def walk(path: str, node: Any, hypothesis: bool) -> Iterator[tuple[str, str]]:
        if isinstance(node, str):
            yield path, node
        elif isinstance(node, Mapping):
            for key, value in node.items():
                child = f"{path}.{key}" if path else str(key)
                if isinstance(key, str):
                    yield f"{child}[key]", key
                if hypothesis and key == "evidence_ids" and is_id_list(value):
                    continue
                yield from walk(child, value, False)
        elif isinstance(node, (list, tuple)):
            for index, value in enumerate(node, 1):
                yield from walk(f"{path}[{index}]", value, path == "hypotheses")

    yield from walk("", plan, False)


def _negation_covers(text: str, start: int) -> bool:
    """True only if a negator directly governs the hazardous verb at start."""
    negators = list(NEGATED.finditer(text, 0, start))
    if not negators:
        return False
    last = negators[-1]
    if "\n" in text[last.end():start]:
        return False
    for token in _WORD.findall(text[last.end():start]):
        low = token.lower()
        if token == "," or low in _FILLERS or low in _JOINERS or _HAZARD_VERB.match(token):
            continue
        return False
    # A double negative ("do not refrain from", "do not not") is an instruction:
    # two negators with nothing but filler between them.
    if len(negators) > 1 and not _has_content(text[negators[-2].end():last.start()]):
        return False
    return True


def _has_content(gap: str) -> bool:
    return any(t.lower() not in _FILLERS and t != "," for t in _WORD.findall(gap))


def _clearly_negated(text: str, match_start: int) -> bool:
    return _negation_covers(text, match_start)


def _all_matches(matcher: Pattern[str], text: str) -> Iterator[re.Match[str]]:
    """Every match start, including ones a longer match would swallow."""
    for pos in range(len(text)):
        m = matcher.match(text, pos)
        if m:
            yield m


def unsafe_action_findings(
    plan: Mapping[str, Any], matcher: Pattern[str],
    permitted_ids: Collection[str] | None = None,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for field, raw in iter_plan_text(plan, permitted_ids):
        for reason, chars in disallowed_text_reasons(raw):
            findings.append({
                "field": field,
                "matched_action_class": chars[:100],
                "reason": reason,
            })
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
