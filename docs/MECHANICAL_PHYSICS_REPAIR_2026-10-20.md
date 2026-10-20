# Mechanical physics repair — 2026-10-20

Scope: a narrowly bounded, executable structural-screening path, plus correction of
acceleration torque accounting. This change **does not** make Hardware Splicer an
automatically verified mechanical design or fabrication system.

## Active repaired functionality

- `apps/mecha-splicer/src/mecha_splicer/engines/sim.py` reports load torque and
  acceleration torque independently. The reflected-inertia acceleration term is
  counted **once**. The 0.28-Nm continuous motor torque is an *assumed example
  limit*, not the measured rating of a sourced motor.
- `src/hardware_splicer/mechanical_fem.py` assembles small-strain, isotropic,
  3D constant-strain tetrahedral FEM from an explicit **conforming volume mesh**.
  Supports per-node loads, fixed DOFs, sparse stiffness solve, displacement,
  elemental stress (engineering Voigt [xx, yy, zz, yz, xz, xy]),
  von Mises stress, reactions, equilibrium residual, and optional yield margin.
- `POST /v1/engineering/mechanical/physics/linear-elasticity` exposes FEM as
  a screening result, explicitly denying physical and fabrication authorization.
- `GET /v1/engineering/mechanical/schema` advertises the new input contract.

To enable the optional numerical backend:

```bash
pip install '.[physics]'
```

Example input (SI units: metres, newtons, pascals):

```json
{
  "nodes_m": [[0,0,0], [0.1,0,0], [0,0.1,0], [0,0,0.1]],
  "elements": [[0,1,2,3]],
  "loads_n": [{"node":1,"force_n":[10,0,0]}],
  "constraints": [{"node":0}, {"node":2}, {"node":3}],
  "youngs_modulus_pa": 2000000000,
  "poisson_ratio": 0.25,
  "yield_strength_pa": 100000000,
  "units": "SI"
}
```

## Validation coverage

- Analytical one-tetra constrained extension: calculated displacement and stress
  match closed-form equations.
- Element winding reversal invariant; 2x modulus -> 0.5x displacement at
  constant force and approximately invariant stress.
- Rejects degenerate tets, isolated nodes, disconnected unrestrained solids,
  insufficient rigid-body supports, invalid units and inputs, and loads that
  cannot produce any deformational response.
- Verifies reaction-force equilibrium and API release-authority isolation.

## What is still missing

1. **Geometry ingestion:** the API requires a caller-provided *tetrahedral volume*
   mesh. STEP parsing elsewhere only extracts model identity/coarse point envelopes.
   Generating a verified volume mesh from STEP/STL is not implemented here.
2. **Convergence and physical calibration:** one numerical output is not enough
   to validate a structure. Mesh refinement, realistic supports, actual material
   test data, test rigs, and real measured loads are still necessary.
3. **Nonlinear phenomena:** joints, threads, contact, buckling, print anisotropy,
   plasticity, thermal, fatigue, vibration and transient motion are not modeled.
4. **Legacy `apps/3d-splicer/src/decomposition`:** that older path remains
   nonfunctional as a general FEM/assembly solver due to syntax errors in
   `core/mesh.py` and `core/component.py`, plus numerous undefined helper
   methods in its physics and structural classes. The new bounded FEM route
   avoids incorrectly treating that legacy path as validated.
5. **Motor characterization:** the Mecha-Splicer torque estimate still uses
   reference load assumptions and does not represent a measured motor
   torque-speed curve or losses across a complete actuator drivetrain.

Safety posture: a computed margin is a design hypothesis, never a production
approval. Physical testing and engineering review remain mandatory.
