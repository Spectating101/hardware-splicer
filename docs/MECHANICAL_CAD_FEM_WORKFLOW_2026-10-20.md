# CAD → volume mesh → FEM screening (2026-10-20)

## What is implemented

Local CLI only: `hardware_splicer.mechanical_cad_fem`.

1. **STEP/STP**: Gmsh OpenCASCADE imports a **single** closed solid.
   It converts STEP length units to millimetres using `Geometry.OCCTargetUnit=MM`.
2. **STL**: Gmsh classifies triangles into discrete surfaces, creates
   parametrizations and builds a solid. The user **must explicitly assert
   millimetre units** using `--stl-units mm` (STL has no units).
3. Generates conforming linear tetrahedra and exterior triangular faces.
4. Checks surface-to-tetrahedral-boundary agreement, closed two-manifold
   edges and connected exterior shell. Rejects multiple volumes, shells
   and open/disconnected surfaces.
5. Selects two **distinct planar axis-extreme faces** as support/loading
   regions (`x_min`, `x_max`, `y_min`, `y_max`, `z_min`, `z_max`).
6. Distributes a specified **total force** to loaded-face nodes using each
   boundary triangle's tributary area (uniform surface traction).
7. Calls the prior bounded isotropic constant-strain tetrahedral FEM solver,
   which reports displacement, von Mises stress, reactions, equilibrium
   residual, and a preliminary yield-strength ratio.

Source SHA-256, mesh size, units, mesh volume, bounding box and boundary
conditions are included in the exported report. For STEP, exact OCC CAD
kernel volume and the mesh-vs-kernel volume discrepancy are also reported.
A discrepancy above 5% is rejected; this guard does not replace
mesh-quality or convergence analysis.

## Installation

Use a Python environment with SciPy, NumPy, Gmsh, Pydantic and required
system libraries (e.g. `libGLU` on Linux):

```bash
pip install -e '.[physics,cad-meshing]'
```

Example: 100 mm long sample bar, 100 N axial total force and 2 GPa
Young's modulus; results are design-screening estimates, not test proof.

```bash
python -m hardware_splicer.mechanical_cad_fem part.step \
  --mesh-size-mm 8 \
  --fixed-plane x_min \
  --loaded-plane x_max \
  --force-n 100 0 0 \
  --youngs-pa 2000000000 \
  --poisson 0.25 \
  --yield-pa 100000000 \
  --out /tmp/part-structural-screening.json
```

For a closed STL, replace `part.step` with `part.stl` and **add**
`--stl-units mm`. All component coordinates must be in correct physical
units. If they are not, regenerate/export the CAD in millimetres first.

## Executed reference example (Optiplex, Gmsh 4.15.0)

Input: native CAD rectangular prism **100 × 10 × 10 mm**, left end
fully fixed, 100 N traction distributed over right end. Assumed isotropic
E=2 GPa, Poisson=0.25; yield limit=100 MPa.

| Format | Mesh size | Tet elements | FEM maximum displacement | Max von Mises |
| --- | --- | --- | --- | --- |
| STEP | 8 mm | 263 | 0.04985 mm | 1.030 MPa |
| STL | 8 mm | 356 | 0.04979 mm | 1.020 MPa |

Axial continuum sanity benchmark: `F L / (A E) = 0.050 mm`; theoretical
nominal axial stress `F / A = 1.0 MPa`. This is not independent
experimental validation, and a single analytical test does not establish
correctness for arbitrary geometries or loads.

For STEP, 12 / 8 / 6 / 4 mm targets produced 173 / 263 / 349 / 944
tetrahedra and displacements 0.049814 / 0.049854 / 0.049940 / 0.049836
mm, respectively. These are mesh-sensitivity observations **for this
single bar**, not general convergence certification.

## Limitations and fail-closed behavior

- This is **not a replacement for real design sign-off**.
- Only a **single solid and one connected watertight exterior skin**;
  complex shells, multi-part assemblies and multi-material solids are refused.
- The support/load face has to be one of the six planar Cartesian extreme
  faces; a curved/rotated surface may be unsupported.
- The force is a **total nodal-distributed traction approximation**, not
  a pressure law, motor-dynamic input, screw preload, joint load, contact,
  temperature field, gravity body force, or real torque on a shaft.
- Fixed faces are idealized zero-displacement clamps.
- STEP curved surface meshes only approximate CAD kernel volume. The
  through-hole fixture showed a 0.25% volume difference at 6 mm mesh size.
- Large parts and meshes are rejected to protect resources. If the part
  cannot fit the guardrails, use a real offline FEA workflow instead.
- Small-strain linear-isotropic elasticity only. No material anisotropy
  (important for FDM), plasticity, buckling, crack propagation, fatigue,
  contact, impact, vibration, creep or thermal deformation.
- No mesh-convergence *certification*, empirical material calibration,
  fixture calibration, or physical test validation.
- Physical operation, fabrication and production release are **never**
  authorized by this tool.
- Local CLI for **trusted CAD files** only; no arbitrary-path HTTP endpoint.

## Next useful steps

1. Add per-part geometric fixtures with holes and thin walls with
   independently benchmarked expected stresses/displacements.
2. Add signed, versioned load-case recipes based on the actual mechanical
   interfaces and a measured BOM/material catalog.
3. Require independent mesh convergence and external FEA comparisons
   before enabling decision-useful stress margins.
4. Reconcile the legacy `apps/3d-splicer` architecture; do not silently
   route structural claims through its broken legacy FEM class.
