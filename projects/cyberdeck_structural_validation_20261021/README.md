# Cyberdeck engineering: real CAD structural simulation with existing open-source FEM

**Executed 21 October 2026 on the authorized Optiplex.** This is a software
structural-validation *research study*, **not** a real load rating, a validated
manufactured device, or a recommendation to fabricate/use a loaded cyberdeck.

## What was actually tested

We reused three established open-source projects instead of writing another
physics solver:

| Existing project | Actual role in this work | Outcome |
| --- | --- | --- |
| [Gmsh](https://gitlab.onelab.info/gmsh/gmsh) | Imports *actual HS STEP base and lid* and tetrahedrally meshes each OCC solid | Works: >30,000 tetrahedra per part |
| [scikit-fem](https://github.com/kinnala/scikit-fem) | Assembles/solves isotropic, small-strain 3D linear elasticity on Gmsh volume meshes | Works on both parts; numerical limitations described below |
| [Shapely/GEOS](https://github.com/shapely/shapely) 2.1.2 | Exact mesh-facet and original KiCad board-outline **planar intersection**; distributes source-derived lip loads | Fixes spurious variation in nominal loaded area |
| Existing **HS bounded tetra solver** | Independent numerical comparison with scikit-fem on identical 10 mm lid mesh | Agreement to approximately 1e-12 relative displacement and von Mises stress |

The **case geometry** is the improved, still *unreleased*, source-derived
component-model-screened candidate from the same original `RPI_DEV` PCB that
HS has been testing. The **exact SHA-256 identifiers** and derived simulation
results are archived alongside this report; the CAD remains in the user's
authorized Optiplex local workspace. The original KiCad board bytes (SHA-256
`ddf94ad6fdaee46a52022b20da8678cebd34cec4f4db817d090cd0e45119f042`)
remain the source of the 33-point nominal board outline. The original KiCad
source and the independent board-only STEP are not reproduced here. The public
RPI_DEV upstream currently reports **no declared license**, so publishing its
original or derived CAD on this new branch is intentionally avoided pending
confirmed reuse rights; public visibility is not an open-source license.

**Case geometry covered here is NOT the old published base/lid in PR #182:**
the old published lid's **SW1 1.584 mm³ component interference remains a known
failure**. The improved case cleared seven original 3D models in a separate
screen, but **19 of the 26 PCB footprints still lack original verified 3D
coverage**. This structural study does not resolve those missing envelopes.

## Boundary and material model: declared hypotheses, not verified physical data

- Four **case screws outside the original board** are treated as perfectly
  fixed nodal collar constraints. The real lid has holes of 3.3 mm diameter
  and the base nominal pilot holes of 2.7 mm. Neither bolts, washer
  distribution, thread preload, friction, board contact or case connection
  stiffness is modelled.
- The original KiCad board-contour interior capture shelf is subject to a
  **hypothetical total 1 N vertical force**, directed upward on the lid and
  downward on the base. The available shelf contact projection is derived
  from CAD+board-polygon intersections rather than assumed from a rectangle.
- Nominal **Young's modulus 1.5 GPa**, **Poisson ratio 0.35**, isotropic elastic.
  Not an identified/qualified printed polymer, build process, strain curve,
  thermal rating or measured material coupon. No meaningful yield safety
  factor or production load rating can follow.
- Static small-strain P1 tetra elements only. No true nonlinear contact,
  print-layer anisotropy, crack/creep/fatigue, thermal load or drop/vibration.

## Actual numerical outcomes

Six mesh sizes (10 to 2 mm) were initially run on both parts. See
[`BROAD_MESH_STUDY.json`](./BROAD_MESH_STUDY.json) and
[`FINE_MESH_STUDY.json`](./FINE_MESH_STUDY.json) for counts, boundary areas,
displacements, element-average peak stresses and force residuals.

At the finer 2.0 → 1.7 → 1.5 mm levels:

| Measured software output | **Base at 1.5 mm** | **Lid at 1.5 mm** |
| --- | ---: | ---: |
| Tetrahedral elements | 30,708 | 17,971 |
| Max hypothetical displacement | 0.01001 mm | 0.02661 mm |
| Peak element von Mises | 0.1630 MPa | 0.3306 MPa |
| Material release/yield test | Not performed | Not performed |

- Original-source contact projection: **299.98 mm² base** and **297.28 mm²
  lid** at coarse levels; finer levels stabilize at approximately **299.70**
  and **297.00 mm²** respectively. These are *nominal planar contact
  candidates*, not true real-world mating area.
- HS's older solver **correctly refuses** the 6,590-tetra base at 10 mm
  because its finite-element cap is 5,000. Using the already installed
  scikit-fem solves that same source geometry without weakening HS's
  original limit.
- The scikit-fem lid and original HS solver agreed to better than
  **3×10⁻¹² relative difference** on exactly the same 10 mm lid
  tetrahedra, loading and constraints. This confirms internal numerical
  consistency at one resolution, **not** physical model correctness.
- A first three-mesh window (2, 1.7, 1.5 mm) *appeared* to pass a pilot
  tolerance (5% displacement, 10% peak stress). However, the additional
  **1.2 mm** lid mesh (31,053 tetrahedra) reported **0.04704 mm** maximum
  displacement and **0.47018 MPa** peak element stress. This is **+76.75%**
  displacement relative to the 1.5 mm result, defeating a convergence claim.
- The base at the fine levels was also inconclusive: displacement and peak
  stress change substantially between refinements.

**Acceptance: geometry-to-mesh-to-linear-FEM executable = PASS;
mesh-independent strength/retention validation = FAIL/INCONCLUSIVE;
physical product qualification = NOT TESTED.**

The wider lesson: a software simulation can produce small-looking stress and
movement numbers that are **not dependable**, even though a structural solver
returns successfully. Source-accurate loads, more than one independent solver,
and deliberately finer verification caught the problem here.

## External tool evaluation / why not add another solver yet

Other relevant established source repositories were checked:

- [CalculiX via pygccx](https://github.com/calculix/pygccx): 3D structural,
  contact and pretension/load modelling; the local `ccx` binary is **not
  installed**. This is the leading *next* candidate when actual fastener
  preloads and nonlinear contact are defined. It carries GPL-3.0 licensing
  and an extra solver deployment requirement; no code has been copied.
- [SfePy](https://github.com/sfepy/sfepy): substantial Python PDE/elasticity
  suite, useful for coupled thermal/mechanical scenarios. Not installed or
  tested here, so not claimed superior.
- [pycalculix](https://github.com/spacether/pycalculix): older 2D CalculiX
  automation project, publicly archived in 2024. Not preferred for a 3D
  screw-clamped case.

A new general-purpose FEM implementation is **not needed**. The engineering
shortfall is the quality of boundary conditions, contact assumptions and
realistic loads, plus unverified material data. A known upstream contact
solver is a better next step than writing HS-specific contact physics.

## Reproduction

The complete model wrapper, using existing FEM libraries rather than new
numerical assembly code, is
[`scripts/screen_cyberdeck_open_source_fem.py`](../../scripts/screen_cyberdeck_open_source_fem.py).

Install only the optional dependencies needed for this scientific workflow:

```bash
pip install -e '.[physics,cad-meshing,physics-validation,physics-geometry]'
```

The candidate STEP files and original source documents must be available
locally to the person authorized to use them; they are NOT reproduced in this
new branch. Separately export your authorized copy of
`RPI_Dev_1.kicad_pcb` to a board-only STEP via KiCad, and derive the original
board interface JSON via HS's installed `inspect_board_interface_bytes`.
Then run:

```bash
python scripts/screen_cyberdeck_open_source_fem.py \
  /path/to/locally-authorized-improved-candidate \
  /path/to/source-verified-kicad-interface.json \
  /path/to/locally-authorized-board-only.step \
  --parts lid base --sizes-mm 2 1.7 1.5 \
  --out /tmp/hs-real-case-structural-study.json
```

Always run an additional finer level before treating apparent convergence as
meaningful; our finer 1.2 mm study overturned the original apparent pass.
The report preserves original STEP file digests, load/constraint information,
full per-mesh results, solver comparisons and blocking outcomes. Regression
tests `tests/test_cyberdeck_open_source_fem.py` check exact polygon load area,
upstream solver agreement, material scaling and source tampering rejection.

## Next actual product gate

1. Reconcile the concurrent improved component-model CAD with the published
   product package and source hashes. The current published SW1 collision must
   be removed in the same tested revision.
2. Resolve missing 3D bodies, critical connector/cable space and source
   copper/PCB keepouts; generate real assembly contact surfaces.
3. Use an established nonlinear contact/bolt solver such as CalculiX with
   physical or justified screw loads and measured polymer print anisotropy,
   then verify refinement and boundary-condition sensitivity.
4. Only after the mechanical load model is valid, consider a physical first
   article with measured fit, stiffness, electrical safety and retention.

The **product is not proven physically functional** by this study.
