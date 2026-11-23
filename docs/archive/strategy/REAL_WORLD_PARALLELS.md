# Real-world parallels — how salvage actually works

How industry and community repair workflows map to Hardware Splicer's splice + bench gates. These are the patterns we're encoding — not inventing.

## RC toy → robot drive (our canonical demo)

**What makers actually do:** Strip the original RC electronics, keep chassis/motors, add ESP32 + L298N/DRV8833 on a perfboard or custom carrier.

| Real practice | Source | Our equivalent |
|---------------|--------|----------------|
| Keep motor harness, discard toy MCU board | [ESPHomeRC-RetrofitCar](https://github.com/rnauber/ESPHomeRC-RetrofitCar), [esp32_RCCar](https://github.com/markloboda/esp32_RCCar) | `connector_reuse` splice block |
| ESP32 cannot drive motors directly — need H-bridge | [ProjectsLearner H-bridge guide](https://projectslearner.com/learn/esp32-h-bridge-module) | Carrier compile wires ESP32 GPIO → driver inputs |
| Separate motor supply vs logic supply | [esp32cam-rc-car](https://github.com/vitorccs/esp32cam-rc-car) README | `VMOTOR` bench gate before logic tie-in |
| Common ground between MCU and driver | Every ESP32 motor tutorial | Continuity / polarity gates in `BRINGUP_CARD.md` |

**Gap vs tutorials:** Blog posts skip structured measurement logs. We require `bench_topology_capture` before `power_on_authorized`.

## Professional motor-driver bench bring-up

**Rossmann Group** documents the gold-standard sequence for dead motor-driver PCBs (hard drives, but same electrical discipline):

1. Discharge capacitors, visual inspection
2. **Current-limited bench supply** (e.g. 0.5 A) ramped while watching FLIR hotspots
3. Multimeter on regulated rails (within ±5% of nominal)
4. Oscilloscope on motor phase outputs before reconnecting load
5. Only then reconnect mechanical assembly

Sources: [PCB Diagnostics vs Logic Board Repair](https://rossmanngroup.com/technical-reference/pcb-diagnostics-vs-logic-board-repair), [Hard Drive PCB Components](https://rossmanngroup.com/technical-reference/hard-drive-pcb-components)

| Their step | Our gate / artifact |
|------------|---------------------|
| Current-limited ramp | `bench_supply_01` in capture template |
| Rail voltage check | `voltage` measurement rows → `gate_id` |
| Phase waveform | Future: scope capture URI on gate |
| Donor board swap + ROM transfer | Analog: donor fixture + `board_evidence` — **we do not auto-authorize donor swaps** |

## Repair café / community diagnostic checklist

[Repair Café Malmö](https://www.repaircafe.nu/tips-for-repair/) and [LCSC board repair guide](https://www.lcsc.com/blog/circuit-board-repair-guide/) converge on:

1. Reproduce the fault
2. Visual inspection (burnt parts, bulging caps)
3. **Power-off** continuity / diode mode on rails
4. **Power-on** voltage mapping against schematic
5. Document what was measured before reassembly

| Community practice | Our encoding |
|--------------------|--------------|
| "Need at least a multimeter" | `BENCH_CAPTURE_TEMPLATE.json` |
| Fuse / switch continuity | `continuity` kind rows |
| Rail voltage vs expected | `voltage` rows with `target` prompt |
| PAT test before hand-back | `power_on_authorized` flag |

[Restarters Community](https://talk.restarters.net/t/buyers-guide-for-multimeters/24593) emphasizes **safe DMMs for 230 V repair cafés** — our template includes `instrument_id` + `calibration_status` for traceability.

## Component salvage industry (not our primary wedge)

Industrial harvesting ([The Lab WorldWide](https://thelabww.com/services/component-harvesting-services/), [Circuit Technology Center](https://www.circuitrework.com/tech-papers/1181.html)) focuses on **desoldering ICs** with IPC traceability — different from **functional block reuse on harness**.

| Industry salvage | Hardware Splicer |
|------------------|------------------|
| Chip-level recovery | Optional future |
| **Harness + connector reuse** | **Core** (`connector_reuse`, splice plan) |
| Reball / RHSD | Out of scope |
| J-STD-020 bake/pack | Fab path, not donor bench |

Hobby ECU guides ([AllPCB salvaging](https://www.allpcb.com/allelectrohub/salvaging-components-from-old-ecu-pcbs-a-beginners-guide)) teach desoldering parts — we target **keeping a working motor driver section** without full board swap.

## Flux / greenfield ECAD (contrast)

[Flux](https://www.flux.ai/) workflow (2026): natural language → plan → schematic → layout → **continuous ERC/DRC during generation** → sourcing.

| Flux | Us |
|------|-----|
| Validates **new** design rules in-editor | Validates **carrier** DRC + **donor** bench gates |
| Steerable agent in browser | Agent via MCP/SDK on disk artifacts |
| Live parts inventory | Catalog hooks; not marketplace-first |
| No donor dissection model | **Core** |

Flux treats AI as a "fast junior engineer" for **new** boards. We treat bench capture as the junior engineer's **lab notebook** for **salvaged** assemblies.

## Mapping table — "does the internet already do this?"

| Workflow stage | Exists in wild? | Structured / agent-ready? | Our status |
|----------------|-----------------|---------------------------|------------|
| RC retrofit tutorials | Yes, many | No — prose + wiring diagrams | S2 compile + gates |
| Repair café checklists | Yes | Partial — human forms | S3 bench session JSON |
| Pro lab motor bring-up | Yes (Rossmann, industrial) | Internal SOPs, not APIs | `bench_topology_capture.v1` |
| Donor board vision | Ad-hoc photos | No | `board_evidence` + Qwen path |
| One-shot agent loop | No | — | `hs_splice_golden_loop` |

## What to steal next (from real practice)

1. **Current-limited first power** — `psu_current_limit_ramp` gate (≤0.5 A) injected on motor/splice builds
2. **Thermal optional row** — `thermal_baseline_scan` gate with FLIR URI in capture template
3. **Repair-café intake** — `repair_intake.symptoms`, `when_it_fails`, `device_hint` on PROJECT_INTAKE
4. **Donor photo dry-run** — `make vision-donor-smoke` on `tests/data/donor_rc_board_sample.png`
5. **Live photo regression** — `HARDWARE_SPLICER_RUN_VISION_LIVE=1 pytest tests/test_donor_board_vision_live_optional.py`

## Try it

```bash
# Matches "junk RC toy + vision evidence" community project
make splice-golden-loop

# Agent one-shot
# MCP: hs_splice_golden_loop { intake: {...}, simulate_bench: false }
```

See [`COMPETITIVE_LANDSCAPE.md`](COMPETITIVE_LANDSCAPE.md) for product positioning and [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) for tool names.
