# G1 operating source & metrology qualification — reviewed candidates

**Vendor research snapshot, not a final purchase/physical approval.** Refer to [CONSOLIDATED_REVIEW.md](CONSOLIDATED_REVIEW.md) for the integrated gate status.
20 November 2026 | Hardware Splicer witness fixture | stacked on HS #367 / #364 / #360 / #358 / #356

**Release status: HOLD. No instrument has been procured, borrowed, powered, connected, calibrated, or physically characterized.** This is an engineering decision dossier, not an equipment authorization or a fabricated observation.

## Why this selection is a material G1 design decision

The existing 5 V witness station assumes an inviolable **5.25 V maximum at J2**. Merely setting a bench source to 5.0 V and sampling an INA228 at 1 Hz does NOT enforce that ceiling: a user could misconfigure the output or a transient could escape sampling. The normal 12 ohm / 1% candidate load has a conservative 2.3306 W upper-bound under worst minimum resistance and 5.25 V, but this says nothing about transients, thermal mounting or DC fault protection.

The next selection must therefore have a *documented programmable overvoltage shutdown capability* with the source's actual overvoltage trip waveform independently tested. OCP/current-limit behavior and source earth isolation must also be observed. This is a necessary but not sufficient condition for G0/PHY-05.

## Published source capability comparison

| Source lead | Manufacturer supports user-configurable OVP? | OCP/current limiting | Decision |
|---|---|---|---|
| **Rigol DP832A, CH1** (0–30 V / 0–3 A) | Yes, 1 mV–33 V OVP range | Yes, 1 mA–3.3 A OCP range | **Preferred borrow candidate**, not approved |
| **Siglent SPD3303X-E, CH1** (0–32 V / 0–3.2 A) | **No** (manufacturer support statement) | Yes, CC + OCP | **Not suitable alone** for strict 5.25 V envelope |
| **Siglent SPD4000X family** | Yes | Yes | Hold: exact model/channel and OVP settable range unselected |

Primary public documentation:
- Rigol official DP800 series datasheet: https://www.rigol.com/dam/global/downloads/brochures/en/data-sheet/dc-powers/DP800_DataSheet_EN.pdf
- Rigol official DP800 programming guide: https://int.rigol.com/Public/Uploads/uploadfile/files/20211028/20211028151336_617a4da001f78.pdf
- Siglent SPD3303X/X-E manufacturer: https://www.siglent.com/na/products-overview/spd3303x-x-e/
- Siglent official support clarification **no user-settable OVP**: https://siglent.tawk.help/article/spd3303x-spd3303x-e-spd3303c-and-charging-applications
- Siglent SPD4000X family datasheet/product: https://siglentna.com/power-supplies/spd4000x-series-programmable-linear-dc-power-supply/

Engineering interpretation: the source-programming resolution or the existence of an OVP menu does NOT demonstrate that the load terminals never exceed 5.25 V. Its OVP response-time/overshoot and actual output topology, including possible battery/USB back-feed and cable parasitics, need a controlled physical test by qualified staff. The selected channel MUST be explicitly named. No remote commands are sent by the source screening tool.

## Proposed *off-device*, preliminary settings — not an operating instruction

For subsequent authorized lab evaluation, the scenario is a nominal 5.0 V output; **OVP target 5.20 V** to leave margin before the 5.25 V J2 absolute limit; **OCP target 0.65 A**, subject to real current limiting and OCP response. Values are design test requirements only, not set on any instrument. The 12 ohm precision resistor's published lower bound in the prior milestone was 11.82654 ohm; 5.25 / 11.82654 = about 0.444 A max fault-free load current, under 0.65 A. A short/fault is not constrained by this resistance.

A source operating in CC mode, an OCP shutdown command setting, and actual measured short-circuit peak/energy are distinct facts. Neither "CC" nor a protective tripping flag proves max current or max voltage throughout an unknown transient.

**PHY-05 remains HOLD** until independent physical source waveform characterization verifies actual max J2 voltage, current limiting, trip-time behavior, source isolation, host USB/earth topology, polarity and fault handling with full calibration and independent operator evidence. A mere software readback of OVP/OCP levels is insufficient.

## The fuse-holder problem is NOT solved by finding a DC-rated fuse family

The original SCHURTER FAB 0031.3551 holder is advertised at **250 VAC** with rated power acceptance dependent on ambient. This is not a fuse cartridge DC breaking rating.

The SCHURTER SPT **5×20 mm** series is a plausible high-breaking-capacity time-lag family with rated variants from 0.5 to 16 A and DC voltage ratings up to 300 VDC. But:

