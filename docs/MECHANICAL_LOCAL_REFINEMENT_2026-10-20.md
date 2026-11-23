# Mechanical local CAD mesh refinement — 2026-10-20

## What changed

This extends the bounded, **local-file-only** STEP/STL → Gmsh → FEM workflow
with geometry-directed local refinement. It is a computational *screening*
feature, not a validated mechanical safety assessor.

Two optional Gmsh mesh sizing strategies are implemented:

1. **Circular edges from STEP CAD:** detect true OpenCASCADE `Circle`
   curves in a single imported STEP solid. A distance/threshold background
   field increases mesh density within a declared influence radius.
   Refuses STEP without circular curves; never assumes a hole exists.
   It will refine all detected circular edges, not just stress-critical ones.
2. **Explicit hotspot coordinates in millimetres:** a `Ball` sizing field
   refines around specified `(x,y,z)` points for STEP or STL.
   Coordinates must be inside the CAD bounding box.

The fields can be combined through Gmsh's `Min` field. The user must
supply a local target size smaller than the global background target
and a positive influence radius. Automatic circular edges require an
explicit opt-in. Up to 12 hotspots or 24 circular edges are allowed.
All prior mesh size, volume consistency, closed solid and element limits
remain in force.

## Examples

Circular STEP through-hole screening:

```bash
python -m hardware_splicer.mechanical_cad_fem drilled.step \
  --mesh-size-mm 8 --local-mesh-size-mm 1.5 \
  --local-radius-mm 8 --refine-circular-edges \
  --fixed-plane x_min --loaded-plane x_max \
  --force-n 100 0 0 --youngs-pa 2000000000 \
  --poisson 0.25 --out /tmp/local-single.json
```

Three localized refinements with the **global size held at 8 mm**:

```bash
python -m hardware_splicer.mechanical_cad_fem drilled.step \
  --mesh-size-mm 8 --local-study-mm 1.5 1.0 0.8 \
  --local-radius-mm 8 --refine-circular-edges \
  --fixed-plane x_min --loaded-plane x_max \
  --force-n 100 0 0 --youngs-pa 2000000000 \
  --poisson 0.25 --yield-pa 100000000 \
  --out /tmp/local-study.json
```

Explicit mounting hotspot for a closed STL:

```bash
python -m hardware_splicer.mechanical_cad_fem bracket.stl \
  --stl-units mm --mesh-size-mm 8 \
  --local-mesh-size-mm 3 --local-radius-mm 10 \
  --hotspot-xyz-mm 50 5 5 \
  --fixed-plane x_min --loaded-plane x_max \
  --force-n 100 0 0 --youngs-pa 2000000000 \
  --poisson 0.25 --out /tmp/bracket-local.json
```

The local study compares effective density by counting the **actual mesh
nodes within the feature influence region**, not assuming total element
count must increase with a smaller local target. A study is marked
`numerically_stable_screening` only if all previously defined
displacement/stress/volume criteria pass and the *near-feature* node
count grows by at least 10% at each step.

Do not treat a local target size as a guaranteed final element edge
length; Gmsh controls the triangulation and may produce unexpected
topologies. Always inspect the resulting mesh and locations.

## Experimental drilled-plate result (Optiplex; Gmsh 4.15.0)

100×20×10 mm plate, Ø6 mm through-hole, 100 N total axial loading,
E=2 GPa, nu=0.25, full opposite-end clamp.

| Strategy | Tetrahedra | Peak von Mises stress |
| --- | ---: | ---: |
| Uniform 8 mm | 566 | 0.949 MPa |
| Uniform 4 mm | 2,030 | 1.097 MPa |
| Local 8 mm background / 1.5 mm target | 717 | 1.181 MPa |
| Local 8 mm background / 1 mm target | 881 | 1.178 MPa |
| Local 8 mm background / 0.8 mm target | 956 | 1.217 MPa |

These are **different numerical estimates, not validated accuracy**.
The local 1.5 → 1 mm pair agrees closely, but the further 0.8 mm mesh
raises the peak stress. That fails the existing 3% relative-change
screen and the local three-mesh study reports
`inconclusive_refinement` with
`peak_stress_changes_with_refinement`.

Local refinement successfully concentrates nodes around the known
through-hole without uniformly refining the entire body. No robust
convergence or independent stress-concentration reference is yet
established. This is exactly why the system must not use raw
`yield_safety_factor` for automatic fabrication decisions.

## What is still out of scope

- NURBS curvature detection beyond OCC `Circle` edges, arbitrary fillets,
  notch detection, automatic semantic identification of load-bearing joints
- Automatic placement of physically appropriate supports and forces,
  real contact conditions, threads, fastening torque or stress singularities
- Adaptive a-posteriori error estimators or guaranteed local stress accuracy
- Nonlinear/contact/multimaterial/anisotropic fatigue, physical testing,
  certified structural analysis or release authority

**Safety:** `mesh_convergence_verified`, `fabrication_authorized` and
`release_authorized` remain false regardless of numerical screening.
