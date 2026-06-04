# Mechanical Sanity Check

This is a conservative checklist with high-fidelity simulation entries where available.

- [info] Tilt torque sanity: moment≈0.11 N·m vs servo stall≈0.18 N·m (SG90).
- [warn] Tilt payload moment is high relative to servo; reduce payload/offset or use stronger servo.

## Simulation Hints
- [warn] (high) Tilt torque safety-factor≈1.68x (stall/reference).
- [info] (pybullet_skip) PyBullet not installed; skipped mechanism dynamics scenes.

## Safety Checks
- [info] Motion subsystem present: add e-stop and startup interlock in controller firmware.
