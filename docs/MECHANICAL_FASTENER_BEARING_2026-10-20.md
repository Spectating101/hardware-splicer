# HS E9 — Bore-bearing structural screening for Mecha brackets (2026-10-20)

## Why this differs from the earlier plate model

The original double-hole plate CAD check clamped an *entire end face*
and pulled the opposite end. Real mounting brackets commonly transmit
load through fastener shanks, bore walls, washers, base surfaces and
frictional/preloaded interfaces, not uniformly across their end faces.
Consequently a good result in the previous screen could not justify
the bracket's performance in an actual installation.

This iteration introduces a first **bounded, reduced-order bore-bearing
boundary model** to evaluate per-hole numerical behavior without
pretending to solve nonlinear bolt contact.

The system models the actual Mecha-Splicer
`simple_plate_bracket` parametric geometry:

- 60 × 20 × 4 mm flat plate
- two through-holes Ø3.2 mm centered at `(10,10)` and `(50,10)` mm
- one closed STEP solid exported from Gmsh OpenCASCADE primitives
- Gmsh optimized curved 10-node tetrahedra, scikit-fem P2 elasticity
- assumed homogeneous isotropic `E=2 GPa`, Poisson ratio `0.25`

## The actual boundary approximation

**Anchor hole (left):** every quadratic displacement DOF on
the *left-facing half* of the first bore wall is fixed in all three
directions. It is explicitly an **over-stiff kinematic restraint**,
not a unilateral/sliding bolt or washer.

**Loaded hole (right):** apply a frictionless-*style* compressive normal
surface traction to the right-facing half of the second bore wall,
using `p(theta) = p0 max(0, -n_x)` with outward solid normal
`n` (which points *into the void* on a through-hole). The pressure
magnitude is integrated using the curved P2 finite-element basis
and normalized to an axial x-resultant of **30 N**.

The model checks that the force and support reactions balance,
the transverse load resultant is less than 5% of 30 N, FE free-DOF
residual is small, and strain energy matches half of the work of
the external force. The curved geometry must also have positive
sampled Jacobians and accurate integrated CAD volume.

This is **not** an actual frictionless contact solution: the load
patch is prescribed, does not change with deformation, includes no
fastener shank compliance/clearance, and the support is fixed rather
than a pressure-only unilateral constraint. Bolt preload, friction,
washer compression, material anisotropy, viscoelasticity, nonlinear
deformation, threading, crack propagation and real printed part
strength are all unverified.

## Run with Mecha's actual template

Export the actual Mecha template spec or use the JSON below:

```json
{
  "bracket": {
    "name": "plate",
    "w_mm": 60,
    "d_mm": 20,
    "t_mm": 4,
    "hole_d_mm": 3.2,
    "hole_spacing_mm": 40
  }
}
```

Install opt-in dependencies:

```bash
python -m pip install -e '.[dev,physics,cad-meshing,physics-validation]'
```

Run a complete spec → STEP → curved bearing load → per-hole stress
refinement workflow:

```bash
python -m hardware_splicer.mechanical_fastener_bearing \
  --spec-json /tmp/mecha-simple-bracket.json \
  --step-out /tmp/mecha-bearing.step \
  --mesh-study-mm 8 6 5 --force-n 30 \
  --out /tmp/mecha-bearing-study.json
```

For an existing trusted STEP model, pass the centers and dimensions:

```bash
python -m hardware_splicer.mechanical_fastener_bearing \
  /tmp/mecha-bearing.step \
  --centers-xy-mm 10 10 50 10 \
  --hole-d-mm 3.2 --thickness-mm 4 \
  --mesh-study-mm 8 6 5 --force-n 30 \
  --out /tmp/mecha-bearing-existing-study.json
```

An **inconclusive** study writes full JSON evidence and exits with
status code **2**. Geometry, solver or resource failures raise an
exception rather than silently returning a pass.

## Real Optiplex experiment

Mesh targets below refer to Gmsh **global target** sizes, not guaranteed
local curved-edge lengths. Values are sampled von Mises stress maxima
within a defined 3 mm neighborhood of each bore.

| Mesh target (mm) | First/anchor hole peak | Second/loaded hole peak | Local force resultant |
| --- | ---: | ---: | ---: |
| 8 | 4.298 MPa | 3.898 MPa | 30 N axial |
| 6 | 4.687 MPa | 4.514 MPa | 30 N axial |
| 5 | 4.204 MPa | 4.238 MPa | 30 N axial |

This compares with approximately **1.01–1.04 MPa** peak estimates
from the old all-end-face loaded/clamped configuration. That increase
shows **the boundary conditions dominate these stress estimates**; it
does NOT establish a more physically accurate yield margin.

The pressure normalization was approximately **2.99 MPa** in
these three runs. The applied force included minor
mesh-dependent lateral components (~0.05–0.27 N), which the
opposing support reacted, all below the documented 5% threshold.

The per-hole report tracks, **separately for each mounting hole**:

- quadrature sample count in the cylindrical neighborhood
- peak sampled von Mises and corresponding physical XYZ location
- volume/area-weighted RMS von Mises over the near-hole neighborhood
- peak stress relative change and RMS change between adjacent meshes
- *angular hotspot movement within each hole*, avoiding confusion
  from a global maximum jumping to the other geometrically symmetric hole
- element/DOF growth, force balance, energy and CAD provenance

Current status is **`inconclusive_bore_bearing_refinement`**. The
first/anchor hole and second/loaded hole have peak-stress relative
changes greater than the declared 5% per-hole limit and
nonstationary angular hotspots. The anchor-hole RMS measure also
changes beyond the declared 3% criterion.

Some RMS measures appear considerably steadier than sampled peak
stress. This suggests more numerical refinement and more physically
appropriate fastener constraints are needed; it **does not establish**
contact/bearing strength.

## Authority and provenance

The implementation checks complete curved cylinder walls (against
analytical `pi × diameter × thickness`), support/load facet
availability, quadratic DOF ceiling (8,000), pressure resultant,
free/reaction equilibrium, and strain/work identity.

The report hashes both the input Mecha bracket spec and the generated
STEP source. In all outcomes:

```json
{
  "true_bolt_contact_validated": false,
  "screw_hole_bearing_strength_verified": false,
  "structural_safety_verified": false,
  "fabrication_authorized": false,
  "release_authorized": false
}
```

**No general fabrication authorization is implied.** This is a
bounded research tool that helps distinguish how a design responds
to alternate stated mechanical boundary assumptions.

## Recommended next layer

Implement non-linear **unilateral pin-to-bore contact** or a simpler
validated finite-element contact benchmark with pin clearance,
including reaction distribution and frictionless slip. Compare with
measured printed-specimen force/displacement data and failure mode,
using at least two print orientations before judging FDM load-bearing
performance. That is more important than further improving numerical
peak maxima under arbitrary contact idealizations.
