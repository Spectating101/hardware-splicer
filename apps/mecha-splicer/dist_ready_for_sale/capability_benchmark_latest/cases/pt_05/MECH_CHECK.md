# Mechanical Sanity Check

This is a conservative checklist with high-fidelity simulation entries where available.

- [info] Tilt torque sanity: moment≈0.39 N·m vs servo stall≈0.98 N·m (MG996R).

## Simulation Hints
- [info] (high) Tilt torque safety-factor≈2.55x (stall/reference).
- [info] (pybullet_skip) PyBullet not installed; skipped mechanism dynamics scenes.

## Safety Checks
- [info] Motion subsystem present: add e-stop and startup interlock in controller firmware.
