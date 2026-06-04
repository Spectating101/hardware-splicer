# Mechanical Sanity Check

This is a conservative checklist with high-fidelity simulation entries where available.

- [info] Estimated rod deflection ~0.04mm (midspan, steel assumption).
- [info] Estimated torque 0.05 N·m (pulley 20T, load-only).
- [info] Accel estimate: a=600 mm/s² → +0.49N, torque≈0.05 N·m (very rough).
- [info] Reduction ratio ≈ 3.00:1 (driven/motor).
- [info] Approx belt pitch length ≈ 201 mm (open belt formula; verify).

## Simulation Hints
- [info] (high) Axis torque (load+dynamic)≈0.06 N·m; continuous-target margin≈4.90x.
- [info] (high) Estimated rod deflection≈0.04 mm (steel, simply-supported assumption).
- [info] (pybullet_skip) PyBullet not installed; skipped mechanism dynamics scenes.

## Safety Checks
- [info] Motion subsystem present: add e-stop and startup interlock in controller firmware.
