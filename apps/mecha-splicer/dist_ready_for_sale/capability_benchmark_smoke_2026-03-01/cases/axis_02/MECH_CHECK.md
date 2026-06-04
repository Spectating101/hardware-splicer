# Mechanical Sanity Check

This is a conservative checklist with high-fidelity simulation entries where available.

- [info] Estimated rod deflection ~0.11mm (midspan, steel assumption).
- [info] Estimated torque 0.06 N·m (pulley 20T, load-only).
- [info] Accel estimate: a=560 mm/s² → +0.57N, torque≈0.07 N·m (very rough).

## Simulation Hints
- [info] (high) Axis torque (load+dynamic)≈0.07 N·m; continuous-target margin≈3.95x.
- [info] (high) Estimated rod deflection≈0.11 mm (steel, simply-supported assumption).
- [info] (pybullet_linear_axis) PyBullet axis scene: max speed≈90.0 mm/s, travel≈180.0 mm, tracking ratio≈1.00.

## Safety Checks
- [info] Motion subsystem present: add e-stop and startup interlock in controller firmware.
