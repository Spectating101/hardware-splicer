# Four documented hardware restorations — source facts, workflow and original HS mistakes

**Research date:** November 3, 2026. **Engine baseline:** [CI run 41635416606](https://github.com/Spectating101/hardware-splicer/actions/runs/41635416606), source-linked original Circuit-AI repair evaluator, 8 pre-solution checkpoints, all independent replay acceptance checks green.

This is **not** video transcription or independent bench validation. The Nintendo Switch evidence is from YouTube's public title and nine *chapter-description timestamps* only, not inspected video frames. The three iFixit cases have owner-reported interventions and updates, not independent DMM/oscilloscope readings. Source narratives below are newly written paraphrases, not copied scripts.

## 1 — Game Boy DMG-01, January 2026 (real, partially repaired)

Original case: https://www.ifixit.com/Answers/View/937739/Why+will+my+Game+Boy+not+turn+on

- **Initial condition (Jan 25):** Stored original Nintendo Game Boy had worked when rediscovered, then stopped turning on after more time in storage. No meter readings in post.
- **Inspection advice (Jan 26):** Check batteries, orientation, external battery terminals, corrosion; power-board inspection follows only if first checks fail. These are proposed tests, not proof.
- **Source observation / action (Jan 27):** Owner found corroded battery-contact pins, gently cleaned with small amount of vinegar, and installed checked fresh batteries. Batteries and cleaning changed together; isolation of each separate contribution was not demonstrated.
- **Reported positive outcome:** Device booted after intervention.
- **Remaining failure:** Owner also reported **missing vertical LCD pixel lines**. Repairer recommended a display connection/line repair; no later source report establishes the screen was fixed.
- **Physical diagnosis:** Contact corrosion plausibly raises resistance/interrupts low-voltage alkaline AA power delivery. This inference is consistent with observed corrosion and restored boot, but not electrically measured. LCD column lines are a **second unresolved fault**, not part of full functional recovery.

**What HS must do:** Identify a retro handheld powered by replaceable AA batteries, NOT suggest testing rechargeable battery packs or charger docking stations. Separate existing batteries, terminal continuity, and power switch checks; after a successful boot, inspect screen/audio/buttons and retain partial-restoration status if LCD still damaged.

**Original engine output:** Category retro_handheld_console (correct); guide families initially laptop_power_path, subsequently battery_charging_gadget (both inappropriate); top battery_charge_path_fault; prompts include board fuse, charger output, battery pack voltage. Workflow flag solvable_now is **only software assessment**.

## 2 — MacBook A1534 (Feb 2023), owner confirms port was the problem

Original case: https://www.ifixit.com/Answers/View/769879/MacBook+not+turning+on

- **Initial symptoms (Feb 18):** 12-inch Retina MacBook 2015 failed to start after overnight charging; remained cold. Owner suspected battery or USB-C port.
- **Actual discriminating clues:** Owner tried two chargers that could power other devices, but not this MacBook; indicator on one USB-C lead flickered with MacBook unlike stable illumination on another device. These reports suggest inconsistent power/negotiation **but are not measured voltages**.
- **Repairer's competing causes:** USB-C jack/port is plausible; cable, battery and board path not eliminated until further checks. Avoid board-level conclusions from cable LED alone.
- **Action evidence:** Owner said a replacement port and battery had been ordered. The thread does not unambiguously identify which components were installed or exact rework details.
- **Reported outcome (Feb 23):** Owner said defective charging port was the problem and MacBook was fixed.
- **Missing independently measurable proof:** USB-C PD/current log, actual repaired port part identifier, battery cycle health, stable boot/thermal run, storage-owner privacy record.

**What HS must do:** Route to laptop_usb_c_power_path, prioritize known-good adapters and inspect jack/connector, then battery isolation and board rail measurements only under appropriate instructions. Keep the repair method unconfirmed despite owner's report of a fixed laptop.

**Original engine output:** Item class small_usb_gadget (wrong), repair family laptop_power_path (reasonable), generic battery_charge_path_fault ranked above specific laptop power fault; assistive_only. A note about seeing a flickering LED should not be treated as a DMM result.

## 3 — iPhone 6s, 2018: replacement flex can be worse than original

Original case: https://www.ifixit.com/Answers/View/517971/Phone+not+charging+after+charging+port+replacement

- **Before intervention (Sep 24):** Original Lightning port worked intermittently if cable was physically held at a particular angle.
- **Intervention:** Owner replaced charging-port assembly.
- **Regression:** Phone no longer charged; battery ran flat, briefly rebooted when charger attached, then shut down. Other functions including screen/microphone/speaker/headphone reportedly worked.
- **Advice:** Expert recommended testing the known partly working original flex again, with battery isolated before reconnection. That is an A/B control for replacement part or installation quality—not definitive proof of failure without electrical measurements.
- **Observed A/B result:** Original port restored **partial** charging when plug was pressed. This is strong evidence that the replacement part or its connection may be defective. It does NOT show original port is now good.
- **Unresolved outcome:** Repairer suspected bad new flex and recommended a reliable replacement. Owner did not later document a fully repaired final phone. Do NOT mark repaired or claim board-level Tristar/charge-controller failure.
- **Missing proof:** Known-good compatible replacement test, charge-current comparison and battery health.

**What HS must do:** Identify *phone charging flex/connector*, compare original/new assembly and connection; preserve the possibility of other charging faults; stop dangerous lithium-battery handling. Do not redirect after the A/B evidence to motor-load or generic relay-driver tests.

**Original engine output:** Generic battery charging at stage 1, then **small_dc_motor_gadget and driver_stage_or_load_fault** at stage 2 (incorrect). Owner's final product remains unrepaired in the accessible case.

## 4 — Nintendo Switch OLED video: two symptoms, multi-component USB-C/HDMI repair

Original video (sthetix, June 5, 2024): https://www.youtube.com/watch?v=Rqw6-qVKbPs

Only **public YouTube video description and chapter markers** were inspected by this study. Details *inside* the chapters (voltages, exactly which chips failed, final HDMI output, microscope visual condition) are **unknown**.

| Video chapter | Source-described activity | Engineering purpose; not a claim of measured success |
| --- | --- | --- |
| 00:29 | Console inspection | Document connector/board condition before guessing cause |
| 03:34 | USB Type-C breakout board | Breakout facilitates pin/connectivity measurements; values not disclosed |
| 05:36 | XZZ schematics | Trace connector, signal, filter and power paths; schematic itself not fetched or analyzed |
| 08:14 | Remove USB port | Rework documented in chapter text; original damaged pins not independently identified |
| 10:19 | Solder replacement port | Restores candidate hardware interface; joint quality not externally certified |
| 12:32 | Replace noise filter | Addresses an additional signal-path component; precise failure diagnosis not text-verified |
| 13:44 | Repeat USB connectivity test | Before/after validation *performed*; actual results not in accessible metadata |
| 14:33 | Solder USB-port anchors | Mechanical reinforcement step |
| 15:30 | Test charging function | Test chapter occurs; resulting current and HDMI success not independently known |

**What HS must do:** Identify a *modern console*, not retro or relay box. Preserve **two functional outputs** (charging and docked HDMI), and ask for USB-C breakout results, connector mechanical condition, verified model schematic/pinout, filter continuity, USB PD/current, and post-repair charging AND HDMI tests. Treat hot-air rework and lithium battery as trained-bench-only, never DIY auto-authorized.

**Original engine output:** Category retro_handheld_console, family relay_power_box, top driver_stage_or_load_fault. Twice labels generic workflow solvable_now with no board evidence. This is a substantial routing and confidence issue.

## Benchmark method and what is actually measured

The machine-readable original source timeline is in examples/public_restoration_replays/cases_2026_11_03.json. Each case has 2 **blinded, chronological** inputs (8 total) with symptoms and the evidence known at that time. Predictions are made using the *actual* RepairCaseEvaluator, RepairEncyclopedia, BoardSessionStore and repair video playbook implementation from apps/circuit-ai. Source future intervention, source outcome and target diagnosis are **not** supplied to the prediction request. After prediction, source gold is opened and reported separately.

| Evaluation dimension | Currently tested? | Interpretation |
| --- | --- | --- |
| Source integrity, original URLs and chronology | Yes | Machine-verified source schema and consistent references |
| Model routing, fault candidate, generated diagnostic task | Yes | Real engine output, not manually authored expected answer |
| Source-gold leakage via evaluation input | Yes | Exact pre-outcome input independently recomputed and compared |
| Root-cause measured at physical board | **No** | Public owner anecdotes are not a DMM measurement |
| Video scene-by-scene visual diagnosis or transcript | **No** | Only description and chapter timestamps accessed |
| Complete physical restoration done by HS | **No** | HS has not handled any product |
| Actual time saved, component cost, resale profit | **No** | No underlying real receipts |

The baseline exposes a clear problem: **high software workflow scores can coexist with wrong hardware-family routing**. This is a diagnostic-quality regression suite, not proof the repair engine can already repair every device. The follow-up should improve routing and relevant source-specific diagnostics while retaining the original baseline as immutable evidence. A separate novel holdout set is needed before claiming generalized accuracy.
