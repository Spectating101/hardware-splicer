"""Look a marking up in KiCad's own libraries, offline.

KiCad ships about twenty thousand symbols with a description, a datasheet link, a default footprint and every pin's name and type,
and thousands of footprints with exact courtyard sizes. They are a real, free, versioned dataset that is already on the machine,
so this reads them instead of keeping a table of our own.

What a hit means, and does not: a library holds a part that has that name. It is not proof that the chip in front of you is that part
(a marking can be a house code, worn or fake), and a family match is the same family, not the same part. Every answer carries the
library's name and version so it can be checked.
"""

from __future__ import annotations

import bisect
import os
import re
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .assembly_plan import _bbox, _children, _layer_of, _points_of
from .kicad_diff import KicadDiffError, parse_kicad_sexp
from .text_safety import has_hidden_characters

MAX_QUERY = 40
MIN_QUERY = 3
MAX_MATCHES = 8
MAX_PINS = 128
MAX_PINS_FOR_GATES = 64         # a part with more pins than this has many supplies and grounds: picking one honestly takes its datasheet
MAX_LIBRARY_FILE = 80 * 1024 * 1024
# A package or grade code after a part number: a few letters (D, DBV, Tx), or something that starts with a separator (-D, _DFN, -LP). Digits
# without a separator mean a different function: 74HC00 is not 74HC04, and LM35 is not LM358.
_SUFFIX = re.compile(r"^(?:[A-Za-z]{1,5}|[-_][A-Za-z0-9_\-./]{1,8})$")
_LETTERS_ONLY = re.compile(r"^[A-Za-z_\-]*$")
_SYMBOL = re.compile(r'^\t\(symbol "((?:[^"\\]|\\.)+)"\n', re.MULTILINE)
_PROPERTY = re.compile(r'\(property "(Value|Description|Datasheet|Footprint|ki_keywords)" "((?:[^"\\]|\\.)*)"')
_EXTENDS = re.compile(r'\(extends "([^"]+)"\)')
_GENERATOR = re.compile(r'\(generator_version "([^"]+)"\)')
_FOOTPRINT_NAME = re.compile(r"^[A-Za-z0-9_.+\-]+:[A-Za-z0-9_.,+\- ]+$")
# A negative supply (VEE) is a supply, not a ground. Several grounds are ranked: the plain one first.
# KiCad writes V_{SS} / V_{CC}: strip the braces before matching. PGND1 ranks with PGND.
_GROUND_RANK = ("GND", "VSS", "DGND", "AGND", "GNDD", "GNDA", "VSSA", "PGND")
# Pins that carry no supply: the exposed pad, a tab or shield, and pins marked not connected.
_MAIN_SUPPLY = ("VDD", "VCC", "VDDIO", "VCCIO", "VIN", "VI", "IN", "V+", "VS", "VSUP", "AVDD", "AVCC", "VDDA", "VM", "VMOT")
_NEG_REF = ("V-", "VEE", "VCC-")
# Sense / internal / bypass pins are not a rail the person should drive (TI DRV8833 VINT; ST L298 SENSE).
_INTERNAL_STEM = ("SENSE", "VINT", "VCAP", "VREG", "VBYP", "VREF")
_NOT_A_SUPPLY = re.compile(r"^(EP|EPAD|PAD|TAB|SHIELD|SHLD|NC|DNC|N/C|~)\d*$", re.IGNORECASE)
_PIN_ONE_PACKAGES = re.compile(r"^(Package_DIP|Package_SO|Package_QFP|Package_DFN_QFN):", re.IGNORECASE)
_TO220 = re.compile(r"TO-?220", re.IGNORECASE)
_SOT23 = re.compile(r"SOT-?23", re.IGNORECASE)
_BGA_OR_MODULE = re.compile(r"^(Package_BGA|RF_Module):", re.IGNORECASE)
_BRACES = re.compile(r"[_\\{}]")


class PartLookupError(ValueError):
    """The query cannot be looked up."""


def kicad_root() -> Path:
    return Path(os.environ.get("HARDWARE_SPLICER_KICAD_DIR", "/usr/share/kicad"))


def libraries_available() -> bool:
    root = kicad_root()
    return (root / "symbols").is_dir() and any((root / "symbols").glob("*.kicad_sym"))


@dataclass(frozen=True)
class _Row:
    library: str
    name: str
    description: str
    datasheet: str
    footprint: str
    keywords: str
    extends: str | None
    path: str
    start: int
    end: int


