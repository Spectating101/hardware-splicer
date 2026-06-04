from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import math

from ..spec import (
    AssemblySpec,
    BeltReductionSpec,
    BracketSpec,
    EnclosureSpec,
    GripperSpec,
    LeadScrewAxisSpec,
    LinearAxisSpec,
    PanTiltSpec,
    PrintSettings,
    ProjectSpec,
    RotaryJointSpec,
    ServoMountSpec,
)
from .bearing_library import get_bearing_dims
from .servo_library import get_servo_dims, torque_nm


@dataclass(frozen=True)
class DfmIssue:
    severity: Literal["info", "warn", "block"]
    message: str


def _min_wall_mm(process: str) -> float:
    return 1.6 if process == "fdm" else 1.0


def check_project(spec: ProjectSpec) -> list[DfmIssue]:
    issues: list[DfmIssue] = []

    if (
        spec.enclosure is None
        and spec.bracket is None
        and spec.servo_mount is None
        and spec.linear_axis is None
        and spec.leadscrew_axis is None
        and spec.rotary_joint is None
        and spec.belt_reduction is None
        and spec.gripper is None
        and spec.pan_tilt is None
        and spec.assembly is None
    ):
        issues.append(
            DfmIssue(
                "block",
                "Spec must include at least one of: enclosure, bracket, servo_mount, linear_axis, leadscrew_axis, rotary_joint, belt_reduction, gripper, pan_tilt, assembly.",
            )
        )
        return issues

    if spec.enclosure is not None:
        issues.extend(check_enclosure(spec.enclosure, process=spec.process, mode=spec.mode))
    if spec.bracket is not None:
        issues.extend(check_bracket(spec.bracket, process=spec.process, mode=spec.mode))
    if spec.servo_mount is not None:
        issues.extend(check_servo_mount(spec.servo_mount, process=spec.process, mode=spec.mode))
    if spec.linear_axis is not None:
        issues.extend(check_linear_axis(spec.linear_axis, process=spec.process, mode=spec.mode))
    if spec.leadscrew_axis is not None:
        issues.extend(check_leadscrew_axis(spec.leadscrew_axis, process=spec.process, mode=spec.mode))
    if spec.rotary_joint is not None:
        issues.extend(check_rotary_joint(spec.rotary_joint, process=spec.process, mode=spec.mode))
    if spec.belt_reduction is not None:
        issues.extend(check_belt_reduction(spec.belt_reduction, process=spec.process, mode=spec.mode))
    if spec.gripper is not None:
        issues.extend(check_gripper(spec.gripper, process=spec.process, mode=spec.mode))
    if spec.pan_tilt is not None:
        issues.extend(check_pan_tilt(spec.pan_tilt, process=spec.process, mode=spec.mode))
    if spec.assembly is not None:
        issues.extend(check_assembly(spec.assembly, mode=spec.mode))
    if spec.print_settings is not None:
        issues.extend(check_print_settings(spec.print_settings, mode=spec.mode))

    return issues