- We have **not chosen an exact link MPN**, verified the DC rating applicable to that individual SKU, or reviewed its actual time-current curve at the source's bounded/prospective fault waveform.
- Even an approved fuse rated 1 A cannot be assumed to clear a sustained **0.65 A** current-limited fault; other ratings (e.g. 0.5 A time-lag) are not automatically safe from normal-load heating, inrush and nuisance-trip issues.
- The 0031.3551 holder's DC/environment and mounting compatibility with the chosen link and heat dissipation must be checked independently. Its 250 VAC label alone cannot certify this.
- **The primary fault protection decision stays with a physically characterized current-limited/OVP/OCP source**; the series fuse remains supplementary and uncredited until a real fault-coordination review completes.

Source pages:
- SCHURTER holder: https://www.schurter.com/en/part/0031.3551
- SCHURTER SPT 5x20 family: https://www.schurter.com/en/datasheet/0001.2510

Do not order a generic fuse by ampere rating alone or replace the holder with a direct short.

## Revised metrology reality at 12 ohm

Under the prior 5V/12ohm/0.075ohm *hypothetical* series model:
- I = 5/12.075 ≈ 0.41408 A; J2 bus ≈ 4.9689 V; R_ref (10 mΩ) produces ~4.1408 mV.
- Hypothetical calibrated-instrument **specification** (not a connected instrument): Siglent SDM3055 DMM, 200 mV DCV, 1-year 23±5°C specification ±(0.015% of reading + 0.004% of range) yields ~8.62 µV at that shunt voltage (~0.208% of current).
- Reference **uncalibrated** nominal shunt resistance ±1%, plus primary Adafruit on-board shunt conservatively **±1% unverified** and hypothetical 20V-range bus voltage DMM accuracy adds approximately 0.031%. A simple *incomplete worst-case additive allowance* already exceeds **2.2%**, even omitting both ADC/drift, temperature, covariance and timing.
- This is **not a lower bound on actual instrument error**; errors can cancel. It is a demonstration that, using presently allowed component specs, a physical ±0.75% disagreement acceptance criterion is **not guaranteed**.
- No actual uncertainty can be finalized without characterized primary/reference shunts, calibrated separate high-side reference and bus channels, synchronized conversion times and a real lab reference capture. The primary/reference paths were not independently measured.

Siglent SDM3055 official datasheet:
https://www.siglenteu.com/wp-content/uploads/dlm_uploads/2023/04/SDM3055_Datasheet_E04A-1.pdf

## Material/practical next step: BORROW, qualify, then decide

The minimum **request for qualified laboratory access** is one DP832A (CH1) or equivalent *documented adjustable OVP+OCP* isolated source; two independent calibrated DCV channels capable of measuring approximately **4 mV differential Kelvin plus 5 V load bus** with compatible safe common-mode and grounds; a suitable reference shunt; a verified oscilloscope/differential probe for source fault waveforms; an actual safe DC fuse/cartridge review; and a qualified operator plus independent reviewer.

The borrowing request should explicitly seek written confirmation of equipment model, availability, actual calibration status/serials, electrical-safety oversight, and permission for a limited **low-voltage only** 5 V/~0.4 A session. No dates or personnel are assumed. The operator should first inspect exact instrument manuals and circuit wiring before any energization; testing fault behavior must be performed by a qualified operator using a reviewed fixture, not a remotely driven short.

The existing *blank* G1 evidence package, protection template and bracketed two-meter SCPI mock are suitable for collecting and structurally reviewing such evidence. The new source screen below adds an explicit vendor OVP eligibility gate but cannot close physical acceptance.

## Reproduce source and metrology screen (no connected equipment)

From the existing witness directory:

    python3 source_suitability.py \
      --catalogue G1_SOURCE_AND_FUSE_CANDIDATES_20261120.json \
      --out /new/unique/source-review.json

It always returns exit **2** with physical_ready, fabrication_allowed, energization_authorized all **false**. It compares hard-coded reviewed source capability facts against editable catalogue values to reject a falsely "OVP-enabled" Siglent SPD3303X-E or silently changed source limits. It reports an incomplete dual-path metrology allowance.

The existing protection preflight now separately demands an OVP setpoint below 5.25 V and observed peak-at-J2 during the protection event no greater than 5.25 V; missing or contradictory evidence causes HOLD. These fields cannot prove independent measurement authenticity by themselves.

**No source is selected, no fuse link is selected, no instrument is borrowed, no physical G0/G1 gate is closed.** This milestone produces a *bounded, falsifiable procurement/borrowing choice* rather than inventing hardware validation.
