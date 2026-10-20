# E7 — Gmsh curved quadratic CAD geometry, isoparametric FEM (2026-10-20)

## New capability

Hardware Splicer's trusted-file mechanical CAD workflow now optionally
represents the **geometry** with quadratic (10-node) tetrahedra, in addition
to the earlier quadratic **displacement** solution.

The STEP input is meshed as linear tetrahedra with Gmsh, then promoted using
`gmsh.model.mesh.setOrder(2)`. Gmsh projects midside nodes to the
OpenCASCADE CAD surfaces. `HighOrder` optimization is invoked to untangle
curved elements before export. The conversion uses the explicit Gmsh
type-11 edge pairing `(0,1),(1,2),(0,2),(0,3),(2,3),(1,3)` to build
the curved `skfem.MeshTet2` mapping without assuming matching node numbering.

For all curved solves, HS checks finite positive Jacobian determinants at
the solver's integration nodes, additional fifth-order quadrature nodes,
and tetrahedron corners/center, and compares integrated curved mesh volume
against the STEP CAD solid's exact OpenCASCADE volume. A failure stops
the solver and produces **no positive calculation outcome**.

**Important:** sampled Jacobian validity does not mathematically certify
the mapping throughout the entire element. Geometry is quadratic, not exact
NURBS. Surface stress singularities, print anisotropy, fasteners, contacts,
fatigue, and physical certification remain unimplemented.

## Installation and examples

```bash
pip install -e '.[dev,physics,cad-meshing,physics-validation]'
```

Single STEP CAD quadratic geometry analysis:

```bash
python -m hardware_splicer.mechanical_quadratic_fem drilled.step \
  --curved-geometry --mesh-size-mm 6 \
  --fixed-plane x_min --loaded-plane x_max \
  --force-n 100 0 0 --youngs-pa 2000000000 \
  --poisson 0.25 --out /tmp/drilled-curved.json
```

**Paired comparison with identical corner topology**:

```bash
python -m hardware_splicer.mechanical_quadratic_fem drilled.step \
  --compare-curved --mesh-size-mm 6 \
  --fixed-plane x_min --loaded-plane x_max \
  --force-n 100 0 0 --youngs-pa 2000000000 \
  --poisson 0.25 --out /tmp/drilled-compare.json
```

The comparison obtains the already optimized, curved mesh once, and uses
the *same* corner vertices and tetrahedral connectivity for both solves.
It flattens high-order midside nodes to edge chord midpoints only for the
straight-geometry comparator. This is intentional: **Gmsh's high-order
optimizer may change some corner vertices**, so independently generating
two meshes might confound the geometry comparison.

Three-level curved P2 stress-sensitivity study:

```bash
python -m hardware_splicer.mechanical_quadratic_fem drilled.step \
  --curved-stress-study-mm 8 7 6 \
  --fixed-plane x_min --loaded-plane x_max \
  --force-n 100 0 0 --youngs-pa 2000000000 \
  --poisson 0.25 --out /tmp/drilled-stress-study.json
```

The paired comparison and curved stress study write JSON evidence and exit
with code **2** if the configured screening criteria are not met.

Only STEP/STP enables the curved CAD mapping. Faceted STL lacks an
underlying continuous BREP surface; it is explicitly refused for
`geometry_order=2`. Existing straight-sided STL screening remains
available without change.

## Real Optiplex benchmark

Material is an assumed homogeneous E=2 GPa, Poisson ratio 0.25. CAD
part is a single 100×20×10 mm plate with a Ø6 mm through-hole,
fully clamped on x-min and pulled with 100 N total traction on x-max.

### Geometry fidelity versus exact CAD volume

| Global mesh target | Straight corner-mesh volume error | Curved integrated mesh volume error |
| --- | ---: | ---: |
| 8 mm | 0.24% | 0.0040% |
| 6 mm | 0.25% | 0.0051% |

This is a significant, measured **volume geometry improvement**, not
a validated stress result. The curved geometry is still an approximation
of the NURBS cylinder.

### The **matched topology** stress comparison

| Target | Tetrahedra | P2 straight peak von Mises | P2 curved peak von Mises | Relative difference |
| --- | ---: | ---: | ---: | ---: |
| 8 mm | 566 | 1.311 MPa | 1.533 MPa | 14.5% |
| 6 mm | 880 | 1.350 MPa | 1.399 MPa | 3.6% |

Gmsh's high-order optimizer was necessary: **without** high-order
optimization, one 8 mm curved fixture had negative sampled Jacobians.
After optimization, both 8 mm and 6 mm examples had positive sampled
Jacobians; the implementation still checks them before every solve.

### Stress sensitivity over curved tetrahedra

| Global mesh target | Tetrahedra | P2 curved peak von Mises |
| --- | ---: | ---: |
| 8 mm | 566 | 1.533 MPa |
| 7 mm | 668 | 1.329 MPa |
| 6 mm | 880 | 1.399 MPa |

The result is **`inconclusive_curved_stress_refinement`**:
peak-stress changes between adjacent curved mesh resolutions exceed
the configured 3% numerical screening criterion, even though the
integrated CAD volumes are much closer to the original solid.

No stress concentration factor, tensile strength, factor-of-safety
margin or fabrication decision is validated by these tests.

## Outputs and safety invariant

- Source STEP SHA-256 and fingerprint of the common linear-geometry mesh
- True P2 isoparametric (curved) vs straight geometric interpolation order
- Number of nonchord midside nodes and largest deviation from a straight edge
- Minimum sampled Jacobian; curved integrated volume and CAD-volume error
- Stress at quadrature points and physical location of sampled peak stress
- P2 displacement, energy, reaction force and numerical residuals
- Matched-mesh geometry sensitivity and multi-mesh stress instability flags
- Boundaries and limitations always present in machine-readable reports

All reports continue to set:

```json
{
  "mesh_convergence_verified": false,
  "structural_safety_verified": false,
  "physical_validation_required": true,
  "fabrication_authorized": false,
  "release_authorized": false
}
```

Existing 8,000-P2-DOF solver limit, bounded single-solid geometry import,
mesh element limits, case validation, and local trusted-file-only CLI
are retained. No arbitrary-path HTTP endpoint or manufacturing control
has been added.

## Recommended next research

A reference problem whose stress concentration can be compared to a
trusted elasticity solution (e.g., a plate with a circular hole in
a carefully specified ideal far-field traction), plus instrumented
printing/fixture load tests. It is important to separate volume
accuracy, high-order element interpolation, stress convergence, and
*actual manufactured-part strength* as different evidence dimensions.
