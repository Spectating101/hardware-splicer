# Mechanical mesh-sensitivity screening — 2026-10-20

## Why this exists

The prior CAD → Gmsh → linear tetrahedral FEM path produced real numerical
results, but **one mesh resolution is not sufficient**. Coarse meshes can
underestimate local notch stresses even when displacement looks credible.

This follow-on introduces a deliberately bounded **three/four-mesh
sensitivity study** for the same CAD source, material properties,
loads and supports. It is a numerical *diagnostic*, **not** FEA
verification, structural certification, or fabrication release.

## Run the workflow

Install the optional numerical and CAD-meshing packages:

```bash
python -m pip install -e '.[dev,physics,cad-meshing]'
```

Example: three decreasing global mesh targets (coarse → fine).
A complete run may produce hundreds to thousands of tetrahedral
elements at each resolution.

```bash
python -m hardware_splicer.mechanical_cad_fem part.step \
  --mesh-study-mm 8 6 4 \
  --fixed-plane x_min \
  --loaded-plane x_max \
  --force-n 100 0 0 \
  --youngs-pa 2000000000 \
  --poisson 0.25 \
  --yield-pa 100000000 \
  --out /tmp/part-mesh-sensitivity.json
```

For STL, add `--stl-units mm`. The CLI also supports
`--displacement-tolerance` (default 0.02) and `--stress-tolerance`
(default 0.03), relative changes between adjacent meshes.

The report includes each mesh's node/element counts, volume error
against the STEP kernel when available, peak von Mises stress,
peak-stress element centroid, maximum displacement, reaction-force
equilibrium residual, raw yield ratio, and adjacent-mesh comparisons.

A *numerically_stable_screening* status requires:

- 3–4 valid, strictly decreasing nominal target mesh sizes
- at least 10% **actual tetrahedral-count increase** per refinement
- no more than 2% change in maximum displacement between adjacent meshes
- no more than 3% change in peak element von Mises stress
- no more than 1% difference in volume vs STEP kernel across all levels
- successful completion of **all** mesh and solve steps; no hidden skips

Otherwise, the study returns `inconclusive_refinement` with
machine-readable blockers such as `peak_stress_changes_with_refinement`,
`insufficient_effective_refinement`, or
`cad_mesh_volume_discrepancy`.

The configurable thresholds are screening criteria, **not** safety
factors, ISO/ASME approval requirements, or physical tolerances.

## Executed reference comparisons (Optiplex; Gmsh 4.15.0)

Material: assumed isotropic E=2 GPa, nu=0.25. Boundary conditions:
one end face fully fixed; 100 N total axial force distributed over
the other end.

**Plain 100×10×10 mm STEP rectangular prism:**

| Target mesh (mm) | Tetrahedra | Maximum displacement (mm) | Peak von Mises (MPa) |
| --- | ---: | ---: | ---: |
| 8 | 263 | 0.049854 | 1.030 |
| 6 | 349 | 0.049940 | 1.015 |
| 4 | 944 | 0.049836 | 1.024 |

Screen: **numerically stable** by the above global criteria.
Analytical nominal axial reference: 0.050 mm displacement, 1.0 MPa
stress. These are illustrative, not certification of other loads.

**100×20×10 mm STEP plate with a central Ø6 mm through-hole:**

| Target mesh (mm) | Tetrahedra | Maximum displacement (mm) | Peak von Mises (MPa) |
| --- | ---: | ---: | ---: |
| 8 | 566 | 0.025588 | 0.949 |
| 6 | 880 | 0.025540 | 0.998 |
| 4 | 2,030 | 0.025635 | 1.097 |

The peak stress rises by roughly 5–9% between consecutive meshes,
**failing the 3% stress criterion**, while displacement is relatively
unchanged. The workflow correctly marks this study *inconclusive*.
The location of the local peak also moves; the peak stress should not
be promoted to a trusted design-margin number.

## Interpretation

- **Stable** = numerical consistency at the tested global mesh sizes.
  It does not show that the *correct physical model* was used.
- **Inconclusive** = do not use the computed peak stress/yield margin
  to decide whether the part is strong enough. Refine geometry,
  mesh more densely near stress raisers, examine constraints and
  compare independent physical/FEA benchmarks.
- Sharp corners and fully fixed idealizations can create stress
  singularities; those peaks may not converge without a physically
  appropriate radius or boundary condition.
- Local mesh adaptation, high-order finite elements, printed polymer
  anisotropy, nonlinear contact, fatigue, buckling and experimental
  mechanical characterization remain unimplemented.
- Numeric stability does **not** raise physical authority: the
  report always sets `mesh_convergence_verified=false`,
  `structural_safety_verified=false`,
  `yield_margin_usable_for_engineering_release=false`,
  `fabrication_authorized=false`, and `release_authorized=false`.

Design target: **prevent misleading safety judgments** and direct
users to the missing evidence, rather than increasing model scope
with unwarranted confidence.