@dataclass
class _Index:
    rows: list[_Row]
    by_name: dict[str, list[_Row]]
    sorted_names: list[str]
    version: str
    skipped_files: int = 0


_LOCK = threading.Lock()


def _clean(value: str, limit: int) -> str:
    text = value.replace('\\"', '"').strip()
    return "" if has_hidden_characters(text) else text[:limit]


@lru_cache(maxsize=1)
def _build_index(root: str) -> _Index:
    symbols = Path(root) / "symbols"
    rows: list[_Row] = []
    version = ""
    skipped = 0
    for path in sorted(symbols.glob("*.kicad_sym")):
        try:
            if path.stat().st_size > MAX_LIBRARY_FILE:
                skipped += 1
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            skipped += 1                   # one unreadable library does not stop the others being used
            continue
        if not version:
            found = _GENERATOR.search(text[:400])
            version = found.group(1) if found else ""
        starts = list(_SYMBOL.finditer(text))
        for i, match in enumerate(starts):
            end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
            own = text[match.start() : end]       # this symbol only: scanning past its end would read the next symbol's properties
            props: dict[str, str] = {}
            for key, value in _PROPERTY.findall(own[:4000]):
                props.setdefault(key, value)
            extends = _EXTENDS.search(own[:600])
            rows.append(
                _Row(
                    library=path.stem, name=match.group(1).replace('\\"', '"'), description=_clean(props.get("Description", ""), 200),
                    datasheet=_clean(props.get("Datasheet", ""), 300), footprint=_clean(props.get("Footprint", ""), 120),
                    keywords=_clean(props.get("ki_keywords", ""), 120), extends=extends.group(1) if extends else None,
                    path=str(path), start=match.start(), end=end,
                )
            )
    by_name: dict[str, list[_Row]] = {}
    for row in rows:
        by_name.setdefault(row.name.lower(), []).append(row)
    return _Index(rows=rows, by_name=by_name, sorted_names=sorted(by_name), version=version, skipped_files=skipped)


def _index() -> _Index:
    with _LOCK:
        return _build_index(str(kicad_root()))


def clear_cache() -> None:
    with _LOCK:
        _build_index.cache_clear()
        _footprint_size.cache_clear()


def source() -> dict[str, Any]:
    """Which library an answer came from, so it can be checked."""

    index = _index()
    return {
        "name": "KiCad symbol library",
        "version": index.version or "unknown",
        "symbols": len(index.rows),
        "skipped_files": index.skipped_files,
        "path": "symbols/*.kicad_sym of the KiCad install on the server",
        "note": "A library entry is a part with that name. It is not proof that the chip you hold is that part.",
    }


def normalise(marking: Any) -> str:
    if not isinstance(marking, str):
        raise PartLookupError("the marking must be text")
    text = marking.strip()
    if has_hidden_characters(text):
        raise PartLookupError("the marking may not contain control or invisible characters")
    if len(text) > MAX_QUERY:
        raise PartLookupError(f"the marking may be at most {MAX_QUERY} characters")
    return text


def _safe_url(url: str) -> str | None:
    return url if re.fullmatch(r"https?://[^\s\"'<>]{4,290}", url) else None


def _prefix_rows(index: _Index, prefix: str) -> list[str]:
    start = bisect.bisect_left(index.sorted_names, prefix)
    names: list[str] = []
    for name in index.sorted_names[start:]:
        if not name.startswith(prefix):
            break
        names.append(name)
        if len(names) >= 50:
            break
    return names


def name_match_tier(marking: str, name: str) -> str | None:
    """The exact/variant name rules, without library I/O or family suggestions.

    Callers validate their text first. A returned tier compares names, never identifies a physical part.
    """

    q, n = marking.strip().lower(), name.strip().lower()
    if len(q) < MIN_QUERY:
        return None
    if q == n:
        return "exact"
    short, long = (q, n) if len(q) <= len(n) else (n, q)
    if len(short) >= 4 and long.startswith(short) and _SUFFIX.fullmatch(long[len(short):]):
        return "variant"
    # KiCad's trailing x covers any character at that position, in the library name only.
    for tail in (1, 2, 3):
        if len(q) - tail >= 6 and n == q[:-tail] + "x" * tail:
            return "variant"
    return None


