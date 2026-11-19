# Internal-use and farm measurement trials

Three internal-use candidates and four narrower farm concepts have digitized models, adverse controls and shipped results. Dimensions and trial conditions are editable in [cases.json](cases.json). No equipment or specimens were physically measured.

Run `python3 verify.py` with Python 3.10 or newer to regenerate and compare the delivered data in a temporary directory. Use `--out /tmp/hs-savings` to keep a separate export, and repeat `--trial` to select individual studies.

The internal estimates reflect the catalog's selected asking prices. On those inputs, the first broadfork costs NT$118.35 less than the selected commercial ask and the rainfall logger costs NT$5,073.77 less. The sled first build costs NT$95.54 more, with the model recovering its design cost at two internal units. Scope, fit and procurement remain important to the comparison. [Catalog returns](../../returns.csv)

## P116

[Chain route](generated/P116/chain-route-candidate.csv) · [Results](generated/P116/results.json) · [All trial files](generated/P116/)

**Paper-chain transplanting sled.** Paperpot Co. lists 1.2-inch cell sides and a nominal two-inch chain spacing. For 50 modeled plugs, a 44 mm throat gives 2.977 mm minimum clearance at ±12° yaw with assumed overfill, lateral runout and guide tolerance. All 50 positions clear the 1 mm gate. The 34 mm control misses the same clearance gate at every position. On the proposed prepared-row slope the opener-to-shoe depth stack contributes up to 6 mm of error. This estimates the clearance of single rotated plug envelopes. Paper adhesion, bending of linked pots, soil disturbance and actual chain pitch require a physical trial. [Paperpot Co. chain dimensions](https://paperpot.co/what-are-paper-chain-pots/)

**Physical check.** Fit an actual 264-cell chain and feed 50 plugs in a prepared bed. Record fewer than five snags and check ten planting depths within 10 mm of the target.

## P117

[Tine schedule](generated/P117/tine-spacing.csv) · [Sleeve tolerance corners](generated/P117/socket-candidate.csv) · [Results](generated/P117/results.json) · [All trial files](generated/P117/)

**Narrow-bed harvest broadfork.** The schedule puts six tines on a 400 mm bar, compared with the different nine-tine commercial tool. An elastic beam screening model applies a hypothetical 220 N transverse load at 650 mm to one cylindrical socket. An undersized 30 × 1.5 mm sleeve control reaches 174.143 MPa at the worst tolerance corner. A 34 × 3 mm section reduces that value to 72.222 MPa, below an illustrative 90 MPa screen. It models the tube section only. The weld, retaining pin, wooden handle, soil load and fatigue govern the assembled result. The thin section's failure makes the cost of a revised socket important. An additional NT$150 erases the catalog's NT$118.35 first-unit saving and leaves a modeled NT$31.65 disadvantage. The NT$150 is a sensitivity input. [Johnny's commercial broadfork](https://www.johnnyseeds.com/tools-supplies/bed-preparation-tools/broadforks/johnnys-920-harvest-broadfork-9061.0.html)

**Physical check.** Measure loads from the intended soil, inspect socket, pins, and handle material, then proof-check the assembled handles with an instrumented fixture and record any permanent bend through 50 bed insertions.

## P129

[Replayed light readings](generated/P129/relative-light-calibrated.csv) · [Raw fixture](generated/P129/relative-light-fixture.csv) · [Results](generated/P129/results.json) · [All trial files](generated/P129/)

**Greenhouse relative light survey bar.** Dark subtraction and gain correction reduce worst simulated three-channel spread from 36.40% to 4.55% across three uniform levels. Both revisions preserve the rank of a clear channel and two neutral-density surrogates. The 5% uniformity gate reveals the offset and gain mismatch that rank alone misses. The ADC model is linear with injected quantization and noise. It does not estimate spectral response, temperature drift, or absolute PAR.

**Physical check.** Match the three channels under uniform light with the bar level. Verify at three light levels and with two neutral-density screens. Check apparent channel bias again after swapping sensor positions.

## P130

[120 mm/h event log](generated/P130/rainfall-120-candidate.csv) · [30 mm/h event log](generated/P130/rainfall-30-candidate.csv) · [Results](generated/P130/results.json) · [All trial files](generated/P130/)

**Rainfall event pulse recorder.** A nominal 200 mm collector and 0.254 mm/tip define a 7.980 mL tip volume. Two ideal 628.32 mL deliveries at 30 and 120 mm/h produce 78 complete tips each plus a partial final bucket. Replaying bounced contacts with 20 ms lockout counts 78 at each rate with zero duplicates and 0.94% indicated depth error. The 10 s control undercounts the higher rate by 50.47%. The unfiltered control reports 156 extra edges. The replay exports UTC date/time stamps. This model uses ideal tipping event times and contact bounce, so actual bucket filling, saturation, wetting loss, and tilting still need measurement. The manufacturer example confirms the use of reed closures and the dependence of volume-per-tip on collector size. [Campbell Scientific specifications](https://help.campbellsci.com/te525-series/te525-series/specifications.htm?TocPath=_____6)

**Physical check.** Independently calibrate the installed funnel and both bucket directions, then deliver a measured volume at two rates with the collector level. Require accumulated depth within 5%, zero duplicate contact events and timestamp continuity.

## P138

[Flume replay](generated/P138/flume-calibrated.csv) · [Pulse fixture](generated/P138/flume-pulse-fixture.csv) · [Results](generated/P138/results.json) · [All trial files](generated/P138/)

**Shallow-channel current survey wand.** Three synthetic flowing points and three stalled points replay from 20 s pulse windows. The assumed rotor transfer above 0.16 m/s is 25 Hz per m/s after a 0.14 m/s intercept. The calibrated replay reaches 0.014 m/s maximum error and 0.028 m/s maximum replicate span over the active points. A forced zero-intercept control misses by as much as 0.154 m/s. Nine stalled runs return an explicit no-rotation state. The generator and decoder share the nominal design coefficients, so this demonstrates quantization and the importance of calibration rather than estimating a rotor's actual characteristics. [USGS current-meter rating method](https://water.usgs.gov/osw/pubs/currentmeter.html)

**Physical check.** Calibrate one measured rotor in a straight flume, then hold out three reference velocities for acceptance and approach stall from both directions. Record rotor orientation, repeatability, flow depth, and the lowest speed giving reliable pulses.

## P140

[8.3 mm profile replay](generated/P140/profiles-8.3-guided.csv) · [10.3 mm profile replay](generated/P140/profiles-10.3-guided.csv) · [Results](generated/P140/results.json) · [All trial files](generated/P140/)

**Fish fingerling size grader.** Two basket gaps are screened with 100 rigid oval coupons each. An elliptical projection model with ±0.20 mm gap tolerance gives 100% modeled separation for both guided sets at up to 8° yaw. Allowing up to 25° yaw separates 83% correctly and fails both gaps against the 95% gate. The model uses inert dimensions and shadow width. It does not address live movement, compression, or welfare.

**Physical check.** Make a gap coupon and run a dry and then submerged inert-profile test. Require 95 of 100 correct and inspect the gap and edges for burrs. Reassess viability before evaluating a handling method beyond inert specimens.

## P146

[Branch replay](generated/P146/air-panel-regulated.csv) · [Results](generated/P146/results.json) · [All trial files](generated/P146/)

**Hatchery low-flow air distribution panel.** A linear four-branch pneumatic model explores three source settings with all branches open and with each branch closed in turn. Each immersed branch has an assumed opening threshold and a measured-value placeholder for its flow coefficient. With a stiff source and the assumed gauge scale errors, the 48 readings are within 4.25% of internal model references. Closing any outlet changes the remaining modeled flows by at most 4.97%. The higher source-droop control changes those flows by up to 23.98% and fails the 10% isolation screen. The readouts and branch curves are hypothetical, and the supplied source remains outside the catalog product. The scope is bench air distribution with empty vessels. [Pentair flow meter and manifold examples](https://pentairaes.com/products/aeration-oxygenation/diffusers-injectors-accessories/flow-meters-manifolds)

**Physical check.** Measure source droop and each branch's pressure-flow curve on the intended empty-vessel rig. Compare four readouts against a traceable air flow instrument at three settings within 10%, then isolate each branch and log redistribution.
