"""A board with no file, described by a person: its size, and each part's kind, package, marking and place on it.

This is how a physical donor board (an e-waste board nobody has a KiCad file for) gets into the take-apart plan. Everything here is
typed or placed by a person, and the plan says so. Sizes of common packages are typical values, labelled as such, and a person can
overwrite any of them with what they measured. A marking is what was read off the part: it is never treated as an identification.
"""

from __future__ import annotations

import re
from typing import Any

from .assembly_plan import _height
from .part_lookup import footprint_size, libraries_available
from .salvage_plan import SalvagePlanError, plan_from_assembly
from .text_safety import finite_number, has_hidden_characters

DONOR_SPEC_SCHEMA = "hardware_splicer.donor_capture.v1"
MAX_PARTS = 300
MAX_NAME = 80
MAX_MARKING = 40
MIN_BOARD_MM, MAX_BOARD_MM = 5.0, 500.0
MIN_PART_MM, MAX_PART_MM = 0.5, 120.0

# kind -> package -> (the footprint name the planner's rules read, the real KiCad footprint its size is taken from or None, typical width mm,
# typical length mm, mounting). Where a real KiCad footprint exists the size is its courtyard, which is exact for that footprint and a
# little larger than the part itself; where none exists the size is a typical value and is labelled as such.
_TABLE: dict[str, dict[str, tuple[str, str | None, float, float, str]]] = {
    "connector": {
        "pin header": ("Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical", "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical", 2.5, 10.2, "through_hole"),
        "USB": ("Connector_USB:USB_A_CNCTech_1001-011-01101_Horizontal", "Connector_USB:USB_A_CNCTech_1001-011-01101_Horizontal", 14.0, 13.0, "through_hole"),
        "JST": ("Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical", "Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical", 7.0, 6.0, "through_hole"),
        "barrel jack": ("Connector_BarrelJack:BarrelJack_CUI_PJ-063AH_Horizontal", "Connector_BarrelJack:BarrelJack_CUI_PJ-063AH_Horizontal", 14.0, 9.0, "through_hole"),
        "terminal block": ("TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal", "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal", 10.2, 7.6, "through_hole"),
        "RJ45": ("Connector_RJ:RJ45_Abracon_ARJP11A-MA_Horizontal", "Connector_RJ:RJ45_Abracon_ARJP11A-MA_Horizontal", 16.0, 21.0, "through_hole"),
        "audio jack": ("Connector_Audio:Jack_3.5mm_CUI_SJ1-3513N_Horizontal", "Connector_Audio:Jack_3.5mm_CUI_SJ1-3513N_Horizontal", 12.0, 6.0, "through_hole"),
        "FFC/FPC": ("Connector_FFC-FPC:Amphenol_F32Q-1A7x1-11006_1x06-1MP_P0.5mm_Horizontal", "Connector_FFC-FPC:Amphenol_F32Q-1A7x1-11006_1x06-1MP_P0.5mm_Horizontal", 12.0, 4.0, "smd"),
        "other connector": ("Connector:Connector_Other", None, 10.0, 8.0, "through_hole"),
    },
    "ic": {
        "DIP": ("Package_DIP:DIP-8_W7.62mm", "Package_DIP:DIP-8_W7.62mm", 9.5, 7.9, "through_hole"),
        "SOIC": ("Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", 6.0, 5.0, "smd"),
        "SOT-23": ("Package_TO_SOT_SMD:SOT-23", "Package_TO_SOT_SMD:SOT-23", 3.0, 3.0, "smd"),
        "TSSOP": ("Package_SO:TSSOP-14_4.4x5mm_P0.65mm", "Package_SO:TSSOP-14_4.4x5mm_P0.65mm", 5.0, 6.4, "smd"),
        "QFP": ("Package_QFP:LQFP-48_7x7mm_P0.5mm", "Package_QFP:LQFP-48_7x7mm_P0.5mm", 9.0, 9.0, "smd"),
        "QFN": ("Package_DFN_QFN:QFN-32-1EP_5x5mm_P0.5mm_EP3.1x3.1mm", "Package_DFN_QFN:QFN-32-1EP_5x5mm_P0.5mm_EP3.1x3.1mm", 5.0, 5.0, "smd"),
        "BGA": ("Package_BGA:BGA-64_9.0x9.0mm_Layout10x10_P0.8mm", "Package_BGA:BGA-64_9.0x9.0mm_Layout10x10_P0.8mm", 10.0, 10.0, "smd"),
        "TO-220": ("Package_TO_SOT_THT:TO-220-3_Vertical", "Package_TO_SOT_THT:TO-220-3_Vertical", 10.0, 15.0, "through_hole"),
    },
    "capacitor": {
        "electrolytic can": ("Capacitor_THT:CP_Radial_D8.0mm_P3.50mm", "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm", 8.5, 8.5, "through_hole"),
        "electrolytic SMD can": ("Capacitor_SMD:CP_Elec_6.3x5.4", "Capacitor_SMD:CP_Elec_6.3x5.4", 6.6, 6.6, "smd"),
        "tantalum": ("Capacitor_Tantalum_SMD:CP_EIA-3216-18_Kemet-A", "Capacitor_Tantalum_SMD:CP_EIA-3216-18_Kemet-A", 3.5, 2.8, "smd"),
        "ceramic 0603": ("Capacitor_SMD:C_0603_1608Metric", "Capacitor_SMD:C_0603_1608Metric", 1.6, 0.8, "smd"),
        "ceramic 0805": ("Capacitor_SMD:C_0805_2012Metric", "Capacitor_SMD:C_0805_2012Metric", 2.0, 1.25, "smd"),
        "ceramic 1206": ("Capacitor_SMD:C_1206_3216Metric", "Capacitor_SMD:C_1206_3216Metric", 3.2, 1.6, "smd"),
        "ceramic disc": ("Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm", 5.0, 5.0, "through_hole"),
        "film box": ("Capacitor_THT:C_Rect_L18.0mm_W5.0mm_P15.00mm_FKS3_FKP3", "Capacitor_THT:C_Rect_L18.0mm_W5.0mm_P15.00mm_FKS3_FKP3", 18.0, 6.0, "through_hole"),
    },
    "resistor": {
        "0402": ("Resistor_SMD:R_0402_1005Metric", "Resistor_SMD:R_0402_1005Metric", 1.0, 0.5, "smd"),
        "0603": ("Resistor_SMD:R_0603_1608Metric", "Resistor_SMD:R_0603_1608Metric", 1.6, 0.8, "smd"),
        "0805": ("Resistor_SMD:R_0805_2012Metric", "Resistor_SMD:R_0805_2012Metric", 2.0, 1.25, "smd"),
        "1206": ("Resistor_SMD:R_1206_3216Metric", "Resistor_SMD:R_1206_3216Metric", 3.2, 1.6, "smd"),
        "axial": ("Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", 6.3, 2.5, "through_hole"),
    },
    "diode or LED": {
        "LED 0603": ("LED_SMD:LED_0603_1608Metric", "LED_SMD:LED_0603_1608Metric", 1.6, 0.8, "smd"),
        "LED 5 mm": ("LED_THT:LED_D5.0mm", "LED_THT:LED_D5.0mm", 5.0, 5.0, "through_hole"),
        "diode SMD": ("Diode_SMD:D_SOD-123", "Diode_SMD:D_SOD-123", 2.7, 1.6, "smd"),
        "diode axial": ("Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal", "Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal", 5.2, 2.7, "through_hole"),
    },
    "crystal": {
        "metal can": ("Crystal:Crystal_HC49-U_Vertical", "Crystal:Crystal_HC49-U_Vertical", 11.0, 4.7, "through_hole"),
        "SMD": ("Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm", "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm", 3.2, 2.5, "smd"),
    },
    "switch": {
        "tactile THT": ("Button_Switch_THT:SW_PUSH_6mm", "Button_Switch_THT:SW_PUSH_6mm", 6.0, 6.0, "through_hole"),
        "tactile SMD": ("Button_Switch_SMD:SW_SPST_CK_RS282G05A3", "Button_Switch_SMD:SW_SPST_CK_RS282G05A3", 6.0, 3.5, "smd"),
    },
    "battery": {
        "coin cell holder": ("Battery:BatteryHolder_Keystone_103_1x20mm", "Battery:BatteryHolder_Keystone_103_1x20mm", 21.0, 21.0, "through_hole"),
        "cell (18650 or similar)": ("Battery:Battery_18650", None, 18.0, 65.0, "through_hole"),
        "lithium pouch": ("Cells:Li-ion_Pouch", None, 40.0, 60.0, "smd"),
    },
    "mains or power part": {
        "transformer": ("Transformer_THT:Transformer_Breve_TEZ-22x24", "Transformer_THT:Transformer_Breve_TEZ-22x24", 24.0, 22.0, "through_hole"),
        "relay": ("Relay_THT:Relay_SPDT_Finder_32.21-x000", "Relay_THT:Relay_SPDT_Finder_32.21-x000", 19.0, 15.5, "through_hole"),
        "fuse (5x20 mm, with its holder)": ("Fuse:Fuseholder_Clip-5x20mm_Bel_FC-203-22_Lateral_P17.80x5.00mm_D1.17mm_Horizontal", "Fuse:Fuseholder_Clip-5x20mm_Bel_FC-203-22_Lateral_P17.80x5.00mm_D1.17mm_Horizontal", 22.0, 6.0, "through_hole"),
        "varistor": ("Varistor:RV_Disc_D12mm_W3.9mm_P7.5mm", "Varistor:RV_Disc_D12mm_W3.9mm_P7.5mm", 12.0, 4.0, "through_hole"),
        "common-mode choke": ("Inductor_THT:L_CommonMode_PulseElectronics_PH9455x105NL_1", "Inductor_THT:L_CommonMode_PulseElectronics_PH9455x105NL_1", 15.0, 12.0, "through_hole"),
    },
    "other": {
        "something else": ("MyLib:Other", None, 5.0, 5.0, "smd"),
    },
}
_PREFIX = {"connector": "J", "ic": "U", "capacitor": "C", "resistor": "R", "diode or LED": "D", "crystal": "Y", "switch": "SW", "battery": "BT", "mains or power part": "K", "other": "Z"}
_KIND_OF = {"connector": "connector", "ic": "ic", "capacitor": "passive", "resistor": "passive", "diode or LED": "passive", "crystal": "other", "switch": "other", "battery": "other", "mains or power part": "other", "other": "other"}
_REF = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,15}$")
_ROTATIONS = (0, 90, 180, 270)


