"""A take-apart plan for a board: which parts are worth removing, in what order, and what to do before trusting any of them.

It is the build sequence run the other way, over the same retained board. It is a view of retained bytes and a rule-of-thumb
assessment. It carries no engineering authority and measures nothing: a part's condition is unknown until it is tested, a
verdict is advice about effort and reuse, and nothing here approves using a salvaged part in a device.

The file path needs a board file; donor capture also accepts a typed description. A part is named only as far as that input
does: a part with no part number is "read the marking", never guessed.
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
    "Unplug the board and disconnect any battery or pack before you start. "
    "Work with ventilation and eye protection, and wash your hands afterwards: older boards can contain leaded solder."
)
# Ordinary workshop practice; no resistor value or wait duration is prescribed.
ORDINARY_CHARGE_PRECAUTIONS = (
    "Capacitors can hold a charge even without a readable "
    "voltage marking: discharge through a suitable resistor, not a screwdriver; use a meter to prove zero before touching or heating. "
    "Leave a resistor across the capacitors and re-measure after a wait: voltage can come back. If you do not know how to do this, "
    "leave the board alone and get help."
)
# Microwave service warning: https://www.partmaster.co.uk/images/mediator/121/nne281bmbpq%20service%20manual.pdf
# leaving HV work to trained personnel is generic practice, not a discharge method.
HV_NO_PROCEDURE = (
    "These circuits can hold a lethal charge that a hand meter and an ordinary resistor are not made for. "
    "This tool gives no discharge procedure: leave the part in place and the case closed, and leave it to someone trained."
)

_SPECIAL_CONNECTOR = re.compile(r"USB|JST|Molex|Micro|Mini|RJ45|Barrel|Audio|FPC|FFC|Terminal|Screw|SMA|HDMI|SD_|Card", re.IGNORECASE)
_PLAIN_HEADER = re.compile(r"PinHeader|PinSocket|Pin_Header", re.IGNORECASE)
# Anchored to whole parts of a name, so a word that merely contains one ("Electronic", "MOVEMENT", "OnePiece") does not match.
_ELECTROLYTIC = re.compile(r"(^|[:_])CP_|C_Elec|Electrolytic|(^|[:_])Elec_|Tantalum|TantalC|EDLC|Supercap", re.IGNORECASE)
# Illinois Capacitor TTA: WVDC is rated working voltage, not measured voltage.
# https://www1.futureelectronics.com/doc/ILLINOIS%20CAPACITOR/338TTA016M.pdf
_VOLTS = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*((?:kV|WV|V)(?:AC|DC)?)(?![a-z])", re.IGNORECASE)
_MAINS_RATED_CAP = re.compile(r"\b[XY][12]\b", re.IGNORECASE)
_PITCH = r"(?<![\d.])(?:5\.0{1,2}|5\.08|7\.50?|7\.62|10\.16|11\.0{1,2})(?!\d)"
_WIDE_TERMINAL = re.compile(rf"(Terminal|Screw|MKDS|Phoenix).*{_PITCH}|{_PITCH}.*(Terminal|Screw|MKDS|Phoenix)", re.IGNORECASE)
_SOLDER_JUMPER = re.compile(r"SolderJumper|SolderBridge|Jumper:", re.IGNORECASE)
_MAINS_PART = re.compile(
    r"Varistor|(^|[:_ ])RV_|(^|[:_ ])MOV(_|\d|$)|(^|[:_ ])IEC(_|\d|$)|Mains|AC_Inlet|Fuse_?holder|Fuse_\d+x\d+|Cartridge|Transformer|Trafo|Common_?Mode|Relay|SONGLE|(?<![a-z])SRD[-_]",
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
_BATTERY = re.compile(r"Battery|CR\d{4}|LiPo|Li-?ion|Lithium|18650|Coin|Pouch|\b(?:vape|battery pack)\b", re.IGNORECASE)
_LITHIUM = re.compile(r"Lithium|LiPo|Li-?ion|18650|Pouch|CR\d{4}", re.IGNORECASE)
_PACK_PLUG = re.compile(r"(?<![a-z0-9])(?:XT(?:30|60|90)|battery[-_ ]?connector)(?![a-z0-9])", re.IGNORECASE)
_CAP_PACKAGE = re.compile(r"Capacitor|(^|:)C[P]?_|Tantalum|EDLC|Supercap", re.IGNORECASE)
_UNMARKED_CAP = re.compile(r"C_Rect|C_Disc|Film|Ceramic[-_ ]?Disc", re.IGNORECASE)
# HVC ceramic-disc series: https://www.hv-caps.com/HV-Ceramic-Disc-Capacitor/hv-ceramic-disc-capacitor163.html
_HV_EQUIPMENT = re.compile(r"(?<![a-z0-9])(?:HV|HVC)(?![a-z])|high[-_ ]*voltage", re.IGNORECASE)
_HV_TOKEN = re.compile(_HV_EQUIPMENT.pattern + r"|microwave|photoflash|(?<![a-z0-9])flash(?![a-z0-9])", re.IGNORECASE)
# CRT service guidance (docs/SALVAGE_PLAN.md); bare anode/flyback also describe ordinary diodes.
_CRT = re.compile(r"(?<![a-z0-9])(?:CRT|EHT|LOPT)(?![a-z0-9])|flyback[-_ ]+transformer|TV[-_ ]+flyback|anode[-_ ]+cap(?![a-z])|aquadag", re.IGNORECASE)
_MICROWAVE = re.compile(r"microwave|(?<![a-z0-9])ma(?:gnet|gnat|gent)rons?(?![a-z0-9])|(?<![a-z0-9])MOT(?![a-z0-9])", re.IGNORECASE)
# EPA lamp guidance in docs/SALVAGE_PLAN.md concerns fluorescent/CCFL lamps, not LED lamp labels.
_LAMP = re.compile(r"CCFL|backlight|fluorescent|mercury|cold[-_ ]+cathode", re.IGNORECASE)
_LAMP_INVERTER = re.compile(r"lamp[-_ ]+inverter", re.IGNORECASE)
_HEATER = re.compile(
    r"heater|fuser|heating[-_ ]?element|(?<![a-z0-9])toaster(?![a-z0-9])|mica[-_ ]?heater|"
    r"hair[-_ ]+dryer[-_ ]+element|kettle[-_ ]+element|oven[-_ ]+element|iron[-_ ]+sole[-_ ]+plate",
    re.IGNORECASE,
)
_THERMAL_FUSE = re.compile(r"thermal[-_ ]*(?:fuse|cut[-_ ]?off|cut[-_ ]?out)|(?<![a-z0-9])TCO(?![a-z0-9])", re.IGNORECASE)
_THERMISTOR = re.compile(r"thermistor|(?<![a-z0-9])NTC(?![a-z0-9])", re.IGNORECASE)
# TDK ICL notes: an inrush disc, not a temperature-sensor NTC or a plain ceramic disc.
_INRUSH_MARK = re.compile(r"(?<![a-z0-9])(?:icl|inrush|sck[-_]?\d+)(?![a-z0-9])", re.IGNORECASE)
_INRUSH_BODY = re.compile(r"thermistor|(?<![a-z0-9])(?:ntc|disc)(?![a-z0-9])", re.IGNORECASE)
_SURGE = re.compile(r"gas[-_ ]?discharge|spark[-_ ]?gap|(?<![a-z0-9])GDT\d*\b", re.IGNORECASE)
_MOV = re.compile(r"varistor|(^|[:_ ])RV_|(^|[:_ ])MOV(_|\d|$)", re.IGNORECASE)
_OPTO = re.compile(r"opto|(?<![a-z0-9])(?:PC8\d{2}|4N[23]\d|VO6\d{2,3}|LTV\d{3}|EL8\d{2}|TLP\d+)", re.IGNORECASE)
_BARRIER = re.compile(
    _OPTO.pattern + r"|digital[-_ ]+isolat|(?<![a-z0-9])ISO\d+",
    re.IGNORECASE,
)
_POWER_TAB = re.compile(r"TO-220|TO-247", re.IGNORECASE)
_MAINS_SILICON = re.compile(r"(?<![a-z0-9])(?:LNK\d+|TNY\d+|TOP\d+|VIPER\d+|UC384\d|NCP12\d+|ICE[23]\w+|IRF840)|offline[-_ ]?switch", re.IGNORECASE)
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


def _part_text(part: dict[str, Any]) -> str:
    identity = part.get("identity") or {}
    return " ".join(str(x or "") for x in (part.get("footprint"), part.get("value"), identity.get("mpn"), identity.get("typed")))


def _voltages(part: dict[str, Any]) -> list[float]:
    # Read markings, not footprint dimensions or part numbers. kV and WV markings are read too (photoflash and microwave capacitors).
    identity = part.get("identity") or {}
    text = " ".join(str(x or "") for x in (part.get("value"), identity.get("typed")))
    return [float(m.group(1)) * (1000 if m.group(2).lower().startswith("kv") else 1) for m in _VOLTS.finditer(text)]


def _is_capacitor(part: dict[str, Any]) -> bool:
    return part.get("component") == "capacitor" or bool(_CAP_PACKAGE.search(part["footprint"])) or bool(
        re.search(r"\b(?:capacitor|supercap\w*|EDLC|tantalum)\b", _part_text(part), re.IGNORECASE)
    ) or (
        part.get("kind") == "passive" and bool(re.match(r"^(?:C|CX)\d", part["ref"], re.IGNORECASE))
    )


def _high_voltage(part: dict[str, Any]) -> bool:
    return _is_capacitor(part) and (
        bool(_MAINS_RATED_CAP.search(_part_text(part)) or _HV_TOKEN.search(_part_text(part)))
        or any(v >= 100 for v in _voltages(part))
    )


def _mains_silicon(part: dict[str, Any]) -> bool:
    text = _part_text(part)
    return bool(_MAINS_SILICON.search(text)) or (
        bool(re.search(r"MOSFET|TO-220|TO-247", text, re.IGNORECASE)) and any(v >= 500 for v in _voltages(part))
    )


def _wide_terminal(part: dict[str, Any]) -> bool:
    text = _part_text(part)
    if _WIDE_TERMINAL.search(text):
        return True
    if not re.search(r"Terminal|Screw|MKDS|Phoenix", text, re.IGNORECASE):
        return False
    # Explicit pitch fields cover widths beyond the legacy list; no body dimension is inferred as pitch.
    return any(float(m.group(1)) >= 5 for m in re.finditer(
        r"(?<![a-z0-9])(?:P|pitch\s*)(\d+(?:\.\d+)?)\s*mm\b", text, re.IGNORECASE
    ))


def _special_hazards(part: dict[str, Any]) -> list[str]:
    """Hazard tokens override a guessed kind. Short source quotes are in docs/SALVAGE_PLAN.md."""
    text = _part_text(part)
    hazards = []
    if _CRT.search(text):
        hazards.append("CRT anodes and flyback circuits can retain charge and regain it after discharge: leave them in place and get trained help")
    if _MICROWAVE.search(text):
        hazards.append("microwave circuits can retain charge in the high-voltage capacitor; leave the HV stack in place, including its transformer and diode")
        # Panasonic: "Never operate the magnetron unless it is properly installed."
        # https://www.partmaster.co.uk/images/mediator/121/nne281bmbpq%20service%20manual.pdf
        hazards.append("do not power a loose magnetron: it is meant to run fitted to its own waveguide and cavity")
    if _LAMP.search(text):
        hazards.append("this marking may refer to a fluorescent or CCFL backlight with high voltage and a mercury-containing lamp: do not break or force it out")
    if _LAMP_INVERTER.search(text):
        # Generic practice for an unknown lamp inverter; no lamp chemistry is inferred.
        hazards.append("a lamp inverter marking points to high voltage: leave it in place and get trained help")
    if _THERMAL_FUSE.search(text):
        hazards.append("a thermal fuse is a non-resettable cut-off: do not bypass it; replace it using the appliance's service information")
    if _heater_context(part):
        hazards.append("a heater or fuser may be hot and connected to mains: let it cool; do not power it without its original thermal cut-off")
    if _HV_EQUIPMENT.search(text) and not _is_capacitor(part):
        hazards.append("this marking points to high voltage: leave the part in place and get trained help")
    return hazards


def _heater_context(part: dict[str, Any]) -> bool:
    # A typed resistor's application label does not turn it into a heater.
    component = part.get("component")
    if component is not None:
        return component in {"other", "mains or power part"} and bool(_HEATER.search(_part_text(part)))
    return bool(_HEATER.search(part["footprint"])) or (
        part["kind"] == "other" and bool(_HEATER.search(_part_text(part)))
    )


def _inrush_ntc(part: dict[str, Any]) -> bool:
    text = _part_text(part)
    return bool(_INRUSH_MARK.search(text) and _INRUSH_BODY.search(text))


def _barrier_part(part: dict[str, Any]) -> bool:
    return bool(_BARRIER.search(_part_text(part)))


def _power_tab(part: dict[str, Any]) -> bool:
    return bool(_POWER_TAB.search(_part_text(part)))


def _mains_side_board(parts: list[dict[str, Any]]) -> bool:
    return any(
        (not p.get("do_not_populate"))
        and bool(_MAINS_PART.search(_part_text(p)) or _high_voltage(p) or _hv_no_procedure(p) or _mains_silicon(p))
        for p in parts
    )


def _hv_no_procedure(part: dict[str, Any]) -> bool:
    """Policy tier, not a statement of measured voltage or a discharge procedure."""
    text = _part_text(part)
    # Mains-range capacitors (100 V to under 1 kV: a charger's bulk capacitor) are left in place but keep the ordinary
    # resistor-and-meter procedure; only 1 kV and up, or an explicit HV / microwave / CRT / lamp / flash context, gets none.
    extreme_capacitor = _is_capacitor(part) and (any(v >= 1000 for v in _voltages(part)) or bool(_HV_TOKEN.search(text)))
    return bool(extreme_capacitor or _CRT.search(text) or _MICROWAVE.search(text)
                or _LAMP.search(text) or _LAMP_INVERTER.search(text) or _HV_EQUIPMENT.search(text)
                or re.search(r"photoflash", text, re.IGNORECASE))


def _mains_context(part: dict[str, Any]) -> bool:
    text = _part_text(part)
    unknown_charge = _is_capacitor(part) and not _voltages(part) and bool(
        _UNMARKED_CAP.search(part["footprint"]) or _ELECTROLYTIC.search(part["footprint"])
    )
    return bool(_hv_no_procedure(part) or _high_voltage(part) or _special_hazards(part) or _MAINS_PART.search(text) or _wide_terminal(part)
                or _mains_silicon(part) or _barrier_part(part) or _inrush_ntc(part) or unknown_charge)


def _lookup_reasons(part: dict[str, Any]) -> list[str]:
    found = part.get("lookup")
    if not found:
        return []
    notes: list[str] = []
    if found["match"]:
        m = found["match"]
        text = f"KiCad's library has a part called \"{m['name']}\": {m['description'] or 'no description'}"
        if found["tier"] != "exact":
            extra = (
                " (a variant: a library name that is this name plus a code; "
                "the code may be a package, a grade or a different chip)"
            )
            text += extra
        notes.append(text)
        if found.get("package_note"):
            notes.append(found["package_note"])
        return notes
    if found["family"]:
        return [f"KiCad's library has parts from the same family ({', '.join(found['family'][:3])}) but not this one: use them to learn what kind of chip it probably is, no more"]
    return ["KiCad's library does not list it: search its datasheet by the marking"]


def _assess(part: dict[str, Any], *, mains_board: bool = False) -> dict[str, Any]:
    """The verdict for one part, with the reasons for it. Never a statement about the part's condition."""

    kind, name = part["kind"], part["footprint"]
    effort, tool = _effort(part)
    reasons: list[str] = []
    hazards: list[str] = []
    verdict = "optional"
    text = _part_text(part)
    special = _special_hazards(part)

    if kind in {"testpoint", "mounting_hole"}:
        verdict = "skip"
        reasons.append("a test pad or a hole: there is nothing to take")
        effort, tool = "none", ""
    elif _SOLDER_JUMPER.search(name):
        verdict = "skip"
        reasons.append("a solder jumper is a bridge on the board itself: there is no part to take")
        effort, tool = "none", ""
    elif _hv_no_procedure(part) or _high_voltage(part):
        verdict = "skip"
        reasons.append("leave-in-place policy: a marking of 100 V or more, X/Y mains class or HV circuit context; a rating is not the voltage now present")
        if _hv_no_procedure(part):
            hazards.append("a high-voltage circuit can hold a dangerous charge; leave it in place and get trained help")
            hazards.append(HV_NO_PROCEDURE)
        else:
            hazards.append("a mains-range capacitor can hold a dangerous charge; leave it in place unless you know how to discharge it")
            hazards.append("if you decide to take it anyway: " + ORDINARY_CHARGE_PRECAUTIONS)
        hazards.extend(special)
        effort, tool = "none", ""
    elif special:
        verdict = "skip"
        reasons.append("a marking or package points to an appliance hazard: leave it in place")
        hazards.extend(special)
        effort, tool = "none", ""
    elif _BATTERY.search(text) or _BATTERY_REF.match(part["ref"]):
        hazards.append("take any cell out before heating anything; never heat a cell")
        hazards.append("tape exposed battery terminals separately; do not short, do not puncture or disassemble, and do not solder directly onto a cell")
        if _LITHIUM.search(text):
            hazards.append("do not reuse a swollen or damaged lithium cell; do not puncture a bulge")
        if _BATTERY_HOLDER.search(name):
            verdict = "optional"
            reasons.append("a battery holder: take it if you need it; the cell is never part of this")
        else:
            verdict = "skip"
            reasons.append("a battery cell: take it out by hand before you start, never with heat, and do not reuse a swollen or damaged one")
            effort, tool = "none", ""
    elif _MAINS_PART.search(text) and not _is_capacitor(part):
        verdict = "optional"
        reasons.append("a part from mains wiring or a switching supply: it can wear out or have carried mains voltage in its original use")
        hazards.append("it may have carried mains voltage; nearby capacitors can hold charge after unplugging: follow the preparation tier before work")
        if re.search(r"Relay|SONGLE|SRD[-_]", text, re.IGNORECASE):
            hazards.append("relay contacts may be worn; do not rely on a used relay for mains switching")
        if _MOV.search(text):
            hazards.append("varistors wear out and may fail short: do not put a used MOV back on mains")
    elif _ELECTROLYTIC.search(text):
        verdict = "test_first"
        reasons.append("a polarised or high-voltage capacitor ages and can fail; its condition is unknown")
        hazards.append("may still hold a charge: discharge it through a resistor first")
        hazards.append("prove zero with a meter before touching or heating; leave a resistor across it and re-measure after a wait because voltage can come back")
        if _ELECTROLYTIC.search(text):
            hazards.append("inspect before removal: discard a bulged or leaking capacitor")
            if not _voltages(part):
                hazards.append("no readable voltage: this could be a photoflash or other high-energy capacitor; treat it as charged until measured")
        if re.search(r"Tantalum|TantalC", text, re.IGNORECASE):
            hazards.append("tantalum is polarised: reverse polarity destroys it; record its polarity before removal")
            # Vishay solid tantalum capacitors FAQ (document 40110):
            # https://www.vishay.com/docs/40110/faq.pdf
            # "overstressing of tantalum capacitors that can lead to overheating and possibly ignition"
            # "Vishay does not recommend the intentional application of reverse voltage on solid tantalum capacitors"
            hazards.append(
                "overstress can overheat a tantalum and possibly ignite it; the maker does not recommend reverse voltage, "
                "so keep the polarity, and a tantalum whose polarity is unknown is not reused"
            )
        if re.search(r"EDLC|Supercap", text, re.IGNORECASE):
            hazards.append("a supercapacitor can arc when shorted: remove jewellery and do not short its terminals")
        if _ELECTROLYTIC.search(text) and re.search(r"bulg|leak|vented", text, re.IGNORECASE):
            verdict = "skip"
            reasons.insert(0, "reported damage: discard a bulged or leaking capacitor")
            effort, tool = "none", ""
    elif _is_capacitor(part) and _UNMARKED_CAP.search(name) and not _voltages(part):
        reasons.append("no readable voltage on a film box or ceramic disc: its role is unknown")
        hazards.append("might be a mains safety capacitor: do not reuse it as a generic capacitor or as a mains protection part")
        hazards.append("may hold charge: discharge through a resistor and prove zero with a meter before touching or heating")
    elif kind == "connector" and _SPECIAL_CONNECTOR.search(name):
        verdict = "keep"
        reasons.append("a specialised connector: harder to find and cheap to keep")
        if _wide_terminal(part):
            verdict = "optional"
            reasons[0] = "a wide terminal block: its previous use and condition are unknown"
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
                reasons.append(f"the board file names it: \"{named}\"{who}; read that as the file's claim")
                reasons.append("read the marking on the chip itself before trusting that")
            reasons.extend(_lookup_reasons(part))
        else:
            verdict = "identify"
            reasons.append("you have not given a marking that looks like a part number: read it off the chip, then decide" if (part.get("identity") or {}).get("source") == "typed" else "the board file does not name it: read its marking, then decide")
    elif kind == "passive":
        if _SMALL_CHIP.search(name):
            verdict = "skip"
            reasons.append("a tiny chip part: cheaper to buy new than to heat for")
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
    if _PACK_PLUG.search(text):
        hazards.append("a battery plug means the pack may still be live: disconnect it before work and tape exposed terminals separately")
    if _OPTO.search(text):
        hazards.append("an optocoupler is an isolation barrier only within its ratings; a used one is not known to still be one: do not rely on it for mains isolation")
    if _barrier_part(part) and not _OPTO.search(text):
        hazards.append(
            "this tool cannot tell whether the isolation it provides still meets its rating after removal and reuse, "
            "so treat a reused one as a part of unknown isolation and do not use it in a place where isolation matters. "
            "General practice, not from the datasheet."
        )
    if _mains_silicon(part):
        hazards.append("this chip may have sat on a mains primary: its previous stress and condition are unknown")
    if _power_tab(part) and (mains_board or _mains_silicon(part)):
        hazards.append(
            "keep any insulating pad or bushing that was under its tab; the metal tab can be connected to one of the pins, "
            "check the datasheet before mounting it. General practice, not from the datasheet."
        )
    if _inrush_ntc(part):
        # TDK Electronics NTC inrush current limiters application notes (July 2019):
        # https://www.tdk-electronics.tdk.com/download/531332/47c4c7e326bcb6f7d72c41945477a94e/pdf-applicationnotes.pdf
        # "may in extreme cases reach a mean" / "temperature of up to 250 °C"
        # "the contact areas may become quite"
        hazards.append(
            "an NTC inrush limiter runs hot in use and may in extreme cases reach a mean temperature of up to 250 °C; "
            "the contact areas may become quite hot too: identify it and read its ratings before reuse, and remove it only when cold"
        )
    elif _THERMISTOR.search(text):
        hazards.append("a thermistor may still be hot: let it cool before handling; its previous use is unknown")
    if _SURGE.search(text):
        hazards.append("do not rely on a used surge protector for protection; its previous use is unknown")
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
            found = part_lookup.lookup_part(_name_of(part), limit=8)
        except part_lookup.PartLookupError:
            continue
        done += 1
        matches = found["matches"]
        user_fp = part.get("footprint")
        resolved = part_lookup.resolve_lookup_gates(matches, user_fp)
        best = resolved["best"]
        readings = part.get("readings") or {}
        gates = resolved["gates"]
        for gate in gates:
            gate["reading"] = readings.get(gate["key"]) or None
        part["lookup"] = {
            "query": found["query"], "tier": best["tier"] if best else ("family" if matches else "none"),
            "match": {k: best[k] for k in ("name", "library", "description", "datasheet", "footprint", "tier_text")} if best else None,
            "family": [m["name"] for m in matches if m["tier"] == "family"][:4],
            "gates": gates,
            "package_note": resolved["package_note"],
            "evidence": {"total": len(gates), "recorded": sum(1 for g in gates if g["reading"]), "ignored": max(0, len(readings) - sum(1 for g in gates if g["reading"]))},
        }
    return part_lookup.source() if done else None


