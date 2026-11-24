# E10 — Unilateral rigid-pin / bore penalty contact (2026-10-20)

## What was implemented

The E9 reduced-order bearing screen prescribed a cosine-weighted
surface traction patch on hole two. E10 replaces that patch with an
**active-set unilateral normal penalty contact law**: at each
quadratic bore-surface quadrature point the force can push, but cannot
pull. The active contact region is recomputed from the current elastic
solution, so it changes with pin displacement.

For an ideal cylindrical bore with outward radial direction `e_r`,
assumed radial clearance `c`, prescribed rigid pin translation
`d_x`, and elastic bore displacement `u`, the linearized
penetration is:

```text
penetration = max(0, d_x e_rx - (u · e_r) - c)
normal_pressure = penalty_pa_per_m × penetration
contact_traction_on_solid = normal_pressure × e_r
```

The reduced-order governing equation is the linear elastic
stiffness balance with this *piecewise linear* unilateral traction.
The solver updates its active set, reassembles contact stiffness and
force, and refuses a result if its active set fails to converge
within a bounded number of iterations. The all-XYZ fixed left-facing
semicylinder on hole one is retained from E9 as a **simplified,
over-stiff anchor**.

**Not solved:** exact zero-penetration Signorini conditions, nonlinear
finite-deformation geometry, deformation of the bolt pin, friction,
sliding, washer/preload contact, joint clearance measurement, or
manufactured FDM strength. This is a penalty-regularized
displacement-controlled *one-hole* contact subproblem, not a full
unilateral two-pin assembly.

## Reproduce with Mecha-Splicer's actual 60 × 20 × 4 mm plate

A Mecha `simple_plate_bracket` template JSON is used to generate
the same two-hole STEP fixture (two Ø3.2 mm bores, x=10 and 50 mm).

```bash
python -m pip install -e '.[dev,physics,cad-meshing,physics-validation]'

python -m hardware_splicer.mechanical_unilateral_pin_contact \
  --spec-json /tmp/mecha-simple-bracket.json \
  --step-out /tmp/mecha-unilateral.step \
  --mesh-study-mm 8 6 5 \
  --drive-mm 0.02 --clearance-mm 0.005 \
  --penalty-pa-per-m 500000000000 \
  --out /tmp/mecha-unilateral-report.json
```

The CLI runs *both* a three-mesh study at the given penalty and
a fixed-mesh **three-penalty sensitivity study**. It emits a JSON
report including STEP/source SHA-256, load/displacement assumptions,
contact activations, pressures, force/support equilibrium, per-hole
P2 stress samples, numerical sensitivity, and explicit blockers.

## Actual Optiplex contact activation experiment

Curved quadratic STEP tetrahedra, `E=2 GPa`, Poisson = 0.25,
radial clearance `0.005 mm`, active-set penalty
`5 × 10¹¹ Pa/m`, with only the **first bore's left-facing half
fully fixed**.

| Driven rigid-pin translation | Curved mesh 8 mm | 6 mm | 5 mm |
| --- | ---: | ---: | ---: |
| 0 mm | 0 N | 0 N | 0 N |
| 0.020 mm | 21.44 N | 21.22 N | 21.23 N |
| 0.050 mm | 68.07 N | 67.41 N | 67.46 N |

At zero motion, the active contact area and pressure are zero:
**the model has no tensile adhesion**. At increasing motion the
active pressure area and bore reaction both increase. This is
a verified *numerical property of this code*, not a measured
material load curve.

For the 0.020 mm case:

| Mesh target | Hole 1 peak sampled von Mises | Hole 2 peak |
| --- | ---: | ---: |
| 8 mm | 3.228 MPa | 2.906 MPa |
| 6 mm | 3.022 MPa | 3.012 MPa |
| 5 mm | 2.908 MPa | 3.295 MPa |

The fixed-penalty three-mesh screen passes its declared *12% peak
and 6% RMS* stress-change criteria, and its 4% bore-force change
criterion. **This does not certify stress convergence, engineering
reliability or correctness of chosen model parameters.**

## The decisive penalty sensitivity result

At constant 0.020 mm pin translation on the **same** 8 mm
curved mesh:

| Normal penalty stiffness | Predicted X reaction | Maximum allowed numerical penetration |
| --- | ---: | ---: |
| 1 × 10¹¹ Pa/m | 9.54 N | 0.01056 mm |
| 5 × 10¹¹ Pa/m | 21.44 N | 0.00499 mm |
| 1 × 10¹² Pa/m | 25.40 N | 0.00307 mm |

**The contact force remains too dependent on an arbitrary penalty
stiffness.** The overall report therefore flags
`contact_force_sensitive_to_penalty_stiffness`, uses status
`inconclusive_joint_contact_screening` and exits with code **2**,
despite the apparently stable three-mesh series.

This reveals why selecting a single numerical penalty based on
convenience is not a valid basis for design decisions.

A separate analytical **one-degree-of-freedom spring-contact law**
checks the active-set formula: no contact until closure, and after
closure `u = k_contact(d-c)/(k_structure+k_contact)`.
It is a mathematical constitutive sanity check, not an independent
3D contact solver.

## Numerical restrictions and release authority

- Bounded CAD import: STEP single solid, verified curved tetrahedra,
  positive sampled Jacobians and integrated STEP volume comparison
- Quadratic displacement DOFs <= 8,000, active-set iterations <= 50
- Contact pressure only compressive, no artificial negative pressure
- Integrated pin-bore resultant balances the simplified fixed anchor
  reaction; numerical free DOF residual checked
- Missing/nonconverged numerical model raises an error
- All releases/fabrication and physical-strength gates remain false

## Priority for E11

Replace penalty sensitivity with **complementarity-consistent
nonpenetrating contact** (active-set Lagrange multipliers or
augmented-Lagrangian treatment), then enforce convergence in normal
gap, contact force and contact area. The *first* bore also needs
unilateral anchor-pin contact rather than an overly rigid fixed
semicylinder. Real printer/process and fastener dimensions plus
measured mechanical data are required before a manufactured bracket
could receive a credible load limit.
