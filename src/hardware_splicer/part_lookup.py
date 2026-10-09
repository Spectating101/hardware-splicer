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
_GROUND_RANK = ("GND", "VSS", "DGND", "AGND", "GNDD", "GNDA", "VSSA", "PGND")
_GROUND_NAME = re.compile(r"^(" + "|".join(_GROUND_RANK) + r")$", re.IGNORECASE)
# Pins that carry no supply: the exposed pad, a tab or shield, and pins marked not connected.
_MAIN_SUPPLY = ("VDD", "VCC", "VDDIO", "VCCIO", "VIN", "VI", "IN", "V+", "VS", "VSUP", "AVDD", "AVCC", "VDDA")   # measured first; a backup or reference pin is not the main supply
_NOT_A_SUPPLY = re.compile(r"^(EP|EPAD|PAD|TAB|SHIELD|SHLD|NC|DNC|N/C|~)\d*$", re.IGNORECASE)
_PIN_ONE_PACKAGES = re.compile(r"^(Package_DIP|Package_SO|Package_QFP|Package_DFN_QFN):")


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

    def is_variant(a: str, b: str) -> bool:
        """a is the start of b (or b of a) and what is left over is a short package or grade code, not another function."""

        short, long = (a, b) if len(a) <= len(b) else (b, a)
        return len(short) >= 4 and long.startswith(short) and bool(_SUFFIX.match(long[len(short):]))

    if q in index.by_name:
        take([q], "exact")
    prefixed = _prefix_rows(index, q) if len(q) >= 4 else []
    take(sorted((n for n in prefixed if n != q and is_variant(q, n)), key=lambda n: (len(n), n)), "variant")
    # A library name that is the start of the marking (the marking carries a package or grade suffix the library leaves off).
    for k in range(len(q) - 1, 3, -1):
        if q[:k] in index.by_name and is_variant(q, q[:k]):
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
        "variant": "the library has a part with this name plus or minus a short package or grade code: likely the same chip with a different package or grade",
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


def power_gates(library: str, name: str, footprint: str | None) -> list[dict[str, Any]]:
    """Things to measure before trusting a chip, read from its pin names and types: supply against ground, and whether they are shorted.

    They say what to measure and where, never what the reading should be: the range is the datasheet's to give.
    """

    try:
        pins = _all_pins(library, name)
    except PartLookupError:
        return []
    if len(pins) > MAX_PINS_FOR_GATES:
        return []
    ground = sorted((p for p in pins if _GROUND_NAME.match(p["name"])), key=lambda p: (_GROUND_RANK.index(p["name"].upper()), len(p["number"]), p["number"]))
    supply: list[dict[str, str]] = []
    for p in pins:
        if p["type"] == "power_in" and not _GROUND_NAME.match(p["name"]) and not _NOT_A_SUPPLY.match(p["name"]) and all(q["name"] != p["name"] for q in supply):
            supply.append(p)          # one measurement per supply name: a part with four VDD pins is measured at one
    if not ground or not supply:
        return []
    supply.sort(key=lambda p: _MAIN_SUPPLY.index(p["name"].upper()) if p["name"].upper() in _MAIN_SUPPLY else len(_MAIN_SUPPLY))
    g = ground[0]
    where = " Pin 1 is the corner with the dot or notch; count anticlockwise from it, seen from above." if footprint and _PIN_ONE_PACKAGES.match(footprint) else ""
    gates: list[dict[str, Any]] = []
    for s in supply[:3]:
        gates.append(
            {
                "key": f"{library}:{name}|voltage|pin {s['number']} ({s['name']})|pin {g['number']} ({g['name']})",
                "kind": "voltage",
                "from": f"pin {s['number']} ({s['name']})",
                "to": f"pin {g['number']} ({g['name']})",
                "instruction": f"With the board powered the way it was originally, measure between pin {s['number']} ({s['name']}) and pin {g['number']} ({g['name']}), and write the reading down.{where}",
                "expect": "write down what you see, then compare it with the datasheet's supply range before you connect anything of yours",
            }
        )
    gates.append(
        {
            "key": f"{library}:{name}|isolation|pin {supply[0]['number']} ({supply[0]['name']})|pin {g['number']} ({g['name']})",
            "kind": "isolation",
            "from": f"pin {supply[0]['number']} ({supply[0]['name']})",
            "to": f"pin {g['number']} ({g['name']})",
            "instruction": f"With the power off, check that pin {supply[0]['number']} ({supply[0]['name']}) and pin {g['number']} ({g['name']}) are not shorted together.{where}",
            "expect": "write down what you see: a reading near zero ohms means something is shorted, which needs understanding before you apply power",
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
    """The courtyard of a KiCad footprint, in mm: a little larger than the part itself, and exact for that footprint."""

    size = _footprint_size(name)
    if size is None:
        return None
    return {"width_mm": size[0], "length_mm": size[1], "source": f"KiCad footprint library {name}, courtyard"}