class DonorCaptureError(ValueError):
    """What was typed cannot make a board."""


def _package_info(row: tuple[str, str | None, float, float, str]) -> dict[str, Any]:
    """A package's size and where the size comes from: KiCad's courtyard when the library has the footprint, else a typical value."""

    _rule_name, real, typical_w, typical_l, mounting = row
    measured = footprint_size(real) if real and libraries_available() else None
    if measured:
        return {"width_mm": measured["width_mm"], "length_mm": measured["length_mm"], "mounting": mounting, "size_source": measured["source"], "size_is_typical": False}
    return {"width_mm": typical_w, "length_mm": typical_l, "mounting": mounting, "size_source": "typical for this kind of part: no footprint in KiCad's library", "size_is_typical": True}


def capture_options() -> dict[str, Any]:
    """The kinds and packages a person can choose, with the typical size each is drawn at. The sizes are typical, not measured."""

    return {
        "schema_version": DONOR_SPEC_SCHEMA,
        "size_basis": "Where KiCad's library has the footprint, the size is its courtyard: exact for that footprint and a little larger than the part. Elsewhere it is typical. Measure the real part and overwrite it: a wrong size only changes the picture, not the advice.",
        "kinds": {
            kind: {"prefix": _PREFIX[kind], "packages": {package: _package_info(row) for package, row in packages.items()}}
            for kind, packages in _TABLE.items()
        },
    }