def lookup_part(marking: Any, limit: int = MAX_MATCHES) -> dict[str, Any]:
    """Parts in KiCad's library that the marking names, in three honest tiers: the same name, a variant (one name starts the other),
    and the same family (a long shared start). Nothing is returned for a marking too short to mean anything."""

    query = normalise(marking)
    result: dict[str, Any] = {"query": query, "source": None, "matches": [], "reason": None}
    if len(query) < MIN_QUERY:
        result["reason"] = f"a marking needs at least {MIN_QUERY} characters to look up"
        return result
    if not libraries_available():
        result["reason"] = "KiCad's libraries are not installed on the server, so there is nothing to look up in"
        return result
    index = _index()
    result["source"] = source()
    q = query.lower()
    chosen: list[tuple[str, str]] = []
    seen: set[str] = set()

    def take(names: list[str], tier: str) -> None:
        for name in names:
            if name not in seen and len(chosen) < limit:
                seen.add(name)
                chosen.append((name, tier))

    if q in index.by_name:
        take([q], "exact")
    prefixed = _prefix_rows(index, q) if len(q) >= 4 else []
    take(sorted((n for n in prefixed if n != q and name_match_tier(q, n) == "variant"), key=lambda n: (len(n), n)), "variant")
    # A library name that is the start of the marking (the marking carries a package or grade suffix the library leaves off).
    for k in range(len(q) - 1, 3, -1):
        if q[:k] in index.by_name and name_match_tier(q, q[:k]) == "variant":
            take([q[:k]], "variant")
            break
    # KiCad writes a trailing x for "any character here" (STM32F103C8Tx covers STM32F103C8T6): the marking fits it if only those places differ.
    for tail in (1, 2, 3):
        if len(q) - tail >= 6:
            wildcard = q[: len(q) - tail] + "x" * tail
            if wildcard in index.by_name and wildcard != q:
                take([wildcard], "variant")
    if not chosen and len(prefixed) >= 3:
        result["reason"] = "that is the start of many different parts: type more of the marking"
    if len(chosen) < limit:
        floor = max(6, int(len(q) * 0.6))
        for k in range(len(q) - 1, floor - 1, -1):
            names = []
            for n in _prefix_rows(index, q[:k]):
                if n in seen:
                    continue
                common = next((i for i in range(min(len(n), len(q))) if n[i] != q[i]), min(len(n), len(q)))
                # They may differ only in letters (a package, a grade): a digit where they part means a different function.
                if _LETTERS_ONLY.match(q[common:]) and _LETTERS_ONLY.match(n[common:]):
                    names.append(n)
            if names:
                take(sorted(names, key=lambda n: (abs(len(n) - len(q)), n)), "family")
                break
    texts = {
        "exact": "the library has a part with exactly this name",
        "variant": "the library has a part with this name plus or minus a short package or grade code: a different package or grade, whose pin numbers follow that entry",
        "family": "the library has parts from the same family, not this one: use them to learn what kind of chip it probably is, no more",
    }
    for name, tier in chosen:
        for row in index.by_name[name][:2]:
            result["matches"].append(
                {
                    "name": row.name, "library": row.library, "tier": tier, "tier_text": texts[tier], "description": row.description,
                    "datasheet": _safe_url(row.datasheet), "footprint": row.footprint or None, "keywords": row.keywords,
                }
            )
    result["matches"] = result["matches"][:limit]
    return result


def _find_row(index: _Index, library: str, name: str) -> _Row | None:
    for row in index.by_name.get(name.lower(), []):
        if row.library == library and row.name == name:
            return row
    return None


