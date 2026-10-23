# HS first manufacturing challenge — executed digital acceptance receipt

Date: 2026-10-23. Challenge `hs_mfg_01_cardboard_corner_joint`. **Not a physical manufacturing success.**

## Task and acceptance

Build a printable, editable **90° low-load alignment connector** for two nominally 3-mm cardboard sheets. Explicit engineering requirements: perpendicular U slots, printable solid body, a mounting hole, bounded configurable sheet-to-slot clearance, positive & negative fit checks, exportable STEP and STL, small fitting coupons, real slicer import/toolpath attempt. No strength-rated or load-bearing performance is asserted. Intended first printer/material are unknown.

## Executed model

Source: `examples/manufacturing/cardboard_corner_joint/generate.py`, using already available **CadQuery/OpenCascade**, not a new custom CAD kernel. Test: `test_geometry.py`, **3/3 tests passed**. Geometry-parameter sweep covered 9 thickness/clearance combinations plus 6 invalid-parameter cases.

| Evidence | Actual output |
|---|---|
| Stock assumed | 3.00 mm; **not physically measured** |
| Clearance assumed | 0.30 mm per side (calibrate on real printer) |
| Slot width | 3.60 mm |
| Connector overall bounds | 46.2 × 46.2 × 24.0 mm |
| BREP modeled volume | 11,417.894 mm³ |
| Exported STL | 560 facets; **one connected watertight oriented mesh** |
| STL modeled volume | 11,418.031 mm³ (mesh discretization) |
| Exported STEP | Successfully re-imported; 11,417.894 mm³ |
| Exact CAD nominal 3mm panel interference | 0.000000 mm³ on both sleeves |
| Exact CAD oversized 3.8mm panel interference | **141.36 mm³** (negative control fires) |
| Calibration specimens | Three watertight STLs, 0.15/0.30/0.45 mm per-side clearance |

## Cross-engine and slicer execution (not physical)

Another available open-source CAD tool, **build123d 0.13.0**, reconstructed the connector from equivalent parameters in a separate isolated sandbox. Its BREP volume measured **11,417.893834 mm³**, a difference of **0.000166 mm³** from the rounded CadQuery value. It exported a watertight 560-facet STL of the same dimensions. Both interfaces use OpenCascade, so this is **CAD API agreement**, not independent physics or CAD-kernel proof. Reproduce using `crosscheck_build123d.py`.

A separate **PrusaSlicer 2.9.4** invocation imported that equivalent mesh and generated a generic, **machine-unvalidated** toolpath:
- Generic FDM parameters: nozzle 0.4 mm, layer height 0.2 mm, 3 perimeters, 20% infill, 1.75 mm filament, nominal density 1.24 g/cm³, **supports disabled**.
- Slicer-reported: **120 layers, 9.67 cm³ extruded material, 11.99 g estimated filament, 55m 45s estimated print time**.
- These numbers are **profile-dependent estimates**, not a completed print or measured costs. No machine-specific G-code is provided; do not execute generic G-code on an unidentified printer.

This goes beyond checking that a CAD file exists. It demonstrates a valid exported solid, independently reproduced CAD geometry, fit-failure detection and passage through a real slicing toolchain. It does **not** prove fit or printable quality on any physical machine.

## Explicit incomplete stage gates

| Gate | Status |
|---|---|
| Geometry validity, unit bounds and STEP/STL | **Passed digitally** |
| Positive/negative nominal fit collision | **Passed digitally** |
| Independent CAD API reconstruction | **Passed digitally** |
| Generic FDM slicing | **Passed (non-machine-specific)** |
| Actual stock thickness/caliper evidence | **Missing** |
| Printed coupon dimensions/fit/warping | **Missing** |
| Full connector physical print | **Missing** |
| Retention / 90° physical alignment / damage | **Missing** |
| Same-task competitor manufactured part | **Missing** |
| Fabrication and build-ready authority | **Not granted** |

## Next operator handoff

1. Measure actual panel stock at five points and calibrate slicer/printer.
2. Print the three fit coupons first; record measured slots and real insertion results.
3. Adjust parameters if necessary, then slice and print the full connector on the actual printer.
4. Photograph the assembly, test low-load alignment within the initial target **90° ± 2°**, repeat fit/removal, and log actual print time/material.
5. Reproduce same task using another CAD workflow to measure how much manual work HS eliminated; use real files, operator time and dimensions.

**Competitive conclusion:** No claim of superiority over Flux, Schemr, FreeCAD, build123d or another tool. We reuse mature CAD/slicer engines and have produced a first inspectable digital manufacturing package that is ready for physical calibration, **not validated manufacture**.

See Prusa's guide on printer-specific clearances: https://help.prusa3d.com/article/modeling-with-3d-printing-in-mind_164135
