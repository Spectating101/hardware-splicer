# HS function-driven geometry: native slicing and feedback

This is the actual manufacturing-feedback milestone stacked on the original
native STEP/STL geometry milestone (#332), not a simulated slicer.

## Real source, real G-code toolpaths

Native PrusaSlicer 2.9.2 from Debian 13 (package prusa-slicer 2.9.2+dfsg-1,
SHA256 4ff3972a868621f48adee0e1d6848ce27ada765a2fdc1d0cb87e81026f6c5392)
sliced all SIX source-verified geometry variants in TWO 0.4 mm-nozzle profiles.

Profile A: 0.20 mm layers, 0.20 mm first layer.
Profile B: 0.28 mm layers, 0.28 mm first layer.
Both: nominal 1.75 mm generic PLA, 1.24 g/cm³ density, 20% gyroid infill,
three perimeters, 220 x 220 mm bed; 205/210 °C hotend and 60 °C bed,
no skirt or brim, and no generated supports.

These are UNCALIBRATED model assumptions, not a physically verified printer
profile; G-code was generated in local scratch and deliberately not released
for arbitrary hardware execution.

| Candidate | Standard filament | Standard time | Draft filament | Draft time |
| --- | ---: | ---: | ---: | ---: |
| Solid plate | 29.00 g | 174.5 min | 31.13 g | 147.9 min |
| Minimal 46 | 17.30 g | 101.9 min | 17.59 g | 80.8 min |
| Minimal 52 | 17.95 g | 105.7 min | 18.27 g | 84.1 min |
| Ladder 58 | 20.21 g | 118.9 min | 20.89 g | 96.1 min |
| Ladder 64 | 20.89 g | 123.1 min | 21.67 g | 99.8 min |
| Reinforced 68 | 24.79 g | 145.1 min | 25.59 g | 117.7 min |

The initially selected Ladder 58 actually saves 30.3% / 32.9% estimated
filament over the solid plate, versus its earlier 39.9% CAD solid-volume
reduction. CAD volume is not the same thing as sliced filament consumption.

## Function-to-manufacture feedback genuinely changes the decision

The original HS static tip proxy used 55% of solid density as a fabricated
effective mass estimate. When the real G-code's filament-mass estimate is
used instead, the MINIMAL 52 alternative now narrowly passes the
nominal 1.50 static tipping factor (1.565/1.577 for the two profiles).
That changes the nominal winner from Ladder 58 to Minimal 52.

Minimal 46 remains below the requirement (1.363/1.373).

A second, deliberately conservative POST-HOC scenario assumes printed
material weighs 10% less, PCB mass is 5% less and the lateral push is
5% greater. Minimal 52 then fails the same minimum factor (1.385/1.395);
Ladder 58 passes (1.623/1.647). Under that explicitly uncalibrated
sensitivity guard, Ladder 58 remains the preferred conceptual geometry.

| Selection | Standard profile | Draft profile |
| --- | ---: | ---: |
| Nominal minimum-mass: Minimal 52 | 17.95 g (38.1% less than plate) | 18.27 g (41.3% less) |
| Guarded minimum-mass: Ladder 58 | 20.21 g (30.3% less) | 20.89 g (32.9% less) |

The uncertainty band is NOT empirically calibrated; the unpowered stand
was NOT physically weighed, fit-checked, tilted, printed or fatigue-tested.
Tipping is a simple static proxy, not force/displacement simulation or FEA.

## Source fidelity and repeatability

The original full native G-code toolpaths remain on the authorized
Optiplex under /tmp/hs-real-slicer-benchmark-v2-20261110/ (~20 MB).
The repository retains source-linked, inspectable evidence receipts:
- slicer_profile.json: the exact unverified FDM assumptions.
- feedback_policy.json: the declared post-hoc guard band.
- slicer_results/SLICER_COMPARISON.json: 12 successful PrusaSlicer calls,
  exact STL sources, full CLI argument receipts, G-code hashes, grams,
  time estimates, layer counts, native slicer executable hash and version.
- slicer_results/NATIVE_SLICER_AUDIT.json: source/metadata integrity gate.
- slicer_results/MASS_FEEDBACK.json: independently recomputed response
  of the function-level constraint ranking to the new material estimate.
- slicer_results/FEEDBACK_AUDIT.json: authority-limited audit.
- verify_independent_reslice.py: a separate Python standard-library
  script that obtains NEW G-code from a real native PrusaSlicer binary
  and rechecks all 12 mass/time values without trusting the original
  primary slicer driver.

The first attempted source slice failed because the preliminary output
parser incorrectly demanded a G0 movement command. PrusaSlicer 2.9
validly uses G1 for all moves. The parser was corrected and then
the EXACT same geometry/profile inputs were rerun. The corrected
source run and a second independent full 12-toolpath rerun succeeded.
This is documented rather than hidden or relabelled as repair accuracy.

Reproduce the native FFF experiment:

    PYTHONPATH=src python3 examples/print_function_pilot/pcb_service_stand/run_slicer.py \
      --slicer /path/to/prusa-slicer \
      --out /tmp/hs_function_slicer_recheck

Reproduce a second, independent toolchain comparison:

    python3 examples/print_function_pilot/pcb_service_stand/verify_independent_reslice.py \
      --slicer /path/to/prusa-slicer

The source-only audit requires no slicer:

    python3 examples/print_function_pilot/pcb_service_stand/verify_independent_reslice.py \
      --source-only

## Remaining barriers

No real measured board geometry/mass, independently qualified ESD-safe
material, print coupon, printer calibration, support-free overhang
inspection, physical 3D print, slip and tip testing, or actual
component retention. The output is an engineering design exploration,
not an authorized fabrication or electronics-handling fixture.

Next engineering acceptance step: use a real board scan or caliper data
and printer/slicer profile, then produce fit coupons, try physical
retention and tip tests; otherwise keep physical status UNVERIFIED.
