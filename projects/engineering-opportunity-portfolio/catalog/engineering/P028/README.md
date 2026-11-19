# Single-station switch endurance tester

The station presses a switch and records whether the contacts closed and opened on command. This digital prototype includes replaceable holders for the Omron B3F-1000 and B3F-4000 and a runnable contact-log evaluator. A technician can change between the two footprints while retaining the same mounting pattern and the same central actuator axis.

## What changed in the holder

Each holder has a 30 × 24 mm carrier under the switch and a removable keeper over its housing. The carrier takes the terminal pattern from the manufacturer's top-view drilling drawing for a 1.6 mm board. The keeper exposes the plunger and prevents the switch lifting out. The profiles give full-size centerlines in millimetres. Use a machining or drilling process suitable for the chosen substrate and compensate for tool diameter in CAM. [Omron B3F drawing, printed pages 4 and 6](https://components.omron.com/eu-en/system/files/2023-01/datasheet_pdf/A070-E1.pdf)

| Parts for the same mounting pattern | Released geometry | Lower-bound projected clearance |
|---|---|---|
| [B3F-1000 carrier](B3F-1000-carrier.svg) and [keeper](B3F-1000-keeper.svg) | Four 1.0 mm terminal holes on a 6.5 × 4.5 mm pattern. Keeper aperture 4.9 mm. | 0.195 mm radial gap around the round top envelope, 0.220 mm minimum retaining land |
| [B3F-4000 carrier](B3F-4000-carrier.svg) and [keeper](B3F-4000-keeper.svg) | Four 1.2 mm holes on a 12.5 × 5.0 mm pattern and two 1.8 mm locating-boss holes 9.0 mm apart. Keeper aperture 8.5 mm. | 0.195 mm radial gap, 1.420 mm minimum retaining land |

The first design allowed 1.2 mm extra aperture diameter and ±0.30 mm of centre error on each axis. The tolerance calculation predicted **0.074 mm interference** in the worst corner. The revision uses 1.4 mm extra diameter and two location points for 2 mm pins, one round and one slotted. Its projected margin requires **total switch-to-keeper misregistration within ±0.18 mm on each axis** after installation. This allowance includes terminal play, part concentricity and plate registration. Achieving it is an open measurement. The calculation includes ±0.10 mm keeper aperture diameter, ±0.20 mm switch housing width and ±0.40 mm for the unspecified round-envelope diameter. The smallest nominal web is 2.4 mm. The larger housing leaves 1.22 mm to a 7 mm diameter washer envelope. The digital acceptance thresholds are 0.15 mm radial gap and 0.20 mm retaining land.

Mounting holes are 3.2 mm diameter on 22 mm centres. The independent pin pattern has a 2.05 mm round bore and a 2.70 × 2.05 mm horizontal slot on 20 mm centres. The locating base, pins, spacers and plunger are additional parts. Both switches have a nominal 4.3 mm overall height. Set spacer height from the measured housing shoulder and use a compliant actuator tip smaller than the plunger. The available plunger travel, keeper height, housing load and screw preload require a bench check. Leave space below the carrier for the terminals and removable leads. Both terminals on one row are internally connected. Sense between opposite rows after confirming continuity on the installed specimen. A 5 V logic supply and external 3.3 kΩ pull-up would give about 1.5 mA through a closed contact, within the published resistive load range for the silver contacts. The wiring remains a design assumption. [Manufacturer electrical and mechanical specifications](https://components.omron.com/eu-en/system/files/2023-01/datasheet_pdf/A070-E1.pdf)

The JES fixture previously inspected by HS uses its own holder interface. These two plates use an independent mounting pattern. An adapter or a measured base is needed before attaching them to that earlier fixture. [Earlier fixture and builder observations](https://incoherency.co.uk/blog/stories/keyswitch-tester.html)

## What the controller can distinguish

The replay takes one raw contact sample every millisecond, with command, tick within the commanded cycle, and boot epoch. The assumed cycle has 40 ms at home, 120 ms for press and 120 ms for release. The debounced value must match the expected contact throughout the last 25 ms of each phase. A transition must persist across 6 ms before changing the debounced value. These timings are software trial settings. Actual servo settling, switch load and test rate are unmeasured.

Across **448 simulated cycles** (14 cases, 32 deterministic seeds per case), 64 passed, 160 reported a contact-state mismatch and 224 were inconclusive because of incomplete or inconsistent acquisition. The samples included press/release bounce, stuck open, closed at home, failed release, a late press, a sustained dropout, missing samples, duplicate sequence numbers, swapped samples, a missing command and controller resets. A later reset invalidated the whole cycle even when the contact stream had shown an earlier fault. An independent six-command CSV exercise produced pass, reset, missing cycle, missed close, pass and missing cycle in that order. [Machine-readable outcomes](results.json)

A deliberately injected 3 ms dropout passed because the debounce interval masks it. A 10 ms dropout during the checked dwell was detected. A missed close may be caused by the sample, leads, fixture or actuator. Servo motion feedback would be needed to identify the cause. The log format assumes a monotonic cycle counter and a commanded-cycle count retained by the host across a controller restart. The timing model measures state at sampled intervals and makes no endurance or cycle-life claim.

## Run the trial

From this directory, use Python 3. No CAD engine or network connection is required.

```sh
python3 -B study.py --verify
python3 -B replay.py simulated-trace.csv --expected-cycles 6
```

The first command regenerates each deliverable in temporary storage, checks dimensions by reading the emitted SVGs against a separately transcribed drill map, rejects the first tolerance design, runs the simulations and compares the outputs byte for byte. To change the design, edit [the holder parameters](geometry.py), run `python3 -B study.py`, and review the differences. The CSV fixture is synthetic and uses boot IDs assigned by the test. [Replay implementation](replay.py) · [Trial implementation](study.py)

## What decides whether it is worth building

For the first bench article, measure XY misregistration and keeper coverage after repeated installation of each switch. Verify that the actuator returns fully and that the fixture does not mark the housing or ride on the terminals. Run a known-good contact, an open circuit, a shorted input and a controller reset while comparing the contact signal and cycle count to an independent recorder. Record hands-on setup time, rework, scrap and actuator wear. In particular the B3F-1000 keeper has only 0.020 mm headroom above the proposed minimum retaining land.

The catalog's 56.3% return at 25 sales still assumes NT$1,550 to build each repeat unit, including one hour of labor, plus NT$5,600 of launch expense. The change from a generic holder to two keyed carriers introduces pins, keepers, spacers and a base interface. Their delivered cost, assembly time and life have not been measured. An additional 30 minutes of labor per unit would consume NT$7,500 across 25 units at the catalog rate of NT$600/hour.
