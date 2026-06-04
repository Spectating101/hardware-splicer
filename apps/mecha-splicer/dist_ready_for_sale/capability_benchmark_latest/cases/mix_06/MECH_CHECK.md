# Mechanical Sanity Check

This is a conservative checklist with high-fidelity simulation entries where available.

- [info] Torque sanity: payload moment≈0.14 N·m vs servo stall≈0.98 N·m (MG996R).

## Simulation Hints
- [info] (high) Arm bending stress≈16.7 MPa (reference load 20 N).
- [info] (high) Gripper torque safety-factor≈7.00x (stall/reference).
- [info] (pybullet_skip) PyBullet not installed; skipped mechanism dynamics scenes.

## Safety Checks
- [info] Motion subsystem present: add e-stop and startup interlock in controller firmware.
- [warn] Outdoor profile: validate ingress sealing, connector strain relief, and corrosion plan.
