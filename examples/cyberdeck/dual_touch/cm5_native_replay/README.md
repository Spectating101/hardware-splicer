# HS native replay — CM5 two-touchscreen pocket cyberdeck

**Objective:** test whether Hardware Splicer itself can transform the product requirement into a revised mechanical design and reject weak physical packaging evidence.

This is NOT the standalone CadQuery v0.3 output. HS now uses its existing `mecha_splicer.bundle.generate_bundle` (native OpenSCAD, BOM, FDM warnings), `hardware_splicer.mechanical_fit.build_mechanical_fit_report` (actual typed AABB clearance checks), and `MachineProject.assess_release` (conservative authority gate). No physical product, powered board, touch/DSI drivers, routed PCB, real thermal test, or fab approval exists.

## Input

`requirements.json` is source- and assumption-labelled: 155 x 80 mm body; **18 mm HARD closed-thickness limit**; two independent Winstar 127.6 x 73.3 x 3.45 mm capacitive MIPI touch displays; single CM5 module and its still-unqualified mating carrier; **no physical keyboard**. This is a CM5 dual-DSI product, NOT the separate 4.3-inch dual-ESP32/RS485 demonstrator already in HS.

The original standalone CadQuery v0.3 housing assumed only a **0.85 mm** enclosure back wall. HS's existing FDM generator enforces a **1.6 mm floor**, a 0.75 mm increase. A truly comparable native HS FDM study MUST carry its native floor into its component stack, rather than copying a 19 mm margin from the thinner external CAD model.

## HS-native result

| Total closed | Nominal CM5/lower-display separation | Gate |
| --- | --- | --- |
| 18 mm | -0.735 mm (overlap) | FAIL |
| 19 mm | 0.265 mm | FAIL 1 mm research margin |
| 20 mm | 1.265 mm | Nominal research margin passes, but **violates user HARD 18 mm limit** |
| 21 mm | 2.265 mm | Same hard-limit violation |

The **continuous theoretical minimum** with exactly these declared layers and >=1 mm research margin is **19.735 mm**. The 20 mm candidate is only a **counterfactual / design exploration**, not authorized as the new user requirement. It can be used to learn what would need changing to return to 18 mm.

**FPC routing remains failed/unqualified:** Winstar's TFT ribbon tail extends approximately 29 mm beyond the 155 mm body if laid straight, so the hinge and bend/connector routing must be redesigned or a different panel selected. Two DSI controllers and both GT928 touch inputs require actual Linux, I2C and backlight verification. The battery is a bare placeholder with NO BMS, swelling clearance, power budget or charger. The 1.5 mm mating and 0.5 mm spreader are assumptions, not qualified MPNs.

## What HS actually generated

- `evidence/hs_packaging_report.json`: bounded parameter sweep, native MechanicalFit AABB pass/fail, explicit user hard-constraint result, FPC gate, BOM, DFM and MachineProject release assessment.
- `evidence/native_project_spec.json`: versioned input to the already-existing Mecha-Splicer clamshell generator.
- `evidence/native_mecha/base_shell.scad`, `lid_shell.scad`, `clamshell_open_preview.scad` and `dual_touch_visual_preview.scad`: **native HS parametric mechanical outputs**, not the earlier CadQuery files.
- `evidence/native_mecha/bom.csv`: CM5 + 2 Winstar panels. No accidental Waveshare ESP32, RS485, CardKB or physical keyboard BOM.
- `evidence/machine_project.json`: canonical requirement/verification graph; safety requirements remain unverified.
- If present, `evidence/native_mecha/*.stl` and `design_evidence.json` are the separately executed OpenSCAD CGAL mesh and sampled hinge checks, **not physical hinge or full-component collisions**.

## Reproduce entirely through HS

From the repository root with Python 3.12+, dependencies for this repo, and the Mecha-Splicer native app:

```bash
export PYTHONPATH=src:apps/mecha-splicer:apps/mecha-splicer/src
python -m hardware_splicer.cyberdeck_packaging_workflow \
  --requirements examples/cyberdeck/dual_touch/cm5_native_replay/requirements.json \
  --out examples/cyberdeck/dual_touch/cm5_native_replay/evidence
python -m pytest -q tests/test_cyberdeck_packaging_workflow.py \
  examples/cyberdeck/dual_touch/tests/test_dual_touch.py \
  apps/mecha-splicer/tests/test_bundle.py
```

For actual CGAL mesh evidence on a machine with OpenSCAD, run the native HS geometric proof via `examples/cyberdeck/produce_terminal.py` using `evidence/native_project_spec.json` as the spec and `evidence/native_mecha` as the output, rather than copying or re-exporting CadQuery models.

## Important limitation

HS has *reproduced* a constrained geometry check from a supplied manufacturer/assumption record; it has **not automatically discovered** or independently qualified the panel, SoM STEP model, FPC, or mating connector. The current typed mechanical AABB checks are **not full CAD-solid collision detection**. Even successful OpenSCAD shell meshes do not prove internal part retention, ribbon bend life, heat dissipation or electrical function.

Next acceptable HS milestone: ingest verified manufacturer mechanical dimensions (including actual connector mating geometry), qualify the real battery/hinge/FPC path, and rerun this same workflow without relaxing the 18 mm hard constraint.
