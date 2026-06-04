# Design Decisions

- Project: `bench_mix_5`
- Mode: `prototype`
- Process: `fdm`
- Simulation Fidelity: `high`

## Composition
- Goal: `mobile_robot`
- Decision: Added linear-axis module for motion subsystem.
- Decision: Added belt reduction stage for drivetrain torque margin.

## Generated Modules
- `motor_mount.scad`
- `idler_mount.scad`
- `carriage.scad`
- `belt_clamp.scad`
- `rod_holder.scad`
- `tensioner_block.scad`
- `endstop_mount.scad`
- `assembly_preview.scad`
- `br_reduction_plate.scad`
- `br_preview.scad`

## Control Profile
- `linear_axis_stepper` (position)

## Assumptions
- Physics outputs are engineering estimates, not certification results.
- Validate final dimensions/tolerances against real hardware before production.
