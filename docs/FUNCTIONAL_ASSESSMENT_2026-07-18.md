# Hardware-Splicer — Functional assessment (2026-07-18)

**Context:** Founder paused outreach; focus is “how good / how functional is this actually?”  
**Machine:** optiplex · tree `main` · UI/API exercised same day.

---

## Verdict (short)

| Layer | Grade | Notes |
|-------|-------|-------|
| **Engine / HTTP agent spine** | **Strong** | Full `agent_quickstart_verify` PASS in ~73s (live Qwen earlier; prefer offline now) |
| **Make product verify** | **Strong** | `verify-product-v1` + install/live smoke PASS |
| **Web UI Quick demo / splice_build** | **Fixed (offline)** | Hang was post-compile second `plan_project_from_intake` (re-Qwen). Skipped; job timeout + UI timeout added |
| **Practical non-golden intake** | **Works offline** | Power-bank→ESP32 sensor node → `sensor_logger` in ~5–11s |
| **Docs / install ergonomics** | **Mixed** | Alien `/root` defaults in verify script (fixed); DEMO still needs re-walk |

**Bottom line:** Agent spine was already real. Quick demo hang was a **second LLM salvage replan after compile** that could stall forever when Qwen quota/network misbehaved. That replan is removed; jobs fail after 180s wall-clock; UI stops “Building…” after ~210s.

---

## Evidence — what passed

### `scripts/agent_quickstart_verify.sh` (this tree, port 8791)

```
catalog_count 50
sync agent-loop DRC 0
async job DRC 0
salvage donor_context DRC 0
bench_loop power_on True (simulated)
vision-assist gates_unchanged
golden-real power_on True simulated False
public-web DMM provenance OK
donor-board-vision offline OK
copper honesty preview / not fab-ready
Qwen phrase + live photo + live vision-assist OK
==> PASS wall_seconds=73
```

Log: `docs/status/generated/agent-quickstart-verify-2026-07-18.log` (copy from `/tmp/hs-aqv-2026-07-18.log`).

### Earlier today

- `make doctor` OK  
- `make verify-product-v1` OK (36 product tests + UI build)  
- install-smoke + live-smoke OK  

### Polish retest (2026-07-18 night, **no live Qwen**)

Env: `HARDWARE_SPLICER_OFFLINE_*=1`, `QWEN_DISABLED=1`.

| Path | Result |
|------|--------|
| Quick demo intake `splice_robot_drive_brief` via `POST /v1/jobs/splice-build` | **succeeded ~8s**, `PROJECT_PACKAGE.json` present, `build_id=robot_drive_base` |
| Practical messy intake (power-bank donor + ESP32 + BME280, no golden id) | **succeeded ~5s**, `build_id=sensor_logger` |
| Artifact bloat | `PROJECT_INTAKE` ~392KB → ~6KB; result payload ~352KB → ~119KB |

---

## Evidence — what failed (UI) — root cause (resolved)

Manual Playwright walk earlier:

1. **Quick demo** → job `8be7c637…` stuck `running` after compile artifacts.  
2. Disk had `COMPILER_EVIDENCE_PATCH` but **no** `POST_SPLICE_SCORING` / `PROJECT_PACKAGE`.  
3. Backend later marked `WorkerInterrupted` on restart.

**Root cause:** `splice_and_build_from_intake` called `plan_project_from_intake` a **second** time after compiler evidence (still hit Qwen salvage/archetype). First plan + compile finished; second plan hung on LLM.

**Fixes landed:**

1. Skip second replan — score from existing plan + compiler patch (`replan_skipped: true`).  
2. Slim `PROJECT_INTAKE` + clarifier `enriched_intent` (no nested salvage graphs).  
3. Job wall-clock timeout (`HARDWARE_SPLICER_JOB_TIMEOUT_S`, default 180).  
4. UI client timeout (~210s) so Building… cannot spin forever.  
5. `QWEN_DISABLED` / `HARDWARE_SPLICER_QWEN_DISABLED` honored in `llm_policy`.

---

## Ranked polish backlog (function first)

| P | Item | Why |
|---|------|-----|
| **P0** | ~~Fix Quick demo / splice_build hang~~ | **Done** (offline retest green) |
| **P0** | ~~UI job timeout honesty~~ | **Done** |
| **P1** | Re-run DEMO_5_MIN_UI end-to-end in browser after rebuild UI | Confirm overlay dismisses |
| **P1** | Keep agent_quickstart_verify defaults local-tree friendly | Fixed: no longer requires `/root/...` |
| **P1** | Prefer offline verify loops (Qwen quota / Alibaba email) | Don’t burn live LLM on polish |
| **P2** | Stranger/fresh-archive dry-run (optional) | Cold exit already claimed |
| **P2** | Physical café bench | Explicitly out of software polish |
| **P3** | Outreach / design partners | **Paused** until DEMO re-walk agreed |

---

## What we should *not* claim yet

- “5-minute UI demo always works”  
- Partner-ready first-run experience  
- That public prerelease = product-validated for strangers  

What we **can** claim (with evidence):

- Cold-internal agent/HTTP bar including optional live vision  
- KiCad DRC truth on agent-loop / salvage paths  
- Copper honesty (preview ≠ fab-ready)  

---

## Value audit (not demo) — 2026-07-18 night

Inspected **on-disk packages** from offline jobs (not UI greenery):

| Job | Intake | Outcome claimed |
|-----|--------|-----------------|
| `e79b5ed…` | Practical: power-bank boost → ESP32 + BME280 + USB-C | `sensor_logger`, verdict `ready_after_measurements`, score B/82% |
| `53e65fb…` | Quick demo robot_drive (donor RC + 2 motors + ESP32 + ToF) | `robot_drive_base`, verdict `ready_after_measurements`, score C/76% |

