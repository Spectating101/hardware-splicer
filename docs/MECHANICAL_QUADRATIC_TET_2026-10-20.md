# E6: Bounded quadratic tetrahedral displacement FEM — 2026-10-20

## Scope and what it is NOT

A new **optional** structural-screening backend uses a P2 (second-order
polynomial) **displacement field**, on the **straight-sided P1 geometric
tetrahedra** already generated from STEP/STL with Gmsh. It uses scikit-fem
as a numerical backend, reuses HS's input validation and face-load
selection, and compares against the previous P1 solver.

This is **not** curved ten-node CAD-conforming tetrahedral geometry:
a circular hole/fillet still uses facets approximating that boundary.
It is also not a nonlinear, contact, vibration, fatigue, fabrication,
material-characterization, or full strength-verification system.

P2 materially improves the classical bending case that was failing.

## Execution

```bash
pip install -e '.[dev,physics,cad-meshing,physics-validation]'
```

Run the bounded P2 solver on a trusted STEP/closed STL file:

```bash
python -m hardware_splicer.mechanical_quadratic_fem part.step \
  --mesh-size-mm 8 --fixed-plane x_min --loaded-plane x_max \
  --force-n 0 0 -1 --youngs-pa 2000000000 --poisson 0.25 \
  --out /tmp/p2-structural-screening.json
```

For the **unperforated long rectangular bar** analytical benchmark, add:

```bash
  --analytic-bar-benchmark cantilever
```

Run an explicit **four-resolution** bending study:

```bash
python -m hardware_splicer.mechanical_quadratic_fem bar.step \
  --mesh-study-mm 12 8 6 4 \
  --fixed-plane x_min --loaded-plane x_max \
  --force-n 0 0 -1 --youngs-pa 2000000000 --poisson 0.25 \
  --analytic-bar-benchmark cantilever \
  --out /tmp/p2-bending-20261020.json
```

Analytical disagreement or inconclusive mesh studies return exit code
**2**, with a JSON report saved for audit. Invalid models raise an
exception, not a fabricated positive result.

## Actual comparison (Optiplex, Gmsh 4.15.0, scikit-fem 11.0.0)

Reference CAD: straight 100 × 10 × 10 mm STEP bar. One x-end fully
fixed, 1 N total vertical force integrated over the opposite x-end.
Assumed homogeneous E=2 GPa, Poisson ratio 0.25.

Analytical work-conjugate end deflection is approximately **0.2015 mm**:
Euler–Bernoulli cantilever bending plus a rectangular
Timoshenko-shear correction.

| Gmsh target (mm) | Tetrahedra | P1 DOFs (3N) | P1 deflection (mm) | P2 deflection (mm) | P2 relative analytical error |
| --- | ---: | ---: | ---: | ---: | ---: |
| 12 | 173 | 234 | 0.090612 | 0.199578 | 0.95% |
| 8 | 263 | 372 | 0.084008 | 0.199915 | 0.79% |
| 6 | 349 | 474 | 0.105505 | 0.200016 | 0.74% |
| 4 | 944 | 1,089 | 0.139311 | 0.200306 | 0.59% |

Corresponding P2 displacement DOFs were 1,212 / 1,896 / 2,460 /
6,033. P2 consumes more degrees of freedom *per element* but is far
more accurate for this smooth bending displacement problem at the
same geometric mesh resolution.

The P2 four-level test passes declared screening thresholds: 5%
maximum error versus this beam formula; 2% maximum deflection change
between adjacent meshes; and 10% minimum actual P2 DOF growth.

### Force and energy validation

P2 face traction is assembled by numerical integration with a
quadratic surface basis. Applied force and support reactions sum
to equal/opposite resultants; free-degree residual and the
strain-energy/external-half-work identity are checked.

Stress is a **quadrature-point sample**, not a constant-element
quantity or exact stress peak. It is *not* currently covered by a
convergence sign-off or published material test.

### A warning for drilled/complex parts

The previous Ø6 mm drilled STEP (100×20×10 mm) yields, at global 8 mm
target, about 0.949 MPa constant-element P1 peak stress and
1.306 MPa sampled P2 quadrature peak stress. Their difference is
evidence of mesh/element-order sensitivity, **not evidence that
either number is physically correct**. Curved hole geometry is still
straight-sided, and idealized support constraints may cause strong
local stress gradients.

The system must not infer structural certification from the
good rectangular cantilever bending result.

## Authority and caps

- Maximum 8,000 quadratic displacement DOFs; pre-solve cap prevents
  large sparse-factorization jobs from silently exhausting resources.
- Prior CAD input size, conforming volume mesh, degenerate geometry,
  missing support, materials and loading checks remain in effect.
- On all outputs:
  `mesh_convergence_verified=false`,
  `independent_physical_model_verified=false`,
  `structural_safety_verified=false`,
  `yield_margin_usable_for_engineering_release=false`,
  `physical_validation_required=true`,
  `fabrication_authorized=false`, and
  `release_authorized=false`.
- No arbitrary CAD filesystem paths are exposed through an HTTP API:
  local trusted-file CLI only.

## Prioritized continuation

1. Add **isoparametric curved geometry** or compare against higher-order
   geometry reference meshing for circular features. Current Gmsh
   straight-sided boundary discretization can dominate notch stress.
2. Stronger independent, stress-concentration, and thick-beam
   analytical fixtures; verify energy convergence and near-clamp effects.
3. Bring material and mounting interfaces from actual HS fabrication
   designs into versioned load cases; gather real measurement receipts
   before using safety margins for manufacturing decisions.
