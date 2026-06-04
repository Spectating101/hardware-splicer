from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from ..spec import (
    BeltReductionSpec,
    BracketSpec,
    EnclosureSpec,
    GripperSpec,
    LeadScrewAxisSpec,
    LinearAxisSpec,
    PanTiltSpec,
    ProjectSpec,
    RotaryJointSpec,
    ServoMountSpec,
)


@dataclass(frozen=True)
class BomLine:
    category: str
    item: str
    spec: str
    qty: int
    notes: str = ""
    sku: str = ""

    def to_dict(self):
        return asdict(self)


def _thread(f: Literal["m2", "m2.5", "m3"]) -> str:
    return f.upper()


def _suggest_screw_length_mm(enc: EnclosureSpec) -> int:
    base = enc.floor_mm + enc.lid_mm + 6.0
    if base < 10:
        return 10
    if base < 12:
        return 12
    if base < 16:
        return 16
    return 20


def build_bom(spec: ProjectSpec) -> list[BomLine]:
    lines: list[BomLine] = []

    if spec.enclosure:
        thread = _thread(spec.enclosure.fastener)
        qty = max(4, len(spec.enclosure.mount_holes) or 4)
        screw_len = _suggest_screw_length_mm(spec.enclosure)
        lines.append(BomLine("fastener", f"{thread} screws", f"{thread}×{screw_len}", qty, "lid + standoffs", sku=f"{spec.enclosure.fastener}_screw_assorted"))
        lines.append(
            BomLine(
                "fastener",
                f"{thread} heat-set inserts",
                f"{thread} heat-set",
                qty,
                "recommended",
                sku=f"{spec.enclosure.fastener}_heatset_inserts_100",
            )
        )
        lines.append(BomLine("hardware", "rubber feet", "self-adhesive", 4, "reduces desk rattle", sku="rubber_feet_20"))

    if spec.bracket:
        lines.extend(_bom_for_bracket(spec.bracket))

    if spec.servo_mount:
        lines.extend(_bom_for_servo_mount(spec.servo_mount))

    if spec.linear_axis:
        lines.extend(_bom_for_linear_axis(spec.linear_axis))

    if spec.leadscrew_axis:
        lines.extend(_bom_for_leadscrew_axis(spec.leadscrew_axis))

    if spec.rotary_joint:
        lines.extend(_bom_for_rotary_joint(spec.rotary_joint))

    if spec.belt_reduction:
        lines.extend(_bom_for_belt_reduction(spec.belt_reduction))

    if spec.gripper:
        lines.extend(_bom_for_gripper(spec.gripper))

    if spec.pan_tilt:
        lines.extend(_bom_for_pan_tilt(spec.pan_tilt))

    return lines


def _bom_for_bracket(br: BracketSpec) -> list[BomLine]:
    thread = "M3"
    return [
        BomLine("fastener", f"{thread} screws", f"{thread}×12", 2, "mount bracket", sku="m3_screw_assorted"),
        BomLine("fastener", f"{thread} nuts", f"{thread} hex", 2, "if not threading into material", sku=""),
        BomLine("fastener", f"{thread} washers", f"{thread}", 2, "spreads load", sku=""),
    ]


def _bom_for_servo_mount(sm: ServoMountSpec) -> list[BomLine]:
    # Conservative: SG90 often uses small self-tapping; MG996R often uses M3-ish. Treat as a placeholder.
    if sm.servo_type == "sg90":
        return [
            BomLine("fastener", "servo screws", "M2 self-tapping (check servo)", 4, "mount servo to plate", sku=""),
            BomLine("hardware", "rubber feet", "self-adhesive", 4, "optional for desk stability", sku="rubber_feet_20"),
        ]
    return [
        BomLine("fastener", "servo screws", "M3 (check servo)", 4, "mount servo to plate", sku="m3_screw_assorted"),
        BomLine("fastener", "washers", "M3", 4, "optional", sku=""),
    ]


