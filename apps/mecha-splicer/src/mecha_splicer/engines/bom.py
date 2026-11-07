from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from ..spec import (
    BeltReductionSpec,
    BracketSpec,
    ClamshellTerminalSpec,
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
    if spec.clamshell_terminal:
        lines.extend(_bom_for_clamshell_terminal(spec.clamshell_terminal))

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


def _bom_for_clamshell_terminal(p: ClamshellTerminalSpec) -> list[BomLine]:
    """Prototype budget inventory, not ordered or wired."""
    if p.input_surface_mode == "dual_touch" and p.compute_architecture == "cm4_dual_dsi":
        return [
            BomLine("compute", "Raspberry Pi CM4102000 wireless Lite 2GB", "55x40mm CM4 with 1.5mm option mated stack 5.078mm", 1,
                "No eMMC; budget for SD interface, radio antenna clearance, and real 5V power", sku="CM4102000"),
            BomLine("display", "Winstar WF50DTYA3MNG10-000", "127.6x73.3x3.45mm 2-lane DSI projected capacitive touch", 2,
                "GT928 + ILI9881C: dual Linux device-tree, exact panel timing and power drivers unverified", sku="WF50DTYA3MNG10-000"),
            BomLine("electronics", "custom CM4 dual-DSI carrier", "nominal 0.8mm PCB with 2x100-pin 0.4mm-pitch mating", 1,
                "Real DSI0/DSI1 differential routing, touch I2C, SD, Wi-Fi keepout and both backlights required", sku=""),
            BomLine("power", "protected battery and charger", "80x50x6mm naked cell placeholder, NOT approved pack", 1,
                "Swelling, protection, BMS, 5V boost, backlight rail and actual capacity unqualified", sku=""),
            BomLine("hardware", "mechanical hinge and two display ribbon cables", "hinge FPC bend radius, EMI, connector and fatigue unqualified", 1,
                "No hinge flex validated. DO NOT route MIPI DSI as ordinary GPIO jumpers", sku=""),
            BomLine("printed", "CM4 dual-touch lower enclosure", "HS native Mecha-Splicer shell, FDM 1.6mm floor", 1,
                "1mm nominal clearance is a research assumption, not manufacturing tolerance", sku=""),
            BomLine("printed", "CM4 dual-touch upper enclosure", "HS native Mecha-Splicer shell, FDM 1.6mm floor", 1,
                "No internal LCD PCB mounting, FPC relief or real lid closing test", sku=""),
        ]
    if p.input_surface_mode == "dual_touch" and p.compute_architecture == "cm5_dual_dsi":
        return [
            BomLine("compute", "Radxa CM5 V2.21", "56x41mm SoM; board-to-board mating stack not qualified", 1,
                "Candidate only; processor carrier / power sequencing and PCB not validated", sku="Radxa_CM5_V2.21"),
            BomLine("display", "Winstar WF50DTYA3MNG10-000", "127.6x73.3x3.45mm 2-lane MIPI DSI capacitive touch", 2,
                "Unverified Linux panel drivers, touch I2C topology and FPC bend; not ordered", sku="WF50DTYA3MNG10-000"),
            BomLine("electronics", "custom CM5 carrier", "nominal 0.8mm PCB; NO routed copper or footprint approval", 1,
                "Must qualify 200+100-pad mating connectors and 5V-to-4V supply", sku=""),
            BomLine("power", "protected pouch cell and charging path", "80x50x6mm nominal naked placeholder", 1,
                "Cell protection/BMS, swelling, thermal and charger not designed", sku=""),
            BomLine("thermal", "CM5 heat spreader", "0.5mm unverified thermal pad/plate", 1,
                "No measured thermal resistance or usable 18mm proof", sku=""),
            BomLine("hardware", "hinge + rated display FPC", f"{p.hinge_pin_d_mm}mm hinge pin, bend radius unqualified", 1,
                "Actual flex tail extends beyond shell if straight; cycles and strain relief not proven", sku=""),
            BomLine("printed", "CM5 dual-touch lower enclosure", "Native Mecha-Splicer shell, not fit qualified", 1,
                "Requires real mounts, PCB, battery clearance", sku=""),
            BomLine("printed", "CM5 dual-touch upper enclosure", "Native Mecha-Splicer shell, not fit qualified", 1,
                "Requires actual panel retention, display connector route", sku=""),
        ]
    if p.input_surface_mode == "dual_touch":
        return [
            BomLine("electronics", "Waveshare ESP32-S3-Touch-LCD-4.3", "ESP32-S3 N16R8, 800x480 touch 106.1x67.8mm", 2,
                "One per clamshell half. SP3485 RS485 transceiver onboard; full PCB Z/ports not yet measured", sku="ESP32-S3-Touch-LCD-4.3"),
            BomLine("wiring", "RS485 differential pair + verified common reference", "2-wire A/B HY2.0 2P plus safe shared power ground", 1,
                "Two on-board SP3485; verify A/B polarity, half-duplex timing, 120-ohm termination and ground. No loose 5V GPIO wiring", sku=""),
            BomLine("wiring", "Hinge flexible wire and protection", "RS485 + potential 5V/GND power cable; test flex radius", 1,
                "Mechanical cable passage is a concept, NOT fatigue/lid-cycle proven", sku=""),
            BomLine("hardware", "steel hinge pin", f"{p.hinge_pin_d_mm}mm diameter, ~{p.case_w_mm}mm long", 1,
                "Test retention and tolerance after printing; no plastic hinge pin", sku=""),
            BomLine("printed", "dual-touch keyboard-half base tray", "PETG base_shell.stl", 1,
                "Second LCD rather than CardKB; module mount/USB access absent", sku=""),
            BomLine("printed", "dual-touch upper display lid tray", "PETG lid_shell.stl", 1,
                "Upper LCD module mount/USB access absent", sku=""),
            BomLine("power", "USB-powered dual-prototype supply", "5V 2A or higher verified, two USB-C power leads", 1,
                "Power both boards through their designated USB inputs for first bench only; no shared battery wiring approved", sku=""),
            BomLine("power", "optional protected Li-ion cells", "3.7V single cell PER board, PH2.0 polarity to verify", 0,
                "Not included; do not parallel two on-board charger outputs", sku=""),
        ]
    return [
        BomLine("electronics", "Waveshare ESP32-S3-Touch-LCD-4.3",
                "4.3 inch 800x480, N16R8, 106.1x67.8mm touch version", 1,
                "Built-in CS8501 lithium charger; mounting Z/holes unknown", sku="ESP32-S3-Touch-LCD-4.3"),
        BomLine("electronics", "M5Stack CardKB v1.1",
                "88x54x5mm 50-key QWERTY I2C @0x5F; 5V", 1,
                "Verify Ctrl/Esc terminal key semantics and pin voltages", sku="U035-B"),
        BomLine("electrical", "I2C bidirectional voltage level shifter",
                "2-channel 3.3V to 5V, SDA/SCL", 1,
                "Selection provisional; no ESP32 pins exposed to 5V until proven", sku=""),
        BomLine("wiring", "4-conductor flexible hinged harness", "SDA/SCL/5V/GND", 1,
                "Need connector pinout, strain relief, bend radius and 5V availability checks", sku=""),
        BomLine("hardware", "steel hinge pin", f"{p.hinge_pin_d_mm}mm diameter approx. {p.case_w_mm}mm long",
                1, "Retention and cycling unverified; use metal not printed plastic", sku=""),
        BomLine("printed", "clamshell keyboard tray", "PETG base_shell.stl", 1,
                "Keyboard retention/fasteners not finished", sku=""),
        BomLine("printed", "clamshell LCD lid tray", "PETG lid_shell.stl", 1,
                "Mounting screw and USB cutouts not designed until measured", sku=""),
        BomLine("power", "USB-C 5V external supply", "5V >=1A, vendor input only", 1,
                "Battery intentionally deferred for first safe bring-up", sku=""),
        BomLine("power", "optional protected single-cell Li-ion pack", "3.7V, PH2.0 polarity to verify",
                0, "No selected cell or validated battery fit/thermal", sku=""),
    ]


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
