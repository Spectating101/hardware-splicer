"""A take-apart plan for a board: which parts are worth removing, in what order, and what to do before trusting any of them.

It is the build sequence run the other way, over the same retained board. It is a view of retained bytes and a rule-of-thumb
assessment. It carries no engineering authority and measures nothing: a part's condition is unknown until it is tested, a
verdict is advice about effort and reuse, and nothing here approves using a salvaged part in a device.

Two limits are stated, not hidden. It needs the board file: a physical board with no file cannot be planned from. And it names a
part only as far as the file does: a part with no part number is "identify first", never guessed.
"""

from __future__ import annotations

import re
from typing import Any

from . import part_lookup
from .assembly_plan import AssemblyPlanError, build_assembly_plan

SALVAGE_PLAN_SCHEMA = "hardware_splicer.salvage_plan.v1"

AUTHORITY_STATEMENT = (
    "This is a rule-of-thumb plan for taking a board apart, read from its file. It measures nothing: the condition of every part "
    "is unknown until you test it, a verdict is advice about effort and reuse, and nothing here approves putting a salvaged part "
    "into a device."
)
BASIS = "rule of thumb on the part's kind, package and mounting, plus what the board file says it is"
TYPED_BASIS = "rule of thumb on the part's kind and package, plus the marking you read off it"

VERDICTS = ("keep", "test_first", "identify", "optional", "skip")
VERDICT_TEXT = {
    "keep": "Worth taking",
    "test_first": "Take it, test first",
    "identify": "Read the marking to decide",
    "optional": "Cheap to buy new",
    "skip": "Leave it",
}

TYPED_AUTHORITY = (
    "This is a rule-of-thumb plan for taking a board apart, from what you described. It measures nothing: every size, place and marking is what "
    "you told it, the condition of every part is unknown until you test it, a verdict is advice about effort and reuse, and nothing here "
    "approves putting a salvaged part into a device."
)

GENERAL_SAFETY = (
    "Unplug the board and take out any battery before you start. Large capacitors can hold a charge: discharge them through a "
    "resistor, not a screwdriver. Work with ventilation and eye protection, and wash your hands afterwards: older boards can "
    "contain leaded solder. Use an anti-static strap if you can."
)

_SPECIAL_CONNECTOR = re.compile(r"USB|JST|Molex|Micro|Mini|RJ45|Barrel|Audio|FPC|FFC|Terminal|Screw|SMA|HDMI|SD_|Card", re.IGNORECASE)
_PLAIN_HEADER = re.compile(r"PinHeader|PinSocket|Pin_Header", re.IGNORECASE)
# Anchored to whole parts of a name, so a word that merely contains one ("Electronic", "MOVEMENT", "OnePiece") does not match.
_ELECTROLYTIC = re.compile(r"(^|[:_])CP_|C_Elec|Electrolytic|(^|[:_])Elec_|Tantalum|TantalC|EDLC|Supercap", re.IGNORECASE)
_VOLTS = re.compile(r"(\d+(?:\.\d+)?)\s*V(?:AC|DC)?\b", re.IGNORECASE)
_MAINS_RATED_CAP = re.compile(r"\b[XY][12]\b", re.IGNORECASE)
_PITCH = r"(?<![\d.])(?:5\.0{1,2}|5\.08|7\.50?|7\.62|10\.16|11\.0{1,2})(?!\d)"
_WIDE_TERMINAL = re.compile(rf"(Terminal|Screw|MKDS|Phoenix).*{_PITCH}|{_PITCH}.*(Terminal|Screw|MKDS|Phoenix)", re.IGNORECASE)
_SOLDER_JUMPER = re.compile(r"SolderJumper|SolderBridge|Jumper:", re.IGNORECASE)
_MAINS_PART = re.compile(
    r"Varistor|(^|[:_])RV_|(^|[:_])MOV(_|\d|$)|(^|[:_])IEC(_|\d|$)|Mains|AC_Inlet|Fuse_?holder|Fuse_\d+x\d+|Cartridge|Transformer|Trafo|Common_?Mode|Relay",
    re.IGNORECASE,
)
_BATTERY_HOLDER = re.compile(r"Holder|Clip|Keystone", re.IGNORECASE)
_BATTERY_REF = re.compile(r"^(BT|BAT)\d", re.IGNORECASE)
_THROUGH_HOLE_IC = re.compile(r"DIP|THT|TO-220|TO-92|TO-247|Socket", re.IGNORECASE)
_FINE_PACKAGE = re.compile(r"QFN|DFN|LGA|BGA|QFP|WSON|USON|UDFN|WLCSP|CSP", re.IGNORECASE)
_MEDIUM_PACKAGE = re.compile(r"SOIC|SOP|SOT|TSSOP|MSOP|SSOP|TO-252|TO-263|SO-", re.IGNORECASE)
# A part number is one token: letters and digits, with hyphens, dots or plus signs, and no spaces or underscores. A label that describes
# a function ("FLASH_128M", "SPI_1x06") is not one, and neither is a bare number.
_PART_NUMBER = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+/-]{2,39}")
_BATTERY = re.compile(r"Battery|CR\d{4}|LiPo|Li-?ion|Lithium|18650|Coin|Pouch", re.IGNORECASE)
_SMALL_CHIP = re.compile(r"_(01005|0201|0402|0603)_|[RCLD]_(01005|0201|0402|0603)|LED_(01005|0201|0402|0603)", re.IGNORECASE)
_BIG_CHIP = re.compile(r"_(0805|1206|1210|2010|2512)_|[RCLD]_(0805|1206|1210|2010|2512)|LED_(0805|1206)", re.IGNORECASE)


