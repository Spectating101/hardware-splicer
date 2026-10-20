# Hardware Splicer E11 — Nodal KKT complementarity at both pin bores

**Status:** implemented, tested against a one-DOF analytical benchmark and
executed on the actual Mecha-Splicer two-hole bracket. The contact-force
equilibrium looks stable; **peak stress does not converge**. This remains
screening and does not approve load-bearing fabrication.

## Technical change from E10

E10 modeled one rigid translated pin by imposing a penalty pressure
`p = k·max(0, pin travel - bore displacement - clearance)` and
kept the first bore partly fixed. The resulting contact force varied
with arbitrary penalty stiffness. E11 replaces the penalty pressure
with a **sparse active-set saddle-point (Kuhn–Tucker) solve**:

```text
minimize 0.5 uᵀ K u - fᵀ u
subject to C u − q >= 0

K u − f − Cᵀ λ = 0
λ >= 0
(C u − q) >= 0
λᵀ(C u − q) = 0
```

Each constraint is a radial rigid pin-to-bore inequality on a
*quadratic finite-element surface node*. The first pin is immobile,
the second is prescribed to move +X. **Both bores are unilateral**:
no surface node is clamped at the left bore, and both contact
reactions arise from nonnegative multipliers. The numerical
active-set selection coefficient is **not part of the equilibrium
stiffness or contact pressure law**.

The stiffness matrix retains a very weak, explicit rigid-mode
stabilization `epsilon·I`, otherwise the assembly is free to
translate/rotate when not touching pins. It is an artificial
numerical gauge, *not* a real fixture. Its resultant force is
computed and rejected if it exceeds 1% of transmitted force.
An explicit gauge-sensitivity study tests its influence.

## Scope caveats

This is **node-collocated contact on a small-displacement linearized
geometry**. Nonpenetration between high-order surface nodes has
**not** been proven, and contact tractions are nodal force
multipliers, not accurate continuum contact pressures.
The mesh uses Gmsh optimized ten-node curved tetrahedral geometry
and scikit-fem quadratic displacements, but bolt deformation,
true pin-to-hole clearance measurement, preload, washers,
friction, tangential slip, finite-rotation contact, plasticity,
printed polymer anisotropy and experimental verification remain
absent. The weak gauge and linear elastic material are idealizations.

This is neither a general-purpose nonlinear-contact solver nor
a validated printed-bracket strength predictor.

## Reference and verification

The analytical 1D spring benchmark constrains `u >= d − c`
with stiffness `k`. For positive closure its exact solution is
`u = d − c`, reaction `F = k(d − c)`; for an open
contact the force is zero.

The numerical KKT solver reproduces `F = 400 N` for
`k=10⁶ N/m`, `d=0.5 mm`, `c=0.1 mm` with **no
penalty-controlled overlap**. Using active-set selectors
10⁶, 10⁷ and 10⁹ N/m returns the same reaction.

The rank-deficient benchmark fails closed. The real 3D model
checks all nodal gaps nonnegative (within 5×10⁻¹⁰ m),
multipliers nonnegative, complementarity and free-DOF equilibrium
small, curved Jacobians and integrated CAD volume valid.

## End-to-end real Mecha bracket example

Template source:
`apps/mecha-splicer/src/mecha_splicer/templates/mint_templates.py`

- 60×20×4 mm plate, two Ø3.2 mm bores centered at
  (10,10) and (50,10) mm
- 0.020 mm rigid translation of the second pin; first pin stationary
- assumed 0.005 mm radial clearance at both pins
- isotropic E=2 GPa, Poisson ratio 0.25
- three optimized Gmsh curved tetrahedral mesh targets 8/6/5 mm

```bash
python -m pip install -e '.[dev,physics,cad-meshing,physics-validation]'

python -m hardware_splicer.mechanical_contact_validation \
  --spec-json /tmp/mecha-simple-bracket.json \
  --step-out /tmp/e11-bracket.step \
  --mesh-study-mm 8 6 5 \
  --drive-mm 0.02 --clearance-mm 0.005 \
  --out /tmp/e11-contact-audit.json
```

Expected exit **2** because both hole-localized peak stresses
are not mesh stable. The JSON report includes the generated
STEP and input-spec SHA256, all mesh levels, numerical
gauge and active-set-selector studies, numerical blockers,
and explicit non-authorizing flags.

### Real Optiplex results

| Global mesh target | Pin-to-pin force scale | Global sampled peak von Mises |
| --- | ---: | ---: |
| 8 mm | 16.2236 N | 4.727 MPa |
| 6 mm | 15.9318 N | 2.528 MPa |
| 5 mm | 15.9895 N | 3.648 MPa |

The two pin force resultants on the coarsest mesh are approximately
−16.2234 N and +16.2236 N in X, their small imbalance being
absorbed by the documented weak numerical gauge. This is not
a prescribed 30 N applied-force problem; it is a **prescribed
pin displacement** contact problem.

The tested worst nodal gap violation was below 2×10⁻¹³ m.
At 8 mm global target, active contact nodes were 27 at the
stationary hole and 13 at the driven hole, and 5 active-set
iterations were needed.

### Check sensitivity to numerical *gauge* (not contact penalty)

| Artificial gauge | Force at 8 mm mesh |
| --- | ---: |
| 0.001 N/m | 16.22349 N |
| 0.010 N/m | 16.22356 N |
| 0.100 N/m | 16.22426 N |

The largest gauge setting generates a resultant gauge force below
0.015% of the nominal contact-force scale. The active-set selection
parameter 10⁶/10⁷/10⁸ N/m gives identical 16.22356 N solutions.

**These outcomes validate the discretized KKT force equilibrium
for this case, not continuum contact-stress accuracy.**

### Hole-specific stress refinement

| Target | First-hole local sampled peak | Second-hole local sampled peak |
| --- | ---: | ---: |
| 8 mm | 4.727 MPa | 3.259 MPa |
| 6 mm | 2.528 MPa | 2.255 MPa |
| 5 mm | 2.906 MPa | 3.648 MPa |

Both holes' peak stresses change beyond the configured 10% screening
criterion. Near-hole RMS measures are considerably less sensitive
but do not make the peak trustworthy.

Combined status: `inconclusive_two_pin_contact_stress`.
Blockers: `hole_0_peak_stress_not_converged`,
`hole_1_peak_stress_not_converged`.

## Limitations, non-authority and what next

Report fields always keep
`continuous_contact_surface_verified=false`,
`true_assembly_strength_verified=false`,
`physical_validation_required=true`,
`structural_safety_verified=false`,
`fabrication_authorized=false`,
`release_authorized=false`.

The next defensible improvements are to:
1. refine contact geometry and pressure reconstruction around each
   bore, comparing against a controlled analytical pin/annulus solution
   instead of only peak samples
2. implement a dedicated continuum-contact reference with
   pin elasticity and verified clearance/load displacement
3. collect actual bore sizes, pin sizes, print orientations and
   measured force/displacement plus failure mode of real specimens

Until then, the model remains a **numerical contact investigator**,
not a strength certification or production-release engine.
