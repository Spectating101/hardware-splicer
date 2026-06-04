# Mechanisms (v1)

This document describes the mechanism primitives Mecha-Splicer can generate today and how to iterate them safely.

Mecha-Splicer’s philosophy is **prototype-grade outputs + conservative checklists**, not a “magic finished robot”.

## Linear Axis: GT2 belt (printable mounts)
**Spec key:** `linear_axis`

**Outputs (typical):**
- `motor_mount.scad`, `idler_mount.scad`
- `carriage.scad`, `belt_clamp.scad`
- `rod_holder.scad` (optional), `tensioner_block.scad` (optional), `endstop_mount.scad` (optional)
- `assembly_preview.scad` (helper)

**When it’s a good fit:**
- Medium-high speed motion (plotter-like, light gantries)
- Lower stiffness requirements than lead-screw

**Common failure modes:**
- Belt tension too low → backlash / skipping
- Rods not parallel → binding
- Frame not stiff → resonance / positional error

## Linear Axis: T8 lead-screw (printable mounts)
**Spec key:** `leadscrew_axis`

**Outputs (typical):**
- `ls_motor_mount.scad`
- `ls_screw_end_support.scad`
- `ls_carriage_nut_mount.scad`
- `rod_holder.scad` (optional), `endstop_mount.scad` (optional)
- `ls_assembly_preview.scad` (helper)

**When it’s a good fit:**
- Higher stiffness / holding force
- Lower speed, higher force applications (lifting, pressing, accurate slow travel)

**Common failure modes (the big one):**
- **Misalignment → binding** (motor stalls, nut wears, parts crack).

**Tuning reminder:**
- `steps_per_mm = steps_per_rev * microsteps / lead_mm_per_rev`
- Example: 200 steps/rev motor, 16× microstepping, 8mm lead → 200*16/8 = 400 steps/mm

## How to validate (practically)
Mecha-Splicer emits `MECH_CHECK.md` with heuristic checks. Treat it as:
- A “did we forget something obvious?” list
- A first-pass filter before you print and assemble

The real validation loop is:
1. Generate bundle → read `MECH_CHECK.md`
2. Print one part → test-fit mating hardware
3. Assemble → check motion smoothness across full travel
4. Adjust clearances/wall thickness/geometry → regenerate

## Rotary Joint: bearing-supported (608/625)
**Spec key:** `rotary_joint`

**Outputs (typical):**
- `rj_bearing_block.scad`
- `rj_arm.scad`
- `rj_preview.scad` (helper)

**When it’s a good fit:**
- Simple rotational joints (pan/tilt prototypes, levers, idlers)
- Low-to-moderate torque where you’ll still use real hardware for the shaft/hub

**Common failure modes:**
- Bearing pocket too tight/loose (tune `clearance_mm`)
- Printed arm slipping on shaft (use a real hub/set-screw or keyed interface)
- Loads that cause the block to flex (increase `wall_mm`, mount to a rigid frame)

## Belt Reduction: GT2 stage
**Spec key:** `belt_reduction`

**Outputs (typical):**
- `br_reduction_plate.scad`
- `br_preview.scad` (helper)

**What it’s for:**
- Getting more torque and lower speed from a stepper-driven belt system (e.g., heavy axes).

**Common failure modes:**
- Plate flex / bearings walking (increase `plate_t_mm`, add standoffs, mount rigidly)
- Wrong belt length (use the emitted belt length estimate as a starting point, then measure/iterate)

## Gripper: servo scissor (prototype)
**Spec key:** `gripper`

**Outputs (typical):**
- `gr_base.scad`
- `gr_jaw_left.scad`, `gr_jaw_right.scad`
- `gr_link.scad`
- `gr_preview.scad` (helper)

**Common failure modes:**
- Too much payload moment for servo torque (reduce `lever_arm_mm`, use stronger servo, add mechanical advantage)
- Friction at pivots (use washers/bushings, ream holes)

## Pan/Tilt: 2-DOF servo mount (prototype)
**Spec key:** `pan_tilt`

**Outputs (typical):**
- `pt_base.scad`, `pt_bracket.scad`, `pt_platform.scad`
- `pt_preview.scad` (helper)

**Common failure modes:**
- Tilt torque too high for the servo (reduce payload, reduce `payload_offset_mm`, use stronger servo)
- Plate flex (increase thickness and add ribs/spacers)

## Assembly: placement graph (v1)
**Spec key:** `assembly`

This generates `ASSEMBLY.scad` which does:
- `use <part.scad>;` for referenced outputs
- `translate/rotate` then calls `module();`

### Mates (v2 within v1)
`assembly.mates` lets you **mate anchors** between parts so Mecha-Splicer can solve placement transforms.

Concept:
- Each `instance` has **anchors** (local coordinate frames).
- A `mate` aligns `A.anchor` to `B.anchor` (with optional `offset`).
- If one side is fixed/placed, the other can be solved.

Mate kinds:
- `anchor` (default): uses `a_anchor` / `b_anchor` exactly
- `center_to_center`: defaults to `center` on both sides
- `mount_plane_flush`: defaults to `mount_plane` on both sides
- `shaft_into_bearing`: defaults to `bearing_center` (A) and `shaft` (B)
- `bolt_pattern`: uses pattern-defined bolt anchors and computes placement from them (see `params`)
- `bolt_pattern` supports `align=best_fit` (least-squares Rz + translation across multiple bolts)
- `rod_pair_align`: aligns two anchors simultaneously (defaults: `rod_left` + `rod_right`) to avoid twist
- Conflict handling: if multiple mates overconstrain a part, higher `priority` mates can override placement; warnings appear in `ASSEMBLY.scad`.

Auto-anchors:
- For some primitives, anchors are auto-generated (e.g. `rj_bearing_block.scad` provides `center` / `bearing_center`).
- Manual anchors on the instance override auto anchors by name.

Auto-anchor quick reference (v1):
- `motor_mount.scad`: `motor_center`, `rod_left`, `rod_right`, `center`
- `idler_mount.scad`: `idler_center`, `rod_left`, `rod_right`, `center`
- `carriage.scad`: `rod_left`, `rod_right`, `belt_center`, `center`
- `ls_motor_mount.scad`: `motor_center`, `coupler_center`, `screw_center`, `rod_left`, `rod_right`, `center`
- `ls_screw_end_support.scad`: `screw_center`, `rod_left`, `rod_right`, `center`
- `ls_carriage_nut_mount.scad`: `screw_center`, `rod_left`, `rod_right`, `center`
- `rj_bearing_block.scad`: `center`, `bearing_center`
- `br_reduction_plate.scad`: `motor_center`, `driven_center`, `idler_center` (if enabled), `center`
- NEMA17 bolt anchors on relevant parts: `nema17_bolt_ne|nw|se|sw`

Keepouts (fastener access):
- Assembly emits `// WARN: Keepout hit ...` comments if a part overlaps a fastener keepout volume.

This is how you combine primitives into “a machine” without leaving the Mecha-Splicer pipeline.