MAX_LOOKUPS = 40


class SalvagePlanError(ValueError):
    """The bytes are not a board a take-apart plan can be made from."""


def _identified(part: dict[str, Any]) -> bool:
    identity = part.get("identity") or {}
    if identity.get("mpn"):
        return True
    typed = str(identity.get("typed") or "").strip()
    if typed:
        return bool(_PART_NUMBER.fullmatch(typed)) and sum(c.isdigit() for c in typed) >= 2 and any(c.isalpha() for c in typed)
    value = str(part.get("value") or "").strip()
    return bool(_PART_NUMBER.fullmatch(value)) and sum(c.isdigit() for c in value) >= 2 and any(c.isalpha() for c in value)


def _effort(part: dict[str, Any]) -> tuple[str, str]:
    name = part["footprint"]
    mounting = part.get("mounting")
    through = mounting == "through_hole" or (mounting is None and bool(_THROUGH_HOLE_IC.search(name)))
    if through:
        return "easy", "a soldering iron with solder wick or a desoldering pump"
    if _FINE_PACKAGE.search(name):
        return "hard", "hot air, flux and tweezers; the pads under it are easy to lift"
    if _MEDIUM_PACKAGE.search(name):
        return "medium", "hot air or an iron with plenty of flux, and tweezers"
    return "medium", "an iron or hot air, flux and tweezers"


def _high_voltage(part: dict[str, Any]) -> bool:
    is_capacitor = str(part.get("ref", "")).upper().startswith("C") or part.get("component") == "capacitor"
    if part.get("kind") != "passive" or not is_capacitor:
        return False
    value = str(part.get("value") or "")
    return bool(_MAINS_RATED_CAP.search(value)) or any(float(m.group(1)) >= 100 for m in _VOLTS.finditer(value))


def _lookup_reasons(part: dict[str, Any]) -> list[str]:
    found = part.get("lookup")
    if not found:
        return []
    if found["match"]:
        m = found["match"]
        text = f"KiCad's library has a part called \"{m['name']}\": {m['description'] or 'no description'}"
        return [text + ("" if found["tier"] == "exact" else " (a variant: the same chip with another package or grade, probably)")]
    if found["family"]:
        return [f"KiCad's library has parts from the same family ({', '.join(found['family'][:3])}) but not this one: use them to learn what kind of chip it probably is, no more"]
    return ["KiCad's library does not list it: search its datasheet by the marking"]


