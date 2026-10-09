"""Small checks on text a person types, shared by the planners that accept it."""

from __future__ import annotations

import unicodedata

# Control characters, invisible formatting characters (zero-width spaces, left-to-right and right-to-left overrides), line and
# paragraph separators, and private or unassigned code points: none of them belong in a name, a label or a marking, and the
# overrides can make text on screen read differently from what it is.
_REFUSED = {"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"}


def has_hidden_characters(value: str) -> bool:
    return any(unicodedata.category(ch) in _REFUSED for ch in value)


def finite_number(value: object) -> float | None:
    """The value as a finite float, or None for anything else, including an integer too large to be a float."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except (OverflowError, ValueError):
        return None
    return number if number == number and number not in (float("inf"), float("-inf")) else None
