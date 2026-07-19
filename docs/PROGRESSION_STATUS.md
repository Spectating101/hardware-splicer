# Hardware-Splicer — Progression status

**Owner:** Cursor agent · Founder reviews checkpoints  
**Doctrine:** [`CONVERSION_DOCTRINE.md`](CONVERSION_DOCTRINE.md)

**Public repo:** https://github.com/Spectating101/hardware-splicer  
**Prerelease:** https://github.com/Spectating101/hardware-splicer/releases/tag/v1.1.0-alpha.16

## Mode — polish / prove function first

Outreach and design-partner sends are **paused** (founder decision 2026-07-18).  
Public A + prerelease stay as infrastructure only.

| Track | Status |
|-------|--------|
| Engine / agent verify | **PASS** (pipeline green ≠ salvage value) |
| UI Quick demo / splice_build | **Runs offline** — hang fixed |
| Practical non-golden intake | **Enabot-lite endgame PASS** (`make verify-vibe-enabot-endgame`) |
| Money-path depth (8 winners) | **8/8 PASS** (`make verify-money-paths`) |
| Mechatronics engine (elec+mech+fw) | **8/8 PASS** (`make verify-mechatronics-paths`) |
| Mechatronics confidence (FW≡graph) | **8/8 PASS** (`make audit-mechatronics-confidence`) |
| Pan-tilt mechatronics golden | **PASS** (`make verify-mechatronics-golden`) |
| Physical closed loop (software pack) | **READY** (`make verify-physical-closed-loop`) — human bench still open |
| Donor-keep + graph-true handoff | **SHIPPED** — gap_fill/goal_picker/workshop cannot replace donor drv; bring-up/wiring regen from build_graph |
| Design-partner invites | **PAUSED** until `PHYSICAL_BENCH_EVIDENCE.json` is operator-closed |

**Assessment:** [`FUNCTIONAL_ASSESSMENT_2026-07-18.md`](FUNCTIONAL_ASSESSMENT_2026-07-18.md) (includes value audit)  
**Spec:** [`superpowers/specs/2026-07-18-mechatronics-engine-design.md`](superpowers/specs/2026-07-18-mechatronics-engine-design.md)

## Money-path scoreboard

Offline compile + honesty bar for the 8 depth winners (`examples/money_paths/manifest.json`):

| path_id | build | bar |
|---------|-------|-----|
| enabot_lite | robot_drive_base | PASS |
| plant_watering | automatic_plant_watering | PASS |
| robot_drive_rc | robot_drive_base | PASS |
| printer_plotter | plotter_motion_stage | PASS |
| usb_fume | usb_fume_extractor | PASS |
| smart_relay | smart_relay_box | PASS |
| sensor_logger | sensor_logger | PASS |
| pan_tilt | inspection_motion_fixture | PASS |

`make verify-money-paths` → report `/tmp/hs_money_paths/MONEY_PATHS_REPORT.json`

## Mechatronics scoreboard

Same 8 paths with firmware + mecha-splicer pack + honest `offline_pack` authority:

| path_id | mech kind | status |
|---------|-----------|--------|
| enabot_lite | mobile_drive | PASS |
| plant_watering | enclosure | PASS |
| robot_drive_rc | mobile_drive | PASS |
| printer_plotter | linear_axis | PASS |
| usb_fume | enclosure | PASS |
| smart_relay | enclosure | PASS |
| sensor_logger | enclosure | PASS |
| pan_tilt | pan_tilt | PASS |

`make verify-mechatronics-paths` · `make audit-mechatronics-confidence` · golden: `make verify-mechatronics-golden`  
Splice-UI: Mechatronics panel on Verify + Package stages.

Confidence bar checks: firmware pins match compiled build_graph, sketch constants match pin map, MCU present when resolved, mecha SCAD on disk, no fake `production_authorized`.

## Physical closed loop (flagship)

Pan-tilt is the one path meant for a real print→wire→flash→bench win.

| Item | Location |
|------|----------|
| Prepare pack | `make prepare-physical-closed-loop` |
| Verify software-ready | `make verify-physical-closed-loop` |
| Runbook | `/tmp/hs_physical_closed_loop/pan_tilt/PHYSICAL_BENCH_RUNBOOK.md` |
| Evidence template | `/tmp/hs_physical_closed_loop/pan_tilt/PHYSICAL_BENCH_EVIDENCE.json` |
| Quick demo | splice-ui prefers `splice_physical_pan_tilt_loop` |

**Human gate (you):** follow the runbook on real hardware, fill evidence JSON, then consider unpausing invites.

## Next actions

1. **Founder bench:** print/wire/flash pan-tilt per runbook; close `PHYSICAL_BENCH_EVIDENCE.json`  
2. Optional: plant-watering as easier second physical path  
3. Soft-I2C ToF on CAM; corpus compile on flagged A/B  
4. Invites stay paused until physical evidence is closed  

## Log

| Date | Note |
|------|------|
| 2026-07-18 | **Donor-keep + pin-true handoff:** strip/refuse gap_fill·goal_picker·workshop drivers when FS drv bound; post-compile bring-up + WIRING_GUIDE from build_graph; money paths still 8/8 |
| 2026-07-18 | Public MIT + prerelease (infra) |
| 2026-07-18 | Pivot: no invites — verify/polish |
| 2026-07-18 | agent_quickstart_verify PASS; UI Quick demo hang documented |
| 2026-07-18 | Root-caused hang (2nd plan→Qwen); skip replan + job/UI timeouts; robot+practical API green offline |
| 2026-07-18 | **Value audit:** practical ignores boost/USB-C; robot demo gap-fills L298N, drops donor H-bridge + 2nd motor; scores are theater |
| 2026-07-18 | **Strong examples:** wifi_logger = real inventory compose; printer/golden/vision still fail donor reuse (A4988 false-positive or L298N gap_fill) |
| 2026-07-18 | **Donor bind shipped:** FS `actuator_driver` → resolved before gap_fill; robot + `vibe_enabot_lite` keep J_MOTOR_* / no L298N gap_fill; tests green |
| 2026-07-18 | **Enabot-lite endgame:** ESP32-CAM MCU + dual IN1–IN4 firmware from bring-up; no L298N/USB shopping; DRC-clean carrier; `make verify-vibe-enabot-endgame` PASS |
| 2026-07-18 | **Product corpus:** 620 Enabot-depth intents across 26 families (`make product-corpus` / `make sweep-product-corpus`); offline sweep ~90%+ A/B after keyword expansion |
| 2026-07-18 | **Money paths 8/8:** depth winners at Enabot honesty/compile bar; `svo` multi-instance + relay/USB/pan-tilt topology fixes; `make verify-money-paths` |
| 2026-07-18 | **Mechatronics engine:** `mechanism_bridge` → mecha-splicer; FW for relay/fume/pan-tilt; `verify-mechatronics-paths` 8/8; pan-tilt golden PASS; splice-ui Mechatronics panel |
| 2026-07-18 | **Confidence harden:** graph-true FW regen; usb_fume recipe includes MCU; pan-tilt GPIO18/16; GPIO0 falsy bug fixed; `audit-mechatronics-confidence` 8/8 |
| 2026-07-18 | **Physical closed loop:** pan-tilt pack + runbook + evidence template; Quick demo prefers it; `make verify-physical-closed-loop` software-ready — human bench open |
