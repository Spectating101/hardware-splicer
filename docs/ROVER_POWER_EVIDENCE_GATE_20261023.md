# Rover motor-power evidence gate — outcome experiment (2026-10-23)

**Branch:** `fix/rover-power-evidence-gate-20261023` (draft, stacked on the rover output repair #199). This is not a complete battery-power design or physical authorization.

## Why this is necessary

The actual example `examples/intakes/splice_robot_drive_brief.json` declares:
- two nominal **6 V** recovered geared DC motors;
- **0.9 A stall current** for each motor (declaration, not a verified observation);
- battery nominal **7.4 V** and **2200 mAh capacity** (neither specifies chemistry, actual loaded voltage nor max discharge current);
- a donor-board motor control path, but no independently verified power connections.

The preceding PR #199 fixed **2 source motors → 2 build-graph motor instances → 2 BOM units**, and removed the catalog recipe's invented 12 V barrel/USB/buck supplies. The generated rover remained blocked because power had not been established.

This change turns that open issue into a **machine-readable, user-visible evidence assessment**, explicitly separate from the existing bench session's authorization checks.

## Actual same-input outcome

| Metric | Before this change (#199) | This change |
|---|---|---|
| Two motor units in compiled graph/BOM | Yes | Yes |
| Physically justified source rails | No | No |
| Electrical build-ready | False | False |
| Power-on authorized | False | False (explicit report gate) |
| Named power requirements in canonical package | Generic compile and bench blockers | **7 structured blockers with next-action evidence tasks** |
| User-visible dedicated power assessment in Verify and Bench | No | **Yes** |
| Physical measurements | None | **None — explicitly null** |
| Combined two-motor stall-current figure | User-supplied individual figures, not consolidated on the project package | **1.8 A**, arithmetic of two *declared* 0.9 A figures (not a measured battery or driver current) |
| Battery capacity converted into discharge capability | Not established | **Explicitly rejected** |
| Unrelated sensor-logger project | Valid control | Unchanged, report status `not_applicable` |

Representative report path: `PROJECT_PACKAGE.json.rover_power_evidence`, also rendered in `PROJECT_PAGE.md` and in the **Verify** and **Bench** stages of Splice UI.

### Manufacturer constraint (not a test result for this rover)

STMicroelectronics' **L298 datasheet DS0218 Rev 5 (Oct 2023)**:
- Operating logic supply **4.5–7 V**, nominal 5 V;
- two independently controlled enable inputs, separate motor/logic supply stages;
- at the **specified datasheet test conditions** (VS = 42 V, VSS = 5 V, Tj = 25 °C), total bridge saturation drop at IL = 1 A **1.8–3.2 V**.

Official document: https://www.st.com/resource/en/datasheet/l298.pdf (pp. 4–5, tables 3–4).

These conditional silicon-level values are **not a prediction** for the actual module at 0.9 A, its heatsink, board layout, or battery voltage. In particular, there is no justified conversion `7.4 V battery → 6 V motor`; nominal pack voltage and motor-rated voltage are different facts, and no terminal voltage has been measured. Driver output loss can be significant and needs proper characterization.

Texas Instruments' DRV8833 is an **external design alternative to research**, not an automatically approved substitution. It has a 2.7–10.8 V motor-supply range and dual H-bridges, with current capabilities depending on package and thermal conditions; direct drive from 7.4 V to 6 V-rated motors still requires an actual verified motor-rail strategy. Reference: https://www.ti.com/product/DRV8833 .

## Required observations, not assumptions

Before a reviewer considers releasing the design, gather:
1. Source identity and chemistry, measured supply voltage range under relevant loading, terminal polarity, connector/fuse limits, and reliable discharge-current rating (mAh alone is insufficient).
2. Motor identity and rated/peak/stall characteristics. The current 0.9 A numbers are user declarations; measure or obtain authoritative model-specific data with controlled setup.
3. Driver-board identity, L298N voltage-drop under load, thermal margin, verified ENA/ENB state, logic VSS, grounds, sensing and actual ESP32 signal compatibility.
4. A verified controller supply/regulator and loaded motor voltage envelope that does not exceed the motor's warranted operating range.
5. Existing **physical** bench-session sign-off and instrument provenance, timestamps and recorded independent evidence.

No code here invents rail voltages, regulator models, motor output measurements, battery pack chemistry, or a certified safe operating point. The existing bench session remains unchanged; the current project-package power authorization is reduced to false until a future independent review can satisfy the new gate. This draft does **not** provide an automated evidence-based clearing path and must not be represented as a completed power-subsystem validator.

## Verification run (isolated, no hardware)

- The original donor rover was rerun through `splice_and_build_from_intake` and emitted 2 motor nodes, 2 motor BOM units, 7 named power blockers, declared stall sum 1.8 A, no measured rails, package power-on false.
- A real sensor-logger control remains successful and `rover_power_evidence.status = not_applicable`.
- Negative controls: missing stall current, explicit quantity of two, 2200 mAh incorrectly treated as current, fake `power_on_authorized=true` in a package, missing measurements. All are properly non-authorizing.
- **81 Python focused/parity tests passed**, including TypeScript-backed translation checks at the previous code point; **94 frontend tests passed**, production Vite build passed. The final snapshot requires normal GitHub CI before merge.
- This is a gain in **engineering decision specificity and safety-gate coverage**, not proof of physical performance, end-to-end completion, cost savings or superiority over other hardware tools.

## Next true-positive milestone

To progress beyond a permanently blocked review, introduce a strictly validated physical-evidence record format and independent sign-off into the existing bench gate system, with traceability to actual driver/motor/source hardware. Only then should the package be eligible for conditional power-on review. Repeat across more than one real low-voltage build and benchmark operator effort and false-ready rates before making market-quality claims.
