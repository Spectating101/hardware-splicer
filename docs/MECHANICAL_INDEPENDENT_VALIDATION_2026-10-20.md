# Independent structural FEM validation (E5) — 2026-10-20

## Scope

This stage verifies Hardware Splicer's bounded linear-tetrahedron FEM implementation
against **scikit-fem v11**, a separate open-source finite-element implementation.
It adds a *separate* elementary beam-theory benchmark to detect shared modelling/
discretization errors that two same-mesh FEM implementations will otherwise miss.

Both tools still assume **small-displacement linear isotropic elasticity**,
the same CAD geometry, material, loads, and idealized supports. Their agreement
is **not** independent proof of real physical strength or correct fabrication.

## Reproducible invocation

Install the optional independent verifier alongside the numerical and
CAD-meshing packages:

```bash
python -m pip install -e '.[dev,physics,cad-meshing,physics-validation]'
```

For a drilled STEP part (implementation-equivalence only):

```bash
python -m hardware_splicer.mechanical_fem_crosscheck drilled.step \
  --mesh-size-mm 6 --fixed-plane x_min --loaded-plane x_max \
  --force-n 100 0 0 --youngs-pa 2000000000 --poisson 0.25 \
  --yield-pa 100000000 \
  --out /tmp/drilled-crosscheck.json
```

For an **unperforated 100×10×10 mm rectangular bar**, add
`--analytic-bar-benchmark axial` for an independent `FL/(EA)` reference.

For an idealized cantilever test with transverse tip loading:

```bash
python -m hardware_splicer.mechanical_fem_crosscheck bar.step \
  --mesh-size-mm 4 --fixed-plane x_min --loaded-plane x_max \
  --force-n 0 0 -1 --youngs-pa 2000000000 --poisson 0.25 \
  --analytic-bar-benchmark cantilever \
  --out /tmp/bar-bending-crosscheck.json
```

The analytic cantilever reference combines Euler–Bernoulli end-load
bending deflection with a rectangular Timoshenko shear correction.
It is used **only for a long, axis-aligned, unperforated, single-solid
STEP bar** with explicitly matching loads and supports. It does not
claim to predict localized stresses.

On numerical or analytic disagreement, the CLI preserves a JSON report
but returns exit code **2** (no silent pass).

## Evidence from actual Optiplex runs

### Drilled STEP (same-mesh implementation comparison)

Geometry: 100×20×10 mm solid with Ø6 mm through-hole; 100 N axial
end-face force; E=2 GPa, nu=0.25; opposite end clamped. Mesh: 880
tetrahedra, 322 nodes (6 mm global target).

- **HS max von Mises:** 998,361.033646 Pa
- **scikit-fem max von Mises:** 998,361.033646 Pa
- max nodal displacement-field absolute difference: approximately
  `9.43e-18` m
- relative max-stress error: ~`8.2e-15`
- relative energy discrepancy: ~`1.8e-14`
- support reactions and per-element stress fields also agree at
  floating-point accuracy.
- Outcome: `independent_numerical_agreement`, not physics certification.

### Crucial counterexample: bending

Geometry: plain 100×10×10 mm bar, E=2 GPa, nu=0.25, left face
clamped; 1 N vertical force uniformly distributed on the right end.

Idealized beam-theory work-conjugate end deflection:

```text
Euler–Bernoulli bending + rectangular shear ≈ 0.20150 mm
```

| Global target | HS load-work-conjugate deflection | Analytic reference | Relative discrepancy |
| --- | ---: | ---: | ---: |
| 8 mm | 0.084008 mm | 0.20150 mm | 58.3% |
| 4 mm | 0.139311 mm | 0.20150 mm | 30.9% |

The scikit-fem solver gives **the same result as HS** at those
same mesh sizes, yet both depart materially from the analytic
slender-beam reference. This demonstrates low-order tetrahedral
**bending stiffness / mesh-resolution bias** and proves why
implementation equivalence must never be mistaken for physical
or discretization accuracy.

At the default 10% analytic-discrepancy threshold, bending reports
`analytic_benchmark_disagreement` while axial tension passes.
The default comparison tolerance for *same-mesh solver agreement* is
`1e-6` relative, not the analytic 10% reference tolerance.

## Machine-readable claims and authority

Crosscheck output includes:

- versioned schema, source CAD SHA-256, exact FEM case SHA-256,
  independent library name/version, mesh size, load case and support
- displacement-field, per-element von Mises, support reactions,
  peak stress and independent elastic-energy comparison
- independent analytic reference (if requested), pass/fail and
  explicit formulas/limits
- fail-closed status with granular disagreement fields

All reports maintain `independent_physical_model_verified=false`,
`mesh_convergence_verified=false`,
`structural_safety_verified=false`,
`yield_margin_usable_for_engineering_release=false`,
`fabrication_authorized=false` and `release_authorized=false`.

The verifier is a **local trusted-file CLI**, not a path-taking HTTP
endpoint; scikit-fem is an **optional dependency**, not required by
the normal Hardware Splicer production API.

## Outstanding engineering work

1. A demonstrably convergent bending mesh benchmark at multiple finer
   resolutions/higher-order tet shapes. Currently the bounded 2,000-node /
   5,000-element limits restrict strong bending convergence on a long beam.
2. Geometry-specific independent solutions for holes, notches,
   brackets, screws, and printed part load cases.
3. Experimental material stiffness/strength measurements,
   printed-part directional properties, realistic fixturing.
4. Independent 3D physics benchmark, dynamic loads and manufactured
   assembly-validation receipts.
