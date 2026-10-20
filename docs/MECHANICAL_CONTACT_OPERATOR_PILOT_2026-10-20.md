# Hardware Splicer — Contact Engineering Pilot

*E12: operator-ready local screening, October 20 2026.*

## Purpose and boundaries

This is a **real usable investigative workflow**, not a load-bearing
manufacturing approval system. Users can generate a Mecha-Splicer double-hole
STEP part, solve curved high-order contact at both pins, audit mesh, interface
resolution, numerical constraint residuals and source material assumptions,
and open a readable HTML review without configuring an API or UI server.

No API endpoint to read arbitrary computer files is exposed. The user
explicitly selects an existing local JSON file and an empty output folder.

The analytical Kirsch reference (E8) established one independent 2D
elasticity test; it does **not** certify the E11 nonlinear joint's
continuum stress. E11 uses node-collocated, small-deformation,
frictionless Signorini-style KKT conditions for rigid pins, with a weak
numerical gauge for otherwise unconstrained rigid motion. It does NOT
represent bolt shank elasticity, washers, preload, slip or calibrated FDM
printed materials.

## 1. Install

```bash
python -m pip install -e '.[dev,physics,cad-meshing,physics-validation]'
```

An environment with Gmsh's shared runtime, SciPy, NumPy and scikit-fem is
required. CI runs the same dedicated FEM stack.

## 2. Create the Mecha bracket spec

A ready-to-use copy is included at
`examples/mechanical/mecha_simple_plate_bracket.json`.
A blank **measured-trials** CSV header is available at
`examples/mechanical/physical_trials_template.csv`.

You can also save the following to `mecha-bracket.json`:

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

These numbers match the actual Mecha-Splicer `simple_plate_bracket`
template. A helper rebuilds the matching parameterized OpenCASCADE solid
as STEP; the independent OpenSCAD-to-STEP geometric equivalence still needs
metrology and proof.

## 3. Single command

```bash
python -m hardware_splicer.mechanical_contact_workbench \
    --spec-json ./mecha-bracket.json \
    --output-dir ./my-first-bracket-study \
    --mesh-study-mm 8 6 5 \
    --drive-mm 0.02 \
    --clearance-mm 0.005 \
    --sweep-mm 0 0.01 0.02 0.04
```

The program writes five tangible artifacts in a new/empty folder:

- `bracket.step`: generated parametric CAD with SHA-256 provenance
- `evidence.json`: raw full-resolution stress and contact calculations,
  both-bore force reactions, KKT residuals, gap probes and numerical blockers
- `review.html`: offline self-contained, script-free, readable review
- `remaining_actions.txt`: the actual unresolved material and testing tasks
- `predicted_load_curve.csv`: simulated rigid-pin displacement versus reaction,
  with active pin contact-node counts; **not measured force/displacement**

**Return code 2 is expected.** It means the completed investigation has
structural-release blockers, *not* that it failed to produce results. An
exception means the engineering calculation itself could not run; never
interpret a failed solver as a favorable outcome.

## 4. What actually improved

The E11 basic solver only guaranteed the unilateral gap inequalities
at **chosen surface nodes**. E12 samples the displacement and pin
gap at additional curved face quadrature points, which can expose
*between-node overlap* even though the KKT nodal constraints are fulfilled.

In the standard 8/6/5 mm bracket screen, the largest sampled
between-node overlap is approximately:

| Global mesh | Largest sampled gap violation |
| --- | ---: |
| 8 mm | 0.0755 micrometres |
| 6 mm | 0.0515 micrometres |
| 5 mm | 0.0493 micrometres |

These violations are small but not zero. The default bounded research
screen checks for violations greater than **0.10 micrometres** and
records the true value. It does *not* claim contact over the full
continuous surface is proven.

Global mesh sizes can be misleading: although the 8→6→5 mm study
increases total displacement degrees of freedom, the number of
contact nodes at the two bores is nearly unchanged (roughly 122
each). E12 flags **insufficient contact-surface refinement** per
hole rather than assuming the growing volume DOFs establish contact
convergence.

A separate local edge-refinement experiment using 8 mm global /
2.0–1.5 mm circular-edge mesh targets increased contact resolution
but did not establish steady stress peaks; 1.0 mm and finer targets
failed Gmsh high-order Newton optimization on this fixture.
Such failures are genuine mesher limitations and are **not** silently
replaced with successful claims.

The near-hole P95 quadrature stress and weighted RMS stress are also
reported. P95 samples changed by less than ~7% between adjacent
global meshes in this nominal study, but neither is a validated
allowable strength. The **largest localized sampled stress** still
changes substantially at both bores. The conservative release
blockers remain.

## 5. Optional physical-test record inventory

You can supply real specimen measurements as CSV via
`--physical-trials-csv ./my-specimen-trials.csv`.
The parser requires exact columns:

```csv
specimen_id,print_orientation,material_batch,fixture_protocol_id,measured_bore_d_mm,measured_pin_d_mm,maximum_force_n,displacement_at_maximum_mm,failure_mode
```

Each subsequent CSV row must contain **real measured values from actual
tests**. The tool does not generate or assume physical measurements.
Supported failure modes: `hole_bearing`, `net_section_fracture`,
`delamination`, `bending`, `fastener_failure`, `fixture_slip`,
`no_failure_observed`, `other`.

The physical inventory checks:

- unique specimen IDs and finite plausible dimensions, forces and travel
- at least two distinct print orientations, with at least three specimens
  per orientation for the minimum *data completeness* gate
- one consistent named fixture protocol (mixed fixtures are flagged)
- actual measured pin/bore clearances versus the FEM clearance assumption

**Passing this inventory never authorizes manufacturing.** It checks
the presence and internal consistency of user-supplied data, not their
authenticity, traceable instruments, equivalence of fixture conditions
to the model, constitutive parameter calibration, failure criteria
or an independent engineer's sign-off.

## Pilot findings and next non-software dependencies

In the canonical test, force transfer between pins is approximately
16 N and robust to artificial KKT active-set selection; near-hole
peak stress remains mesh-dependent. The code therefore reports
`inconclusive_two_pin_contact_stress`, and all
`fabrication_authorized` / `release_authorized` flags remain false.

**Software screening is usable** for investigation and planning test
fixtures. Reliable load-bearing strength ratings still require:
actual bore/pin dimensions, constitutive material tests per print
orientation, a controlled and model-matched physical load rig with
measured force-displacement traces, and independently verified
contact-pressure/stress convergence.

To date no such physical measurements have been supplied. This is an
explicit product boundary, not a placeholder claim of verification.


## 6. Simulated load curve, not a design load rating

The operator bundle also simulates a constrained set of rigid-pin movements
(at the coarsest mesh) and outputs the uncalibrated numerical force as
`predicted_load_curve.csv`, alongside active contact-node counts.
In the representative test:

| Assumed pin travel | Simulated transmitted force |
| --- | ---: |
| 0 mm | 0 N |
| 0.01 mm | about 0 N (both clearances just closing) |
| 0.02 mm | about 16.2 N |
| 0.04 mm | about 54.4 N |

This is suitable for designing *what to measure* on a controlled fixture,
not for declaring a maximum safe load. A real force–displacement curve
must come from actual calibrated measurement equipment and a matched fixture.