def _assess(part: dict[str, Any]) -> dict[str, Any]:
    """The verdict for one part, with the reasons for it. Never a statement about the part's condition."""

    kind, name = part["kind"], part["footprint"]
    effort, tool = _effort(part)
    reasons: list[str] = []
    hazards: list[str] = []
    verdict = "optional"

    if kind in {"testpoint", "mounting_hole"}:
        verdict = "skip"
        reasons.append("a test pad or a hole: there is nothing to take")
        effort, tool = "none", ""
    elif _SOLDER_JUMPER.search(name):
        verdict = "skip"
        reasons.append("a solder jumper is a bridge on the board itself: there is no part to take")
        effort, tool = "none", ""
    elif _BATTERY.search(name) or _BATTERY_REF.match(part["ref"]):
        hazards.append("take any battery out before heating anything, and never heat a lithium cell")
        if _BATTERY_HOLDER.search(name):
            verdict = "optional"
            reasons.append("a battery holder: take it if you need it; the cell is never part of this")
        else:
            verdict = "skip"
            reasons.append("a battery cell: take it out by hand before you start, never with heat, and do not reuse a swollen or damaged one")
            effort, tool = "none", ""
    elif _MAINS_PART.search(name):
        verdict = "optional"
        reasons.append("a part from mains wiring or a switching supply: it can wear out or have carried mains voltage in its original use")
        hazards.append("only reuse it if you know how to work safely with mains voltage; varistors and relays wear out, and transformers and filter parts can hold energy")
    elif _ELECTROLYTIC.search(name) or _high_voltage(part):
        verdict = "test_first"
        reasons.append("a polarised or high-voltage capacitor ages and can fail; its condition is unknown")
        hazards.append("may still hold a charge: discharge it through a resistor first")
        if _high_voltage(part):
            verdict = "skip"
            reasons.append("rated for 100 V or more: not worth the risk of a stored charge")
            hazards.append("a high-voltage capacitor can hold a dangerous charge for a long time")
            effort, tool = "none", ""
    elif kind == "connector" and _SPECIAL_CONNECTOR.search(name):
        verdict = "keep"
        reasons.append("a specialised connector: harder to find and cheap to keep")
        if _WIDE_TERMINAL.search(name):
            hazards.append("a terminal block this wide often carried mains voltage: check where it was connected before you trust or reuse it")
    elif kind == "connector" and _PLAIN_HEADER.search(name):
        verdict = "optional"
        reasons.append("a plain 2.54 mm header is cheap to buy new")
    elif kind == "connector":
        verdict = "keep"
        reasons.append("a connector that is not a plain header")
    elif kind == "ic":
        if _identified(part):
            verdict = "keep"
            identity = part.get("identity") or {}
            if identity.get("typed"):
                reasons.append(f"you read its marking as \"{identity['typed']}\", which looks like a part number")
                reasons.append("a marking can be a house code, worn, or fake: check it against a datasheet before trusting it")
            else:
                named = identity.get("mpn") or part.get("value")
                who = f" ({identity['manufacturer']})" if identity.get("manufacturer") else ""
                reasons.append(f"the board file names it: \"{named}\"{who}, so it can be identified without guessing")
                reasons.append("read the marking on the chip itself before trusting that")
            reasons.extend(_lookup_reasons(part))
        else:
            verdict = "identify"
            reasons.append("you have not given a marking that looks like a part number: read it off the chip, then decide" if (part.get("identity") or {}).get("source") == "typed" else "the board file does not name it: read its marking, then decide")
    elif kind == "passive":
        if _SMALL_CHIP.search(name):
            verdict = "skip"
            reasons.append("a tiny chip part: cheaper and safer to buy new than to heat for")
            effort = "hard"
            tool = "tweezers and hot air; easy to lose or overheat"
        elif _BIG_CHIP.search(name):
            verdict = "optional"
            reasons.append("a larger chip part: easy enough to lift, but cheap to buy")
        else:
            verdict = "optional"
            reasons.append("a common part: cheap to buy new")
    else:
        verdict = "optional"
        reasons.append("a common part of an uncommon kind: take it if you need that function")
    if str(part.get("outline_basis", "")).startswith("no outline"):
        reasons.append("the footprint names no package and has no outline, so its size and effort are guesses")
    if verdict in {"keep", "test_first", "identify", "optional"} and kind == "ic":
        hazards.append("heat and moisture can damage a chip: do not stay on one spot, and keep it dry")
    typed = (part.get("identity") or {}).get("source") == "typed"
    label = VERDICT_TEXT[verdict]
    if typed and verdict == "keep" and kind == "ic":
        label = "Worth taking, if the marking checks out"   # a reading is not an identification
    return {"verdict": verdict, "label": label, "effort": effort, "tool": tool, "reasons": reasons, "hazards": hazards, "basis": TYPED_BASIS if typed else BASIS}


