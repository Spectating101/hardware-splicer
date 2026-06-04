# Mechanical Sanity Check

This is a conservative checklist with high-fidelity simulation entries where available.

- [info] Estimated rod deflection ~0.06mm (midspan, steel assumption).
- [info] Estimated torque 0.05 N·m (pulley 20T, load-only).
- [info] Accel estimate: a=480 mm/s² → +0.39N, torque≈0.05 N·m (very rough).

## Simulation Hints
- [info] (high) Axis torque (load+dynamic)≈0.06 N·m; continuous-target margin≈5.01x.
- [info] (high) Estimated rod deflection≈0.06 mm (steel, simply-supported assumption).
- [info] (pybullet_linear_axis) PyBullet axis scene: max speed≈75.0 mm/s, travel≈150.0 mm, tracking ratio≈1.00.

## Safety Checks
- [info] Motion subsystem present: add e-stop and startup interlock in controller firmware.
