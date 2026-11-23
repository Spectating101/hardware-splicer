# Field and water engineering trials

Twelve digital trials cover nursery tools, field instruments, pond sampling, and Indonesian small-lot coffee grading. The pilot names describe intended uses. Tray, liner, plotter, and shop dimensions are editable assumptions in [cases.json](cases.json). No host, buyer, or physical specimen was confirmed.

Open the exported files in each section. With Python 3.10 or newer, run the verifier to regenerate and compare the delivered files. Set `--out` to write a separate export. It exits with an error when a candidate misses its gate or a deliberately adverse control passes its gate.

```sh
python3 verify.py
python3 verify.py --trial P150 --config cases.json --out /tmp/hs-field-wave
```

All twelve have positive modeled contribution per sale under the catalog's Taiwan workshop assumptions. The two Indonesian coffee pilots use that same cost base. At 25 modeled sales they remain NT$1,850 and NT$2,975 short of recovering launch costs. The seed roller stand and water sampler have the strongest modeled 25-sale results in this batch at NT$10,325 and NT$10,175. These figures assume all 25 units sell at the target price. [Catalog returns](../../returns.csv)

## P111

[Main export](generated/P111/seed-head-candidate.csv) · [Results](generated/P111/results.json) · [All trial files](generated/P111/)

**Plug-tray vacuum seed head.** The two opening schedules register 72 openings to an assumed 12 × 6 tray on 27 mm centers, with the first opening as the datum. A 0.65 mm nominal hole at −0.05 mm tolerance supplies 4.81× the assumed 15 mg seed load at 2 g and 5 kPa of local vacuum. The 0.40 mm control gives 1.64× against a 3× gate. The largest revised hole is 0.25 mm below the assumed minimum seed width. Machining can consume 0.354 mm of the 2 mm radial location budget, leaving 1.646 mm for tray registration. The ideal-seal model assumes pressure at the seed face. Edge leaks, hole burrs, double pickup and vent release can invalidate that prediction.

**Physical check.** Measure the proposed tray centers and seed lot, then log vacuum with a fully loaded and partly uncovered plate. Count single fills across ten trays and require at least 90% with the vacuum source identified.

## P112

[Main export](generated/P112/dibble-candidate.csv) · [Results](generated/P112/results.json) · [All trial files](generated/P112/)

**Tray dibble press.** The CSV locates 24 pin tips for an assumed leek tray coupon on 38 mm centers. A simply supported aluminum brace under a centered 50 N total load gives 1.280 mm maximum depth error after adding tip and tray stack allowances to brace sag. The 3 mm brace control gives 4.521 mm against the 2 mm gate. The model covers axial depth under the declared load. It omits tray flex, off-center force, pin tilt and linkage compliance.

**Physical check.** Record peak handle-to-plate force, measure all 24 impressions from a 10 mm setting, and inspect for cracks after 50 cycles. Recalculate the brace for the measured force if 50 N proves low.

## P119

[Main export](generated/P119/gate-spaced-events.csv) · [Results](generated/P119/results.json) · [All trial files](generated/P119/)

**Seed roller metering test stand.** The sampled gate function rejects one-sample interruptions and requires two clear readings to re-arm. Replaying the exported 1 ms ADC traces detected 100 of 100 spaced surrogates with zero false events. A control with only one clear sample between each paired interruption detected 50 of 100. The exported events contain the first blocked sample timestamp and become available after re-arming. The surrogate uses 3 ms occultation and 30 ms normal spacing.

**Physical check.** Confirm the roller shaft and collar dimensions on the host and size the chute around the installed roller. Count at least 98 of 100 drops of a named opaque seed lot against video. Increase overlap deliberately and report the point at which counts degrade.

## P122

[Main export](generated/P122/pressure-candidate.csv) · [Results](generated/P122/results.json) · [All trial files](generated/P122/)

