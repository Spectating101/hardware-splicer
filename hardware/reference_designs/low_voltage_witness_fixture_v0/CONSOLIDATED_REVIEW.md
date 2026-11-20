# HS × Policy Lab 5 V witness — consolidated engineering review

**20 November 2026 | SOFTWARE INTEGRATION VERIFIED / PHYSICAL RELEASE HOLD**

Canonical navigation and reviewer handoff for one **consolidated witness draft**. Historical source artifacts and measurements are software-only. No previously published source or evidence is silently rewritten.

## Current truth

The prototype has an editable routed KiCad9 PCB, zero-violation electrical checks, a nominal 10Ω SPICE model, 183-sample INA228 fake-register replay, unchanged Policy Lab PLRS-6 structural receipt, a strict software fault-discrimination layer, 12Ω externally mounted load candidates, source/fuse research, two-meter read-only SCPI mock, and a physical-evidence preflight.

**No board has been fabricated, no hardware has been energized, and no independent physical energy measurement or calibration has occurred.** No prototype is released for production.

| Gate | Software-established | Still physically unverified |
|---|---|---|
| G0 | KiCad ERC/DRC, net-to-pad parity, SPICE modeled loads | Real resistor/chassis thermal derating; enforced 5.25V J2 ceiling; selected source/fuse/earth |
| G1 | Raw data/receipt hashes, two-claimed-meter query brackets and CSV cross-binding | Built device, calibrated actual instruments, genuine independent acquisition, verified external timebase and operator |
| G2 | Artificial +1%/+5%/+10% reference bias, time shifts, dropouts and raw tampering detected | Calibrated measurement accuracy, justified sub-1% tolerance and real blind tests |
| G3 | Evaluation design | Measured time, cost, accuracy or market advantage |

**BUILD_HOLD.md remains the physical release authority.** Passing software checks does not permit Gerber fabrication, parts purchase, source connection, power-on, physical claims or token issuance.

## Material design decisions and caveats

The original 10Ω load can exceed the 2.5W declared maximum under some 5.25V corners. The initial 12Ω ±5% thought experiment was incomplete because it neglected resistor TCR. The later sourced review found:

- YAGEO SQP10AJB-12R, 12Ω ±5%, conservative 300ppm/°C: modeled worst-normal-load upper bound **2.516W** over the full component temperature-range resistance assumptions — *fails the 2.5W bound*.
- Vishay RE65G12R0C02, 12Ω ±1%/20ppm/°C: analogous **2.331W** bound — *passes resistance/power math only*, with mounting, ambient derating, actual delivered resistance and chassis unqualified.
- Neither candidate is selected for the original 10Ω KiCad/SPICE/BOM or physically bought.

Rigol DP832A CH1 is a **borrowing candidate** with vendor-documented adjustable OVP/OCP; Siglent SPD3303X-E is not sufficient alone for the strict J2 maximum because the manufacturer says it lacks user-configurable OVP. Neither has been tested. An OVP menu is not proof of peak J2 voltage below 5.25V. The SCHURTER 0031.3551 holder is not a DC fuse link; 1A nominal fuse clearing at sustained 0.65A source limit is NOT assured.

At a modeled 12Ω operating point, the 10mΩ reference signal is about 4.14mV. The uncharacterized 1%-tolerance primary and reference shunts plus illustrative DMM range specs yield an **incomplete ~2.24% worst-direction additive allowance**, before ADC, thermal and timing effects. This is not an estimate of actual error and cannot justify the fixture screen's 0.75% threshold as physical acceptance.

## One full software review command

From this directory, with Python's pcbnew, KiCad9, ngspice, node and a clean Policy Lab PR #180 checkout at commit 9f06f669e9252d2ff105581c2aaa6750d007dcd9:

    /usr/bin/python3 review_witness.py \
      --pl-root /absolute/path/to/solarpunk-coin \
      --out /tmp/new-unique-witness-review

The review runs ALL focused tests, fresh KiCad/ERC/DRC/net parity, ngspice, native HS INA228 fake-register capture, unchanged PLRS-6 intake, prior seven-case fault matrix, separate 12Ω modeled replay, PSU/OVP/fuse source screen, and negative G1 packet/protection/dual-SCPI combined checks. The unit tests explicitly include a new G1 primary/reference cross-stream binding screen.