def _number(value: Any, label: str, low: float, high: float) -> float:
    number = finite_number(value)
    if number is None:
        raise DonorCaptureError(f"{label} must be a number")
    if not low <= number <= high:
        raise DonorCaptureError(f"{label} must be between {low:g} and {high:g}")
    return number


def _text(value: Any, label: str, limit: int, *, required: bool = False) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise DonorCaptureError(f"{label} must be text")
    value = value.strip()
    if required and not value:
        raise DonorCaptureError(f"{label} is required")
    if len(value) > limit:
        raise DonorCaptureError(f"{label} may be at most {limit} characters")
    if has_hidden_characters(value) or "\x7f" in value:
        raise DonorCaptureError(f"{label} may not contain control or invisible characters")
    return value


MAX_READINGS = 8
MAX_READING = 40


def _readings(value: Any, label: str) -> dict[str, str]:
    """What the person wrote down against each measurement: text keyed by the measurement it answers. It is kept, never interpreted."""

    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > MAX_READINGS:
        raise DonorCaptureError(f"{label} must be an object with at most {MAX_READINGS} entries")
    clean: dict[str, str] = {}
    for key, text in value.items():
        if not isinstance(key, str) or len(key) > 120 or has_hidden_characters(key):
            raise DonorCaptureError(f"{label} has a measurement name that cannot be used")
        clean[key] = _text(text, f"{label}[{key[:20]!r}]", MAX_READING)
    return clean


