# Design Decisions

- Project: `bench_axis_2`
- Mode: `prototype`
- Process: `fdm`
- Simulation Fidelity: `high`

## Composition
- Composer: auto_compose disabled or no system_goal

## Generated Modules
- `motor_mount.scad`
- `idler_mount.scad`
- `carriage.scad`
- `belt_clamp.scad`
- `rod_holder.scad`
- `tensioner_block.scad`
- `endstop_mount.scad`
- `assembly_preview.scad`

## Control Profile
- `linear_axis_stepper` (position)

## Assumptions
- Physics outputs are engineering estimates, not certification results.
- Validate final dimensions/tolerances against real hardware before production.
