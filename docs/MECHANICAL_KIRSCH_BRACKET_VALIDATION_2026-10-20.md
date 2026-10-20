# Hardware Splicer E8 — Kirsch reference and Mecha mounting bracket (2026-10-20)

## Two different questions, two different evidence types

**Reference A** proves that an independent, genuinely curved **2D
plane-stress** finite-element model reproduces the classical Kirsch
analytical stress field around a free circular hole under remote
uniaxial tension. It applies the analytical Kirsch traction tensor
to the **outer cylindrical boundary** of an annular computational
domain. The hole itself is traction-free. Three discrete displacement
DOFs eliminate rigid motion, *not* represent a clamp.

**Transfer B** takes the real `simple_plate_bracket` parametric source
from Mecha-Splicer, reconstructs that plate with two cylindrical holes
as a STEP solid using OpenCASCADE, and runs the existing **3D P2 curved
tetrahedral** structural screening. It uses a *hypothetical* x-min
whole-edge clamp and 30 N x-max axial traction. These DO NOT correspond
to authentic fastener contacts or measured polymer properties.

Reference A's success cannot make Transfer B safe or correct. Kirsch
assumes an infinite, single-hole isotropic plate under ideal tractions,
while this bracket is finite, contains **two** holes, and uses
non-Kirsch boundary conditions.

Analytical references:
- MIT Mechanics of Materials, Kirsch analytical circular hole, Airy solution:
  https://ocw.mit.edu/courses/3-11-mechanics-of-materials-fall-1999/2ed676922db750766161cdd004b2270a_MIT3_11F99_airy.pdf
- OpenGeoSys Kirsch benchmark and polar stress formulas:
  https://www.opengeosys.org/6.5.9/docs/benchmarks/small-deformations/kirsch/
- JU Applied Mechanics, stress concentration of a wide plate:
  https://mechanics.ju.se/SolidMechanics/StressConcentration.html

## Reference A: reproduce the Kirsch 2D analytical field

The closed-form Kirsch stress is a tensor function of radius, angular
position, hole radius and remote tensile stress `sigma0`. At
the hole rim under x-directed tension:

```text
sigma_rr = 0
tau_r_theta = 0
sigma_theta_theta(theta = 90°) = +3 sigma0
sigma_theta_theta(theta = 0°)  = -1 sigma0
```

The oft-cited **stress concentration factor 3** is the rim
tangential stress divided by the nominal far-field stress in this
**idealized infinite plate**. It is not valid by default for a finite
double-hole part or local clamp-contact stress.

The reference uses Gmsh 6-node curved triangles transferred into
scikit-fem P2 plane-stress displacement FEM. It compares the
numerical Cartesian stress tensor with the **exact analytic Kirsch
tensor at FE quadrature locations**.

Unlike simply reporting an FE global maximum, the gate computes
area-weighted relative stress-field L2 errors both near the hole
(from `r=a` through `r=2a`) and over the whole annulus.

Example:

```bash
pip install -e '.[dev,physics,cad-meshing,physics-validation]'

python -m hardware_splicer.mechanical_kirsch_reference \
  --mesh-study-mm 2.3 1.7 1.3 \
  --out /tmp/kirsch-reference-evidence.json
```

Actual Optiplex results, `a=3 mm`, outer radius 18 mm,
`sigma0=1 MPa`, `E=2 GPa`, `nu=0.25`:

| 2D mesh target (mm) | P2 displacement DOFs | Near-hole weighted L2 field error | Full-annulus field error |
| --- | ---: | ---: | ---: |
| 2.3 | 2,170 | 7.49% | 2.60% |
| 1.7 | 3,762 | 5.14% | 1.78% |
| 1.3 | 6,004 | 4.09% | 1.40% |

All three runs are within the declared **12% near-hole field-error**
screening limit and exhibit monotonically falling near-hole field
error as effective resolution increases. This is an **independent
analytical stress-field comparison**, not a real-world materials test.

## Transfer B: a genuine Mecha-Splicer parametric product template

Canonical source:
`apps/mecha-splicer/src/mecha_splicer/templates/mint_templates.py`,
template `simple_plate_bracket`. Geometry is defined in
`apps/mecha-splicer/src/mecha_splicer/engines/openscad.py`.

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

Original Mecha generator uses:
- a 60×20×4 mm rectangular plate
- two cylindrical Ø3.2 mm through-holes, centered at `(10,10)`
  and `(50,10)` mm
- OpenSCAD difference of plate minus cylinders

The E8 helper regenerates the identical *parametric primitives* using
Gmsh/OpenCASCADE and exports an auditable STEP file. It is **not**
an automated proof of BREP-to-OpenSCAD geometric equivalence.

Use a JSON file with the spec above (or export the actual template's
`default_spec`) and run:

```bash
python -m hardware_splicer.mechanical_bracket_screening \
  --spec-json /tmp/mecha-bracket-spec.json \
  --step-out /tmp/mecha-bracket.step \
  --mesh-study-mm 8 6 5 \
  --edge-force-n 30 \
  --report-out /tmp/mecha-bracket-evidence.json
```

A **nonzero exit code 2 is EXPECTED** for the current bracket
because peak-stress hotspot localization fails.

Assumed material is a homogeneous, isotropic `E=2 GPa`,
`nu=0.25` polymer proxy. Neither actual FDM print-direction
stiffness nor tensile/creep/fatigue properties were measured.

### Actual three-mesh results

| Global curved mesh target (mm) | Quadratic peak sampled von Mises | Approx. hotspot |
| --- | ---: | --- |
| 8 | 1.011 MPa | x=9.8 mm, near first hole |
| 6 | 1.036 MPa | x=49.9 mm, near second hole |
| 5 | 1.011 MPa | x=50.1 mm, near second hole |

The **peak-stress magnitude** changes by only ~2.4–2.5% between
the tested adjacent meshes (below the 3% screening criterion).
However the peak location shifts by **40.3 mm** between the 8
and 6 mm meshes. Its position lies by a different mounting hole,
so the report now records:

```json
{
  "status": "inconclusive_bracket_transfer",
  "curved_fem_study": {
    "blockers": [
      "p2_peak_hotspot_moves_with_curved_mesh_refinement"
    ]
  },
  "structural_safety_verified": false,
  "fabrication_authorized": false
}
```

A 5 mm peak-location tolerance is explicitly declared. Another part
may legitimately have symmetric, equivalent hotspots, but **the
global peak location alone is inadequate to say which specific
mounting feature is critical**. The current tool therefore fails
closed rather than hiding uncertainty.

## Safety and provenance

The E8 reports record the source spec SHA-256, generated STEP SHA-256,
mesh refinement levels, assumed load and supports, curved Jacobians,
stress field/peak locations and numerical blockers.

**Nothing here authorizes** a build for load-bearing use, claims
real fastener-bore contact, validates FDM anisotropy, verifies stress
concentration factors for the two-hole bracket, or supplies actual
bolt preload.

The existing quadratic solver still has its **8,000 DOF ceiling**
and geometry checks, and the new routines remain **trusted-file
local CLIs**, not public path-based HTTP endpoints.

## Next validation priorities

1. Model **screw-hole bearing / finite contact surfaces** and bolt
   restraint, not an entire end face rigid clamp; compare with
   physical bolt preload and fastener geometry.
2. Give each hole its own localized-stress convergence series
   (including angular/radial bins), not only a global maximum.
3. Test actual printed brackets in at least two printing
   orientations and record measured force/displacement curves.
4. Extend the same provenance-based screening to Mecha enclosure
   cutouts and standoffs after validating a relevant load case.