def symbol_pins(library: str, name: str, limit: int | None = MAX_PINS) -> dict[str, Any]:
    """Every pin of a library symbol: number, name and electrical type. A derived symbol takes its pins from the symbol it extends."""

    index = _index()
    row = _find_row(index, library, name)
    if row is None:
        raise PartLookupError("no such library symbol")
    seen_extends = 0
    while row.extends and seen_extends < 4:
        base = _find_row(index, row.library, row.extends)
        if base is None:
            break
        row, seen_extends = base, seen_extends + 1
    text = Path(row.path).read_text(encoding="utf-8")[row.start : row.end]
    tree = None
    for candidate in (text, text.rstrip()[:-1]):
        try:
            tree = parse_kicad_sexp(candidate)
            break
        except KicadDiffError:
            continue
    if tree is None:
        raise PartLookupError("the library symbol could not be read")
    pins: list[dict[str, str]] = []

    def walk(node: list[Any]) -> None:
        for child in node:
            if not isinstance(child, list) or not child:
                continue
            if child[0] == "pin" and len(child) > 2 and isinstance(child[1], str):
                name_node = next((c for c in _children(child, "name")), None)
                number_node = next((c for c in _children(child, "number")), None)
                pins.append({"type": child[1], "name": str(name_node[1]) if name_node and len(name_node) > 1 else "", "number": str(number_node[1]) if number_node and len(number_node) > 1 else ""})
            else:
                walk(child)

    walk(tree)
    unique: dict[str, dict[str, str]] = {}
    for pin in pins:
        unique.setdefault(pin["number"], pin)
    ordered = sorted(unique.values(), key=lambda p: (len(p["number"]), p["number"]))
    return {"library": library, "name": name, "pins_total": len(ordered), "pins": ordered if limit is None else ordered[:limit]}


def _all_pins(library: str, name: str) -> list[dict[str, str]]:
    found = symbol_pins(library, name, limit=None)
    return found["pins"]


def _pin_token(name: str) -> str:
    return _BRACES.sub("", name).upper()


def _ground_rank(token: str) -> int | None:
    if token in _GROUND_RANK:
        return _GROUND_RANK.index(token)
    if token.startswith("PGND"):
        return _GROUND_RANK.index("PGND")
    if token.startswith("GND"):
        return 0
    return None


def _is_internal(token: str) -> bool:
    return any(token == stem or token.startswith(stem) for stem in _INTERNAL_STEM)


def _supply_rank(token: str) -> int:
    if token in _MAIN_SUPPLY:
        return _MAIN_SUPPLY.index(token)
    for i, stem in enumerate(_MAIN_SUPPLY):
        if token.startswith(stem):
            return i
    return len(_MAIN_SUPPLY)


def footprint_family(footprint: str | None) -> str | None:
    """The capture-page family a KiCad footprint name belongs to, or None when it does not map."""

    if not footprint:
        return None
    upper = footprint.upper()
    library, _, item = upper.partition(":")
    if _TO220.search(upper):
        return "TO-220"
    if _SOT23.search(upper):
        return "SOT-23"
    if library == "PACKAGE_DIP":
        return "DIP"
    if library == "PACKAGE_QFP":
        return "QFP"
    if library == "PACKAGE_DFN_QFN":
        return "QFN"
    if library == "PACKAGE_BGA":
        return "BGA"
    if library == "RF_MODULE":
        return "MODULE"
    if library == "PACKAGE_SO":
        if "TSSOP" in item:
            return "TSSOP"
        if "SOIC" in item or item.startswith("SO-") or item.startswith("SO_"):
            return "SOIC"
        return "SO"
    if library == "PACKAGE_TO_SOT_THT":
        return "TO_THT:" + item.split("_", 1)[0]
    if library == "PACKAGE_TO_SOT_SMD":
        return "TO_SMD:" + item.split("_", 1)[0]
    return library or None


def footprint_fits_user(library_footprint: str | None, user_footprint: str | None) -> bool:
    """True unless both sides name a family and those families differ."""

    if not library_footprint or not user_footprint:
        return True
    library_key, user_key = footprint_family(library_footprint), footprint_family(user_footprint)
    if library_key is None or user_key is None:
        return True
    return library_key == user_key


def pick_named_match(matches: list[dict[str, Any]], user_footprint: str | None) -> dict[str, Any] | None:
    """The first exact/variant hit, preferring one whose footprint family fits the package the person chose."""

    named = [row for row in matches if row.get("tier") in {"exact", "variant"}]
    if not named:
        return None
    if user_footprint:
        fitting = [row for row in named if row.get("footprint") and footprint_fits_user(row.get("footprint"), user_footprint)]
        if fitting:
            return fitting[0]
    return named[0]


def _orientation(footprint: str | None) -> str:
    # JEDEC SPP-012: "The pin-numbering convention is counterclockwise, as viewed from above, for standard-bend product (leads bent down)"
    if not footprint:
        return ""
    if _PIN_ONE_PACKAGES.match(footprint):
        return (
            " The dot or notch marks the pin-1 end; pin 1 is the first leg counter-clockwise from it seen from the top "
            "for standard-bend leads; if you are looking at the underside of a board, the order appears reversed."
        )
    if _TO220.search(footprint) or _SOT23.search(footprint) or footprint.upper().startswith("PACKAGE_TO_SOT"):
        return (
            " The lead order depends on the part and must be taken from the datasheet's package drawing, "
            "not from the package name (7805 vs LM317)."
        )
    if _BGA_OR_MODULE.match(footprint):
        return " Balls are named by row and column, not counted around the edge."
    return ""


