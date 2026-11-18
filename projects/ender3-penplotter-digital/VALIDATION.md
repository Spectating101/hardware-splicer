# Digital verification and limits

`reports/verification.json` is the authoritative local integrity result. `artifact_integrity` concerns source bytes, exports and independently reconstructed numbers. `requirements_met` concerns the stated quantitative design constraints. Neither field means a physical device was built or tested.

## Source and dimensional checks

The manufacturer repository/commit and SHA-256 of every execution source are checked. The standalone E-plate STEP is reopened and bothM3 cylinder axes are independently extracted. Its volume is compared to the exact extracted full-assembly instance metadata. The separately downloaded nozzle STEP verifies the selected nozzle instance and its tool datum. The original PDF and E-plate SLDPRT accompany the editable study. The generic2020 profile source is345mm long while the source BOM top profile is330mm; parking uses its cross-section, not that generic length.

The full44.8MB assembly is ignored by Git and is not required in isolated execution copies. Its pinned URL/hash is retained. It was successfully imported once after duplicate manufacturer instance names were made unique in memory; only names changed, not transforms or shapes. `assembly_parts.json` records300 extracted instance bounding boxes, locations and volumes. This is sourced datum evidence, not a physical measurement.

The exact new adapter and cap are intersected with the detailed vendor E plate. Intended boss-face contact is permitted and positive-volume interference must be below0.001mm3. The parking T-nut/profile fit uses the actual manufacturer solids, not a guessed nominal slot. Radiator bore axes and14mm pitch are independently checked from the actual radiator source. Nut fit, thread strength, screw torque, printed dimensional error and cable routing are untested.

## Numerical assumptions

The6mm web with40mm width is evaluated as an ideal rectangular cantilever under2N lateral load, length42.55mm, E1400MPa. Its deflection limit is0.3mm. This is a preliminary beam proxy, not FEA, print strength validation, bolt pullout analysis or proof against creep and delamination. The material density1.27g/cm3 estimates the solid volume mass of all three printed parts; it does not model slicer infill.

Both final clamp solids change with the selected8..12mm pen diameter. The modeled bore includes1.2mm diametric liner allowance and a0.4mm cap gap; no pen grip force or reliable marking force is claimed. There is no passive spring-loaded contact mechanism.

## Export and motion checks

The independent verifier does not import either authoring script. It reopens all three part STEP/STL pairs, requires one valid CAD solid, closed consistently wound mesh and≤0.3% CAD/mesh volume difference. It reopens the full STEP and GLB, checks reference-envelope labels, export hashes and both PNG decodes. It recomputes every engineering constraint actual/limit/pass and every numeric summary field from reopened geometry or the emitted commands.

It independently locates the 0.1 mm sheet in the delivered STEP and the named, transformed paper mesh in GLB. Both must have the requested centered dimensions and matching solid volume. Paper stays inside the unchanged 235 mm bed, and the full viewport leaves at least 10 mm on every side. Source SVG points remain inside the declared 100 × 80 logical canvas. Every reconstructed ink endpoint remains inside the requested viewport and at least 10 mm inside the actual exported paper, allowing 0.00011 mm for serialization. Linear segments cannot leave these convex rectangles when both endpoints are contained.

It strictly parses the actual G-code, rejecting unknown or duplicate words, nonfinite numbers, extrusion in any syntax, unsupported commands and all heater requests except explicitM104/M140 S0. Every SVG pen-down segment must match the emitted machine segment after measured offset compensation. Every CSV position, drawing flag, feed and ideal segment duration must match a second decoder. Absolute metric mode is mandatory. XY endpoints bound all affine linear segments; they must remain on the235mm physical bed and within the pinned235mm controller travel. Z must stay between paper0 and requested lift, and all non-drawing XY moves must maintain that lift.

The clamp lower face is30mm above the pen tip. Its29mm clearance above the assumed≤1mm tape exceeds the2mm design limit. Fixtures can overhang a bed edge without contacting its surface; no false XY bed-edge exclusion is imposed on parts suspended above the bed. The parked nozzle clearance is derived from its represented parking pose and original nozzle datum. Complete frame, roller, wiring, tie-restraint and swept machine collisions are **not** solved by the reference envelopes.

## Physical work not performed

No donor identification on hardware, printing, fit test, electrical inspection, firmware boot, thermistor reading, mains work, homing, stepper test, real plotting, repeatability measurement, pen-force test or endurance test has occurred. Retaining the stock ambient thermistors is a defined conversion requirement supported by source configuration, not a successful MINTEMP or powered-motion test. The generated G-code is for local digital replay only.

## Recorded local results

The historical pre-paper-parameter baseline at the default 100 × 80 mm viewport, 10 mm pen and 3 mm lift passed 49 checks. New paper-aware runs add geometry and containment checks; consult their own receipts. That historical run reconstructed305 linear segments in12 strokes,771.81mm of pen-down travel and560.25mm of pen-up XY travel. Ideal feed time was124.39s. Minimum pen-tip bed margin was71.5mm, controller travel margin70.3mm and fixture clearance above the assumed tape29mm. Exact adapter/cap-to-carriage solid intersection was0mm3. The ideal beam proxy deflection was0.05095mm under2N. All three solid printed parts total82.40g at the assumed density.

`scripts/test_tamper.py` repeats the independent verifier on isolated copies. Six checks passed: intact package without the large original assembly accepted; decimal extrusion word `E.5` rejected; duplicate heater words `M104 S200 S0` rejected; hidden excess-Z move rejected; consistently forged fixture-clearance reports rejected; and a self-consistent fabricated failed-goal result rejected. The recorded details are in `reports/tamper_tests.json`. These are artifact integrity tests, not physical acceptance tests.
