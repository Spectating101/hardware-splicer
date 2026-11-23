# HS ↔ Policy Lab: G0–G4 witness-milestone readiness

**Date:** 2026-11-20
**Status:** source-bound numerical candidate, **HOLD FOR FABRICATION AND POWER-ON**.
**Scope:** experimental 5 V, roughly 0.35–0.4 A witness load, not the separate 24 V / 120 W measurement-station program.
**Baseline:** HS [PR #356](https://github.com/Spectating101/hardware-splicer/pull/356), [audit #358](https://github.com/Spectating101/hardware-splicer/pull/358), independent load experiments [#359](https://github.com/Spectating101/hardware-splicer/pull/359) and [#360](https://github.com/Spectating101/hardware-splicer/pull/360), raw evidence-coherence repair [#365](https://github.com/Spectating101/hardware-splicer/pull/365). No active HS or Policy Lab UI, schematic, PCB, regulator or source power output is modified by this work.

## Executive decision

**Preferred DIGITAL load candidate: 13 Ω, ±1% (TE Connectivity CGS `355013RFT`, 5 W).**
Selection is conditional and *does not authorize purchasing, populating, fabricating or energizing* the design. The part is **SMD**, not a plug-in leaded load: an engineered, insulated mounting carrier, thermal route and strain relief must be designed and reviewed. TE confirms value, tolerance and nominal rating; its own catalog currently displays "not currently available" while at least one distributor lists stock. Neither Taiwan stock nor selected procurement is established. The original 10 Ω model must remain an audit control, not be silently edited in-place.

**Physical release decision: HOLD.** All G0 remaining evidence and G1/G2 physical measurements need an operator and real instruments. The present G3 software fixture replay **cannot** establish an authenticated measurement. G4 cost/finance is deliberately not assessed.

The research model pins exact original station-spec bytes (SHA-256 `78257576dd6b78c158ed35157ade26d79a10ee9071b9d704758d0c17e29ad016`) rather than changing the source contract. Only the explicit 4.75–5.25 V and trial numerical constraints are examined.

## G0 — Resolve load-selection disagreement without hiding assumptions

Under **fault-free resistive operation**, ignoring favorable voltage drops across connectors and two shunts:

```
R_min = R_nom * (1 - tolerance)
R_max = R_nom * (1 + tolerance)
P_load_upper = V_max^2 / R_min
I_load_upper = V_max / R_min
I_load_lower = V_min / (R_max + assumed_series_R_max)
reserve_limit = 2.5 W * (1 - 10%) = 2.25 W
```

The 0.34 A minimum current and 10% reserve are **researcher/other-agent trial criteria**, not manufacturer safety limits or regulatory standards. The source ceiling 0.65 A is also an unverified *trial assumption*. Worst-case corner parameters are not representative distributions or guaranteed resistor thermal behavior.

| External load (modeled) | Worst P at 5.25 V | Min modeled I | 2.5 W? | 10% power reserve? | 0.34 A min? |
| --- | ---: | ---: | --- | --- | --- |
| 10 Ω ±5% (original) | 2.9013 W | 0.446 A | **FAIL** | FAIL | PASS |
| 12 Ω ±5% (HS #360) | 2.4178 W | 0.373 A | PASS | **FAIL** | PASS |
| 13 Ω ±5% (HS #359) | 2.2328 W | 0.344 A | PASS | PASS, narrowly | PASS, narrowly |
| 13 Ω ±1% (TE candidate) | 2.1416 W | 0.358 A | PASS | PASS | PASS |
| 15 Ω ±5% (negative control) | 1.9342 W | 0.299 A | PASS | PASS | **FAIL** |

**Not yet demonstrated:** real part solder pad/cable clearance, heat dissipation under sustained load, full source-output envelope including transients, current-limit/OCP behavior, actual 5 V power delivered at J2, exact reference shunt mounting, independently selected DC fuse and holder, fault-current and DC interruption coordination, host-I2C grounding, and independent review. Safety consequences are outside this arithmetic upper bound.

The original circuit limits 2.5 W **J2 load power**, not necessarily the upstream source's fault energy. A claimed 1 A fuse will not necessarily open under a 0.65 A current-limited fault. Fuse holder and link must be chosen together and validated for the actual source fault current, fault clearing requirement and DC interrupt capability. Current sensing and software do **not** replace hardware protection.

### Candidate sourcing and engineering status

| Function | Identified **candidate**, not selected/procured | Remaining gate |
| --- | --- | --- |
| 13 Ω 1% load | TE CGS `355013RFT` / `2-2176403-8`, thick-film SMD 5 W | Unverified Taiwan availability, solder footprint/carrier, temperature/derating, mechanical/thermal limits |
| Lower precision alternate | Ohmite `95J13RE`, 13 Ω 5 W ±5% axial | Smaller power/current margins; selected lot/resistance and thermal effects unknown |
| Independent shunt | Vishay `WSK2512R0100FEA`, 10 mΩ ±1%, four-terminal 1 W | Procurement, Kelvin layout, measured actual R, temperature and independent calibration |
| Adjustable isolated DC bench supply | Siglent `SPD3303X` CH1 candidate (not fixed CH3) | Not connected; source OVP/OCP/current limits, overshoot, isolation and fault clearing not verified |
| Reference meter | Siglent `SDM3055` 200 mV DCV range candidate | No instrument identified; one-channel DMM alone cannot simultaneously read J2 voltage and shunt drop |
| Source protection | Suitable DC-rated fuse+holder or other qualified protective architecture | **Not chosen**; cannot infer trip from nominal fuse rating or assumed current limit |

Manufacturer and reference material:
- TE: https://www.te.com/en/product-2-2176403-8.html
- Ohmite: https://www.ohmite.com/catalog/90-series/95J13RE/
- Vishay WSK2512: https://www.digikey.com/en/products/detail/vishay-dale/WSK2512R0100FEA/12142494
- Siglent SPD3303X: https://www.siglent.com/na/products-overview/spd3303x-x-e/
- SDM3055 accuracy: https://siglent.oss-cn-shenzhen.aliyuncs.com/English_content/Document/Digital%20Multimeters/SDM3055_datasheet_e04a.pdf
- TI INA228 manufacturer: https://www.ti.com/product/INA228
- SCHURTER fuse selection: https://www.schurter.com/en/knowledge/fuse-link

## G1 — Ready-to-execute independent bench evidence protocol (NOT performed)

Only **after** a competent hardware operator confirms G0 electrical/thermal/protection requirements, select the physical instruments and log the following original records, held separately from synthetic fixtures:

1. **Identity and safety:** exact drawing revision/hashes, operator and reviewer identities, instrument model+serial, ambient/grounding/earth/isolation checks, selected load and source/fuse MPNs, DC wiring and polarity, thermal mounting sign-off, host interface isolation, PSU OCP/OVP settings, and physical emergency disconnect. Do not connect to mains inside the fixture; any bench PSU mains input remains in its certified enclosure.
2. **Station verification without relying on software:** unenergized inspections; source output/overvoltage/current-limit assessment by qualified operator and manufacturer procedure; verified protection scheme including fault current and clearing time. **No deliberate short circuit or destructive testing is authorized by this document.**
3. **Measurement boundary:** INA228 VBUS across J2 load, primary current through its own shunt; independent DMM/logger across *separate* 10 mΩ Kelvin reference and independently measured J2 voltage. Reference instruments must tolerate high-side common-mode without shorting through grounded test leads.
4. **Temporal evidence:** independent UTC timebase/offset procedure or a verified shared trigger; original raw INA228 register capture, original independent reference voltage and shunt-drop traces, intersample coverage, instrument configuration and calibration, no derived-only CSV substituted for original source.
5. **Cadence/negative controls:** preregister steady load plateaus, blinded injected low-risk test changes under operator-approved conditions, zero/known-load cases, missing records, timestamp shifts and source-byte alterations. Do not drive physical faults until safe G0 hardware protection and test procedures exist.
6. **Custody and reproduction:** raw evidence preserved byte-for-byte; independent source/retention receipt and external digest pin or signature; separate second-person review; explicit statements about uncontrolled thermal drift, cabling, fixture power versus whole-system power and any missing measurement.

**G1 exit:** only source-identified real records plus independent reference trace and signed/verified custody, *not a successful synthetic fixture import*.

## G2 — Physical agreement and the present <1% measurement problem

The 10 mΩ reference at the **modeled 13 Ω ±1% low-current corner** produces approximately **3.58 mV**, below 5 mV originally assumed near 0.5 A. The SDM3055 datasheet's 1-year, 23±5°C, 200 mV DCV model is **±(0.015% of reading + 0.004% of range)**. At that 3.58 mV signal this is about **8.5 µV**, or **0.24% of the signal**, before instrument calibration conditions, noise, thermal EMF, range choice, instrument timing and source measurement geometry.

The independently uncharacterized Vishay 10 mΩ shunt is nominally **±1%**, so even a simple pessimistic combination of the nominal resistor tolerance and DMM specification already exceeds **1.2%**. That is not a complete uncertainty budget or a confidence interval. Thus the **0.75%** diagnostic threshold in the existing fixture screen cannot be a physical acceptance criterion. The code reports that threshold as synthetic sensitivity only.

**G2 exit** requires measured/reference shunt resistance with calibration chain, temperature/offset/drift, verified voltage/current pairing and covariance or dependence, independently bounded timing, and a preregistered **physical** tolerance at the smallest expected shunt signal. Pairwise agreement alone cannot prove absolute truth if both channels share systematic error.

## G3 — Existing Policy Lab integration (software readiness only)

The existing native `verify_and_replay.py` emits 183 fake INA228 samples through an unchanged Policy Lab PLRS-6 intake. HS's improved `measurement_screen.py` has independent raw-register-to-CSV coherence checks added in #365. The unchanged receiver can produce an integrity-bound **TEST_FIXTURE** structural intake; that status is the correct software result, not physical measurement assurance.

A separate source replay reviewer adds two explicit checks to this demonstration: recompute the G2 discrepancy result from the actual saved INA228 register/CSV/reference fixture, then re-run Policy Lab's **unchanged** PLRS-6 capture converter into a new temporary directory and compare its entire receipt against the saved source. The canonical PLRS-6 receipt reports verified hash **counts** (two normalized streams and six supporting files in this fixed case), not Booleans. This source replay was executed on the Optiplex: both replays PASS, 183 fixture pairs, evidence root `8207a99b8696bad5640764fc1d33333fa8f5fe0c375174776d5bece7b2bb3f38`. Changing a reference source value with the earlier screen receipt preserved is explicitly rejected as a stale G2 decision.

Reproduce using an existing, authorized Policy Lab `feature/measurement-investigation-20261120` checkout and the **original** fresh witness replay directory:

```bash
python3 projects/witness-g0-g4/review_g3.py \
  --native-replay /PATH/TO/ORIGINAL/HS_NATIVE_REPLAY \
  --screen /PATH/TO/ORIGINAL/screen.json \
  --pl-root /PATH/TO/POLICY_LAB_BRANCH \
  --expect-evidence-root 8207a99b8696bad5640764fc1d33333fa8f5fe0c375174776d5bece7b2bb3f38
```

The pinned root here is an independently supplied **expected digest of this software fixture**, not an independently authenticated sensor record. The tool explicitly reports `source_authenticity: NOT_ESTABLISHED` even after a full internal replay. This is not vendor attestation or independent operator custody.

**G3 exit** for a real case requires G1/G2 provenance, material measurement uncertainty and policy-specific admission; an L0/fake fixture must remain fixture-only regardless of reproduced hashes or how many internal tests pass.

## G4 — Economic value and claim authorization (NOT started)

Separate (a) actual kWh/Joules at precisely defined load/system boundary; (b) useful independently accepted output; (c) purchased energy tariffs including contracted demand/capacity; (d) authenticated revenue or legally enforceable claims. Hardware test-power data cannot justify token issuance, reserve backing or economic value. Without invoices/output verification, report **UNKNOWN**, not zero or a synthetic profit.

## Reproduce digitally (no instruments)

Run at repository root:

```bash
python3 -m unittest discover -s projects/witness-g0-g4 -p 'test_*.py' -v
python3 projects/witness-g0-g4/assessment.py --out /tmp/witness-g0-g4-new.json
python3 projects/witness-g0-g4/assessment.py --verify /tmp/witness-g0-g4-new.json
python3 -m unittest discover -s hardware/reference_designs/low_voltage_witness_fixture_v0 -p 'test_*.py' -q
```

The assessment uses only Python stdlib, fails if original station bytes change, and **always** returns `build_authorized=false`, `power_on_authorized=false`, and `policy_lab_financial_claim_authorized=false`. An operator-supplied claim like `fabricated=true` is rejected rather than accepted as assurance.

For fresh native KiCad/ngspice/sensor-fixture/PLRS-6 replay, use existing HS `verify_and_replay.py` with an existing Policy Lab checkout containing `scripts/equipment/dc_bench_capture.mjs`. It does not touch real equipment.

**Evidence limit:** the pinned station SHA and generated output hashes show internally consistent *local* provenance, not that a claimed source is authentic. Independent source custody is a separate external requirement.

## Handoff / unresolved items

**Decision already established digitally:** propose 13 Ω nominal, 1% tolerance, 5 W as next external-load study.

**Not assigned:** purchaser, lab operator, independent metrologist, authorized second reviewer, utility or institutional data-holder. No part order, expense or hardware action was requested or executed.

**Physical build HOLD remains until:** selected and qualified load, approved mount, actual PSU plus overvoltage/overcurrent and fault protection, DC fuse strategy, reference instrument with second channel/timebase, complete BOM/PCB revision, and authorized review. We do not turn this research note into a fabrication file.

**Next original research question:** after real independently measured steady-load performance, can Policy Lab distinguish small known load changes from reference uncertainty? Only then extend the measurement framework toward AI-device energy and financial economics.