**Expected successful software review: exit code 2** and status SOFTWARE_INTEGRATION_VERIFIED_PHYSICAL_HOLD, with physical_ready=false and fabrication_allowed=false. Exit code 1 is an incomplete/broken software integration, NOT a partial pass.

Results are written to a new directory outside the repo as review.json plus per-stage evidence folders, SHA-256 source hashes, exact HS and PL commits, and no overwriting.

The full review refuses changed PL commits, uncommitted checkouts and missing native dependencies. Review every stage, not just the terminal headline. The Policy Lab receiving code is NEVER modified.

## New source-binding correction

Previously the G1 evidence checker and SCPI receiver checked their own input integrity but did not bind the **G1 reference export** back to the reference session or compare source-stream sample timing. The consolidated G1 checker now also requires:
- matching G1 reference-export SHA and the SCPI receipt's recorded reference CSV hash;
- claimed reference serial present in the SCPI ID response;
- at least 183 primary/reference samples, matching sample count and 3-minute coverage;
- monotonically increasing UTC timestamps, 0.5–1.5s sample gaps, and host timestamp offset within the claimed budget, capped at 200ms;
- the packet's declared time window covering both original streams.

This is a **structural** cross-stream check. SHA and SCPI identity strings can be forged; two instruments can share an erroneous clock; host query timestamps do not prove ADC aperture or physical independence. Human custody, calibration, grounding and external timebase validation remain mandatory.

## Canonical files and responsibilities

| Function | Primary source | Physical status |
|---|---|---|
| Electrical design | generate_schematic.py, generate_pcb.py, verify_and_replay.py | No build |
| Original verification | audit_readiness.py, measurement_screen.py | Software-only |
| 12Ω model | bench_candidate_replay.py, load-candidate-matrix-v1.json | Not selected |
| Supplier/protection | source_suitability.py, protection_preflight.py | Candidate leads only |
| Reference acquisition | reference_scpi_bracket.py | Mock or read-only unverified instrumentation |
| G1 packet review | g1_evidence_gate.py, g1_commissioning_gate.py | No physical approval |
| Unified reproducibility | **review_witness.py** | Full software review |
| Release authority | **BUILD_HOLD.md** plus independent qualified engineer | HOLD |

## Audit history retained, not competing final contracts

The original dated dossiers are retained so an independent reviewer can see the evolution and corrections:
- INDEPENDENT_READINESS_AUDIT_20261120.md — initial 10Ω/5.25V contradiction, shunt tolerance and fuse gap.
- WITNESS_G0_G2_DISCRIMINATION.md — first 12Ω ±5% arithmetic and stricter bias test; later TCR correction supersedes its room-temperature-only implication.
- G0_PART_SCREEN_AND_G1_EVIDENCE_20261120.md — named candidates and G1 structured receipt.
- G1_INDEPENDENT_BENCH_COMMISSIONING_20261120.md — dual-meter acquisition and source/fuse/earth operator requirements.
- G1_SOURCE_SELECTION_AND_INSTRUMENT_BORROW_20261120.md — source candidate selection and two-path incomplete uncertainty.

**Branch boundary:** Six prior witness PRs #356, #358, #360, #364, #367, #368 are being consolidated into one review unit **above** upstream open foundational PRs #351 (measurement hardware/software) and #354 (feasibility). Their upstream integration branch is substantially ahead of main and must be reconciled separately. This consolidated draft is NOT main-ready or fabrication-ready. The source history and existing test evidence remain available in Git.

## Next independent physical action

Find an authorized lab that can lend an OVP/OCP-capable isolated source, separately calibrated 4–5mV Kelvin and ~5V load-bus reference channels, and suitable timing/fault instrumentation; appoint a qualified operator and independent reviewer. Record original device exports, serials/certificates, DC fuse/source coordination, actual load mounting, thermal and source trip waveforms. No participant has agreed or schedule exists. The G1 packet must be filled only from real evidence after the independent engineering review.

**Until that happens, HOLD all purchases, fabrication and energization.**