def _what(part: dict[str, Any]) -> str:
    """What a chip is called by the file, so two different chips are never one step."""

    if part["kind"] != "ic" or not _identified(part):
        return ""   # chips nobody can name are one job whatever their labels say
    identity = part.get("identity") or {}
    return str(identity.get("mpn") or identity.get("typed") or part.get("value") or "")


def _order_key(part: dict[str, Any]) -> tuple[Any, ...]:
    kind = part["kind"]
    salvage = part["salvage"]
    # Tall and easy first so they are out of the way: connectors, electrolytics, then chips from easy to hard, then the rest.
    phase = 0 if kind == "connector" else 1 if _ELECTROLYTIC.search(part["footprint"]) else 2 if kind == "ic" else 3
    effort = {"easy": 0, "medium": 1, "hard": 2, "none": 3}[salvage["effort"]]
    return (part["side"] != "front", phase, effort if phase == 2 else 0, -part["height_mm"], part["footprint"], salvage["verdict"], _what(part), part["ref"])


def _title(group: list[dict[str, Any]], verdict: str) -> str:
    refs = ", ".join(p["ref"] for p in group[:6]) + (f" and {len(group) - 6} more" if len(group) > 6 else "")
    noun = {"connector": "connector", "ic": "chip", "passive": "part", "other": "part"}.get(group[0]["kind"], "part")
    if _ELECTROLYTIC.search(group[0]["footprint"]):
        noun = "capacitor"
    plural = noun + ("s" if len(group) != 1 else "")
    return f"Remove the {plural} {refs}" if len(group) == 1 else f"Remove {len(group)} {plural}: {refs}"


def build_salvage_plan(pcb_text: str, *, pcb_sha256: str | None = None) -> dict[str, Any]:
    """The take-apart plan for the board in ``pcb_text``. Pure: no I/O, deterministic for the same bytes."""

    try:
        base = build_assembly_plan(pcb_text, pcb_sha256=pcb_sha256)
    except AssemblyPlanError as exc:
        raise SalvagePlanError(str(exc)) from exc
    return plan_from_assembly(base)


TYPED_LIMITS = [
    "Everything here is what you typed or placed: nothing was read from a file. Places are only as good as your measuring, and sizes are KiCad's library courtyards or typical for the package unless you gave them.",
    "A marking you read off a chip is a marking, not an identification: it can be a house code, rubbed, or fake. Check it against a datasheet.",
    "Whether a part still works is unknown until it is tested.",
]


def _name_of(part: dict[str, Any]) -> str:
    identity = part.get("identity") or {}
    return str(identity.get("mpn") or identity.get("typed") or part.get("value") or "").strip()


