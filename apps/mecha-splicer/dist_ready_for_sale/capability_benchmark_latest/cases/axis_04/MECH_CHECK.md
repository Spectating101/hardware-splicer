# Mechanical Sanity Check

This is a conservative checklist with high-fidelity simulation entries where available.

- [info] Estimated rod deflection ~0.29mm (midspan, steel assumption).
- [info] Estimated torque 0.09 N·m (pulley 20T, load-only).
- [info] Accel estimate: a=720 mm/s² → +1.03N, torque≈0.10 N·m (very rough).

## Simulation Hints
- [info] (high) Axis torque (load+dynamic)≈0.10 N·m; continuous-target margin≈2.74x.
- [info] (high) Estimated rod deflection≈0.29 mm (steel, simply-supported assumption).
- [info] (pybullet_skip) PyBullet not installed; skipped mechanism dynamics scenes.

## Safety Checks
- [info] Motion subsystem present: add e-stop and startup interlock in controller firmware.
