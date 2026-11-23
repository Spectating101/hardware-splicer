# Marine and tank engineering trials

Ten digital trials cover marine hardware fit, reel and fairlead geometry, wetting logic, and optics. The named pilots define the intended service conditions. No host or customer was measured. The adjustable parameters live in [cases.json](cases.json). All margins are model results and the enclosure work is limited to a dry reference blank.

Open the exported files alongside each item. The standard-library verifier runs with Python 3.10 or newer and compares the delivered files with the replay. Use `--out` to write a separate export.

```sh
python3 verify.py
python3 verify.py --trial P172 --out /tmp/hs-marine-reel
```

The catalog estimates a positive 25-sale result for four of these candidates. The dry-deck reel leads at NT$10,438, followed by the drop camera at NT$6,138, instrument bridge at NT$2,688, and guard set at NT$563. These estimates assume all units sell at the catalog price and the same build assumptions hold. The camera module cited below establishes optical and mounting inputs. Its optics can inform the experiment, and the actual quoted BOM must be checked against the catalog allowance separately. [Catalog returns](../../returns.csv)

## P032

[Guard face](generated/P032/face-candidate.svg) · [Six-seat survey table](generated/P032/six-seats-candidate.csv) · [Results](generated/P032/results.json) · [All trial files](generated/P032/)

