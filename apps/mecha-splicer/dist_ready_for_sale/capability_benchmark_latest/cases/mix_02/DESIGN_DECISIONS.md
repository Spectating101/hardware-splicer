# Design Decisions

- Project: `bench_mix_2`
- Mode: `prototype`
- Process: `fdm`
- Simulation Fidelity: `high`

## Composition
- Goal: `quadruped`
- Decision: Added rotary joint module for leg articulation.
- Decision: Added servo mount module for actuation interface.
- Decision: Added gripper module as default end effector.

## Generated Modules
- `servo_mount.scad`
- `rj_bearing_block.scad`
- `rj_arm.scad`
- `rj_preview.scad`
- `gr_base.scad`
- `gr_jaw_left.scad`
- `gr_jaw_right.scad`
- `gr_link.scad`
- `gr_preview.scad`

## Control Profile
- `gripper_servo` (position)

## Assumptions
- Physics outputs are engineering estimates, not certification results.
- Validate final dimensions/tolerances against real hardware before production.
