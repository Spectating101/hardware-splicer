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
import json
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
MAX_VOLTAGE_GATES = 6
MAX_ISOLATION_RAILS = 3
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
# Exact internal / bypass names are not a rail to drive (TI DRV8833 VINT). VREGIN is a regulator input
# (Silicon Labs CP2102N §2.1) and must not be dropped by a VREG prefix. SENSE / VREF stay prefix exclusions
# (ST L298 SENSE; TI PCA9306 VREF1/VREF2), so a part whose only supplies are VREF gets no gates by design.
_INTERNAL_EXACT = frozenset({"VINT", "VCAP", "VCAP1", "VCAP2", "VBYP", "VREG"})
_INTERNAL_PREFIX = ("SENSE", "VREF")
_NOT_A_SUPPLY = re.compile(r"^(EP|EPAD|PAD|TAB|SHIELD|SHLD|NC|DNC|N/C|~)\d*$", re.IGNORECASE)
_PIN_ONE_PACKAGES = re.compile(r"^(Package_DIP|Package_SO|Package_QFP|Package_DFN_QFN):", re.IGNORECASE)
_TO220 = re.compile(r"TO-?220", re.IGNORECASE)
_SOT23 = re.compile(r"SOT-?23", re.IGNORECASE)
_BGA = re.compile(r"^Package_BGA:", re.IGNORECASE)
_RF_MODULE = re.compile(r"^RF_Module:", re.IGNORECASE)
_NUMBERED_RAIL = re.compile(r"^([A-Z]+)(\d+)$")
_BRACES = re.compile(r"[_\\{}]")
_BALL_GRID = re.compile(r"BGA|DSBGA|WLCSP", re.IGNORECASE)
_BALL_PIN = re.compile(r"^[A-Z]+\d+$", re.IGNORECASE)
_SOT23_56 = re.compile(r"SOT-?23-?[56]\b", re.IGNORECASE)
_SOT23_3 = re.compile(r"(?:SOT-?23(?:-?3)?\b|TO-?236)", re.IGNORECASE)
_POINTER_SUPPLY = frozenset({"VDDA", "VREF+", "VREF-", "VDDIO", "VCCIO", "AVDD", "AVCC"})
_CHARGER_PINS = frozenset({"PROG", "STAT", "CHRG", "BAT"})
_GENERAL_PRACTICE = " General practice, not from the datasheet."
CAUTIONS_PATH = Path(__file__).resolve().parent / "data" / "part_cautions.json"
_ENTRY_KEYS = frozenset({"names", "cautions"})
_CAUTION_KEYS = frozenset({"text", "basis", "quote", "source"})
_SOURCE_KEYS = frozenset({"label", "url", "as_of"})
_BASIS = frozenset({"datasheet", "general practice"})


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
        _caution_table.cache_clear()


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or has_hidden_characters(value):
        raise RuntimeError(f"{label} must be plain text")
    if "\n" in value or "\r" in value:
        raise RuntimeError(f"{label} may not contain a line break")
    return value


def _validate_source(source: Any, label: str, *, required: bool) -> dict[str, str] | None:
    if source is None:
        if required:
            raise RuntimeError(f"{label} needs a source")
        return None
    if not isinstance(source, dict) or set(source) - _SOURCE_KEYS:
        raise RuntimeError(f"{label} source may only have label, url and as_of")
    for field in ("label", "url", "as_of") if required else [key for key in ("label", "url", "as_of") if key in source]:
        if field not in source:
            raise RuntimeError(f"{label} source needs {field}")
        _require_text(source[field], f"{label} source {field}")
    if required:
        if not str(source["url"]).startswith(("http://", "https://")):
            raise RuntimeError(f"{label} source url must be a web link")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(source["as_of"])):
            raise RuntimeError(f"{label} source as_of must be a YYYY-MM-DD date")
    return {key: str(source[key]) for key in ("label", "url", "as_of") if key in source}