def check_enclosure(enc: EnclosureSpec, *, process: str, mode: str) -> list[DfmIssue]:
    issues: list[DfmIssue] = []

    if enc.wall_mm < _min_wall_mm(process):
        issues.append(DfmIssue("warn", f"wall_mm={enc.wall_mm:.2f} is thin; consider >= {_min_wall_mm(process):.2f}mm."))

    if enc.clearance_mm < 0.2:
        issues.append(DfmIssue("warn", f"clearance_mm={enc.clearance_mm:.2f} is tight; consider 0.3–0.6mm."))

    outer_w = enc.inner_w_mm + 2 * enc.wall_mm
    outer_d = enc.inner_d_mm + 2 * enc.wall_mm
    if outer_w <= 0 or outer_d <= 0:
        issues.append(DfmIssue("block", "Invalid enclosure dimensions after wall thickness."))

    if mode == "professional":
        if enc.wall_mm < 2.0:
            issues.append(DfmIssue("info", "Professional mode: consider thicker walls (>=2.0mm)."))
        if enc.lid_style == "snap":
            issues.append(DfmIssue("warn", "Professional mode: snap lids are sensitive; screw lid is safer."))

    for c in enc.cutouts:
        if c.kind == "rect" and c.rect:
            if c.rect.w_mm < 2.0 or c.rect.h_mm < 2.0:
                issues.append(DfmIssue("warn", f"Cutout '{c.label}' is very small; may be fragile."))
        if c.kind == "circle" and c.circle:
            if c.circle.d_mm < 2.0:
                issues.append(DfmIssue("warn", f"Cutout '{c.label}' diameter is very small; may be fragile."))

    # Standoff sanity (edge distance)
    if enc.include_standoffs and enc.mount_holes:
        min_edge = max(1.5, enc.wall_mm)
        for mh in enc.mount_holes:
            if mh.x_mm < min_edge or mh.y_mm < min_edge or mh.x_mm > (enc.inner_w_mm - min_edge) or mh.y_mm > (enc.inner_d_mm - min_edge):
                issues.append(DfmIssue("warn", "A mount hole is very close to enclosure inner edge; standoff may collide with wall."))

        if enc.standoff_od_mm < enc.standoff_hole_d_mm + 2.0:
            issues.append(DfmIssue("warn", "standoff_od_mm is small relative to hole; standoff may crack."))

    return issues


def check_bracket(br: BracketSpec, *, process: str, mode: str) -> list[DfmIssue]:
    issues: list[DfmIssue] = []

    if br.t_mm < _min_wall_mm(process):
        issues.append(DfmIssue("warn", f"t_mm={br.t_mm:.2f} is thin; consider >= {_min_wall_mm(process):.2f}mm."))

    if br.hole_d_mm < 2.0:
        issues.append(DfmIssue("warn", f"hole_d_mm={br.hole_d_mm:.2f} is tiny; check fastener choice."))

    if br.hole_spacing_mm > br.w_mm:
        issues.append(DfmIssue("block", "hole_spacing_mm exceeds bracket width; holes would be outside the part."))

    if mode == "professional" and br.t_mm < 4.0:
        issues.append(DfmIssue("info", "Professional mode: consider 4–6mm thickness for stiffness."))

    return issues


def check_servo_mount(sm: ServoMountSpec, *, process: str, mode: str) -> list[DfmIssue]:
    issues: list[DfmIssue] = []
    if sm.plate_t_mm < _min_wall_mm(process):
        issues.append(DfmIssue("warn", f"plate_t_mm={sm.plate_t_mm:.2f} is thin; consider >= {_min_wall_mm(process):.2f}mm."))
    if sm.clearance_mm < 0.3:
        issues.append(DfmIssue("warn", f"clearance_mm={sm.clearance_mm:.2f} is tight; consider 0.4–0.8mm."))
    if sm.hole_d_mm < 1.8:
        issues.append(DfmIssue("warn", f"hole_d_mm={sm.hole_d_mm:.2f} is tiny; may print undersized."))
    if mode == "professional" and sm.plate_t_mm < 6.0:
        issues.append(DfmIssue("info", "Professional mode: consider 6–8mm plate thickness for stiffness."))
    return issues