**Six-piece underwater ROV guard set.** QYSEA identifies V6 EXPERT compatibility and an 80 mm per-unit envelope for its six-pack. The new 75 mm face is an independent concept tied to six proposed survey positions. Rasterizing each exported face over a swept blade disk gives a minimum 77.74% projected opening for 1.9 mm ribs, compared with 55.57% for the 3.5 mm control and a 73% gate. The assumed outer seat edge margin is only 0.05 mm, so host measurement controls the next revision. The 6.0 mm radial margin is at the ring. Ribs cross the plane above the rotor and their axial clearance and support remain interface checks. Projected open area does not estimate thrust or protect against debris of any specified size. [QYSEA six-pack listing](https://store.qysea.com/products/propeller-protectors)

**Physical check.** Survey all six seats, axial gaps and retainer locations with the exact host unpowered. Then verify retention and compare debris snagging and thrust against a baseline in a controlled tank.

## P172

[Winding schedule](generated/P172/reel-candidate.csv) · [Results](generated/P172/results.json) · [All trial files](generated/P172/)

**Manual deck tether reel.** The 95 mm nominal drum has 58.07 m modeled net capacity with a 2 m connector reserve. The 94 mm smallest drum meets Blue Robotics' 75 mm minimum working bend diameter for its 7.6 mm Standard Fathom tether. The 59 mm control has more storage and fails the bend gate. The static brake budget is 3.45 N·m at a hypothetical 25 N pull and 1.25× margin. Actual winding quality and brake torque remain unknown. [Blue Robotics Standard Fathom tether](https://bluerobotics.com/store/cables-connectors/cables/fathom-rov-tether-by-the-meter/)

**Physical check.** Wind and unwind one disconnected 50 m sample ten times. Check connectors, flange clearance, smallest bend, kinks, and brake slip under the measured dry-deck pull.

## P173

[Reference blank hold](generated/P173/reference-blank-reference-blank.csv) · [Results](generated/P173/results.json) · [All trial files](generated/P173/)

**Enclosure vacuum check kit.** A sealed-volume temperature correction uses absolute pressure and gas temperature. With a +1 °C drift, the raw reference trace moves up to 0.34 kPa, over the assumed 0.25 kPa diagnostic gate. The corrected trace moves 0.054 kPa. A synthetic leak control remains above 0.293 kPa across the reference starts even after the double-ended 0.16 kPa gauge uncertainty. The model assumes constant atmospheric pressure and a gauge thermally equilibrated to the gas. The bench test assesses integrity at its test condition and does not establish a pressure or depth rating.

**Physical check.** Use a purchased test rig and compatible reference blank. Compare a traceable gauge at the three bench levels, measure actual drift and ambient variation over ten minutes, and verify the face and seals on the specified adapter.

## P174

[Jaw table](generated/P174/jaw-set-candidate.csv) · [Results](generated/P174/results.json) · [All trial files](generated/P174/)

**Cable penetrator vise block.** The model sizes replaceable jaws around the manufacturer's 12, 16 and 20 mm bulkhead flats. With the assumed fit tolerances, the 0.15 mm oversize jaw yields 0.07–0.23 mm clearance. The 0.03 mm oversize control can interfere by 0.05 mm. The model spreads a 120% plug-torque load over assumed effective jaw contact for up to 80.27 MPa average bearing stress. Individual fitting and jaw edges may take a larger local load. Plug seating torque varies by cable, and the manufacturer's assembly guidance controls actual assembly. [Blue Robotics WetLink assembly guide](https://bluerobotics.com/learn/wetlink-penetrator-installation-guide/)

**Physical check.** Measure fittings and jaws. Fit all three sizes and assemble ten samples to the maker's guidance with a torque tool. Inspect flats for damage and confirm jaw retention.

## P175

[Slotted deck pattern](generated/P175/bridge-candidate-deck.csv) · [Results](generated/P175/results.json) · [All trial files](generated/P175/)

**Clamp-on ROV instrument bridge.** A 280 mm slotted deck fits the envelope of the 338 mm wide BlueROV2. The model assumes the customer's clamp surfaces are 240 mm apart and the instrument pattern is 70 × 40 mm. It puts the full 24.52 N proof load on one slotted aluminum bar. The revised 8 mm bar deflects 0.098 mm, while the 3 mm control deflects 1.856 mm against a 0.6 mm screening gate. This load check omits clamp slip, frame compliance, impacts and off-axis load. The manufacturer's envelope alone cannot establish the actual clamp and instrument interfaces. [BlueROV2 datasheet](https://bluerobotics.com/wp-content/uploads/2025/04/BROV2-DATASHEET.pdf)

**Physical check.** Measure one exact customer frame and instrument mounting pattern. Load the installed bridge with twice the declared instrument mass for ten minutes. Compare deck and witness marks before and after unloading.

## P176

[Trim table](generated/P176/trim-matched.csv) · [Results](generated/P176/results.json) · [All trial files](generated/P176/)

**Paired clip-on trim floats.** Archimedes' principle with two assumed foam volumes, wet mass gain, saddle masses and tolerance bounds gives a 13.10% worst pair mismatch. Adding 30 g to the higher-lift side lowers the modeled mismatch to 1.75%, with at least 237.9 g-equivalent lift per float. This uses assumed mass gain and material density. Roll moment, flow, foam compression and attachment need an actual pool setup.

**Physical check.** Use a scale to compare both submerged lifts before and after 24 hours at the intended pool condition. Hold within 5% and check the clip and shim retention.

## P177

[Per-wetting outcomes](generated/P177/pad-trials-candidate.csv) · [ADC replay](generated/P177/pad-trials-adc.csv) · [Results](generated/P177/results.json) · [All trial files](generated/P177/)

**Two-zone enclosure ingress alarm.** The digital state machine latches the correct simulated pad in all forty fresh/saline wettings, with 40 ms maximum detection time at the assumed sample cadence. The one-sample control matches the later wetting and falsely latches before it in all forty trials. The revised model rejects reset while still wet, clears after a dry reset, and detects a simulated out-of-band input. ADC ranges are arbitrary fixture assumptions. The state is volatile and actual pads can have overlapping wet, dry and fault amplitudes.

**Physical check.** Calibrate wet, dry and fault thresholds with the actual pads and installed leads. Wet each of two pads ten times each in fresh and saline water, and verify the indicator, logic output and reset behavior.

## P178

[PCB pickup pattern](generated/P178/camera-board-mount.svg) · [Optical target model](generated/P178/target-1080p.csv) · [Results](generated/P178/results.json) · [All trial files](generated/P178/)

**Shallow tank drop camera.** The reference camera has a 32 mm PCB, 28 mm bolt pattern, 80° × 64° field of view and a 1920-column output. A flat-port refraction model gives 351 mm horizontal coverage at 300 mm water standoff and 0.87 mm radial window margin at the worst sensor corner. The 3 mm target is sampled at 16.42 pixels on average. The 640-column control gives 5.47 against an eight-pixel screening gate. Lens focus, image contrast, haze, actual resolution and 5 m USB link behavior remain unverified. [Blue Robotics BR-100126](https://bluerobotics.com/store/sensors-cameras/cameras/cam-usb-low-light-r1/)

**Physical check.** Record a 3 mm feature at 30 cm on the intended host computer with the proposed 5 m lead. Repeat after a two-hour soak at the declared shallow condition and inspect the assembled head for ingress.

## P179

[Illuminance grid](generated/P179/target-illuminance.csv) · [Results](generated/P179/results.json) · [All trial files](generated/P179/)

**Paired shallow inspection lights.** A uniform-cone approximation for two hypothetical 140 lm heads yields at least 659.9 lx across nine points on a 500 mm card. A lumped heat model estimates 41.5 °C case temperature for a 5 K/W wet thermal path. The 13 K/W control reaches 61.5 °C against the 52 °C gate. The thermal assumptions are screening inputs. Verify beam distribution, temperature and the material limits of the purchased heads.

**Physical check.** Measure full-output lux and case temperature through an instrumented soak and repeat the electrical and light checks after retrieval.

## P180

[Fairlead sweep](generated/P180/sweep-candidate.csv) · [Results](generated/P180/results.json) · [All trial files](generated/P180/)

**ROV tether fairlead.** Nine tangent angles model a radiused guide with 3° remaining coverage at ±60°, including a 2° placement allowance. The clamp's tolerance interval spans 21–53 mm for an assumed rim range of 22–48 mm. Its 82.5 mm minimum surface diameter exceeds the Fathom 75 mm bend requirement. The 42.5 mm control fails it. The geometry omits cable twist, friction, and clamp holding force. [Blue Robotics Fathom tether specification](https://bluerobotics.com/store/cables-connectors/cables/fathom-rov-tether-by-the-meter/)

**Physical check.** Clamp to both rim limits, sweep a 5 m sample through the working angles 100 times, and inspect the jacket and clamp witnesses for damage and slippage.
