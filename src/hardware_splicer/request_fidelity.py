"""Compare the parts a request listed with the parts in the compiled design.

The compiler can drop or merge a requested part (two servos compiled as one) and still
pass every board-level check, because those checks only look at what was drawn. This
check looks at the request. It is independent of the compiler and reports, never repairs.
"""

from __future__ import annotations

import re
from collections import Counter
from difflib import SequenceMatcher
from typing import Any, Dict, List, Mapping, Sequence

from .pcb.module_registry import find_module, list_canvas_modules

SCHEMA_VERSION = "hardware_splicer.request_fidelity.v1"
CLAIM_BOUNDARY = (
    "Compares the parts the request listed with the parts in the compiled design, by module and count. "
    "It also looks in the goal text for parts it names and for a mains or high-voltage load. "
    "It does not check wiring, firmware or whether the design performs the requested function."
)

# Parts a goal can name in words. Each row is (label, pattern for the goal, pattern for a module id that
# satisfies it). A goal that names one of these and a design with no matching module is a mismatch, whatever
# the picker chose. A mechanical relay is not a solid-state relay, and a digital temperature probe is not a
# thermistor, so the module patterns are narrow on purpose.
_NAMED_PARTS: tuple[tuple[str, re.Pattern[str], re.Pattern[str]], ...] = (
    ("thermistor", re.compile(r"\bthermistors?\b|\bntc\b", re.I), re.compile(r"thermistor|ntc", re.I)),
    (
        "thermocouple",
        re.compile(r"\bthermocouples?\b|\bmax6675\b|\bmax31855\b|\bmax31856\b", re.I),
        re.compile(r"thermocouple|max6675|max3185", re.I),
    ),
    (
        "solid-state relay (SSR)",
        re.compile(r"\bssrs?\b|\bsolid[- ]state relays?\b", re.I),
        re.compile(r"ssr|solid.?state", re.I),
    ),
    (
        "microSD card",
        re.compile(r"\bmicro[- ]?sd\b|\bsd[- ]?cards?\b|\btf cards?\b", re.I),
        re.compile(r"sd_card|sd-card|microsd|tf_card", re.I),
    ),
    ("GPS receiver", re.compile(r"\bgps\b|\bgnss\b|\bneo-?6m\b", re.I), re.compile(r"gps|gnss|neo-?6m", re.I)),
    ("load cell", re.compile(r"\bload cells?\b|\bhx711\b", re.I), re.compile(r"hx711|load.?cell", re.I)),
    ("OLED display", re.compile(r"\boleds?\b|\bssd1306\b", re.I), re.compile(r"ssd1306|oled|sh1106", re.I)),
    (
        "real-time clock",
        re.compile(r"\brtc\b|\breal[- ]time clock\b|\bds3231\b|\bds1307\b", re.I),
        re.compile(r"rtc|ds3231|ds1307", re.I),
    ),
    (
        "stepper motor",
        re.compile(r"\bstepper(?: motors?)?\b", re.I),
        re.compile(r"stepper|a4988|drv8825|tmc2209", re.I),
    ),
    ("servo", re.compile(r"\bservos?\b", re.I), re.compile(r"sg90|servo|mg996", re.I)),
)

_NEGATION = re.compile(
    r"(?:\bno|\bnot|\bwithout|\bexcluding|\bexcept|\binstead of|\bw/o|\bnor)\W+(?:\w+\W+){0,2}$", re.I
)

_VOLT = re.compile(
    r"(?<![\w.])(\d+(?:\.\d+)?)\s*(k?)\s*(?:v|volts?)(?:\s*(ac|dc))?(?![a-z0-9])", re.I
)
_MAINS_WORDS = re.compile(r"\bmains?\b|\bline voltage\b|\bhigh[- ]voltage\b|\bwall (?:power|outlet|socket)\b|\bac outlet\b", re.I)

HIGH_VOLTAGE_FINDING = (
    "The goal states a mains or high-voltage load ({evidence}). Switching or sensing mains is outside this "
    "bounded low-voltage lane: HS will not mark such a design build ready. A person with mains-safety "
    "training has to specify and review isolation, creepage, fusing, enclosure and certification."
)


def detect_high_voltage_goal(goal: str | None) -> Dict[str, Any] | None:
    """Return the evidence when a goal states a mains or high-voltage load, else None.

    Thresholds: 50 V AC or more, 120 V DC or more, and a bare voltage of 100 V or more (mains is the usual
    reading of "230 V" or "110 V"). Below that, and everything without an explicit voltage, is not flagged.
    """
    text = str(goal or "")
    if not text.strip():
        return None
    word = _MAINS_WORDS.search(text)
    if word and not _NEGATION.search(text[: word.start()]):
        return {"kind": "keyword", "evidence": word.group(0)}
    for match in _VOLT.finditer(text):
        value = float(match.group(1)) * (1000.0 if match.group(2) else 1.0)
        kind = (match.group(3) or "").lower()
        limit = {"ac": 50.0, "dc": 120.0}.get(kind, 100.0)
        if value >= limit:
            return {"kind": "voltage", "evidence": match.group(0).strip(), "volts": value, "current_type": kind or None}
    return None