def _rail_pairs(pins: list[dict[str, str]]) -> tuple[list[dict[str, str]], dict[str, str]] | tuple[list[dict[str, str]], None]:
    """Supply pins to measure, and the pin each is measured against. Empty when the symbol does not name a pair."""

    has_plain_gnd = any(_pin_token(p["name"]) == "GND" for p in pins)
    grounds = []
    seen_g: set[str] = set()
    for pin in pins:
        token = _pin_token(pin["name"])
        rank = _ground_rank(token)
        if rank is None:
            continue
        if token == "VSS" and has_plain_gnd:
            continue          # L298 names the logic rail Vss while GND is the return (ST L298)
        if token in seen_g:
            continue
        seen_g.add(token)
        grounds.append((rank, pin))
    grounds.sort(key=lambda item: (item[0], len(item[1]["number"]), item[1]["number"]))
    supply: list[dict[str, str]] = []
    for pin in pins:
        token = _pin_token(pin["name"])
        if pin["type"] != "power_in":
            continue
        if _ground_rank(token) is not None and not (token == "VSS" and has_plain_gnd):
            continue
        if _is_internal(token) or _NOT_A_SUPPLY.match(pin["name"]) or _NOT_A_SUPPLY.match(token):
            continue
        if any(_pin_token(other["name"]) == token for other in supply):
            continue
        supply.append(pin)
    supply.sort(key=lambda pin: (_supply_rank(_pin_token(pin["name"])), len(pin["number"]), pin["number"]))
    if grounds:
        return supply, grounds[0][1]
    neg = next((pin for pin in supply if _pin_token(pin["name"]) in _NEG_REF), None)
    pos = [pin for pin in supply if _pin_token(pin["name"]) not in _NEG_REF]
    if neg and pos:
        return pos, neg
    outs = [
        pin for pin in pins
        if pin["type"] == "power_out"
        and not _is_internal(_pin_token(pin["name"]))
        and not _NOT_A_SUPPLY.match(pin["name"])
    ]
    if supply and outs:
        return supply, outs[0]
    return [], None


def _split_rails(supply: list[dict[str, str]]) -> bool:
    tokens = [_pin_token(pin["name"]) for pin in supply]
    return sum(1 for token in tokens if re.fullmatch(r"VCC[A-Z]", token)) >= 2


def _notes(pins: list[dict[str, str]], supply_pin: dict[str, str], *, kind: str, footprint: str | None, split: bool) -> str:
    names = {_pin_token(pin["name"]) for pin in pins}
    token = _pin_token(supply_pin["name"])
    bits: list[str] = []
    if kind == "voltage" and token.startswith("VBAT"):
        bits.append("VBAT may be a coin-cell backup: do not feed it from a supply you did not plan.")
    if kind == "voltage" and any(name.startswith("VCAP") for name in names):
        bits.append("VCAP is not a supply: do not apply a voltage there.")
    if kind == "voltage" and "EN" in names:
        bits.append("An enable pin (EN) can make a regulator's output read off with input present.")
    if kind == "voltage" and names & {"PROG", "STAT", "BAT"}:
        bits.append("Do not charge a cell to test a charger chip.")
    motor = any(name.startswith("VM") or name.startswith("PGND") or name == "VMOT" for name in names) or (
        token == "VS" and any(name.startswith("SENSE") for name in names)
    )
    if motor and kind in {"isolation", "voltage"}:
        bits.append("Motor drivers read low through body diodes and windings.")
    if split and kind == "isolation":
        bits.append("These rails must not be joined.")
    if kind == "voltage" and any(_pin_token(pin["name"]) in {"OUT", "VO"} and pin["type"] == "power_out" for pin in pins):
        bits.append("A reading on the input does not show what the output is doing.")
    if kind == "voltage" and footprint and _TO220.search(footprint):
        bits.append("The metal tab is a terminal: its function is in the datasheet, not implied by the package name.")
    if kind == "voltage" and footprint and "DFN_QFN" in footprint.upper():
        bits.append("If the datasheet puts the ground on the exposed pad, that pad is the return, not a supply.")
    if kind == "voltage":
        bits.append("Reversing the probes on a supply pair can destroy the part.")
    return (" " + " ".join(bits)) if bits else ""