def validate_capture(spec: Any) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise DonorCaptureError("the capture must be an object")
    if spec.get("schema_version", DONOR_SPEC_SCHEMA) != DONOR_SPEC_SCHEMA:
        raise DonorCaptureError(f"schema_version must be {DONOR_SPEC_SCHEMA}")
    name = _text(spec.get("name", "Donor board"), "name", MAX_NAME, required=True)
    board = spec.get("board")
    if not isinstance(board, dict):
        raise DonorCaptureError("board must give width_mm and length_mm")
    width = _number(board.get("width_mm"), "board.width_mm", MIN_BOARD_MM, MAX_BOARD_MM)
    length = _number(board.get("length_mm"), "board.length_mm", MIN_BOARD_MM, MAX_BOARD_MM)
    thickness = _number(board.get("thickness_mm", 1.6), "board.thickness_mm", 0.4, 5.0)
    parts = spec.get("parts", [])
    if not isinstance(parts, list) or len(parts) > MAX_PARTS:
        raise DonorCaptureError(f"parts must be a list of at most {MAX_PARTS}")
    clean: list[dict[str, Any]] = []
    seen: set[str] = set()
    counters: dict[str, int] = {}
    for index, row in enumerate(parts):
        label = f"parts[{index}]"
        if not isinstance(row, dict):
            raise DonorCaptureError(f"{label} must be an object")
        kind = row.get("kind")
        if not isinstance(kind, str) or kind not in _TABLE:
            raise DonorCaptureError(f"{label}.kind must be one of: {', '.join(_TABLE)}")
        package = row.get("package")
        if not isinstance(package, str) or package not in _TABLE[kind]:
            raise DonorCaptureError(f"{label}.package for {kind} must be one of: {', '.join(_TABLE[kind])}")
        name_fp, _real, _typical_w, _typical_l, mounting = _TABLE[kind][package]
        info = _package_info(_TABLE[kind][package])
        typical_w, typical_l = info["width_mm"], info["length_mm"]
        ref = _text(row.get("ref"), f"{label}.ref", 16)
        if ref and not _REF.match(ref):
            raise DonorCaptureError(f"{label}.ref must be letters, digits and underscores, starting with a letter")
        if not ref:
            while True:
                counters[kind] = counters.get(kind, 0) + 1
                ref = f"{_PREFIX[kind]}{counters[kind]}"
                if ref.lower() not in seen:
                    break
        if ref.lower() in seen:
            raise DonorCaptureError(f"{label}.ref {ref!r} is used twice")
        seen.add(ref.lower())
        x = _number(row.get("x_mm"), f"{label}.x_mm", 0.0, width)
        y = _number(row.get("y_mm"), f"{label}.y_mm", 0.0, length)
        part_w = _number(row["width_mm"], f"{label}.width_mm", MIN_PART_MM, MAX_PART_MM) if row.get("width_mm") is not None else typical_w
        part_l = _number(row["length_mm"], f"{label}.length_mm", MIN_PART_MM, MAX_PART_MM) if row.get("length_mm") is not None else typical_l
        rotation = row.get("rotation_deg", 0)
        if isinstance(rotation, bool) or rotation not in _ROTATIONS:
            raise DonorCaptureError(f"{label}.rotation_deg must be 0, 90, 180 or 270")
        side = row.get("side", "front")
        if not isinstance(side, str) or side not in ("front", "back"):
            raise DonorCaptureError(f"{label}.side must be front or back")
        marking = _text(row.get("marking"), f"{label}.marking", MAX_MARKING)
        readings = _readings(row.get("readings"), f"{label}.readings")
        clean.append(
            {"ref": ref, "kind": kind, "package": package, "footprint": name_fp, "mounting": mounting, "x": x, "y": y, "w": part_w, "l": part_l,
             "sized_by_you": row.get("width_mm") is not None or row.get("length_mm") is not None, "size_source": info["size_source"], "size_is_typical": info["size_is_typical"], "rotation": int(rotation), "side": side, "marking": marking, "readings": readings}
        )
    return {"name": name, "width": width, "length": length, "thickness": thickness, "parts": clean}