def _attach_lookups(parts: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Ask KiCad's library about each chip that has a name. A hit is what the library holds under that name: it is never proof."""

    if not part_lookup.libraries_available():
        return None
    done = 0
    for part in parts:
        if part["kind"] != "ic" or part.get("do_not_populate") or not _identified(part) or done >= MAX_LOOKUPS:
            continue
        try:
            found = part_lookup.lookup_part(_name_of(part), limit=4)
        except part_lookup.PartLookupError:
            continue
        done += 1
        matches = found["matches"]
        best = next((m for m in matches if m["tier"] in {"exact", "variant"}), None)
        readings = part.get("readings") or {}
        gates = part_lookup.power_gates(best["library"], best["name"], best["footprint"]) if best else []
        for gate in gates:
            gate["reading"] = readings.get(gate["key"]) or None
        part["lookup"] = {
            "query": found["query"], "tier": best["tier"] if best else ("family" if matches else "none"),
            "match": {k: best[k] for k in ("name", "library", "description", "datasheet", "footprint", "tier_text")} if best else None,
            "family": [m["name"] for m in matches if m["tier"] == "family"][:4],
            "gates": gates,
            "evidence": {"total": len(gates), "recorded": sum(1 for g in gates if g["reading"]), "ignored": max(0, len(readings) - sum(1 for g in gates if g["reading"]))},
        }
    return part_lookup.source() if done else None


def plan_from_assembly(base: dict[str, Any], *, typed: bool = False) -> dict[str, Any]:
    """The take-apart plan for parts already described as an assembly plan's parts (from a board file, or typed in by a person)."""

    parts = [dict(p) for p in base["parts"]]
    lookup_source = _attach_lookups(parts)
    fitted = [p for p in parts if not p["do_not_populate"]]
    for part in parts:
        part["salvage"] = _assess(part) if not part["do_not_populate"] else {
            "verdict": "skip", "label": "Not fitted", "effort": "none", "tool": "", "reasons": ["the design marks it do-not-populate, so there is no part on the board"], "hazards": [], "basis": BASIS,
        }

    to_take = sorted([p for p in fitted if p["salvage"]["verdict"] != "skip"], key=_order_key)
    groups: list[list[dict[str, Any]]] = []
    for part in to_take:
        key = (part["side"], part["kind"], part["footprint"], part["salvage"]["verdict"], part["salvage"]["effort"], _what(part))
        if groups and groups[-1][0].get("_key") == key:
            groups[-1].append(part)
        else:
            part["_key"] = key
            groups.append([part])

    steps: list[dict[str, Any]] = [
        {
            "step_id": "step-01", "order": 1, "kind": "prepare", "title": "Make the board safe to work on",
            "instruction": GENERAL_SAFETY, "side": "front", "turn_board_over": False, "refs": [], "part_ids": [], "checks": [],
        }
    ]
    current_side = "front"
    for group in groups:
        first = group[0]
        salvage = first["salvage"]
        refs = [p["ref"] for p in group]
        reason = salvage["reasons"][0] if salvage["reasons"] else ""
        text = f"{salvage['label']}: {reason}."
        if salvage["tool"]:
            text += f" Use {salvage['tool']}."
        if salvage["hazards"]:
            text += " " + " ".join(h[0].upper() + h[1:] + ("" if h.endswith(".") else ".") for h in salvage["hazards"])
        checks: list[dict[str, Any]] = []
        if salvage["verdict"] == "test_first":
            checks.append({"kind": "suggested_check", "check": "test", "from": ", ".join(refs), "to": "capacitance and ESR meter", "net": None, "expect": "close to the printed value; otherwise discard"})
        if salvage["verdict"] in {"keep", "identify"} and first["kind"] == "ic":
            checks.append({"kind": "suggested_check", "check": "read_marking", "from": ", ".join(refs), "to": "the text printed on the chip", "net": None, "expect": "write down what is printed, then compare it with a datasheet" if typed else "write down what is printed and whether it agrees with what the file says"})
        if first["kind"] == "ic":
            for note in _lookup_reasons(first):
                text += " " + note[0].upper() + note[1:] + ("" if note.endswith(".") else ".")
        if first["kind"] == "ic" and first.get("lookup") and first["lookup"]["gates"]:
            library_name = first["lookup"]["match"]["name"]
            for gate in first["lookup"]["gates"]:
                checks.append({"kind": "suggested_check", "check": "measure", "from": f"{', '.join(refs)} {gate['from']}", "to": gate["to"], "net": None, "detail": gate["instruction"], "expect": gate["expect"], "gate_kind": gate["kind"], "reading": gate.get("reading")})
            evidence = first["lookup"]["evidence"]
            text += f" Readings recorded: {evidence['recorded']} of {evidence['total']}. A recorded reading is a number you wrote down, not a pass: only the datasheet says what it should be."
            text += f" The pin names in the measurements come from KiCad's entry for {library_name}, not from your chip: confirm them in its datasheet before you touch a probe to it."
        if first["kind"] == "connector":
            checks.append({"kind": "suggested_check", "check": "inspect", "from": ", ".join(refs), "to": "pins and housing", "net": None, "expect": "straight pins, no melted plastic"})
        steps.append(
            {
                "step_id": f"step-{len(steps) + 1:02d}", "order": len(steps) + 1, "kind": "salvage", "title": _title(group, salvage["verdict"]),
                "instruction": text, "side": first["side"], "turn_board_over": first["side"] != current_side, "verdict": salvage["verdict"], "verdict_label": salvage["label"], "effort": salvage["effort"],
                "refs": refs, "part_ids": [p["id"] for p in group], "checks": checks,
            }
        )
        current_side = first["side"]
    skipped = [p["ref"] for p in fitted if p["salvage"]["verdict"] == "skip"]
    open_gates = [p["ref"] for p in fitted if p.get("lookup") and p["lookup"]["evidence"]["total"] > p["lookup"]["evidence"]["recorded"]]
    steps.append(
        {
            "step_id": f"step-{len(steps) + 1:02d}", "order": len(steps) + 1, "kind": "finish", "title": "Sort, label and test what you kept",
            "instruction": "Put each kind of part in its own labelled bag with where it came from. Nothing you took is known to work until it has been tested."
            + (f" Left on the board: {', '.join(skipped[:12])}{' and more' if len(skipped) > 12 else ''}." if skipped else "")
            + (f" Measurements still to record before you trust them: {', '.join(open_gates[:12])}{' and more' if len(open_gates) > 12 else ''}." if open_gates else ""),
            "side": current_side, "turn_board_over": False, "refs": [], "part_ids": [],
            "checks": [{"kind": "suggested_check", "check": "test", "from": "every part you kept", "to": "a meter or a test circuit", "net": None, "expect": "behaves as its type should; otherwise discard"}],
        }
    )

    for part in parts:
        part.pop("_key", None)
    counts = {verdict: sum(1 for p in parts if p["salvage"]["verdict"] == verdict and not p["do_not_populate"]) for verdict in VERDICTS}
    return {
        "schema_version": SALVAGE_PLAN_SCHEMA,
        "mode": "salvage",
        "authority": TYPED_AUTHORITY if typed else AUTHORITY_STATEMENT,
        "origin": "typed" if typed else "file",
        "lookup_source": lookup_source,
        "limits": TYPED_LIMITS if typed else [
            "Needs the board's file. A physical board with no file cannot be planned from.",
            "A part is named only as far as the file names it. Anything else is 'read the marking', never a guess.",
            "Whether a part still works is unknown until it is tested.",
        ],
        "source": base["source"],
        "board": base["board"],
        "parts": parts,
        "steps": steps,
        "not_fitted": base["not_fitted"],
        "summary": {
            "counts": counts,
            "keep": [{"ref": p["ref"], "what": (p["identity"].get("mpn") or p["identity"].get("typed") or p["value"]), "manufacturer": p["identity"]["manufacturer"]} for p in fitted if p["salvage"]["verdict"] == "keep"],
            "steps": len(steps),
            "evidence": {
                "chips_with_measurements": sum(1 for p in fitted if p.get("lookup") and p["lookup"]["evidence"]["total"]),
                "readings_recorded": sum(p["lookup"]["evidence"]["recorded"] for p in fitted if p.get("lookup")),
                "readings_open": sum(p["lookup"]["evidence"]["total"] - p["lookup"]["evidence"]["recorded"] for p in fitted if p.get("lookup")),
            },
        },
        "warnings": base["warnings"],
    }