### Practical intake — is it valuable?

**Partially useful as a catalog sketch. Not useful as salvage guidance for the stated goal.**

| Claim / artifact | Reality |
|------------------|---------|
| Reuse power-bank **boost stage** | Mapped donor → catalog `usb-power-5v` (USB **Micro-B** 5V jack). Zero boost/Anker reasoning. |
| USB-C breakout in inventory | `unresolved` — dropped from BOM/package |
| Sensor node (BME280) | Correct module pick; I2C GPIO21/22 in bringup is sane |
| Gap analysis | Invents goal modules `nrf24l01` + `dht22` the user never asked for (catalog bleed) |
| Bring-up card | Hookup lines for ESP32↔BME280 are human-usable; also injects **pump/motor** checks for a sensor build |
| Firmware | Stub: prints `bringup: wire pins…` — not a logger |
| Wiring guide | Raw `{'nodeId': 'n1', 'pinId': 'V+'}` dumps — not bench-usable |
| Cost $26 | Prices salvage lines; theater |
| `fabrication_ready: false`, `power_on_authorized: false` | **Honest** — keep this |

**Maker next step if they trusted the package:** order/mill a generic USB+ESP32+BME280 carrier and ignore their actual power-bank board and USB-C part. That is the opposite of the salvage thesis.

### Robot Quick demo — is it valuable?

**Useful as a canned `robot_drive_base` compile. Misleading as “splice the donor RC H-bridge.”**

| Claim / artifact | Reality |
|------------------|---------|
| Donor board “Dual H-bridge intact” | `resolved_modules`: donor_board **`unresolved`**. Gap-fill adds **new** `l298n` (`dc_motor_without_driver`) |
| Two 6V gear motors | BOM has **one** `dc_motor_3v_6v` (left only). Right motor disappears |
| Constraints battery 7.4V / motors 6V | `power_topology: barrel_12v` + compile BOM includes **12V barrel** — wrong rail for the stated parts |
| Pin truth | Bringup: GPIO4/GPIO2 → L298N; firmware: pins **2/3**; wiring guide: **D2/D3**. Three disagree |
| Firmware | Single-motor serial f/b/s stub; no ToF, no second channel |
| Functional score 76% | Mostly artifact-presence checks (10/27), not “would drive on the bench” |

**Maker next step if they trusted the package:** buy an L298N and a 12V brick, throw away the donor driver the demo promised to reuse.

### What is actually valuable today

1. **Inventory → known catalog module IDs** when names match regexes (ESP32, BME280, ToF).  
2. **DRC-clean KiCad carrier** for those catalog modules (real compiler work).  
3. **Safety honesty flags** (`fabrication_ready=false`, bench gates open, power-on blocked).  
4. **Human bring-up hookup bullets** when they aren’t polluted by wrong templates.

### What is not valuable (or actively harmful)

1. **Donor-board salvage** — unknown PCBs stay unresolved; system substitutes catalog drivers.  
2. **Scores / cost / “ready_after_measurements”** as product quality signals — file-presence theater.  
3. **Firmware scaffolds** — unsafe to flash without reconciling pins.  
4. **Wiring_GUIDE.md** — machine dump, not a wiring sheet.  
5. **Quick demo narrative** — sells donor splice; delivers gap-filled catalog robot.

### Strong-examples scoreboard (not Quick demo) — 2026-07-18

Ran the repo’s strongest intakes via `POST /v1/jobs/splice-build` (offline, no live Qwen). Raw: `/tmp/hs_strong_examples_value.json`.

| Case | Build | Value grade | What actually happened |
|------|-------|-------------|------------------------|
| **wifi_logger_scratch** (`salvage_wifi_logger_brief`) | `generic_low_voltage_build` | **GOOD_INVENTORY_COMPOSE** | Explicit module_ids → clean USB+ESP32+DHT22; real DHT firmware on GPIO4; DRC 0. Best path in the set. |
| **plant_watering_tier5** | `automatic_plant_watering` | **CATALOG_COMPILE_ONLY** | Inventory maps cleanly; soil+MOSFET+pump hookup + real threshold firmware. Useful DIY kit path — not donor salvage. |
| **printer_motion** (inkjet `functional_salvage` fixture) | `plotter_motion_stage` | **FALSE-POSITIVE salvage** | Donor board regex→`a4988-stepper` (labeled salvaged). **No** `J_MOTOR_X/Y` harness reuse in bringup. 24V PSU→`dc-barrel-12v`. Y stepper/limit dropped. Bringup mixes A4988 STEP/DIR **and** direct 28BYJ drive — inconsistent. |
| **golden_real_rc** (real photo + repair intake) | `robot_drive_base` | **FAIL_SALVAGE_THESIS** | Donor unresolved; gap-fill **L298N**; photo/fixture unused for driver keep. |
| **vision_repair_rc** (API “strong” vision example) | `robot_drive_base` | **FAIL_SALVAGE_THESIS** | Same failure mode as golden_real / Quick demo. |

**Takeaway:** The only path that is honestly valuable today is **known-parts inventory → catalog/scratch compose** (wifi logger, plant watering). The “strong” donor examples (printer fixture, golden photo, vision repair) still do **not** deliver connector-level donor reuse; they either keyword-substitute a catalog driver or gap-fill one.

---

## Next work (recommended)

1. Browser re-walk DEMO only as UX check — **do not treat it as value proof**.  
2. Fix salvage honesty: unresolved donor must block “splice” claims; don’t gap-fill L298N while calling it salvaged donor driver.  
3. Align firmware pins with bringup/wiring; drop template pump text on sensor builds.  
4. Replace nodeId wiring dumps with module/pin labels.  
5. Partners only after a **practical salvage** case keeps the donor subsystem (not catalog substitute).