**Filter differential pressure panel.** A synthetic common-tee sweep covers 0.25–2.0 bar at zero true differential with opposite-sign gauge errors, quantization and up to 50 mm of water head difference. Two 2.5 bar gauges each specified at ±0.4% full scale yield a conservative 0.0349 bar error bound. The ±1.6% control yields 0.0949 bar, exceeding the 0.05 bar gate. The CSV contains 20 sign and pressure combinations per revision. This is a gauge-selection model for a static clean-water fixture.

**Physical check.** Choose actual rated gauges, valves and fittings that can meet the bound. Bench-equalize the ports with water, compare across the declared range and inspect for leaks within the lowest component rating. Taiwan's Ministry of Agriculture provides the irrigation filter context. [Ministry of Agriculture](https://kmweb.moa.gov.tw/knowledgebase.php?func=0&id=291753&type=0)

## P126

[Main export](generated/P126/soil-tension-resistor-results.csv) · [Results](generated/P126/results.json) · [All trial files](generated/P126/)

**Soil tension recorder.** The model decodes reversed-polarity 12-bit ADC readings for an IRROMETER WATERMARK 200SS with a 10 kΩ series resistor. The 30 electrical corners from five resistor values, three temperatures, and two resistor tolerances reach 0.147% maximum resistance error. Separate records flag open, short and incompatible rail captures. The fixed 24 °C control is biased by up to 11.028 kPa versus the colocated-temperature calculation. The tension export reports positive suction magnitude for the guide's 10–100 kPa calibration window. Both the ADC and reference resistors are synthetic. Lead impedance, settling, electrode offsets and the actual temperature probe can change the result.

