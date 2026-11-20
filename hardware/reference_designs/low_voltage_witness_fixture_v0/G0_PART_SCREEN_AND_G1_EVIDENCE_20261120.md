# G0 load-part and G1 physical evidence milestone — 20 November 2026

**Decision: HOLD for procurement, fabrication and energization.**
This milestone is stacked on HS #360, #358 and #356, alongside
PL #180 / #179. It specifies credible test-article candidates and a
preflight contract for an independent physical operator. No actual bench
equipment exists in this work.

## Why the previous 12-ohm suggestion needed another review

The original v0 fixture specifies 5.0 V nominal, 5.25 V maximum J2
voltage and a 2.5 W normal-load ceiling. Its nominal 10-ohm SPICE,
BOM, KiCad and pinned 183 software samples remain unchanged.
The previous 12-ohm/-5% illustration gave 2.4178 W at 5.25 V,
**but omitted resistor temperature coefficient**.

We identified two actual Taiwan-distributor MPNs for a new external load.
Neither part was purchased or approved.

| Unprocured candidate | Resistance | Initial tolerance | TCR bound | Component temperature range | Rmin across range | Upper-bound normal power |
|---|---:|---:|---:|---|---:|---:|
| YAGEO SQP10AJB-12R, cement axial, 10 W | 12 ohm | +/-5% | +/-300 ppm/C | -55 to +155 C | 10.9554 ohm | **2.515883 W: FAIL** |
| Vishay Dale RE65G12R0C02, chassis, 10 W | 12 ohm | +/-1% | +/-20 ppm/C | -55 to +250 C | 11.82654 ohm | **2.330563 W: MATH WITHIN** |

For a normal resistive load, not a fault or short:

    Rmin = Rnominal * (1 - initial_tolerance) *
           (1 - absolute_TCR * max_temperature_distance_from_25C)
    Pmax = (5.25 V)^2 / Rmin

This ignores beneficial shunt/contact/fuse series resistance. It
conservatively combines manufacturing and temperature deviations in
the direction of minimum resistance. The YAGEO catalogue lists distinct
TCR classes; use the 300ppm/C conservative assumption until the exact
delivered component is confirmed. The precision candidate is a modeled
option only; its power rating depends on a correctly attached chassis
and derating, **not** the existing bare 125 x 58 mm PCB.

Manufacturer and distributor leads (check again before ordering):
- YAGEO SQP10AJB-12R: https://www.digikey.tw/en/products/detail/yageo/SQP10AJB-12R/18737
- YAGEO SQP/NSP datasheet: https://yageogroup.com/content/datasheet/asset/file/YAGEO-SQP_NSP_DATASHEET
- Vishay RE65G12R0C02: https://www.digikey.tw/en/products/detail/vishay-dale/RE65G12R0C02/26752174
- Vishay RH/RE chassis and heat-sink instructions: https://www.vishay.com/docs/30201/rhnh.pdf
- Original SCHURTER holder: https://www.schurter.com/en/part/0031.3551

Power-envelope resistance arithmetic is NOT thermal qualification.
Even a load whose resistance math passes can overheat at elevated
ambient temperature or if the mounting/chassis is insufficient.
Fuse interruption and source protection remain entirely unproven.

## New native 12-ohm simulation and Policy Lab replay

The added bench_candidate_replay.py processes the two MPN-specific
profiles under manufacturer worst-case tolerance/TCR assumptions
and cross-checks each with independent ngspice operating-point math.

For the precision 12-ohm scenario it also generates an entirely new,
write-once TEST_FIXTURE from the actual HS INA228 register emulator
and logger, with 183 1-Hz samples and a separately created but
**model-derived and NOT independent** reference path. It invokes the
existing strict HS screen and optionally the *unchanged* frozen Policy
Lab PLRS-6 capture receiver. The original 10-ohm source artifacts
remain untouched and hash-bound.

Nominal series model: 5.00 V source, hypothetical 0.075-ohm series
resistance, 12-ohm external load.
- Modeled nominal load: approximately **2.05754 W**.
- Modeled three-minute load energy: approximately **0.102877 Wh**.
- Original 10-ohm model: approximately 2.462918 W / 0.123146 Wh.

From this folder on a machine with ngspice and the HS code:

    python3 bench_candidate_replay.py \
      --pl-root /absolute/PLRS6-checkout \
      --baseline-verification evidence/fixture-replay-20261120/verification.json \
      --out /new/unused/output --fail-if-held

The optional release gate must return exit **2**, with
fabrication_allowed=false. A clean software intake does NOT change that.

## Metrological boundary: 1% still cannot be justified

At nominal ~0.414 A, the 10-milliohm reference produces ~4.14 mV
instead of the previous ~5 mV. A 1% current comparison is ~41 uV.
The prior hypothetical Siglent SDM3055 200-mV range spec gives
roughly +/-8.62 uV at that signal, or ~0.208%, before resistor
tolerance. With the proposed reference shunt's uncalibrated +/-1%
tolerance, the incomplete simple worst-case already exceeds 1.2%.
Primary-channel accuracy, thermal EMF, reference voltage,
instrument calibration and timing are not included. The strict
HS screen's 0.75% threshold is a **synthetic diagnostic only**,
not physically valid agreement tolerance.

## G1 independent physical evidence preflight

The new G1_BENCH_EVIDENCE_TEMPLATE.json is empty on purpose.
The new g1_evidence_gate.py performs SHA-256 and source-kind
checks over copied real operator submissions. It requires distinct
identities, a named part and supply, DC fuse coordination,
source-current-limit/fault records, isolation and grounding,
load thermal mounting, as-built identity, genuine primary
samples/registers/receipt, independent reference native exports,
meter calibration/serial, external-clock evidence and separately
signed operator review. It rejects old TEST_FIXTURE receipts even
if relabeled in an outer manifest.

    python3 g1_evidence_gate.py \
      --packet /real/bench/packet.json \
      --out /new/report.json --fail-if-held

No actual evidence has been supplied. The template must therefore fail.
Even a fully filled, hash-consistent packet is only **structurally
submitted for independent human review** and can NEVER grant power-on
or fabrication authorization through this code. It cannot prove
real device identity, calibration authenticity, source isolation,
mechanical safety or independence merely from file bytes.

## Unresolved review gates

- **G0:** independently select/check the actual load, its mounting
  and thermal derating, real source and voltage ceiling, DC fuse link,
  cables, connectors and USB/earth topology.
- **G1:** physically mount, inspect, calibrate and capture independently
  using an authorized operator, timebase and separate reference.
- **G2:** establish a measured uncertainty budget and defensible
  threshold, then run blind bias/timing/fault controls and independent repeat.
- **G3:** only afterwards measure economic and workflow value.

**All physical approval, procurement, manufacturing and energization
gates remain HOLD.** The executable work here is a sourced design
choice, native software replay and controlled evidence contract,
not a physical test.