def _bom_for_linear_axis(ax: LinearAxisSpec) -> list[BomLine]:
    # Common GT2 linear axis components; placeholders intended for locking later.
    rod_qty = 2
    bearing_qty = 4 if ax.use_linear_bearings else 0  # LM8UU-style on a 2-rod carriage
    belt_len_mm = int(max(600, ax.rod_length_mm * 2))
    lines = [
        BomLine("motion", "smooth rod", f"{ax.rod_d_mm}mm × {ax.rod_length_mm}mm", rod_qty, "steel recommended", sku=""),
        BomLine("motion", "linear bearing", f"LM{int(ax.rod_d_mm)}UU (or printed bushings)", bearing_qty, "carriage", sku=""),
        BomLine("motion", "GT2 belt", f"{ax.belt_width_mm}mm width, {belt_len_mm}mm length", 1, "cut to fit", sku=""),
        BomLine("motion", "GT2 pulley", f"{ax.pulley_teeth}T, 5mm bore", 1, "motor shaft", sku=""),
        BomLine("motion", "idler pulley", f"GT2 idler, {ax.belt_width_mm}mm", 1, "tensioner", sku=""),
        BomLine("motion", "stepper motor", "NEMA17 (17HS) class", 1, "drive", sku=""),
        BomLine("fastener", "M3 screws", "assorted", 1, "mounts + carriage", sku="m3_screw_assorted"),
        BomLine("hardware", "endstop switch", "micro-switch", 1 if ax.include_endstops else 0, "limit sensing", sku=""),
    ]

    if ax.frame == "2020_extrusion":
        # Common motion frame choice: 2× 2020 extrusions.
        lines.append(BomLine("frame", "2020 extrusion", f"{ax.frame_length_mm}mm length", 2, "rigid base rails", sku=""))
        lines.append(BomLine("frame", "T-nuts", "M5 for 2020", 8, "mount printed parts", sku=""))
        lines.append(BomLine("fastener", "M5 screws", "M5×10", 8, "for T-nuts", sku=""))

    if ax.include_rod_holders:
        # 4 holders for 2 rods (2 ends)
        lines.append(BomLine("hardware", "rod holders", "printed", 4, "print `rod_holder.scad`", sku=""))
        lines.append(BomLine("fastener", "M3 nuts", "hex", 8, "rod holder clamp", sku=""))
        lines.append(BomLine("fastener", "M3 screws", "M3×16", 8, "rod holder clamp", sku="m3_screw_assorted"))

    return lines


def _bom_for_leadscrew_axis(ax: LeadScrewAxisSpec) -> list[BomLine]:
    # Common T8 leadscrew axis components; placeholders intended for locking later.
    rod_qty = 2
    bearing_qty = 4  # LM8UU-style on a 2-rod carriage (v1 default)
    lines = [
        BomLine("motion", "smooth rod", f"{ax.rod_d_mm}mm × {ax.rod_length_mm}mm", rod_qty, "steel recommended", sku=""),
        BomLine("motion", "linear bearing", f"LM{int(ax.rod_d_mm)}UU (or printed bushings)", bearing_qty, "carriage guidance", sku=""),
        BomLine("motion", "lead screw", f"{ax.screw_d_mm}mm × {ax.screw_length_mm}mm (T8)", 1, "match lead + length", sku=""),
        BomLine("motion", "lead screw nut", "T8 brass nut", 1, "carriage mount", sku=""),
        BomLine("motion", "flexible coupler", "5mm→8mm", 1, "NEMA17 shaft to T8", sku=""),
        BomLine("motion", "bearing", "608ZZ (8×22×7)", 2, "end support (optional but recommended)", sku=""),
        BomLine("motion", "stepper motor", "NEMA17 (17HS) class", 1, "drive", sku=""),
        BomLine("fastener", "M3 screws", "assorted", 1, "mounts + carriage", sku="m3_screw_assorted"),
        BomLine("hardware", "endstop switch", "micro-switch", 1 if ax.include_endstops else 0, "limit sensing", sku=""),
    ]

    if ax.frame == "2020_extrusion":
        lines.append(BomLine("frame", "2020 extrusion", f"{ax.frame_length_mm}mm length", 2, "rigid base rails", sku=""))
        lines.append(BomLine("frame", "T-nuts", "M5 for 2020", 8, "mount printed parts", sku=""))
        lines.append(BomLine("fastener", "M5 screws", "M5×10", 8, "for T-nuts", sku=""))

    if ax.include_rod_holders:
        lines.append(BomLine("hardware", "rod holders", "printed", 4, "print `rod_holder.scad`", sku=""))
        lines.append(BomLine("fastener", "M3 nuts", "hex", 8, "rod holder clamp", sku=""))
        lines.append(BomLine("fastener", "M3 screws", "M3×16", 8, "rod holder clamp", sku="m3_screw_assorted"))

    return lines