def _validate_caution(caution: Any, label: str) -> dict[str, Any]:
    if not isinstance(caution, dict) or set(caution) - _CAUTION_KEYS:
        raise RuntimeError(f"{label} may only have text, basis, quote and source")
    text = _require_text(caution.get("text"), f"{label} text")
    basis = caution.get("basis")
    if basis not in _BASIS:
        raise RuntimeError(f"{label} basis must be datasheet or general practice")
    quote = caution.get("quote")
    source = caution.get("source")
    if basis == "datasheet":
        quote = _require_text(quote, f"{label} quote")
        source = _validate_source(source, label, required=True)
    else:
        if quote is not None:
            quote = _require_text(quote, f"{label} quote")
        source = _validate_source(source, label, required=False)
    row: dict[str, Any] = {"text": text, "basis": basis}
    if quote is not None:
        row["quote"] = quote
    if source is not None:
        row["source"] = source
    return row


@lru_cache(maxsize=8)
def _caution_table(path: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"part caution table could not be read: {exc}") from exc
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise RuntimeError("part caution table must have an entries list")
    out: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        label = f"part caution entry {index}"
        if not isinstance(entry, dict) or set(entry) != _ENTRY_KEYS:
            raise RuntimeError(f"{label} must have exactly names and cautions")
        names = entry.get("names")
        if not isinstance(names, list) or not names or not all(isinstance(item, str) and item.strip() for item in names):
            raise RuntimeError(f"{label} names must be a non-empty list of text")
        compiled: list[re.Pattern[str]] = []
        for pattern in names:
            try:
                compiled.append(re.compile(pattern, re.IGNORECASE))
            except re.error as exc:
                raise RuntimeError(f"{label} has a bad name pattern {pattern!r}: {exc}") from exc
        cautions = entry.get("cautions")
        if not isinstance(cautions, list) or not cautions:
            raise RuntimeError(f"{label} needs a cautions list")
        rows = [_validate_caution(item, f"{label} caution {i}") for i, item in enumerate(cautions)]
        out.append({"names": list(names), "patterns": compiled, "cautions": rows})
    return out


def load_part_cautions(path: Path | None = None) -> list[dict[str, Any]]:
    """The curated caution table after the same kind of checks as the device module library."""

    table = _caution_table(str(path or CAUTIONS_PATH))
    return [{"names": row["names"], "cautions": row["cautions"]} for row in table]


def _render_caution(row: dict[str, Any]) -> str:
    text = str(row["text"]).rstrip()
    if row.get("basis") == "general practice":
        return text if text.endswith(_GENERAL_PRACTICE.strip()) else f"{text}{_GENERAL_PRACTICE}"
    label = str((row.get("source") or {}).get("label") or "").strip()
    if not label or label in text:
        return text
    return f"{text} {label}."