def check_linear_axis(ax: LinearAxisSpec, *, process: str, mode: str) -> list[DfmIssue]:
    issues: list[DfmIssue] = []

    if ax.travel_mm > ax.rod_length_mm - 80.0:
        issues.append(DfmIssue("block", "travel_mm is too close to rod_length_mm; not enough room for mounts + carriage."))

    if ax.rod_spacing_mm < ax.rod_d_mm + 10.0:
        issues.append(DfmIssue("block", "rod_spacing_mm too small; carriage will collide / be weak."))

    if ax.clearance_mm < 0.3:
        issues.append(DfmIssue("warn", f"clearance_mm={ax.clearance_mm:.2f} is tight for printed bearings/bores; consider 0.4–0.8mm."))

    # Very rough load sanity: rod deflection at midspan (steel rods)
    # delta = F*L^3 / (48*E*I)
    E = 200e9  # Pa
    d = ax.rod_d_mm / 1000.0
    L = ax.rod_length_mm / 1000.0
    I = math.pi * d**4 / 64.0
    F = ax.payload_n
    if I > 0:
        delta = (F * (L**3)) / (48.0 * E * I)  # meters
        delta_mm = delta * 1000.0
        if delta_mm > 0.75:
            issues.append(DfmIssue("warn", f"Estimated rod deflection ~{delta_mm:.2f}mm (midspan). Consider thicker/shorter rods or support."))
        else:
            issues.append(DfmIssue("info", f"Estimated rod deflection ~{delta_mm:.2f}mm (midspan, steel assumption)."))

    # Rough torque requirement: T = F * r
    # GT2 pitch 2mm, pulley teeth => circumference = teeth*2mm, radius = C/(2*pi)
    pitch_mm = 2.0
    r_m = (ax.pulley_teeth * pitch_mm / 1000.0) / (2.0 * math.pi)
    T = F * r_m  # N*m
    # Typical NEMA17 usable torque depends; 0.4N*m is a common ballpark.
    if T > 0.35:
        issues.append(DfmIssue("warn", f"Estimated torque {T:.2f} N·m may exceed typical NEMA17 margins. Reduce load or increase mechanical advantage."))
    else:
        issues.append(DfmIssue("info", f"Estimated torque {T:.2f} N·m (pulley {ax.pulley_teeth}T, load-only)."))

    # Add acceleration component: F_total = F_load + m*a
    # payload_n is force already; approximate payload mass from force (m=F/g).
    g = 9.81
    m = (ax.payload_n / g)
    a = ax.target_accel_mm_s2 / 1000.0
    F_acc = m * a
    F_total = ax.payload_n + F_acc
    T_total = F_total * r_m
    issues.append(DfmIssue("info", f"Accel estimate: a={ax.target_accel_mm_s2:.0f} mm/s² → +{F_acc:.2f}N, torque≈{T_total:.2f} N·m (very rough)."))
    if T_total > 0.45:
        issues.append(DfmIssue("warn", "Torque incl. accel looks high; expect missed steps unless you lower accel/load or increase torque margin."))

    if ax.frame == "none":
        issues.append(DfmIssue("warn", "frame=none: this only generates printable parts; you still need a rigid frame (2020 extrusion or plate)."))

    if mode == "professional" and ax.wall_mm < 3.0:
        issues.append(DfmIssue("info", "Professional mode: consider wall_mm >= 3.0 for motor/idler mount stiffness."))

    return issues


