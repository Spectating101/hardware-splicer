# HS cable anchor and display-compatibility failure pilot

**Verdict: physical cable harness BLOCKED.** Actual CAD parts were generated
and independently sliced, but the nominal cable intersects the printed
guides and the round-wire model is not a real display interconnect.

## New genuine printable parts

Using the original balanced_60 hinge from PR #333 and the retained
shaft in PR #334:

- Lower printed leaf with integrated M2-hole saddle
- Upper printed leaf with spatially staggered integrated saddle
- Separate lower screw-down saddle cap
- Separate upper screw-down saddle cap

Four actual STEP and STL parts are in generated/. All have verified
single-solid valid STEP and watertight STL roundtrip. No actual M2
fasteners, nuts, sourced wire or clamping force tests are available.

Saddle centers are local (81.6,10,5) and (81.6,-20,5) mm.
The round-wire channel is radius 0.8mm around an assumed cable
of radius 0.55mm. Existing HS function-intent/MachineProject
traceability is expanded to 12 requirements and seven functions.

The newly added opposite saddle protrusions do not intersect one
another in 13 sampled hinge positions. This does NOT rerun all
contacts against original inherited leaf solids, and does not
constitute a complete continuous-motion mechanism certification.

## Critical negative engineering results

Four actual fixed-length, source-pinned nominal cable centerline
paths were tested at 37 angles; none passes the full numerical
bend-radius and 20mm closed-envelope screen:

| Path | Minimum modeled bend radius | Closed cable-inclusive height | Result |
| --- | ---: | ---: | --- |
| short_40 | 1.62mm | 16.57mm | Fails hypothetical 2mm bend |
| medium_44 | 1.69mm | 18.57mm | Fails hypothetical 2mm bend |
| long_48 | 1.82mm | 20.56mm | Fails bend and height |
| relaxed_52 | 2.04mm | 22.56mm | Passes hypothetical bend, fails height |

Even worse: genuine swept 3D cable solids for the medium_44 route
penetrate the actual printed guide material at all three checked poses:

| Hinge angle | Solid cable/printed-guide intersection |
| --- | ---: |
| Open 0° | 4.22 mm³ |
| Half-fold 90° | 13.77 mm³ |
| Closed 180° | 3.16 mm³ |

Floating cable geometry is not an attachable, motion-compatible cable.

## Source-backed electrical compatibility gate

This 1.1mm round wire is mechanically unsuitable as a direct substitute
for a wide flat multiconductor display ribbon.

Manufacturer references:

- igus bend-radius guidance:
  https://www.igus.com/cables/unharnessed-cables-bending-radius
- Molex Premo-Flex flexible FFC families and flex-life distinctions:
  https://www.molex.com/content/dam/molex/molex-dot-com/en_us/pdf/solutions-guide/987652-1121.pdf
- Molex 15026 0.5mm-pitch LVDS FPC and mating One-Touch 200485 connectors:
  https://www.molex.com/content/dam/molex/molex-dot-com/en_us/pdf/datasheets/987652-5681.pdf

Molex 15026 describes at least 20 manual 180-degree folding cycles
in its source test, not proof of long-term repeated daily folding.
Series 15166 thin ultra-flexible FFC has distinct catalogue flex-life
claims but is NOT proven electrically suitable for a particular display.

The 5x outer-diameter (5.5mm) radius screen is a **generic scenario**,
not a manufacturer's specification for this unsourced round cable.
All four paths fail that stricter scenario. Actual screen connector,
signals, circuit count, cable datasheet and permitted bend plane are
still unknown.

## Actual native print-slicing test

PrusaSlicer 2.9.2 generated four real, source-linked G-code files
using a generic uncalibrated 0.4mm nozzle, 0.20mm layer and 20%
gyroid-infill PLA profile (3 perimeters, no supports):

| Part | Estimated filament | Estimated duration |
| --- | ---: | ---: |
| Lower integral leaf | 25.34 g | 2h54m |
| Lower removable cap | 0.37 g | 3m40s |
| Upper integral leaf | 26.28 g | 3h03m |
| Upper removable cap | 0.37 g | 3m41s |
| **Total** | **52.36 g** | **about 6h05m** |

No physical printer has been calibrated and no part has been printed.
The real G-code stays on the authorized Optiplex under
/tmp/hs-anchor-slicer-20261112/ and must NOT be treated as released
for production. Native G-code and STL SHA-256 evidence is preserved.

## Reproduction

With actual CadQuery, numpy, trimesh installed:

    PYTHONPATH=src python3 examples/functional_hinge_cable_anchors/run.py \
      --out /tmp/hs_cable_mount_new

Audit exact published outputs, reconstruct nominal geometry and
replay 3D cable intersections without prior G-code:

    PYTHONPATH=src python3 examples/functional_hinge_cable_anchors/run.py \
      --audit-only

Audit native slicer receipts without running physical slicer:

    python3 examples/functional_hinge_cable_anchors/slice_mounts.py --audit-only

Run actual new PrusaSlicer 2.9.2 slice with source input:

    PYTHONPATH=src python3 examples/functional_hinge_cable_anchors/slice_mounts.py \
      --slicer /path/to/prusa-slicer \
      --out /tmp/hs_cable_slicer_output \
      --receipt /tmp/hs_cable_slicer_receipt.json

The independent audit re-imports all four original STEP/STL parts,
recalculates all four cable bend/envelope screens and the selected
3D intersection volumes. It blocks false "ready to fabricate" labels.

## Remaining engineering gate

Source an actual display and matching connector/cable (MIPI-DSI,
eDP, LVDS or other as actually required), then replace the round cable
with a genuine flat-cable assembly that includes connector footprints,
fixed exit tangents, measured cable dimensions and actual rated
flex constraints. Reoptimize the hinge architecture and closed
envelope without reducing source acceptance limits. Then use
physical hinge coupons, sourced fasteners and repeated folding
tests before declaring strain relief functional.