def _bom_for_rotary_joint(j: RotaryJointSpec) -> list[BomLine]:
    bearing_label = "608ZZ (8×22×7)" if j.bearing == "608zz" else "625ZZ (5×16×5)"
    shaft_label = f"{j.shaft_d_mm}mm shaft/bolt"
    # Conservative: users often mount joints with M3 into a plate or 2020.
    return [
        BomLine("motion", "bearing", bearing_label, 1, "rotary joint support", sku=""),
        BomLine("motion", "shaft", shaft_label, 1, "must match bearing ID", sku=""),
        BomLine("fastener", "M3 screws", "assorted", 1, "mount block + arm", sku="m3_screw_assorted"),
        BomLine("fastener", "M3 nuts", "hex", 6, "if not threading into material", sku=""),
        BomLine("fastener", "washers", "M3", 6, "optional", sku=""),
    ]


def _bom_for_belt_reduction(s: BeltReductionSpec) -> list[BomLine]:
    # Prototype-grade BOM; assumes you buy pulleys and use 625 bearings for shafts/idlers.
    ratio = f"{s.driven_pulley_teeth}/{s.motor_pulley_teeth}"
    return [
        BomLine("motion", "GT2 pulley (motor)", f"{s.motor_pulley_teeth}T, 5mm bore", 1, f"ratio {ratio}", sku=""),
        BomLine("motion", "GT2 pulley (driven)", f"{s.driven_pulley_teeth}T, 5mm bore", 1, f"ratio {ratio}", sku=""),
        BomLine("motion", "bearing", "625ZZ (5×16×5)", 2 + (1 if s.include_idler else 0), "driven + idler support", sku=""),
        BomLine("motion", "shaft", "5mm shaft/bolt", 1 + (1 if s.include_idler else 0), "for bearings", sku=""),
        BomLine("motion", "GT2 belt", f"{s.belt_width_mm}mm width (length per center distance)", 1, "pick length after layout", sku=""),
        BomLine("motion", "stepper motor", "NEMA17 (17HS) class", 1, "drive", sku=""),
        BomLine("fastener", "M3 screws", "assorted", 1, "mount plate to frame", sku="m3_screw_assorted"),
    ]


def _bom_for_gripper(g: GripperSpec) -> list[BomLine]:
    servo_label = "SG90" if g.servo_type == "sg90" else "MG996R"
    return [
        BomLine("actuator", "servo", servo_label, 1, "gripper drive", sku=""),
        BomLine("fastener", "M3 screws", "assorted", 1, "jaw pivots + linkage", sku="m3_screw_assorted"),
        BomLine("fastener", "M3 nuts", "hex", 8, "pivot + linkage", sku=""),
        BomLine("fastener", "washers", "M3", 8, "reduce friction", sku=""),
    ]


def _bom_for_pan_tilt(pt: PanTiltSpec) -> list[BomLine]:
    pan = "SG90" if pt.pan_servo == "sg90" else "MG996R"
    tilt = "SG90" if pt.tilt_servo == "sg90" else "MG996R"
    return [
        BomLine("actuator", "servo (pan)", pan, 1, "base rotation", sku=""),
        BomLine("actuator", "servo (tilt)", tilt, 1, "tilt axis", sku=""),
        BomLine("fastener", "M3 screws", "assorted", 1, "mount plates/brackets", sku="m3_screw_assorted"),
        BomLine("fastener", "M3 nuts", "hex", 8, "mounting", sku=""),
    ]
