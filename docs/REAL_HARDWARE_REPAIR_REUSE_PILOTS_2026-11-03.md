# Hardware Splicer — repair, recovery and remanufacturing physical product pilots

**Date:** 2026-11-03. **Scope:** Source-backed feasibility research and gated field trials; no physical hardware was acquired, measured, repaired, flown, or sold in this work.

## Design rule: reuse what HS already built

There is already a repair lane and case evaluator in \`apps/circuit-ai/src/intelligence/\`, donor/salvage planning in the engineering device paths, and existing donor circuit fixtures under \`examples/fixtures/\`. We should **not** build a parallel repair site or new drone autopilot. We should make those existing paths produce inspectable evidence for a **complete functioning physical product**, not just a board scan, a BOM, or attractive rendered components.

At this source revision, \`apps/circuit-ai/eval/real_repair_cases/README.md\` lists **7 reference-based evaluation cases** (4 software "solvable_now", 3 "assistive_only", average workflow score ~0.725). These are software test cases sourced from repair documentation, **not seven physically repaired devices**. In \`apps/circuit-ai/data/repair_value_trials/trials.json\`, some recorded test-trial examples describe repaired outcomes and recovered value, but they are **evaluation fixtures, not independently observed field economics**. An external human operator must provide hardware measurements and outcome receipts before any commercial performance claim.

The machine-readable candidate and evidence-gate ledger is \`examples/real_hardware_recovery/pilots_2026_11.json\`. Run \`python -m scripts.evaluate_real_hardware_recovery_pilots_001 --output /tmp/hs_recovery_pilots.json\` from the repository root. The evaluator reads the existing HS case library and verifies its reused paths, enforces source-link and safety boundaries, and **blocks actual hardware success claims until original field evidence is submitted**.

## Real product ordering

| Order | Product to show | Why now | Existing HS reuse | Boundary for a defensible result |
| --- | --- | --- | --- | --- |
| 1 | **Working repaired 5V USB fan** | Cheapest-lowest-risk practical proof of intake → continuity and current-limited diagnosis → actual functional repair | \`small_motor_usb\` lane + \`usb_fan_no_spin\` case | Before/after fault and power measurements, video showing repaired motor at load, operator signoff |
| 2 | **Restored Lenovo ThinkPad T480** (or model-verified similarly serviceable laptop) | The result can be tested objectively: boot, storage SMART, runtime and thermal stress | \`laptop_no_power\` reference and existing repair sessions | Model/FRU compatibility, battery isolation, data consent, post-repair boot and thermal receipts |
| 3 | **Pixel 9 phone fault** | High perceived value but sealed battery, fragile screen, adhesive and regional service-parts complications | Existing generic repair intake/evaluator, not yet a model-specific phone lane | Approved repair manual, source parts, no unsafe battery, post-repair function matrix and privacy safeguards |
| 4 | **Retired Framework mainboard reused as a mini-PC** | A genuinely different finished product using published CAD, service manuals and board reuse paths | Device design and salvage/reuse components, existing product engine | Correct mainboard revision, power input, grounding, cooling, enclosure clearance, OS runtime test |
| 5 | **Printer carriage reused as a camera slider** | Compelling multi-discipline salvage showcase: motor, mechanics, enclosure, firmware, power | \`splice_donor_inkjet_motion_board.json\` | Actual motor/driver ratings, endstops, current-limited rail, emergency stop, bounded real motion demonstration |
| 6 | **Damaged drone converted into an unpowered/propeller-free bench flight-controller rig** | Demonstrates actual sensor/controller/ESC/motor integration without unverified airborne claims | Existing \`drone_fc_power.kicad_pcb\`, donor parts and cross-stack integration | Verified motor/ESC compatibility, known-good battery, SITL failsafe and propeller-free bench results; **not flight authorization** |

Priorities here rank **demonstrability and evidence quality**, not market demand or realized profit. They are a proposed experiment portfolio, not verified inventory or product sales.

## Upstream systems to integrate directly

- **Service repair:** [iFixit T480 device/repair guide library](https://www.ifixit.com/Device/Lenovo_ThinkPad_T480), [Microsoft Surface official service guides](https://learn.microsoft.com/en-us/surface/service-guides), [Google Pixel official self-repair/manual information](https://support.google.com/pixelphone/answer/14257407), and [Apple Self Service Repair](https://support.apple.com/self-service-repair) for supported models and parts. Documentation and real parts availability must be checked **for each precise model and location**, not guessed from the brand.
- **Repairable and reusable equipment:** [Framework original mainboard case and interface CAD](https://github.com/FrameworkComputer/Framework-Laptop-16) and [manufacturer's module reuse approach](https://frame.work/sustainability/). Reuse documented cases instead of designing a new mainboard.
- **Donor-board / motion salvage:** existing HS donor PCB, connector/pinout and motor-driver salvage paths. Unknown donor motor voltage/current and unknown cable polarity remain physically blocked until measured.
- **Drone:** [ArduPilot physical component requirements](https://docs.ardupilot.org/copter/docs/what-you-need.html), [ArduPilot SITL](https://docs.ardupilot.org/copter/docs/common-simulation.html), [PX4 multicopter configuration](https://docs.px4.io/main/en/config_mc/), and [Betaflight propeller-free motor and failsafe checks](https://betaflight.com/docs/wiki/getting-started/setup-guide). Avoid duplicating autopilot algorithms. Verify that any recovered motor, ESC and firmware protocols are compatible; never treat a junk battery or a scraped battery cell as automatically reusable.
- **Taiwan flight:** [Taiwan CAA drone registration](https://www.caa.gov.tw/Article.aspx?a=3820&lang=1) includes individual aircraft of maximum takeoff weight 250g or more, and school/company-owned UAVs. See official rules for DIY registration, flying zones, pilot requirements and operational restrictions; a ground-bench pass is **not** permission to fly outdoors.
- **Data protection / batteries:** [NIST SP 800-88 Rev. 2 media sanitization program](https://csrc.nist.gov/pubs/sp/800/88/r2/final) and [iFixit battery/device safety](https://www.ifixit.com/Info/Device_Safety). No disassembly of compromised cells, no unconsented customer files, no uncontrolled mains repairs.

## Mandatory HS physical product evidence

For each real acquired device, attach **operator-provided and hashed actual evidence** for:
1. Device identity with serial/IMEI redacted, ownership/repair consent, precise defect.
2. Model-specific procedure, device ratings, required tools and compatible parts, safe isolation and a STOP list.
3. Actual fault measurements before intervention, and any sourced salvage-board pinout and voltage/current match.
4. Actual intervention, photos, measured outputs, full-product functional acceptance and independent human review.
5. Measured time, parts, acquisition price, realized sale or recovered-use value, and after-sale returns if commercialized.

No simulation, web guide, generator output, "software case solved" status, stock photo or synthetic field-test record can satisfy a physical measurement or independently proven profit. Product economics are still unknown. A defensible *unit economics* ledger is:

\`realized_sale_or_avoided_replacement_value - acquisition_cost - replacement_parts - labor_time*labor_rate - energy_and_tools - warranty_return_reserve\`

Do not claim passive revenue or positive margins without actual field receipts. The catalog deliberately leaves all measured cost and resale fields null. The evaluator never enables power, drone flight, or sale: those require human safety and legal authority outside the software output.

## Pilot execution instructions

First **source one owned, simple 5V USB fan** and obtain photo/connector and voltage/current observations; use the existing repair session, not a recreated UI. Next pilot a serviceable laptop (T480 is a documented example, not a requirement). For junk-to-new-product validation, use a printer rail/camera slider before an airborne drone: it proves full mechanics, current-limited actuation and firmware in a far more measurable environment. Drone work begins with SITL and propeller-free bench only.

When a pilot actually produces working hardware, attach the test evidence and review its power/flight and privacy requirements manually. Only then promote the candidate to a claim of actual completed work.
