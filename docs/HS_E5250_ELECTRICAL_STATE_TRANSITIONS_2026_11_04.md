# HS E5250 second move: measurement-aware electrical fault-state transitions

**November 4, 2026.** The first whole-product E5250 case exposed an important practical failure: generic text-only Circuit-AI kept guessing battery charging faults at T0–T2 despite a charger protection trip and a reported board short, then guessed a USB-C fault at T3–T4 after the main rail recovered and the repairer observed an RTC-dependent boot issue. A CI-green diagnostic workflow did not solve the product.

This PR changes the **existing Circuit-AI evaluator**, not a standalone second application. It adds one minimal typed evidence-state layer with explicit source provenance and state transitions. It records supporting source evidence IDs, contradictions of stale diagnoses, next required discriminating evidence, and a hard physical-work/part-purchase hold.

## Real product state flow (source-reported, not HS-measured)

| Stage | Input evidence | Electrical state / leading differential |
| --- | --- | --- |
| T0 | External adapter 19.9 V unloaded; LED shuts off when connected | Adapter/load protection trip; likely input loading, but adapter and board not yet independently separated |
| T1 | Source reports 2.3 A fault current with voltage collapsed nearly to zero; short persists after DC jack removal | Downstream board input short **reported**, DC jack alone contradicted |
| T2 | First hot current-sense resistor was a false localization; MLCC removal reportedly cleared short | MLCC input fault isolation **reported**; replacement specifications unknown |
| T3 | Main board rail later 19.9 V, ~40 mA idle, power button 3.3 V, yet no boot | **New** startup/EC/RTC state, not ongoing short or proven USB-C failure |
| T4 | Startup behavior changes when RTC/BIOS battery disconnected | RTC-dependent startup **reported**, mechanism and cell condition not independently verified |

Reference: [original dated Sorin Electronics technician article](https://sorinelectronics.co.uk/dell-laptop-not-charging/) and [original evidence dossier #273](https://github.com/Spectating101/hardware-splicer/pull/273).

## Integration and reproducibility

- `apps/circuit-ai/src/intelligence/repair_power_path_evidence.py`: strict typed records for source observations, numeric values with units and measurement conditions, source actor/provenance, event IDs and chronologically advancing power states. **A bench PSU setpoint is never treated as measured board voltage.**
- `apps/circuit-ai/src/intelligence/repair_case_evaluator.py`: accepts optional `evidence_events` and applies state-based leading hypotheses directly to the generated existing `RepairEncyclopedia` guide and existing `BoardSessionStore` case file. Inputs without typed records retain their old behavior.
- `scripts/run_hs_e5250_typed_evidence_progression.py`: first executes/reloads the original 5-stage failure trace, then runs actual Circuit-AI five times with cumulative **stage-available** typed source data. It publishes both original and new leading hypotheses, exact source events, contradictions, blockers, and full raw outputs.
- `scripts/verify_hs_e5250_typed_evidence_progression.py`: separate evidence/chronology/source attribution and product authority audit. The original #273 real-source case input and old failure trace remain frozen; source reports do not become laboratory-certified readings.
- CI reproduces the original failure, performs the new stateful actual-engine replay, verifies the real source and runs negative controls rejecting fabricated independent measurements, wrong units, duplicate or out-of-sequence observations, and false physical authority.

## Strict limits

These are **retrospectively hand-mapped developer-known source observations**. State labels are engineer-generated differential guidance, not calibrated probabilities, independently confirmed component-level faults, future unknown repairs, or proof HS electrically repaired a laptop. This is a product capability improvement; the same E5250 episode is **not** a new blind validation.

No hardware touched or tested by HS. No current injection, flammable heating solvent, energized RTC reconnection, unspecified MacBook donor MLCC substitution, flight or mains work is approved. Component rating and board revision unknown, so **parts procurement blocked**. Three of eight product acceptance gates were only source-reported; HS has independently confirmed zero.

## Next real-product engineering milestone

Apply this exact typed source-event interface to a **different, genuinely untouched professional repair**, especially one with a branch point where an apparently correct initial guess becomes inconsistent with a subsequent voltage measurement. Record the first run before tuning. The physical acceptance milestone remains an owner-consented qualified bench demonstration with captured instrument traces, verified replacement BOM, post-repair battery/thermal/ports/RTC validation and a signed product acceptance record.
