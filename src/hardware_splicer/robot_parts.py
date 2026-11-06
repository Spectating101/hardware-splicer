"""A library of bought robot parts in which every fact names its source.

Each entry is one purchasable part: where it is listed, which documents describe it, and the facts a robot design needs
from it (voltages, speeds, currents, sizes, pinouts), each with a unit, a basis and a source. A published fact also
carries a verbatim quote from that source, so a person or ``verify_quotes`` can check it. A figure that is typical for the
class rather than published says so and asks for a bench measurement. A fact nobody publishes is listed as unconfirmed
with a reason; it is never filled in.

An entry records sources, not proof: every part stays ``SOURCED_NOT_MEASURED`` until a person measures it, and nothing
here can mark a part verified, approved or fit for a build.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

LIBRARY_PATH = Path(__file__).resolve().parent / "data" / "robot_parts.json"
SCHEMA_VERSION = "hardware_splicer.robot_parts.v1"
STATUS = "SOURCED_NOT_MEASURED"
MARKETPLACES = {"ruten", "maker_shop", "official_store", "cross_border"}
BASES = {"published", "typical"}
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

REQUIRED_FACTS: dict[str, dict[str, str]] = {
    "drive_motor": {"rated_voltage": "V", "output_free_speed_rpm": "rpm", "rated_current": "A", "stall_current": "A",
                    "stall_torque": "N·m", "gear_ratio": "ratio", "encoder_cpr": "count/rev_motor",
                    "encoder_supply_voltage": "V", "shaft_diameter": "mm", "body_dimensions": "mm", "mass": "g",
                    "connector": "text"},
    "wheel": {"outer_diameter": "mm", "width": "mm", "bore": "mm", "mass": "g"},
    "caster": {"height": "mm", "mount": "text", "mass": "g"},
    "lidar": {"supply_voltage": "V", "supply_current": "A", "interface": "text", "baud_rate": "baud", "protocol": "text",
              "scan_rate": "Hz", "range_max": "m", "range_min": "m", "motor_control": "text", "pinout": "text",
              "body_dimensions": "mm", "mass": "g"},
    "battery_pack": {"nominal_voltage": "V", "full_voltage": "V", "capacity": "mAh", "max_discharge_current": "A",
                     "bms": "text", "connector": "text", "body_dimensions": "mm", "mass": "g"},
    "dc_dc_converter": {"input_voltage_range": "V", "output_voltage": "V", "max_output_current": "A",
                        "body_dimensions": "mm"},
    "compute_board": {"soc": "text", "ram": "GB", "supply_voltage": "V", "typical_current": "A", "peak_current": "A",
                      "ros2_support": "text", "body_dimensions": "mm", "mass": "g"},
    "imu": {"sensor": "text", "interface": "text", "supply_voltage": "V", "body_dimensions": "mm"},
}
PART_KINDS = frozenset(REQUIRED_FACTS)


class RobotPartError(ValueError):
    """The library holds an entry that breaks its rules."""


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _fact_sources(fact: dict) -> list[Any]:
    if "alternatives" in fact:
        return [alt.get("source") for alt in fact.get("alternatives") or [] if isinstance(alt, dict)]
    return [fact.get("source")]


def _check_fact(name: str, fact: Any, unit: str | None, declared: set[str], quoted: set[tuple[str, str]]) -> list[str]:
    if not isinstance(fact, dict):
        return [f"fact {name} must be an object"]
    out = []
    if unit is not None and fact.get("unit") != unit:
        out.append(f"fact {name} has unit {fact.get('unit')!r}, expected {unit!r}")
    elif not _text(fact.get("unit")):
        out.append(f"fact {name} needs a unit")
    basis = fact.get("basis")
    if basis not in BASES:
        out.append(f"fact {name} has basis {basis!r}; only {sorted(BASES)} (nothing has been measured)")
    if basis == "typical" and "measure" not in str(fact.get("note", "")).lower():
        out.append(f"fact {name} is typical, so its note must ask for a bench measurement (say 'measure')")
    if "alternatives" in fact:
        alts = fact.get("alternatives")
        if fact.get("confidence") != "conflicting":
            out.append(f"fact {name} lists alternatives, so its confidence must be 'conflicting'")
        if not isinstance(alts, list) or len(alts) < 2 or not all(isinstance(a, dict) and "value" in a for a in alts):
            out.append(f"fact {name} is conflicting and needs at least two alternatives, each with a value and a source")
    elif "value" not in fact:
        out.append(f"fact {name} has no value")
    elif fact.get("confidence") == "conflicting":
        out.append(f"fact {name} is marked conflicting but gives one value; list the alternatives")
    for source in _fact_sources(fact):
        if source not in declared:
            out.append(f"fact {name} cites source {source!r}, which is neither a declared source nor the listing")
        elif basis == "published" and (name, source) not in quoted:
            out.append(f"fact {name} is published but has no quote from {source}")
    return out


def validate_part(entry: dict) -> list[str]:
    """Every rule the entry breaks, as sentences; empty when it is valid."""
    if not isinstance(entry, dict):
        return ["entry must be an object"]
    out: list[str] = []
    if not isinstance(entry.get("id"), str) or not _ID.match(entry["id"]):
        out.append(f"id {entry.get('id')!r} must be lowercase letters, digits and hyphens")
    kind = entry.get("kind")
    if kind not in PART_KINDS:
        out.append(f"kind {kind!r} is not one of {sorted(PART_KINDS)}")
    if not _text(entry.get("name")):
        out.append("name is empty")
    if entry.get("status") != STATUS:
        out.append(f"status must be {STATUS}; an entry cannot claim a part is verified or approved")

    listing = entry.get("listing") if isinstance(entry.get("listing"), dict) else {}
    if not str(listing.get("url", "")).startswith("https://"):
        out.append("listing needs an https url")
    if listing.get("marketplace") not in MARKETPLACES:
        out.append(f"listing marketplace {listing.get('marketplace')!r} is not one of {sorted(MARKETPLACES)}")
    if not _text(listing.get("variant")):
        out.append("listing must name the variant chosen (a listing's lowest price is often a different variant)")
    price = listing.get("price_twd")
    if not isinstance(price, (int, float)) or price <= 0:
        out.append("listing needs a positive price_twd")
    if not isinstance(listing.get("captured"), str) or not _DATE.match(listing["captured"]):
        out.append("listing needs a captured date (YYYY-MM-DD)")

    sources = entry.get("sources")
    if not isinstance(sources, list) or not sources:
        out.append("sources must be a non-empty list")
        sources = []
    for s in sources:
        if not (isinstance(s, dict) and _text(s.get("url")) and _text(s.get("label")) and _text(s.get("as_of"))):
            out.append(f"source {s!r} needs a url, a label and an as_of date")
    declared = {s["url"] for s in sources if isinstance(s, dict) and _text(s.get("url"))}
    if _text(listing.get("url")):
        declared.add(listing["url"])

    facts = entry.get("facts") if isinstance(entry.get("facts"), dict) else {}
    quotes = entry.get("quotes") if isinstance(entry.get("quotes"), list) else []
    quoted = set()
    for q in quotes:
        if not (isinstance(q, dict) and _text(q.get("claim")) and _text(q.get("quote")) and _text(q.get("source"))):
            out.append(f"quote {q!r} needs a claim, a quote and a source")
            continue
        if q["claim"] not in facts:
            out.append(f"quote claim {q['claim']!r} names no fact")
        if q["source"] not in declared:
            out.append(f"quote for {q['claim']} cites {q['source']}, which is not a declared source")
        quoted.add((q["claim"], q["source"]))

    required = REQUIRED_FACTS.get(kind, {})
    unconfirmed = {u.get("fact") for u in entry.get("unconfirmed") or [] if isinstance(u, dict) and _text(u.get("reason"))}
    for name, fact in facts.items():
        out.extend(_check_fact(name, fact, required.get(name), declared, quoted))
    for name in required:
        if name not in facts and name not in unconfirmed:
            out.append(f"required fact {name} is missing; source it or list it as unconfirmed with a reason")
    return out


def load_parts(path: Path = LIBRARY_PATH) -> list[dict]:
    """The library's parts; raises ``RobotPartError`` naming every problem in every entry."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION:
        raise RobotPartError(f"{path}: schema_version must be {SCHEMA_VERSION}")
    parts = data.get("parts")
    if not isinstance(parts, list):
        raise RobotPartError(f"{path}: parts must be a list")
    problems = []
    ids = [p.get("id") for p in parts if isinstance(p, dict)]
    for dup in sorted({i for i in ids if ids.count(i) > 1}, key=str):
        problems.append(f"duplicate id {dup}")
    for part in parts:
        problems.extend(f"{part.get('id') if isinstance(part, dict) else part!r}: {p}" for p in validate_part(part))
    if problems:
        raise RobotPartError("; ".join(problems))
    return parts
