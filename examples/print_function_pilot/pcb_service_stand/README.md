# HS Function → Geometry → 3D Print — first real functional pilot

This is the first executed closed-loop *concept-level* geometry-selection
trial in HS. It is not an autonomously invented industrial component.

**Intended function:** hold a small, unpowered PCB vertically for
hands-free visual inspection, with an open-top edge slot, separated
supports and access to both board faces. The trial uses a nominated
80 × 56 × 1.6 mm board, with 25 g nominal mass. These are **declared
test parameters**, not physically measured dimensions from a specific
phone, C64 or repair device.

## Why this matters

HS already includes:
- an actual function-intent → MachineProject bridge;
- STEP source identity and mechanical pose/fit checks;
- STEP BRep authoring through existing multi-CAD workflows;
- mechanical release authority gates.

This pilot extends these into one executable chain:
**functional requirements → HS MachineProject traceability →
multiple real CadQuery solid candidates → native STEP/STL export →
STEP roundtrip and mesh/manifold checks → CAD-derived volume →
declared tolerance/print-bed/static-tip model → ranked candidate.**

The minimum-volume candidate must satisfy *all* the declared numerical
constraints. Failed candidates are retained and explained.

## Real toolchain and generated outputs

CadQuery 2.6.1 authored six native solids; OCP independently reimported
their STEP files; trimesh independently reimported their STL files and
confirmed each mesh is watertight. Each candidate passes nominal
PCB-envelope nonintersection, declared slot clearance and wall thickness.

Execute using a Python environment containing CadQuery 2.6.1,
trimesh 4.12.2, the standard HS package and pytest:

    PYTHONPATH=src python3 examples/print_function_pilot/pcb_service_stand/run.py \
      --out /tmp/hs_print_stand_functional_trial

It deliberately refuses overwriting prior results. The generated
folder includes function_intent.json (validated by native HS
MachineProject), one STEP and STL per candidate, selected_holder.step,
selected_holder.stl, FUNCTION_GEOMETRY_EVALUATION.json, and a
separate NATIVE_AUDIT.json.

The checked-in generated/ folder is the actual successful native
toolchain output, NOT a render or hand-written proxy.

## Published functional assumptions

- Nominal board 80 × 56 × 1.6 mm, mass 25 g — **not measured**
- Slot 2.2 mm across (0.30 mm clearance per side)
- Two separated upright supports and 14 mm PCB edge-slot bottom height
- Print volume 220 × 220 × 250 mm, 0.4 mm nozzle nominal
- Generic PLA density 1.24 g/cm³ with **0.55 effective printed
  density fraction ASSUMED**, not calculated by a slicer
- Hypothetical lateral force 0.10 N at the top of a 56 mm board
- Quasistatic tip-factor threshold 1.50 under those assumptions
- No measured friction, anisotropic layer adhesion, impact resistance,
  fatigue analysis, ESD properties or actual hardware test
- Zero print-support ceilings by design (top-open slots); not
  validated by an actual slicing profile

## Native design evaluation

| Design | CAD solid volume cm³ | Modelled tip factor | Fit + native files | Declared numeric gates |
| --- | ---: | ---: | --- | --- |
| Solid plate | 40.47 | 2.506 | pass | pass |
| Minimal rail, depth 46 | 19.97 | 1.245 | pass | FAIL tip proxy |
| Minimal rail, depth 52 | 20.93 | 1.431 | pass | FAIL tip proxy |
| **Ladder rail, depth 58** | **24.31** | **1.690** | **pass** | **pass / selected** |
| Ladder rail, depth 64 | 25.36 | 1.897 | pass | pass |
| Reinforced rail, depth 68 | 30.62 | 2.186 | pass | pass |

**Result:** 39.9% reduction in BRep solid volume versus the
full plate under the declared 0.10 N push and assumed effective
density. This is **NOT 39.9% less printed filament** until slicing
and material/profile assumptions are tested.

### An honest design-change counterfactual

Increase the specified hypothetical push from 0.10 N to 0.16 N
without changing the CAD generator or its scoring logic.

The selected topology becomes the FULL PLATE; its modelled static
tip factor drops to 1.566, while each open rail drops below the
declared minimum 1.5. The selector demonstrates that "best" is
requirement-dependent, not one arbitrarily preferred shape.

## Source and release integrity

- The input geometry specification is versioned design_request.json.
- Both original functional intent and native geometry generated
  artifacts carry SHA-256 source/provenance checks.
- An independent audit reloads all STEP and STL files, recomputes
  BRep/mesh volumes, verifies SHA, prevents design-source substitutions,
  and confirms that the selected file is exactly the lowest-volume
  **feasible** candidate — not a fake output JSON label.
- Existing HS function-intent bridge creates five requirements,
  three functions, and one unresolved interface.
- No new competing project registry is introduced.
- Intended fabrication/test authority stays *false* throughout.

## Real next-world acceptance tests

1. Caliper-measure an actual PCB thickness/edge bevel and build-surface
   envelope. Redesign with those source-verified measurements.
2. Use a real slicer and named printer profile to obtain exact
   layer preview, support use, wall count, material use and estimated
   print time; reject candidates with actual slicer problems.
3. Print at least one fit coupon first, then the full stand. Inspect
   slot width and stress risers with calipers, including tolerance
   changes and repeated insertion.
4. Measure actual board and printed stand mass; compare experimental
   unpowered lateral push / slide / tip behavior against the simple
   model. The model is not FEA and does not qualify structural load.
5. Ordinary PLA is **not ESD certified**. Do not position this as
   a protection-qualified fixture for ESD-sensitive electronics
   without a proper ESD-safe material and process.

**Conclusion:** HS can now generate *actual printable CAD artifacts*
and conditionally select a functionally motivated geometry within a
limited parametric design family. It cannot yet prove the print will
fit, retain, or protect a real board; and it has not autonomously
created new topologies from open-ended natural-language prompts.
