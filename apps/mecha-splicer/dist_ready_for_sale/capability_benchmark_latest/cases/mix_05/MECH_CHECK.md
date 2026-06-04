# Mechanical Sanity Check

This is a conservative checklist with high-fidelity simulation entries where available.

- [info] Estimated rod deflection ~0.08mm (midspan, steel assumption).
- [info] Estimated torque 0.09 N·m (pulley 20T, load-only).
- [info] Accel estimate: a=600 mm/s² → +0.90N, torque≈0.10 N·m (very rough).
- [info] Reduction ratio ≈ 3.00:1 (driven/motor).
- [info] Approx belt pitch length ≈ 201 mm (open belt formula; verify).

## Simulation Hints
- [info] (high) Axis torque (load+dynamic)≈0.11 N·m; continuous-target margin≈2.66x.
- [info] (high) Estimated rod deflection≈0.08 mm (steel, simply-supported assumption).
- [info] (pybullet_skip) PyBullet not installed; skipped mechanism dynamics scenes.

## Safety Checks
- [info] Motion subsystem present: add e-stop and startup interlock in controller firmware.
- [warn] Outdoor profile: validate ingress sealing, connector strain relief, and corrosion plan.