def check_leadscrew_axis(ax: LeadScrewAxisSpec, *, process: str, mode: str) -> list[DfmIssue]:
    issues: list[DfmIssue] = []

    # Geometry sanity
    if ax.travel_mm > ax.screw_length_mm - 80.0:
        issues.append(DfmIssue("block", "travel_mm is too close to screw_length_mm; not enough room for mounts + nut carriage."))
    if ax.travel_mm > ax.rod_length_mm - 80.0:
        issues.append(DfmIssue("block", "travel_mm is too close to rod_length_mm; not enough room for mounts + carriage."))
    if ax.rod_spacing_mm < ax.rod_d_mm + 10.0:
        issues.append(DfmIssue("block", "rod_spacing_mm too small; carriage will collide / be weak."))
    if ax.clearance_mm < 0.3:
        issues.append(DfmIssue("warn", f"clearance_mm={ax.clearance_mm:.2f} is tight for printed bores; consider 0.4–0.8mm."))

    # Rough load sanity: rod deflection (steel rods assumption)
    E = 200e9  # Pa
    d = ax.rod_d_mm / 1000.0
    L = ax.rod_length_mm / 1000.0
    I = math.pi * d**4 / 64.0
    F = ax.payload_n
    if I > 0:
        delta = (F * (L**3)) / (48.0 * E * I)  # meters
        delta_mm = delta * 1000.0
        if delta_mm > 0.75:
            issues.append(DfmIssue("warn", f"Estimated rod deflection ~{delta_mm:.2f}mm (midspan). Consider thicker/shorter rods or support."))
        else:
            issues.append(DfmIssue("info", f"Estimated rod deflection ~{delta_mm:.2f}mm (midspan, steel assumption)."))

    # Speed sanity (lead-screw rpm)
    lead = ax.lead_mm_per_rev
    rpm = (ax.target_speed_mm_s / lead) * 60.0 if lead > 0 else 0.0
    issues.append(DfmIssue("info", f"Target speed {ax.target_speed_mm_s:.1f} mm/s @ lead {lead:.1f} mm/rev → ~{rpm:.0f} rpm (very rough)."))
    if rpm > 1200:
        issues.append(DfmIssue("warn", "Leadscrew rpm is high; whip/backlash/heating likely unless screw is well supported/aligned."))
    elif rpm > 800:
        issues.append(DfmIssue("info", "Leadscrew rpm is moderate-high; ensure good support and alignment to avoid whip."))

    # Rough torque estimate: T = F * lead / (2π * efficiency)
    # Efficiency is low for trapezoidal/ACME screws; use conservative placeholder.
    eff = 0.35
    g = 9.81
    m = (ax.payload_n / g)
    a = ax.target_accel_mm_s2 / 1000.0
    F_acc = m * a
    F_total = ax.payload_n + F_acc
    lead_m = lead / 1000.0
    T_total = (F_total * lead_m) / (2.0 * math.pi * max(0.05, eff))
    issues.append(DfmIssue("info", f"Accel estimate: a={ax.target_accel_mm_s2:.0f} mm/s² → +{F_acc:.2f}N, torque≈{T_total:.2f} N·m (very rough)."))
    if T_total > 0.45:
        issues.append(DfmIssue("warn", "Torque estimate incl. accel looks high for a typical NEMA17; expect missed steps unless you reduce load/accel or use gearing/stronger motor."))
    elif T_total > 0.35:
        issues.append(DfmIssue("info", "Torque estimate is near common NEMA17 margins; tune accel/current conservatively."))

    if ax.screw_length_mm > 400.0 and rpm > 600:
        issues.append(DfmIssue("warn", "Long leadscrew + higher rpm increases whip risk; shorten screw, add support, or reduce speed."))

    if ax.frame == "none":
        issues.append(DfmIssue("warn", "frame=none: this only generates printable parts; you still need a rigid aligned frame (2020 extrusion or plate)."))

    if mode == "professional" and ax.wall_mm < 3.0:
        issues.append(DfmIssue("info", "Professional mode: consider wall_mm >= 3.0 for motor/end support stiffness."))

    return issues


def check_print_settings(ps: PrintSettings, *, mode: str) -> list[DfmIssue]:
    issues: list[DfmIssue] = []
    if ps.perimeters < 3:
        issues.append(DfmIssue("warn", "perimeters < 3 is weak for functional parts; consider 4+ for mounts/mechanisms."))
    if ps.infill_pct < 20:
        issues.append(DfmIssue("warn", "infill_pct < 20% is often too weak for functional parts."))
    if ps.material == "PLA" and mode == "professional":
        issues.append(DfmIssue("warn", "PLA creeps/softens; for professional/long-life parts consider PETG/ABS/Nylon."))
    if ps.orientation == "strong_in_z":
        issues.append(DfmIssue("info", "Orientation strong_in_z reduces delamination risk but may worsen XY stiffness; verify load direction."))
    return issues