**Physical check.** Compare five traceable resistances while probing the polarity reversal and settling time. Check the field sensor through a wet/dry cycle and verify recorded time and temperature against references. [IRROMETER integration guide](https://www.irrometer.com/200ss.html)

## P128

[Main export](generated/P128/leaf-wetness-confirmed-duration.csv) · [Results](generated/P128/results.json) · [All trial files](generated/P128/)

**Leaf-wetness duration node.** The synthetic orchard stream has ten five-minute wet periods, isolated misleading readings in each state, and a missing sample. Two thresholds and three consecutive confirmations give 20 of 20 correct state edges, a maximum 25 s timestamp error and an 85 s notification latency. The one-sample control emits 60 edges. The replay reports closed wet windows and marks the gap unknown. The thresholds operate on arbitrary ADC units for the chosen synthetic stream.

**Physical check.** Log ten repeated wet/dry transitions against a timed reference. Check the two-minute edge limit with realistic droplets, orientation and drying conditions, then repeat with a forced data gap.

## P132

[Main export](generated/P132/core-sampler-candidate.csv) · [Results](generated/P132/results.json) · [All trial files](generated/P132/)

**Soil core ejector sampler.** At the assumed 40 mm sleeve diameter and stated diameter tolerances, the 39 mm ejector shoe keeps 0.60 mm diametral running clearance. A concentric Euler model for a 220 mm unsupported stainless rod with a fixed-free effective length factor gives 1,881 N for the 8 mm revision and 111.7 N for the 4 mm control. The digital gate is 240 N, twice the assumed 120 N ejector load. Soil friction, local bends, rod-to-shoe connection and gritty jams require measurement.

**Physical check.** Log peak ejector load and recover five 75 mm cores in specified moist soil. Each unloaded core must remain within 10% of insertion length.

## P134

[Main export](generated/P134/secchi-quadrants.svg) · [Results](generated/P134/results.json) · [All trial files](generated/P134/)

**Water clarity disk with line reel.** The SVG defines alternating quadrants for a 200 mm freshwater disk. The spool geometry has 14.5 m ideal storage capacity after allowing one line layer of flange clearance. The line CSV checks fifty 100 mm marks under ±0.2% residual strain and ±2 mm marking error. The worst error is 12 mm over 5 m. The 1% strain control gives 52 mm against a 20 mm gate. Line lay, knots and flattening affect practical spool capacity. Disk attitude and observer variation affect clarity readings.

**Physical check.** Compare all marks to a steel tape under the submerged disk load. Measure still-water disappearance and reappearance alongside a reference disk from a stationary platform. [EPA freshwater Secchi disk geometry](https://nepis.epa.gov/Exe/ZyPURL.cgi?Dockey=00001KKO.TXT)

## P135

[Main export](generated/P135/purge-candidate.csv) · [Results](generated/P135/results.json) · [All trial files](generated/P135/)

**Depth-selective water grab sampler.** An 85 mm bore and 176.2 mm effective chamber length yield 999.85 mL. A continuously mixed purge with assumed exchange of 110 mL/s, ±20% exchange and ±5% capacity yields at most 5.09% cross-layer tracer after a 45 s hold. The 10 s control yields 44.87% against the 10% limit. Both allow 15 mL each for closure carryover and retrieval leakage. Chamber exchange and leakage are parameters in a mass-balance model. Actual flushing through the open ends may have stagnant regions or lower exchange.

**Physical check.** Measure the purge curve and deployment time in a layered tracer tank. Verify depth and both closures with the messenger. Each of five retrievals must have under 10% crossover.

## P139

[Main export](generated/P139/ruler-compensated.svg) · [Results](generated/P139/results.json) · [All trial files](generated/P139/)

**Hatchery fish length board.** The full-size SVG exports 401 graduations from a datum aligned to the raised stop. With the assumed printer factor of 0.995 and residual scale error of ±0.10%, ten read-back stations predict 0.600 mm worst error including ±0.20 mm stop placement. The uncompensated SVG gives 2.598 mm against a 1 mm gate. The artwork is wider than 420 mm and needs a continuous print at the intended scale. Calibrate the actual printer before compensating.

**Physical check.** Compare ten tick positions with a steel rule up to 400 mm after applying the insert and seating the stop. Repeat after wet cleaning and inspect readability.

## P150

[Main export](generated/P150/sieve-1-candidate.svg) · [Results](generated/P150/results.json) · [All trial files](generated/P150/)

**Green coffee size sieve stack.** The exported SVGs give 225 hole centerlines per screen across two 142 × 142 mm local comparison plates, with a catch pan completing the three fractions. The trial uses round apertures of 6.35 and 5.56 mm with 9 mm pitch. Including up to 0.10 mm positive aperture tolerance, the compensated layout has 2.55 mm minimum web. A control that sends nominal hole diameters directly to the cut has 0.18 mm aperture oversize and only 2.37 mm web against a 2.50 mm gate. A simplified pin-gauge mix of 250 g sorts into 75 g, 100 g and 75 g without ambiguous cases. This predicts geometric passage for known gauge sizes. It gives no rate or lodging data for irregular beans. The SVGs carry perforation centerlines and the page dimensions set the raw plate size. Confirm the fabricator's kerf handling before cutting.

**Physical check.** Gauge ten openings per plate, compare three weighed fractions on a known 250 g surrogate mix to within 1% total mass, and check sampling of real beans after repeated shaking. Verify the receiving mill's size scheme before quoting. [Specialty Coffee Association sizing-screen practice](https://sca.coffee/education/how-to-prepare)

## P151

[Main export](generated/P151/riffle-chute-schedule.csv) · [Results](generated/P151/results.json) · [All trial files](generated/P151/)

**Green coffee sample riffle divider.** The 299 mm chute schedule gives twelve alternating 24 mm clear channels for a bead surrogate 8 mm or smaller. A 60° slope clears the assumed friction slope ratio of 0.7. Ten seeded 1 kg bead splits with uniform entry have up to 4.20% half-mass error and 3.55 percentage points difference in color fractions. Routing an extra 8% of incoming particles to one chute drives the worst half-mass error to 11.40% against the 5% gate. The idealized model starts at the clear chutes and omits bridging, bounce and particles lost on separators.

**Physical check.** Validate a full-width feed scoop and account for debris or retained mass. Make ten splits with a weighed 1 kg bead mixture, report both mass and color per side, then repeat with dry coffee. The USGS example uses riffle splitting for a different material and supports the general workflow. [USGS sample-splitting procedure](https://pubs.usgs.gov/bul/b1823/02.htm)