def _r(value: float) -> float:
    return round(float(value), 3) + 0.0


def _corners(x: float, y: float, w: float, l: float, rotation: int) -> list[list[float]]:
    half_w, half_l = (w / 2, l / 2) if rotation in (0, 180) else (l / 2, w / 2)
    # c0 -> c1 runs along the part's own x axis, as the build sequence expects.
    return [[_r(x - half_w), _r(y - half_l)], [_r(x + half_w), _r(y - half_l)], [_r(x + half_w), _r(y + half_l)], [_r(x - half_w), _r(y + half_l)]]


def capture_to_assembly(spec: Any) -> dict[str, Any]:
    """The assembly-plan shape for a typed board, so everything that reads a plan reads this."""

    clean = validate_capture(spec)
    parts: list[dict[str, Any]] = []
    for row in clean["parts"]:
        kind = _KIND_OF[row["kind"]]            # what the person chose decides how the part is treated, never its reference label
        height, basis = _height(row["footprint"], kind)
        parts.append(
            {
                "id": row["ref"], "ref": row["ref"], "value": row["marking"], "footprint": row["footprint"], "kind": kind, "side": row["side"],
                "x": _r(row["x"]), "y": _r(row["y"]), "rotation_deg": float(row["rotation"]),
                "corners": _corners(row["x"], row["y"], row["w"], row["l"], row["rotation"]),
                "outline_basis": "the size you typed" if row["sized_by_you"] else (f"typical size for a {row['package']} (you did not measure it)" if row["size_is_typical"] else f"KiCad library courtyard for a {row['package']} (you did not measure it): a little larger than the part"),
                "height_mm": _r(height), "height_basis": basis, "pin1": None, "pad_count": 0, "do_not_populate": False,
                "mounting": row["mounting"], "component": row["kind"],
                "identity": {"mpn": None, "manufacturer": None, "typed": row["marking"] or None, "source": "typed"},
                "readings": row["readings"],
                "pads": [],
            }
        )
    return {
        "source": {"pcb_sha256": None, "typed": True},
        "board": {
            "thickness_mm": clean["thickness"], "thickness_basis": "typed by you",
            "outline": {"kind": "rectangle", "bbox": {"x0": 0.0, "y0": 0.0, "x1": _r(clean["width"]), "y1": _r(clean["length"])}},
            "size_mm": [_r(clean["width"]), _r(clean["length"])],
        },
        "parts": parts,
        "not_fitted": [],
        "warnings": [],
        "name": clean["name"],
    }


def build_donor_salvage_plan(spec: Any) -> dict[str, Any]:
    """The take-apart plan for a board a person described. Pure: no I/O."""

    try:
        base = capture_to_assembly(spec)
        plan = plan_from_assembly(base, typed=True)
    except SalvagePlanError as exc:
        raise DonorCaptureError(str(exc)) from exc
    plan["name"] = base["name"]
    return plan