def power_gates(library: str, name: str, footprint: str | None) -> list[dict[str, Any]]:
    """What to measure on a library symbol: power-off diode and ohms first, then a current-limited bench supply.

    They say what to measure and where, never what the reading should be: the range is the datasheet's to give.
    """

    try:
        pins = _all_pins(library, name)
    except PartLookupError:
        return []
    if len(pins) > MAX_PINS_FOR_GATES:
        return []
    supply, reference = _rail_pairs(pins)
    if not supply or reference is None:
        return []
    supply = supply[:3]
    split = _split_rails(supply)
    where = _orientation(footprint)
    # Fluke 87V MAX: "disconnect power and discharge all high-voltage capacitors before you measure resistance, continuity, capacitance, or a diode junction."
    # Fluke 87V MAX: "the resistance reading represents the total resistance of all paths between the probes."
    # TI SCDA039: "there are ESD diodes tied between the input and the positive supply rail (VDD/VCC) and an ESD diode tied from the input to the negative supply rail or ground (VSS/GND)."
    gates: list[dict[str, Any]] = []
    g_from = f"pin {reference['number']} ({reference['name']})"
    for kind, expect in (
        (
            "diode",
            "write down both readings, then compare them with the datasheet or a known-good chip",
        ),
        (
            "isolation",
            "write down both readings: ohms is every path in parallel, not a fact that the pins are shorted",
        ),
        (
            "voltage",
            "write down the voltage and the current; only the datasheet says what belongs on that pin pair",
        ),
    ):
        for pin in supply:
            extra = _notes(pins, pin, kind=kind, footprint=footprint, split=split)
            pair = f"pin {pin['number']} ({pin['name']})"
            if kind == "diode":
                instruction = (
                    f"With the power off, in diode mode, measure both ways between {pair} and {g_from}. "
                    f"Write both readings down.{where}{extra}"
                )
            elif kind == "isolation":
                instruction = (
                    f"With the power off, measure ohms both ways between {pair} and {g_from}. "
                    f"Ohms reads every path in parallel, and a chip's protection diodes can read low in one probe direction, "
                    f"so write both readings down and compare them with the datasheet or a known-good chip.{where}{extra}"
                )
            else:
                instruction = (
                    f"Only after writing down the power-off readings, and only from a current-limited bench supply set to the "
                    f"supply voltage in the datasheet for this pin pair (never the board's own supply, never a mains-derived one), "
                    f"measure between {pair} and {g_from}. Write down the voltage and the current it draws.{where}{extra}"
                )
            gates.append(
                {
                    "key": f"{library}:{name}|{kind}|{pair}|{g_from}",
                    "kind": kind,
                    "from": pair,
                    "to": g_from,
                    "instruction": instruction,
                    "expect": expect,
                }
            )
    return gates


@lru_cache(maxsize=512)
def _footprint_size(name: str) -> tuple[float, float] | None:
    if not _FOOTPRINT_NAME.match(name):
        return None
    library, _, item = name.partition(":")
    root = (kicad_root() / "footprints").resolve()
    path = (root / f"{library}.pretty" / f"{item}.kicad_mod").resolve()
    if root not in path.parents or not path.is_file():
        return None
    try:
        tree = parse_kicad_sexp(path.read_text(encoding="utf-8"))
    except (KicadDiffError, OSError):
        return None
    points: list[tuple[float, float]] = []
    for item_node in tree:
        if isinstance(item_node, list) and item_node and item_node[0] in {"fp_line", "fp_rect", "fp_circle", "fp_poly", "fp_arc"} and _layer_of(item_node) == "F.CrtYd":
            points += _points_of(item_node)
    box = _bbox(points)
    if box is None:
        return None
    return (round(box[2] - box[0], 3), round(box[3] - box[1], 3))


def footprint_size(name: str) -> dict[str, Any] | None:
    """The courtyard of the KiCad footprint named, which may not be your exact package."""

    size = _footprint_size(name)
    if size is None:
        return None
    return {"width_mm": size[0], "length_mm": size[1], "source": f"courtyard of the KiCad footprint {name}, which may not be your exact package"}
