# Witness PCB independent physical-readiness audit — 20 Nov 2026

**Verdict: HOLD.** This is an independent audit of the existing software-only 5 V witness board (HS #356). The original schematic, PCB, station specification and frozen Policy Lab intake are not modified. No physical device has been connected or tested.

## Reproduce

From the witness design directory:

    python3 -m unittest -v test_audit_readiness.py
    python3 audit_readiness.py --pl-root /path/to/pl-with-PLRS6 \
        --native-replay /path/to/independent-verify_and_replay-output \
        --out /path/to/new-empty-output

The output includes report.json, report.md, and the individual injected raw TEST_FIXTURE inputs and receipts.

Add the flag --fail-if-held to the audit CLI when using it as an independent release gate. It returns exit code 2 for the current HOLD; exit code 0 without the flag only means the *audit executed*, not that fabrication is authorized.

## 1. The proposed 2.5 W operating ceiling is inconsistent

The existing station-spec-5v.json states 5.0 V nominal, 5.25 V maximum bus, and maximum_power_w = 2.5. Its original SPICE test only covers 5.0 V and nominal 10 Ω. Independent arithmetic and ngspice corner checks find:

| Source voltage | Assumed load | Modeled current | Load power | 2.5 W ceiling |
|---|---:|---:|---:|---|
| 5.00 V | 10.0 Ω | 0.496278 A | 2.462918 W | within |
| 5.25 V | 10.0 Ω | 0.521092 A | 2.715367 W | exceeds |
| 5.00 V | 9.5 Ω | 0.522193 A | 2.590515 W | exceeds |
| 5.25 V | 9.5 Ω | 0.548303 A | 2.856042 W | exceeds |

The 9.5 Ω resistance is a declared hypothetical −5% change, not a measured vendor tolerance. All these modeled currents are less than the proposed 0.65 A supply current limit. Source current limiting alone does not ensure a 2.5 W load ceiling across the proposed bus range. This is not an assertion that the load is unsafe at 2.86 W; the actual load, protection and assembly have not been selected.

**Engineering decision needed:** establish a coherent maximum voltage, actual load tolerance, and power envelope; revise the original spec or test conditions only after independent engineering review.

## 2. The frozen Policy Lab receiver is an integrity gate, not metrological acceptance

The original software fixture generated 183 INA228 register-decoded records and a reference derived from the same idealized model. Its apparent agreement cannot establish independent instrument performance.

| TEST_FIXTURE modification | Policy Lab structural result |
|---|---|
| Unmodified | accepted for structural intake; no physical claims |
| Reference current +1% | still structurally ingested, no disagreement warning |
| Reference current +5% | still ingested, no warning (4.76% using the larger denominator) |
| Reference current +10% | still ingested, three diagnostic discrepancy windows |
| Reference clock +0.5 seconds | still ingested, no clock-authentication claim |
| Reference sample missing beyond maximum gap | rejected |
| Primary samples tampered against saved sidecar/register hash | rejected |

The frozen receiver uses a non-metrological 5% window warning and **never grants physical readiness**, even with no warning. This is a scoped design, not a policy failure. Calibrated agreement needs a new explicitly reviewed stage with physical reference instruments, traceability and a prospective uncertainty threshold.

## 3. Independent reference feasibility is still unproved

At 0.5 A a 10 mΩ Kelvin shunt produces only about 5 mV. One **unselected** candidate reference is the Siglent SDM3055, whose 200 mV DCV manufacturer specification is ±(0.015% reading + 0.004% range), under stated calibration and temperature conditions. This gives approximately ±8.75 µV / ±0.175% of the 5 mV signal. The proposed Vishay WSK2512 10 mΩ part has nominal ±1% resistor tolerance. An uncalibrated simple additive extreme is therefore already about ±1.175% before other errors. This is NOT a complete calibrated uncertainty budget, nor evidence of instrument suitability, availability or purchase intent.

Manufacturer/source leads:
- https://www.siglent.com/in/products-overview/sdm3055/
- https://siglentna.com/digital-multimeters/sdm3055-5-%C2%BD-digits-dual-display-digital-multimeters/
- https://www.digikey.com/en/products/detail/vishay-dale/WSK2512R0100FEA/12142494
- https://www.adafruit.com/product/5832

Before selection, check shunt characterization, actual high-side differential common-mode, return and earth safety, voltage + current time pairing, serial/source identity, device clock, raw logging and calibration. Borrowing suitable certified laboratory instruments is a sensible first feasibility option.

## 4. The proposed fuse does not constitute proven protection

The BOM lists an unselected 1 A nominal fuse candidate and an intended 0.65 A current-limited source. This does not demonstrate fuse clearing under a sustained fault or specify a DC interrupt rating. Select fuse link and holder, source, conductors and load together under a documented independent safety review. The holder's AC voltage rating is NOT the DC breaking capability of an installed fuse link.

SCHURTER reference: https://www.schurter.com/en/knowledge/fuse-link

## Prioritized acceptance gates

- **G0: design consistency:** resolve the power-envelope discrepancy; name exact supply, isolation, fuse, shunts, reference channels, mounting and grounding; complete independent electrical/thermal/assembly review. Hold fabrication until this is resolved.
- **G1: physical evidence:** authorized lab/operator builds and checks the device with suitable instruments, original raw device exports, device serials, calibration records, external timebase and second-operator oversight. None has occurred.
- **G2: scientific discrimination:** freeze an actual uncertainty budget and meaningful energy difference before a real study. Demonstrate detection of true planted offsets/time shifts/losses and reject false decisions. Compare the result against a normal independent engineer with adequate off-the-shelf instruments and scripts.
- **G3: production/commercial value:** only after G1–G2 compare operator time, incremental engineering cost, repeatability, error reductions and external willingness to use the resulting service or equipment.

No procurement, physical commissioning, funding approval or commercialization is claimed by this audit.