def plan_from_assembly(base: dict[str, Any], *, typed: bool = False) -> dict[str, Any]:
    """The take-apart plan for parts already described as an assembly plan's parts (from a board file, or typed in by a person)."""

    parts = [dict(p) for p in base["parts"]]
    lookup_source = _attach_lookups(parts)
    fitted = [p for p in parts if not p["do_not_populate"]]
    mains_board = _mains_side_board(fitted)
    for part in parts:
        part["salvage"] = _assess(part, mains_board=mains_board) if not part["do_not_populate"] else {
            "verdict": "skip", "label": "Not fitted", "effort": "none", "tool": "", "reasons": ["the design marks it do-not-populate, so there is no part on the board"], "hazards": [], "basis": BASIS,
        }

    to_take = sorted([p for p in fitted if p["salvage"]["verdict"] != "skip"], key=_order_key)
    groups: list[list[dict[str, Any]]] = []
    for part in to_take:
        key = (part["side"], part["kind"], part["footprint"], part["salvage"]["verdict"], part["salvage"]["effort"], _what(part), tuple(part["salvage"]["hazards"]))
        if groups and groups[-1][0].get("_key") == key:
            groups[-1].append(part)
        else:
            part["_key"] = key
            groups.append([part])

    context_parts = [p for p in fitted if _mains_context(p)]
    hv_parts = [p for p in fitted if _hv_no_procedure(p)]
    preparation = GENERAL_SAFETY
    if hv_parts:
        preparation += " High-voltage leave-in-place context: " + ", ".join(p["ref"] for p in hv_parts) + ". " + HV_NO_PROCEDURE
    else:
        preparation += " " + ORDINARY_CHARGE_PRECAUTIONS
    if context_parts:
        preparation += " Mains or high-voltage context: " + ", ".join(p["ref"] for p in context_parts) + "."
        preparation += " Do not wear a wrist strap near high voltage."
    else:
        preparation += " Use an anti-static strap if you can."

    steps: list[dict[str, Any]] = [
        {
            "step_id": "step-01", "order": 1, "kind": "prepare", "title": "Unplug and check stored charge",
            "instruction": preparation, "side": "front", "turn_board_over": False, "refs": [], "part_ids": [], "checks": [],
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
            checks.append({"kind": "suggested_check", "check": "test", "from": ", ".join(refs), "to": "capacitance and ESR meter", "net": None, "expect": "record the test setup and readings; consult the datasheet; this report gives no expected reading"})
        if salvage["verdict"] in {"keep", "identify"} and first["kind"] == "ic":
            checks.append({"kind": "suggested_check", "check": "read_marking", "from": ", ".join(refs), "to": "the text printed on the chip", "net": None, "expect": "write down what is printed, then compare it with a datasheet" if typed else "write down what is printed and whether it agrees with what the file says"})
        if first["kind"] == "ic":
            for note in _lookup_reasons(first):
                text += " " + note[0].upper() + note[1:] + ("" if note.endswith(".") else ".")
        if first["kind"] == "ic" and first.get("lookup") and first["lookup"]["gates"]:
            library_name = first["lookup"]["match"]["name"]
            recorded_pairs = 0
            total_pairs = 0
            for gate in first["lookup"]["gates"]:
                bits: list[str] = []
                for part in group:
                    total_pairs += 1
                    reading = None
                    for other in (part.get("lookup") or {}).get("gates") or []:
                        if other.get("key") == gate["key"]:
                            reading = other.get("reading")
                            break
                    if reading:
                        recorded_pairs += 1
                        bits.append(f"{part['ref']}: {reading}")
                    else:
                        bits.append(f"{part['ref']}: not recorded")
                reading_text: str | None
                if len(group) > 1:
                    reading_text = "; ".join(bits)
                else:
                    reading_text = gate.get("reading")
                checks.append({"kind": "suggested_check", "check": "measure", "from": f"{', '.join(refs)} {gate['from']}", "to": gate["to"], "net": None, "detail": gate["instruction"], "expect": gate["expect"], "gate_kind": gate["kind"], "reading": reading_text})
            text += f" Readings recorded: {recorded_pairs} of {total_pairs}. A recorded reading is a number you wrote down, not a pass: only the datasheet says what it should be. None of these readings shows a removed chip works."
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
            + (f" Measurements still to record as notes (none of them shows a removed chip works): {', '.join(open_gates[:12])}{' and more' if len(open_gates) > 12 else ''}." if open_gates else ""),
            "side": current_side, "turn_board_over": False, "refs": [], "part_ids": [],
            "checks": [{"kind": "suggested_check", "check": "test", "from": "every part you kept", "to": "a meter or a test circuit", "net": None, "expect": "write down what you tried and what you saw"}],
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
            "Needs the board's file for this path. For a physical board without a file, use the separate typed capture path.",
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