def check_rotary_joint(j: RotaryJointSpec, *, process: str, mode: str) -> list[DfmIssue]:
    issues: list[DfmIssue] = []
    b = get_bearing_dims(j.bearing)

    if abs(j.shaft_d_mm - b.id_mm) > 0.75:
        issues.append(DfmIssue("warn", f"shaft_d_mm={j.shaft_d_mm:.1f}mm does not match bearing ID {b.id_mm:.1f}mm; expect slop or assembly issues."))

    pocket_d = b.od_mm + 2 * j.clearance_mm
    # Wall around pocket
    min_w = pocket_d + 2 * j.wall_mm
    min_d = pocket_d + 2 * j.wall_mm
    if j.block_w_mm < min_w - 0.01:
        issues.append(DfmIssue("block", f"block_w_mm too small for bearing pocket; need >= {min_w:.1f}mm."))
    if j.block_d_mm < min_d - 0.01:
        issues.append(DfmIssue("block", f"block_d_mm too small for bearing pocket; need >= {min_d:.1f}mm."))

    if j.clearance_mm < 0.15:
        issues.append(DfmIssue("warn", f"clearance_mm={j.clearance_mm:.2f} is tight; bearing pockets often need 0.2–0.4mm depending on printer."))

    if j.wall_mm < _min_wall_mm(process):
        issues.append(DfmIssue("warn", f"wall_mm={j.wall_mm:.2f} is thin; consider >= {_min_wall_mm(process):.2f}mm."))

    if j.block_h_mm < b.width_mm + 1.0:
        issues.append(DfmIssue("warn", "block_h_mm is close to bearing width; ensure pocket has enough seat + top material."))

    # Mount hole spacing sanity
    if j.mount_hole_spacing_x_mm > j.block_w_mm:
        issues.append(DfmIssue("block", "mount_hole_spacing_x_mm exceeds block_w_mm; holes would be outside the part."))
    if j.mount_hole_spacing_y_mm > j.block_d_mm:
        issues.append(DfmIssue("block", "mount_hole_spacing_y_mm exceeds block_d_mm; holes would be outside the part."))

    if mode == "professional" and j.wall_mm < 5.0:
        issues.append(DfmIssue("info", "Professional mode: consider thicker walls (>=5mm) around bearing pockets for stiffness."))

    return issues


def check_belt_reduction(s: BeltReductionSpec, *, process: str, mode: str) -> list[DfmIssue]:
    issues: list[DfmIssue] = []
    if s.center_distance_mm > (s.plate_w_mm - 40.0):
        issues.append(DfmIssue("warn", "center_distance_mm is large relative to plate_w_mm; driven shaft may be too close to edge."))
    if s.plate_t_mm < _min_wall_mm(process):
        issues.append(DfmIssue("warn", f"plate_t_mm={s.plate_t_mm:.2f} is thin; consider thicker plate for stiffness."))
    ratio = float(s.driven_pulley_teeth) / float(s.motor_pulley_teeth)
    issues.append(DfmIssue("info", f"Reduction ratio ≈ {ratio:.2f}:1 (driven/motor)."))

    # Open-belt length approximation (useful for sourcing)
    pitch = s.belt_pitch_mm
    r1 = (s.motor_pulley_teeth * pitch / 1000.0) / (2.0 * math.pi)
    r2 = (s.driven_pulley_teeth * pitch / 1000.0) / (2.0 * math.pi)
    C = s.center_distance_mm / 1000.0
    if C > 0:
        L = 2 * C + math.pi * (r1 + r2) + ((r2 - r1) ** 2) / (4 * C)
        issues.append(DfmIssue("info", f"Approx belt pitch length ≈ {L*1000:.0f} mm (open belt formula; verify)."))
    if mode == "professional" and s.plate_t_mm < 8.0:
        issues.append(DfmIssue("info", "Professional mode: consider 8–10mm plate thickness or add ribs/standoffs."))
    return issues


