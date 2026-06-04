# Mechanical Sanity Check

This is a conservative checklist with high-fidelity simulation entries where available.

- [info] Tilt torque sanity: moment≈0.17 N·m vs servo stall≈0.98 N·m (MG996R).
- [info] Professional mode: consider thicker base/bracket plates (>=8mm) for stiffness.

## Simulation Hints
- [info] (high) Tilt torque safety-factor≈5.71x (stall/reference).
- [info] (pybullet_pan_tilt) PyBullet pan-tilt scene: RMS error pan≈2.14deg, tilt≈1.54deg.

## Safety Checks
- [info] Motion subsystem present: add e-stop and startup interlock in controller firmware.
- [warn] Outdoor profile: validate ingress sealing, connector strain relief, and corrosion plan.
