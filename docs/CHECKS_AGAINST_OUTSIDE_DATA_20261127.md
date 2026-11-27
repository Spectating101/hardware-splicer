# HS checked against outside data (27 Nov 2026)

What HS's checks and predictions scored when measured on data HS did not make. Each line points to the record that holds the cases.

## Schematic review

| Set | Bugs | KiCad ERC | kicad-happy | HS | All three |
|---|---|---|---|---|---|
| Dev: the 70 fix commits HS's rules were written from (`examples/schematic_bug_benchmark/fix_commit_benchmark_20261125.json`) | 70 | 5 | 10 | 21 caught, 6 partial | |
| Held out: 35 bugs from 117 other repositories, picked by commit message before any checker ran (`heldout_benchmark_20261127.json`) | 35 | 9 | 9 | 4 with the dev-set rules; 5 with one rule added after | 14 |

The held-out set is the honest number: HS's lead on the dev set was mostly rules fitted to those cases. On new projects HS
adds bugs the other two miss (an IC with GND and VCC swapped, an op-amp on inverted rails) and misses the generic
connection faults they check: dangling labels, undriven inputs, supply pins with no path to a rail, pull resistors on
boot pins. So `review_schematic(..., also=("kicad_erc", "kicad_happy"))`, and the toolbelt's `also` argument, run both
beside HS's rules. 21 of the 35 bugs are missed by all three: connector pinouts, signal swaps with no pair name, part
choice and design intent.

Three rules tried on the held-out misses were dropped because they were wrong more often than right on 110 known-good
boards: VDD pins fed only by capacitors (core and internal-regulator pins are), inputs with no driver (bootstrap and
switch-node pins are typed input), and named nets reaching one pin (unused named GPIO on module connectors).

## Predictions against measurements (`examples/backtests/`)

* Hover time: NanoBench's Crazyflie 2.1 at 40.85 g held height 40-88 s; HS's arithmetic said 4.1 min. At the stock 27 g it
  matches Bitcraze's 7 min within 5%. HS now marks hover time an upper bound when usable thrust-to-weight is under 1.5.
* Rocker-bogie climb: HS's one-radius cap was its edge model's limit, not the rover's; a wall phase was added. OSR's
  "over 2x wheel height" stays unchecked without OSR's bogie rotation range.
* SO-101 shoulder load: owner reports (an SO-100 shoulder overload, an SO-101 builder stripping STS3215 gears above
  about 15% of rated torque) fit HS's warning; no measured shoulder torque exists yet.
* `PREDICTIONS.json` keeps every open prediction with how to measure it.

## Routing (`examples/routing_trial/copper_vs_designer_reference_boards_20261127.json`)

Three open 2-layer boards stripped to the designer's placement and re-routed by Copper: one DRC-clean with 12 vias
against the designer's 39 (14% more track), one with 2 connections left, one complete but with 7 shorts. HS now also
sizes power tracks from stated currents before routing and checks the routed board after (`trace_capacity`, IPC-2221;
`board.net_currents_a`, `hs_trace_current`).

## CAD from other programs (`examples/step_fit/`)

`step_fit` (toolbelt `hs_step_fit`) checks any STEP assembly, whatever made it: SolidWorks, Fusion 360, Onshape, FreeCAD or
KiCad. Parts keep their names from the STEP tree; it reports overlapping pairs with their volume, tight gaps, loose parts,
size, volumes and masses. On SO-100's published follower assembly (19 parts, exported from Fusion 360) it ran in 48 s and
found 3 overlaps, the largest 170 mm3 between a servo model and a bracket, and 5 gaps under 1 mm. Editing a part in
SolidWorks and re-exporting STEP now gets HS's fit check back; SolidWorks' own files and feature tree are still out of reach.
