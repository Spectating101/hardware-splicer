# Mechanical Sanity Check

This is a conservative checklist with high-fidelity simulation entries where available.

- [info] Tilt torque sanity: moment≈0.18 N·m vs servo stall≈0.18 N·m (SG90).
- [warn] Tilt payload moment is high relative to servo; reduce payload/offset or use stronger servo.
- [info] Professional mode: consider thicker base/bracket plates (>=8mm) for stiffness.

## Simulation Hints
- [block] (high) Tilt torque safety-factor≈0.98x (stall/reference).
- [info] (pybullet_skip) PyBullet not installed; skipped mechanism dynamics scenes.

## Safety Checks
- [info] Motion subsystem present: add e-stop and startup interlock in controller firmware.
- [warn] Outdoor profile: validate ingress sealing, connector strain relief, and corrosion plan.
