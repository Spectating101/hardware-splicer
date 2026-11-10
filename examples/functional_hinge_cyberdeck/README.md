# Hardware Splicer: functional cyberdeck hinge prototype

This is an actual two-leaf, 180-degree rotating CAD assembly, not an
illustrated model. It builds upon the function-to-solid-to-slicing
integration in HS PR #332.

## Fixed *unmeasured* design input

- Each nominal half: 152 x 78 x 2.4 mm printed backing plate.
- Assumed screen package: 140 x 68 x 2.3 mm on each side.
- Five alternating coaxial annular knuckles: two lower, three upper.
- 3 mm NOMINAL METAL pin with 3.5 mm printed bore (reference only).
- Declared minimum inter-leaf clearance 0.4 mm, screen clearance
  1.0 mm, radial pivot wall 1.8 mm, closed model height <=13.5 mm.
- 0–180 degree sweep about the printed hinge axis.
- External cable service reservation: radius 9 mm, at least 2 mm
  from the printed body, outside the panel's right edge.
- Neither a cable route nor cable anchors, FFC fatigue/strain-relief,
  steel pin retention, or measured screen and printer profiles exist.

Source reference_spec.json contains original input and strict physical
authority gates. It passes through HS's existing function-intent /
MachineProject gate: six functional requirements and three functions,
physical fabrication authority remains FALSE.

## Seven actual moving native CAD alternatives

Every alternative contains TWO separate, valid CadQuery BRep bodies.
All 14 bodies are exported to STEP and watertight STL, reimported and
checked against source volume and SHA256. Every nominal design is
evaluated at 37 BRep motion poses in 5-degree increments, checking
leaf-to-leaf, screen-to-screen, screen-to-opposite-leaf and reserved
cable corridor proximity with OpenCascade distance and true Boolean
intersections where near contact.

| Reference variant | Folded printed height | Minimum screen separation | Result |
| --- | ---: | ---: | --- |
| Slim 4.3mm axis | 8.6 mm | Overlap | Reject: screen collision |
| Compact 5.1mm axis | 10.2 mm | 0.8 mm | Reject: below 1.0 mm |
| Balanced 6.0mm axis | 12.0 mm | 2.6 mm | SELECTED |
| Cable-crowded 6.0mm axis | 12.0 mm | 2.6 mm | Reject: reserved corridor only 1.0mm clear |
| Thin-wall 6.0mm | 12.0 mm | 2.6 mm | Reject: radial ring wall 1.65mm |
| Reinforced 6.4mm | 12.8 mm | 3.4 mm | Pass, slightly heavier |
| Tall 7.3mm | 14.6 mm | 5.2 mm | Reject: exceeds folded limit |

Selected Balanced 6.0mm was also re-evaluated with a separate
181-pose, 1-degree sweep. All sampled checks passed:
minimum printed-part clearance 1.1814mm; screen-to-screen 2.6mm;
screen-to-opposite-leaf 3.1623mm; reserved cable space 2.5mm.

These are DISCRETE, NOMINAL, undistorted part positions. Sampling
cannot certify clearance continuously between angles, under
real manufacturing tolerances or under mechanical loads.

## Actual assembly files

The generated/selected folder contains:
- lower_leaf.step, lower_leaf.stl, upper_leaf.step, upper_leaf.stl
- assembly_open_0.step
- assembly_half_90.step
- assembly_folded_180.step
- cable_service_keepout_only.step (virtual spatial restriction only)

The three assembly STEP files are genuine 3-solid OCC assemblies:
two printed leaves + nominal, unmeasured metal shaft. The source
models intentionally have no retaining fastener or electronics
connector. All seven pairs of STL and STEP are saved under
generated/candidates/; never print the cable envelope as hardware.

## REAL PrusaSlicer 2.9.2, eight source-hashed jobs

Fixed experimental profile: nominal generic PLA density 1.24g/cm3,
0.4mm nozzle, three perimeters, 20% gyroid infill, 0.2mm or 0.28mm
layers, support generation OFF, uncalibrated generic 220x220mm bed.
These are REAL slice outputs but not verified toolpaths for a
specific physical printer.

| Both separate printed hinge leaves | 0.20 mm layers | 0.28 mm layers |
| --- | --- | --- |
| Balanced 6.0mm | 50.37g; total 5h 44m 37s | 59.80g; total 5h 17m 13s |
| Reinforced 6.4mm | 51.28g; total 5h 51m 22s | 60.67g; total 5h 22m 9s |

Reported masses and durations are SLICER ESTIMATES. Metal shaft,
displays, cable, electronics, adhesives and screws are excluded.
Horizontal 3.5mm bearing bores and unsupported bridges may print
poorly: no measured hole quality, friction, creep or fold endurance
has been performed.

The native_fdm_results.json file retains source STL and G-code hashes,
actual PrusaSlicer command receipts and every print estimate. A
separate stdlib verification script regenerated all eight actual
G-code toolpaths on the authorized workstation, reproducing material
and time estimates. No G-code was supplied to a printer or released
as machine-safe instructions. Local full raw output is in
/tmp/hs-hinge-real-gcode-20261110/.

## Running the source engineering benchmark

Requires CadQuery 2.6.1, Trimesh and the HS source package:

    PYTHONPATH=src python3 examples/functional_hinge_cyberdeck/run_hinge.py \
      --out /tmp/new_hinge_cad_run

Use native independent BRep and STL audit with the functions audit and
fine_selected in hardware_splicer.functional_hinge_audit. The first
writes no false authority; the second recomputes 181 actual poses.

PrusaSlicer reproducibility without HS CAD dependencies:

    python3 examples/functional_hinge_cyberdeck/verify_independent_slicing.py \
      --slicer /usr/bin/prusa-slicer

Source-only integrity check:

    python3 examples/functional_hinge_cyberdeck/verify_independent_slicing.py \
      --source-only

## Genuine next physical acceptance gates

1. Identify actual LCD/touch module models, connectors, active glass
   area, power supplies and caliper-measured package dimensions.
2. Solve the actual independent-module cable and/or removable wired
   connection. External cable clearance is NOT cable routing or a
   tested flexible interconnect.
3. Design the actual pin retainer, realistic hinge friction/torque,
   stops, load and wear requirements.
4. Print a small 3.5mm radial bore tolerance coupon, then two leaves.
   Measure shaft fit, support quality and repeated folding durability.
5. Recalculate the complete closed stack with actual screen modules,
   covers, fasteners, battery, wiring and printed tolerance ranges.
6. Do not claim production-ready geometry until physical prototype,
   electrical isolation and real printer validation are complete.

This is a function-driven REAL 3D moving mechanism prototype, not a
physical cyberdeck and not a lifetime-qualified hinge.
