# Witness G0/G2 continuation — bounded load option and fail-closed fixture discrimination

**Status: HOLD / DESIGN CANDIDATE / SOFTWARE TEST FIXTURE ONLY.**

Stacked on HS #358 and #356. This does not modify the frozen Policy Lab
PLRS-6 receiver or authorize procurement, fabrication, energization or
physical claims.

## G0: consistent *proposed* normal-load envelope

The current v0 board's SPICE source uses a 10 ohm external load at 5 V, but
station-spec-5v.json also specifies 5.25 V maximum and a 2.5 W load ceiling.

For fault-free resistive load operation, the conservative bound is:

    P_load <= V_J2_max^2 / R_load_min
    R_load_min = R_nominal * (1 - tolerance_percent/100)

The 5.25 V ceiling must apply at the J2 load terminals; an INA228 sample
is not hardware overvoltage protection and cannot rule out transients.
Treating 5.25 V as the entire available load voltage neglects any favorable
series-shunt/contact drop. This is not a fault-current calculation.

| Model choice (unselected) | Minimum load | Max bus | Conservative load power | Limit |
|---|---:|---:|---:|---|
| v0 10 ohm, hypothetical -5% | 9.50 ohm | 5.25 V | 2.9013 W | FAIL |
| Candidate 12 ohm, hypothetical -5% | 11.40 ohm | 5.25 V | 2.4178 W | Within 2.5 W |
| Candidate 12 ohm, hypothetical -10% | 10.80 ohm | 5.25 V | 2.5521 W | FAIL |

For 12 ohm/-5% the conservative maximum normal current is approximately
0.4605 A. The 10 milliohm reference shunt signal is up to 4.61 mV; 1% current
difference is only 46 uV there, and less at lower current. The original
500 mA/5 mV target changes with this load choice.

**No selection or model replacement yet.** A real 12 ohm part with guaranteed
temperature/tolerance range, mounting and thermal behavior must be chosen,
and the canonical BOM, station spec, ngspice model, emitted test data and
associated evidence must then be regenerated together. The current 10 ohm
baseline and immutable pinned source are retained as an audit control.
PHY-10 remains OPEN. Correct fuse clearing, supply source limiting, cable
ratings and fault-energy behavior remain separate blockers.

## G2: new software-only discrepancy screen

The new measurement_screen.py is an *additional* diagnostic, not a change
to the frozen PLRS-6 structural intake. On the actual pinned 183-row fixture:

- SHA-256 and byte-length bind the primary CSV and raw INA228 registers
  to primary/session.json. Reference CSV bytes are hashed but **not**
  authenticated as an independent, calibrated instrument.
- UTC timestamps, increasing sample times, ≤1.5 s sample gaps, strict
  one-to-one pair counts and ≤200 ms paired clock offset are enforced.
  A reference 500 ms clock shift is rejected.
- Trapezoidal V*I energy is integrated over primary intervals using paired
  reference shunt readings (I_ref = V_shunt / R_shunt).
- Each paired power sample and the whole interval use the primary reading
  as the relative-error denominator. 0.75% is a deliberately stricter
  **synthetic test sensitivity**, not a physically justified acceptance
  threshold. It catches 1% reference bias, 5% reference bias and isolated
  injected spikes.
- Exit code 0 only means PASS_FIXTURE_DISCRIMINATION_ONLY; exit code 2
  means FAIL_FIXTURE_DISAGREEMENT or INVALID_INPUT_HOLD. Every outcome
  stays nonphysical and fabrication-ineligible.

The existing +/-1% nominal reference-shunt tolerance, before calibration,
already prevents a defensible 0.75% *real instrument* agreement claim.
Reference independence, absolute clock integrity, high-side input safety and
uncertainty are all **unproven**. Authentic primary bytes also do not
authenticate a sensor or prove correct engineering values.

### Reproduce without hardware

From this directory, using a fresh output report path:

    python3 -m unittest -v test_measurement_screen.py
    python3 measurement_screen.py \
      --primary evidence/fixture-replay-20261120/primary/samples.csv \
      --reference evidence/fixture-replay-20261120/reference-fixture.csv \
      --primary-session evidence/fixture-replay-20261120/primary/session.json \
      --primary-registers evidence/fixture-replay-20261120/primary/registers.jsonl \
      --out /tmp/new-unique-witness-screen-report.json

The output is never silently overwritten. Injection tests exercise +1%,
+5% and +10% reference biases, one transient, +0.5 s time shift, missing
samples, bad timestamps, malformed/negative readings, primary byte tampering
and raw-register tampering. These are expected-software-behavior tests only.

## Remaining acceptance gates

**G0 design consistency:** name and validate exact load resistor, source,
fuse link+holder, cables, Kelvin shunt, thermal mounting and grounding.
Regenerate canonical design inputs and operating-corner analysis. The
mathematical candidate above does not close this gate.

**G1 physical provenance:** independent qualified lab operation, distinct
reference hardware, serials, calibrated high-side voltage/shunt channels,
verified time pairing, original raw exports and independent operator.
No actual measurements have occurred.

**G2 physical agreement:** pre-register an instrument-backed uncertainty
budget at 4–5 mV with shunt calibration, DMM range terms, tempco/self-heating,
thermal EMF, offset, drift, timebase and covariance. Establish physically
justified threshold and blind real-device fault tests; a synthetic screen
does not complete G2.

**G3 economics:** no performance or cost-saving claim until physical
reproducibility and useful operational comparison exist.

**Release remains HOLD.**
