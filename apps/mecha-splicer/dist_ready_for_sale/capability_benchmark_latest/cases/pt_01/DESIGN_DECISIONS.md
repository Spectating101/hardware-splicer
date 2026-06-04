# Design Decisions

- Project: `bench_pt_1`
- Mode: `prototype`
- Process: `fdm`
- Simulation Fidelity: `high`

## Composition
- Composer: auto_compose disabled or no system_goal

## Generated Modules
- `pt_base.scad`
- `pt_bracket.scad`
- `pt_platform.scad`
- `pt_preview.scad`

## Control Profile
- `pan_servo` (angle)
- `tilt_servo` (angle)

## Assumptions
- Physics outputs are engineering estimates, not certification results.
- Validate final dimensions/tolerances against real hardware before production.