def check_gripper(g: GripperSpec, *, process: str, mode: str) -> list[DfmIssue]:
    issues: list[DfmIssue] = []
    if g.jaw_t_mm < _min_wall_mm(process):
        issues.append(DfmIssue("warn", f"jaw_t_mm={g.jaw_t_mm:.2f} is thin; jaws may flex."))
    if g.clearance_mm < 0.4:
        issues.append(DfmIssue("warn", f"clearance_mm={g.clearance_mm:.2f} is tight; consider 0.5–0.9mm for printed linkages."))

    # Geometry feasibility stubs (non-kinematic): ensure hole positions are inside the jaw.
    link_x = max(g.jaw_w_mm, g.jaw_len_mm * 0.45)
    if link_x > g.jaw_len_mm - g.jaw_w_mm / 2.0:
        issues.append(DfmIssue("block", "Jaw link hole position falls outside jaw length; increase jaw_len_mm or adjust geometry."))
    if g.jaw_len_mm < 40.0:
        issues.append(DfmIssue("warn", "jaw_len_mm is very short; usable opening and mechanical advantage will be poor."))

    dims = get_servo_dims(g.servo_type)
    servo_t = torque_nm(dims)
    moment = g.max_payload_n * (g.lever_arm_mm / 1000.0)
    issues.append(DfmIssue("info", f"Torque sanity: payload moment≈{moment:.2f} N·m vs servo stall≈{servo_t:.2f} N·m ({dims.name})."))
    if moment > 0.5 * servo_t:
        issues.append(DfmIssue("warn", "Payload moment is high relative to servo; expect weak grip unless geometry adds mechanical advantage."))
    if mode == "professional" and g.jaw_t_mm < 8.0:
        issues.append(DfmIssue("info", "Professional mode: consider thicker jaws (>=8mm) and use metal pins/bushings."))
    return issues


def check_pan_tilt(pt: PanTiltSpec, *, process: str, mode: str) -> list[DfmIssue]:
    issues: list[DfmIssue] = []
    if pt.clearance_mm < 0.4:
        issues.append(DfmIssue("warn", f"clearance_mm={pt.clearance_mm:.2f} is tight; consider 0.5–0.9mm for printed brackets."))

    # Geometry feasibility stubs (non-kinematic): platform vs bracket clearance.
    if pt.platform_w_mm > pt.bracket_w_mm - 2 * pt.clearance_mm or pt.platform_h_mm > pt.bracket_h_mm - 2 * pt.clearance_mm:
        issues.append(DfmIssue("warn", "Platform is close to bracket size; expect interference at high tilt angles unless you add spacers/offsets."))

    tilt = get_servo_dims(pt.tilt_servo)
    t_torque = torque_nm(tilt)
    moment = pt.max_payload_n * (pt.payload_offset_mm / 1000.0)
    issues.append(DfmIssue("info", f"Tilt torque sanity: moment≈{moment:.2f} N·m vs servo stall≈{t_torque:.2f} N·m ({tilt.name})."))
    if moment > 0.5 * t_torque:
        issues.append(DfmIssue("warn", "Tilt payload moment is high relative to servo; reduce payload/offset or use stronger servo."))
    if mode == "professional" and pt.base_t_mm < 8.0:
        issues.append(DfmIssue("info", "Professional mode: consider thicker base/bracket plates (>=8mm) for stiffness."))
    return issues


def check_assembly(a: AssemblySpec, *, mode: str) -> list[DfmIssue]:
    issues: list[DfmIssue] = []
    if not a.instances:
        issues.append(DfmIssue("warn", "assembly.instances is empty; ASSEMBLY.scad will contain no parts."))
        return issues
    seen: set[str] = set()
    for inst in a.instances:
        if inst.id:
            if inst.id in seen:
                issues.append(DfmIssue("block", f"Duplicate assembly instance id: {inst.id}"))
            seen.add(inst.id)
        if not inst.output_file.endswith(".scad"):
            issues.append(DfmIssue("warn", f"Assembly instance references non-.scad file: {inst.output_file}"))
        if not inst.module:
            issues.append(DfmIssue("block", "Assembly instance missing module name."))
    if mode == "professional":
        issues.append(DfmIssue("info", "Assembly is a placement aid; verify clearances and fastener access in your real build."))
    return issues