def _curated_rows(name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in _caution_table(str(CAUTIONS_PATH)):
        if any(pattern.search(name) for pattern in entry["patterns"]):
            rows.extend(entry["cautions"])
    return rows


def _is_ball_grid(footprint: str | None, pins: list[dict[str, str]] | None) -> bool:
    if footprint and _BALL_GRID.search(footprint):
        return True
    return bool(pins) and any(_BALL_PIN.fullmatch(str(pin.get("number") or "")) for pin in pins or [])


def _sot23_leads(footprint: str | None) -> int | None:
    if not footprint:
        return None
    if _SOT23_56.search(footprint):
        return 6 if re.search(r"6", _SOT23_56.search(footprint).group(0)) else 5
    if _SOT23_3.search(footprint):
        return 3
    return None


_SOT23_3_TEXT = (
    "Top view, two-lead side below: pin 1 is left, pin 2 is right, and pin 3 is the single lead "
    "on the other side. That order is the usual SOT-23 drawing (Diodes Incorporated 2N7002 "
    "datasheet DS11303; Nexperia 2N7002 datasheet as examples); confirm against the datasheet "
    "drawing for the exact part."
)
_SOT23_56_TEXT = "Pin numbers go round the package, not across it. Use the package drawing for the part in hand."
_BALL_TEXT = (
    "Balls under the package cannot be probed, and the contacts are not counted like DIP pins. "
    "Measure only at accessible pads or test points."
)
_CELL_TEXT = "Do these checks with no cell connected. A lithium cell can start a fire if charged wrongly."
_POINTER_TEXT = (
    "Pins such as VDDA, VBAT, VREF+ and VDDIO are separate supply pins. Whether they may differ "
    "from the main supply is a datasheet question; read the power-supply section before measuring them."
)


def part_cautions(
    name: str,
    *,
    tier: str = "exact",
    library: str | None = None,
    footprint: str | None = None,
    pins: list[dict[str, str]] | None = None,
) -> list[str]:
    """Sourced and general-practice cautions for a named library symbol. A family match gets none."""

    if tier not in {"exact", "variant"}:
        return []
    if pins is None and library:
        try:
            pins = _all_pins(library, name)
        except PartLookupError:
            pins = []
    names = {_pin_token(pin["name"]) for pin in (pins or [])}
    curated = _curated_rows(name)
    out = [_render_caution(row) for row in curated]
    if _is_ball_grid(footprint, pins):
        out.append(_render_caution({"text": _BALL_TEXT, "basis": "general practice"}))
    leads = _sot23_leads(footprint)
    if leads == 3:
        out.append(_SOT23_3_TEXT)
    elif leads in {5, 6}:
        out.append(_render_caution({"text": _SOT23_56_TEXT, "basis": "general practice"}))
    charger_named = bool(curated) and any("no cell connected" in row["text"].lower() for row in curated)
    if not charger_named and (
        (library or "") == "Battery_Management" or ("BAT" in names and names & {"PROG", "STAT", "CHRG"})
    ):
        out.append(_render_caution({"text": _CELL_TEXT, "basis": "general practice"}))
    pointer = names & _POINTER_SUPPLY
    if "VBAT" in names and not (names & _CHARGER_PINS):
        pointer.add("VBAT")
    if pointer:
        out.append(_render_caution({"text": _POINTER_TEXT, "basis": "general practice"}))
    return out


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
        "variant": "the library has a part whose name is this name plus a code; the code may be a package, a grade or a different chip, so check the datasheet",
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
    named = next((match for match in result["matches"] if match["tier"] in {"exact", "variant"}), None)
    result["cautions"] = (
        part_cautions(named["name"], tier=named["tier"], library=named["library"], footprint=named.get("footprint"))
        if named else []
    )
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
    if token in _INTERNAL_EXACT:
        return True
    return any(token == stem or token.startswith(stem) for stem in _INTERNAL_PREFIX)


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
    if _is_ball_grid(footprint, None):
        return (
            " Balls are named by row and column, not counted around the edge. "
            "Balls under the package cannot be probed; measure only at accessible pads or test points."
        )
    if _PIN_ONE_PACKAGES.match(footprint):
        return (
            " The dot or notch marks the pin-1 end; pin 1 is the first leg counter-clockwise from it seen from the top "
            "for standard-bend leads; if you are looking at the underside of a board, the order appears reversed."
        )
    leads = _sot23_leads(footprint)
    if leads == 3:
        return (
            " Top view, two-lead side below: pin 1 is left, pin 2 is right, and pin 3 is the single lead "
            "on the other side. Confirm against the datasheet drawing for this part."
        )
    if leads in {5, 6}:
        return (
            " Pin numbers go round the package, not across it; take them from the "
            "datasheet's package drawing."
        )
    if _TO220.search(footprint) or footprint.upper().startswith("PACKAGE_TO_SOT"):
        return (
            " The lead order depends on the part and must be taken from the datasheet's package drawing, "
            "not from the package name (7805 vs LM317)."
        )
    if _RF_MODULE.match(footprint):
        # Espressif ESP32-WROOM-32 datasheet §2: numbered perimeter contacts from the pin-1 mark, not a BGA ball array.
        return (
            " Modules have numbered contacts around the edge from the pin-1 mark in the datasheet drawing."
        )
    return ""


def _isolation_domain(token: str) -> str | None:
    """GND1 / VSS2 / GNDA — not PGND, which is a motor return rather than an isolation domain."""

    for stem in ("GND", "VSS"):
        if token.startswith(stem) and len(token) > len(stem):
            suffix = token[len(stem):]
            if re.fullmatch(r"[0-9A-Z]", suffix):
                return suffix
    return None


def _supply_domain(token: str, domains: set[str]) -> str | None:
    """VCC1/GND1, VDDA/VSSA — not VBAT (the last letter is part of the name) or VDD3P3."""

    for suffix in sorted(domains, key=len, reverse=True):
        if token.endswith(suffix) and token[: -len(suffix)].isalpha():
            return suffix
    return None


def _looks_like_domain_supply(token: str) -> bool:
    return bool(re.fullmatch(r"(?:VCC|VDD|VIN|VM)(?:\d|[A-Z])$", token))


def _collect_supplies_and_grounds(pins: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[tuple[int, dict[str, str]]]]:
    has_plain_gnd = any(_pin_token(p["name"]) == "GND" for p in pins)
    grounds: list[tuple[int, dict[str, str]]] = []
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
    return supply, grounds


def _numbered_suffix(pin: dict[str, str]) -> int:
    found = _NUMBERED_RAIL.fullmatch(_pin_token(pin["name"]))
    return int(found.group(2)) if found else 0


def _collapse_numbered_rails(supply: list[dict[str, str]], domains: set[str]) -> list[dict[str, str]]:
    """VM1/VM2/VM3 are one motor rail; VCC1/VCC2 stay separate when GND1/GND2 exist."""

    kept: list[dict[str, str]] = []
    numbered: dict[str, list[dict[str, str]]] = {}
    for pin in supply:
        token = _pin_token(pin["name"])
        found = _NUMBERED_RAIL.fullmatch(token)
        if found and found.group(2) not in domains:
            numbered.setdefault(found.group(1), []).append(pin)
        else:
            kept.append(pin)
    for group in numbered.values():
        kept.append(min(group, key=_numbered_suffix))
    kept.sort(key=lambda pin: (_supply_rank(_pin_token(pin["name"])), len(pin["number"]), pin["number"]))
    return kept


def _rail_pairs(pins: list[dict[str, str]]) -> list[tuple[dict[str, str], dict[str, str]]]:
    """Each supply paired with the ground of its own domain. No pair when a domain cannot be matched."""

    supply, grounds = _collect_supplies_and_grounds(pins)
    domains: dict[str, dict[str, str]] = {}
    for _rank, pin in grounds:
        suffix = _isolation_domain(_pin_token(pin["name"]))
        if suffix and suffix not in domains:
            domains[suffix] = pin
    undomained = next((pin for _rank, pin in grounds if _isolation_domain(_pin_token(pin["name"])) is None), None)
    supply = _collapse_numbered_rails(supply, set(domains))
    if grounds:
        pairs: list[tuple[dict[str, str], dict[str, str]]] = []
        for pin in supply:
            token = _pin_token(pin["name"])
            marker = _supply_domain(token, set(domains))
            if marker:
                pairs.append((pin, domains[marker]))
            elif domains and _looks_like_domain_supply(token):
                continue
            elif undomained is not None:
                pairs.append((pin, undomained))
        return pairs[:MAX_VOLTAGE_GATES]
    neg = next((pin for pin in supply if _pin_token(pin["name"]) in _NEG_REF), None)
    pos = [pin for pin in supply if _pin_token(pin["name"]) not in _NEG_REF]
    if neg and pos:
        return [(pin, neg) for pin in pos][:MAX_VOLTAGE_GATES]
    outs = [
        pin for pin in pins
        if pin["type"] == "power_out"
        and not _is_internal(_pin_token(pin["name"]))
        and not _NOT_A_SUPPLY.match(pin["name"])
    ]
    if supply and outs:
        return [(pin, outs[0]) for pin in supply][:MAX_VOLTAGE_GATES]
    return []


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
        # TI DRV8833 datasheet, functional block diagram and typical application: output-stage diodes and attached windings sit across the outputs.
        bits.append(
            "Windings attached to the outputs, and the output stage's own diodes, are in parallel with what you measure on a connected driver."
        )
    if split and kind == "isolation":
        # TI TXB0108 datasheet §§1 and 5.20–5.21: the constraint is VCCA <= VCCB; equal rails are allowed, so they are not forbidden to join.
        bits.append("The two rails are separate pins to check each on its own.")
    if kind == "voltage" and any(_pin_token(pin["name"]) in {"OUT", "VO"} and pin["type"] == "power_out" for pin in pins):
        bits.append("A reading on the input does not show what the output is doing.")
    if kind == "voltage" and footprint and _TO220.search(footprint):
        bits.append("The metal tab is a terminal: its function is in the datasheet, not implied by the package name.")
    if kind == "voltage" and footprint and "DFN_QFN" in footprint.upper():
        bits.append("If the datasheet puts the ground on the exposed pad, that pad is the return, not a supply.")
    if kind == "voltage":
        # Fluke DC-voltage procedure: measurement-lead polarity may be reversed; reversing the supply on a chip can destroy it.
        bits.append("Connect a supply the right way round: reversing the supply on a chip can destroy it.")
    return (" " + " ".join(bits)) if bits else ""


def power_gates(library: str, name: str, footprint: str | None) -> list[dict[str, Any]]:
    """What to measure on a library symbol: power-off diode and ohms first, then a current-limited bench supply.

    They say what to measure and where, never what the reading should be: the range is the datasheet's to give.
    Voltage uses a bench supply with a current limit, not the board and not an unisolated mains connection.
    """

    try:
        pins = _all_pins(library, name)
    except PartLookupError:
        return []
    if len(pins) > MAX_PINS_FOR_GATES:
        return []
    pairs = _rail_pairs(pins)
    if not pairs:
        return []
    supply_pins = [pin for pin, _ref in pairs]
    split = _split_rails(supply_pins)
    where = _orientation(footprint)
    sourced = part_cautions(name, tier="exact", library=library, footprint=footprint, pins=pins)
    sourced_text = (" " + " ".join(sourced)) if sourced else ""
    # Fluke 87V MAX: "disconnect power and discharge all high-voltage capacitors before you measure resistance, continuity, capacitance, or a diode junction."
    # Fluke 87V MAX: "the resistance reading represents the total resistance of all paths between the probes."
    # TI SCDA039: "there are ESD diodes tied between the input and the positive supply rail (VDD/VCC) and an ESD diode tied from the input to the negative supply rail or ground (VSS/GND)."
    gates: list[dict[str, Any]] = []
    kind_pairs = {
        "diode": pairs,
        "isolation": pairs[:MAX_ISOLATION_RAILS],
        "voltage": pairs[:MAX_VOLTAGE_GATES],
    }
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
        for pin, reference in kind_pairs[kind]:
            extra = _notes(pins, pin, kind=kind, footprint=footprint, split=split) + sourced_text
            pair = f"pin {pin['number']} ({pin['name']})"
            g_from = f"pin {reference['number']} ({reference['name']})"
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
                # General practice: a bench supply takes energy from the mains but is isolated; do not use the board or an unisolated mains connection.
                instruction = (
                    f"Only after writing down the power-off readings, and only from a bench supply with a current limit set to the "
                    f"supply voltage in the datasheet for this pin pair (not the board's own supply and not anything connected to "
                    f"the mains without isolation), "
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


_MISSING_PACKAGE_NOTE = (
    "the library does not say which package these pin numbers belong to and they must be taken from the "
    "datasheet drawing of the person's package (names still shown)"
)


def resolve_lookup_gates(matches: list[dict[str, Any]], user_footprint: str | None) -> dict[str, Any]:
    """The named match a plan would pick, its gates, and a note when pin numbers are not known to be this package."""

    best = pick_named_match(matches, user_footprint)
    package_note: str | None = None
    gates: list[dict[str, Any]] = []
    if best and best.get("footprint") and user_footprint and not footprint_fits_user(best.get("footprint"), user_footprint):
        family = footprint_family(best["footprint"]) or best["footprint"]
        package_note = (
            f"the library's closest entry is {best['name']} in package {family}, so its pin numbers would not be yours"
        )
    elif best and not best.get("footprint") and user_footprint:
        package_note = _MISSING_PACKAGE_NOTE
        gates = power_gates(best["library"], best["name"], best.get("footprint"))
        for gate in gates:
            gate["instruction"] = f"{gate['instruction']} {package_note[0].upper()}{package_note[1:]}"
    elif best:
        gates = power_gates(best["library"], best["name"], best.get("footprint"))
    cautions = (
        part_cautions(best["name"], tier=best["tier"], library=best["library"], footprint=best.get("footprint") or user_footprint)
        if best else []
    )
    return {
        "best": best,
        "gates": gates,
        "gates_from": best["name"] if best else None,
        "package_note": package_note,
        "cautions": cautions,
    }


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