def assess_goal_fidelity(goal: str | None, build_graph: Mapping[str, Any] | None) -> Dict[str, Any]:
    """Compare the parts the goal text names, and any mains load it states, with the compiled design."""
    text = str(goal or "")
    in_design = [str(n.get("moduleId") or "") for n in (build_graph or {}).get("nodes") or []]
    missing: list[Dict[str, Any]] = []
    # With no compiled graph there is nothing to compare against; absence never upgrades, so the gate's own
    # "did not compile" blocker stands.
    if build_graph is not None:
        for label, goal_pattern, module_pattern in _NAMED_PARTS:
            named = next(
                (m for m in goal_pattern.finditer(text) if not _NEGATION.search(text[: m.start()])),
                None,
            )
            if named is None or any(module_pattern.search(mid) for mid in in_design if mid):
                continue
            missing.append({"label": label, "named_as": named.group(0)})
    return {"named_parts_missing": missing, "high_voltage": detect_high_voltage_goal(text)}


def assess_request_fidelity(
    requested_parts: Sequence[Mapping[str, Any]],
    build_graph: Mapping[str, Any] | None,
    *,
    goal: str | None = None,
) -> Dict[str, Any]:
    requested: Counter[str] = Counter()
    names: Dict[str, list[str]] = {}
    unmapped: list[str] = []
    for part in requested_parts:
        module_id = str(part.get("module_id") or "").strip()
        name = str(part.get("name") or module_id or "unnamed part")
        if not module_id:
            unmapped.append(name)
            continue
        requested[module_id] += 1
        names.setdefault(module_id, []).append(name)

    in_design: Counter[str] = Counter()
    if build_graph is not None:
        in_design.update(str(node.get("moduleId") or "") for node in build_graph.get("nodes") or [])

    missing = []
    for module_id, count in requested.items():
        if build_graph is None or in_design[module_id] >= count:
            continue
        unknown = find_module(module_id) is None
        missing.append(
            {
                "module_id": module_id,
                "names": names[module_id],
                "requested": count,
                "in_design": in_design[module_id],
                "unknown_module_id": unknown,
                "did_you_mean": suggest_module_ids(module_id) if unknown else [],
            }
        )
    unrequested = [
        {"module_id": module_id, "count": count}
        for module_id, count in in_design.items()
        if module_id and module_id not in requested
    ]

    goal_check = assess_goal_fidelity(goal, build_graph) if goal else {"named_parts_missing": [], "high_voltage": None}

    if goal_check["high_voltage"]:
        status = "out_of_scope"
    elif goal_check["named_parts_missing"]:
        status = "mismatch"
    elif build_graph is None or not (requested or unmapped):
        status = "not_assessable"
    elif missing:
        status = "mismatch"
    elif unmapped:
        status = "not_assessable"
    else:
        status = "matches"

    result = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "missing_parts": missing,
        "unmapped_requests": unmapped,
        "unrequested_in_design": unrequested,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    if goal:
        result["goal_named_parts_missing"] = goal_check["named_parts_missing"]
        result["high_voltage_goal"] = goal_check["high_voltage"]
    return result


_WORD = re.compile(r"[a-z0-9]+")


def suggest_module_ids(guess: str, limit: int = 3) -> List[str]:
    """Known part ids a guessed id was probably meant to be; empty when nothing is plausible.

    A suggestion needs a distinctive word in common (a chip name, which contains a digit) or two words in
    common, or a near-identical spelling. Sharing only a generic word such as "module" or "rtc" is not
    enough: a wrong suggestion is worse than none.
    """
    guess_words = set(_WORD.findall(guess.lower()))
    scored = []
    for module in list_canvas_modules():
        module_id = str(module["id"])
        words = set(_WORD.findall(module_id.lower()))
        shared = guess_words & words
        distinctive = any(any(ch.isdigit() for ch in w) and len(w) >= 3 and not re.fullmatch(r"\d+v?", w) for w in shared)
        ratio = SequenceMatcher(None, guess.lower(), module_id.lower()).ratio()
        if distinctive or len(shared) >= 2 or ratio >= 0.8:
            scored.append((len(shared), ratio, module_id))
    return [module_id for _, _, module_id in sorted(scored, reverse=True)[:limit]]
