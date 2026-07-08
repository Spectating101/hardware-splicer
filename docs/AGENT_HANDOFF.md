# Agent handoff — Hardware-Splicer

**Start here.** Any agent (MCP client, HTTP caller, Python script) can drive the splice product without a UI. The library/SDK is the primary handoff; MCP and HTTP are thin wrappers over the same functions.

**What changed since May:** [`HANDOFF_UPDATE.md`](HANDOFF_UPDATE.md) — build/upgrade delta for continuity.  
**Strategy / funding / vs Blueprint:** [`BLUEPRINT_POSITIONING_AND_FUNDING.md`](BLUEPRINT_POSITIONING_AND_FUNDING.md) — do not kill HS because of Blueprint; Taiwan competition + grant path.

## What this engine does (splice thesis)

1. **Dissect** donor hardware — functional blocks, extractability classes, evidence gates
2. **Plan** splice contracts — what to keep on harnesses, what not to cut yet
3. **Compile** a **carrier board** — KiCad schematic + placed PCB wired to donor connectors
4. **Bench** — close measurement gates before power-on (S3)

**Honest bar today:** S2 compile demos pass KiCad DRC (`make verify-splice`). S3 golden paths close gates in CI (`verify-splice-loop`) or via hand-filled real capture (`verify-splice-real-bench`). Circuit synthesis planners are test-covered (`88f1db8`) on a **parallel greenfield path** — not merged into splice verify yet. Splice and synthesis builds auto-emit **PROJECT_PACKAGE** artifacts (Blueprint-shaped tabs + **GATES**). Field validation on community junk is a future partner step.

**Competition / judge entry:** [`COMPETITION_HANDOFF.md`](COMPETITION_HANDOFF.md) · full proposal [`COMPETITION_PROPOSAL.md`](COMPETITION_PROPOSAL.md)

## Recommended flow

```
hs_sdk_info
  → hs_modules_catalog          # canvas compose — pick moduleIds (Design Studio catalog)
  → hs_compose_drc_agent        # preferred: compose + manual DRC rounds + optional finalize_package
  → hs_design_quality           # inspect build_dir DRC truth after compose
  → hs_render_project_package   # if not using finalize_package on compose
  → hs_splice_bench_status      # read open gates + next_actions
  → hs_splice_bench_submit      # record measurements, close gates
```

**Design Studio path (greenfield canvas):** same as `hs_compose` + `POST /v1/compose` — see [`DESIGN_STUDIO_DRC_AGENT.md`](DESIGN_STUDIO_DRC_AGENT.md). Read `design_quality.drc_fix_loop`; pass `drc_fixup` on retry.

**Salvage / donor shortcut:**

```
hs_clarify_hardware_intent   # optional
  → hs_splice_build          # or hs_plan_salvage
  → hs_render_project_package
  → hs_splice_bench_status / hs_splice_bench_submit
```

**Shortcut (CI / demo):** `hs_splice_golden_loop` — build + template + capture submit in one call. Set `simulate_bench: false` for real instrument readings.

**Golden real S3:** SDK `splice_golden_real()` or `make verify-splice-real-bench` / `make splice-golden-real` — Wikimedia donor photo + pinned live Qwen `board_evidence` + manual bench capture (`simulated: false`).

Do **not** claim fab-ready or power-on-safe from KiCad DRC alone. Read `design_quality_gate.fabrication_ready` and `bench_session.power_on_authorized`.

## Circuit synthesis (greenfield path — `88f1db8`)

Bounded **intent → topology → candidate → compile** for supported domains (motor driver, H-bridge, power rail, level shift, sensor interface, relay, battery, analog conditioning). Unsupported goals return **blocked candidates** with structured blockers — no fake schematics.

```text
plan_circuit_synthesis(intent)   # safe dispatcher
  → SynthesisCandidate (blocked | ready_for_review)
synthesize_circuit(intent)       # plan + compile when not blocked
  → KiCad build dir + topology_authority metadata
```

Per-domain SDK helpers: `plan_motor_driver_circuit`, `plan_h_bridge_circuit`, `plan_power_rail_circuit`, etc. Capability card: `circuit_synthesis_capability()`.

**HTTP** (synthesis + project package):

| Route | Purpose |
|-------|---------|
| `GET /v1/circuit-synthesis/capability` | Supported topologies + authority ceiling |
| `POST /v1/circuit-synthesis/plan` | Dispatcher plan only (includes clarifier metadata) |
| `POST /v1/circuit-synthesis/compile` | Plan + compile ready candidates |
| `POST /v1/circuit-synthesis/motor-driver` | … per-domain planners (h-bridge, power-rail, …) |
| `POST /v1/intent/clarify` | Clarifying questions for vague hardware goals |
| `POST /v1/project-package/render` | Refresh PROJECT_PACKAGE from build dir |

```python
from hardware_splicer.sdk import plan_circuit_synthesis, synthesize_circuit

candidate = plan_circuit_synthesis({
    "goal": "drive_brushed_dc_motor",
    "supply_voltage_v": 12,
    "motor_current_a": 1.5,
    "logic_voltage_v": 3.3,
})
print(candidate.get("blocked"), candidate.get("blockers"))

result = synthesize_circuit(candidate["intent"] if "intent" in candidate else {...}, export_gerber=False)
```

Deep reference: [`CIRCUIT_SYNTHESIS_LAYER_PLAN.md`](CIRCUIT_SYNTHESIS_LAYER_PLAN.md). **Splice path and synthesis path are separate today** — RC demos still use donor fixtures + catalog `robot_drive_base`.

## Project package (Blueprint-shaped output)

Competitive positioning vs Blueprint.am: they win open-ended **generative planning + polished project page**; we win **verification discipline** (compile DRC, bench gates, casefiles). The project package layer packages our artifacts into their tab shape **plus GATES**:

| Tab | Artifact |
|-----|----------|
| INFO | goal, supply, clarifier notes |
| BOM | salvage or compile BOM lines |
| WIRING | `WIRING_GUIDE.md` |
| INSTRUCTIONS | `ASSEMBLY_GUIDE.md` |
| **GATES** | compile / bench / blocked verdict |

Emitted automatically on `splice_build` and `synthesize_circuit` (when `out_dir` set). Refresh anytime:

```python
from hardware_splicer.sdk import clarify_hardware_intent, render_project_package

clarify_hardware_intent({"goal": "robot with motor"})
render_project_package("/tmp/splice_out")
```

| Surface | Entry |
|---------|-------|
| SDK | `clarify_hardware_intent()`, `render_project_package()` |
| MCP | `hs_clarify_hardware_intent`, `hs_render_project_package` |
| HTTP | `POST /v1/intent/clarify`, `POST /v1/project-package/render` |
| CLI | `python scripts/build_project_package.py --build-dir …` |
| Verify | `make test-project-package` |

## Surfaces (pick one)

| Surface | When to use |
|---------|-------------|
| **Python SDK** | Notebooks, CI, custom agents in-process |
| **MCP** (`python -m hardware_splicer.mcp_server`) | Cursor, Claude Desktop, any MCP client — splice + synthesis + project package tools |
| **HTTP API** (`scripts/hardware_splicer.py serve`) | Remote agents, multi-tenant hosts — splice + circuit-synthesis routes |

All three call the same code in `src/hardware_splicer/sdk.py`.

## Camera / vision / bench capture (already in repo)

You do **not** need to build vision from scratch. Capabilities exist in two layers:

### Hardware-Splicer spine (agent-ready now)

| Capability | SDK / MCP | Notes |
|------------|-----------|-------|
| Capability inventory | `vision_capabilities()` / `hs_vision_capabilities` | Points to all modules |
| Intake photo vision | `vision_enrich_intake()` / `hs_vision_enrich_intake` | Qwen/Gemini on `attachments` + `vision_assistance` |
| Offline attachment indexing | runs inside `plan_project_from_intake` | filename/meta → pending vision |
| Splice + vision | `splice_build` with vision-enabled intake | Example: `examples/intakes/plant_watering_vision_brief.json` |
| Bench gate submit (manual rows) | `splice_bench_submit` | `{gate_id, value, unit, status}` |
| Bench gate submit (capture packet) | `splice_bench_submit_capture` / `hs_splice_bench_submit_capture` | Accepts `bench_topology_capture.v1` |

CLI equivalent:

```bash
python3 scripts/hardware_splicer.py intake \
  --brief examples/intakes/plant_watering_vision_brief.json \
  --vision-live --vision-apply --out /tmp/vision_intake
```

### Circuit-AI layer (deeper board + bench truth)

Lives under `apps/circuit-ai/` — same product family, separate HTTP server if you run Circuit-AI API:

| Module | Purpose |
|--------|---------|
| `qwen_board_vision.py` | Donor board photos → `board_evidence.v1` candidates |
| `bench_topology_capture.py` | Structured DMM/supply/thermal readings → `topology_evidence` |
| `measurement_session_progress.py` | Track which required readings are still open |
| `enhanced_detector.py` + `defect_detector.py` | Dum-E-era PCB inspect (components + defects) |
| `multi_view_capture.py` | Multi-angle capture orchestration (arm/turntable/phone workflows) |

API routes (Circuit-AI): `POST /vision/qwen/board-evidence`, `POST /hardware/topology-capture/template`, `POST /hardware/topology-capture/convert`.

Archive doc for the old Dum-E arm interface experiment: `apps/circuit-ai/docs/archive/2026-01-27_root_docs/DUM_E_STATUS.md` — **one interface option**, not the only endgame. Web/Flux/notebook-style UIs remain valid; vision feeds any of them.

**Policy (unchanged):** photos → candidates + measurement queue; bench capture → gate closure. Vision alone does not authorize power-on.

### Plumbed loop (splice path)

```text
donor photo OR board_evidence.v1 on circuit.boards
  → hs_donor_board_vision / automatic in hs_splice_build
  → functional_salvage blocks (no static JSON fixture required)
hs_splice_build
  → VISION_EVIDENCE_REPORT.json + DONOR_BOARD_VISION_REPORT.json
  → SPLICE_BENCH_SESSION.json + BENCH_CAPTURE_TEMPLATE.json
fill template → hs_splice_bench_submit_capture → gates close
```

Or one-shot: `hs_splice_golden_loop` / `POST /v1/splice-golden-loop` / `make splice-golden-loop`.

Example without static donor fixture: `examples/intakes/splice_robot_drive_vision_brief.json`
(uses `@tests/data/board_evidence_rc_motor_donor.json`; swap for live `vision_source.path` + Qwen when keyed)

| Step | MCP | HTTP |
|------|-----|------|
| Donor board → functional_salvage | `hs_donor_board_vision` | `POST /v1/donor-board-vision` |
| Get fillable template | `hs_splice_bench_capture_template` | `POST /v1/splice-bench/capture-template` |
| Submit filled capture | `hs_splice_bench_submit_capture` | `POST /v1/splice-bench/submit-capture` |

### Still optional / future wiring

| Gap | Status |
|-----|--------|
| Dum-E multi-view → richer board_evidence fuse | `multi_view_capture.py` exists; not on MCP path yet |
| Serial DMM / PSU auto-fill → capture template | Schema ready; no instrument driver in hardware_splicer |
| Single-process Circuit-AI API proxy | Optional; board vision imported from `apps/circuit-ai` in-process today |

## Python SDK

```python
from pathlib import Path
from hardware_splicer.sdk import (
    sdk_info,
    splice_build,
    splice_bench_status,
    splice_bench_submit,
    inspect_fab_build_dir,
)

print(sdk_info()["agent_handoff"])

# 1. Splice + compile (intake path or dict)
result = splice_build(
    "examples/intakes/splice_robot_drive_brief.json",
    out_dir="/tmp/splice_robot",
    export_gerber=False,
)
build_dir = result["artifacts"]["splice_plan"].replace("/SPLICE_PLAN.json", "")
# or use the parent of splice_plan artifact

# 2. Bench gates (also opened automatically by splice_build)
status = splice_bench_status(build_dir)
print(status["readiness"], status["critical_open_count"], status["next_actions"])

# 3. Submit measurements
submit = splice_bench_submit(
    build_dir,
    [
        {"gate_id": "vmotor_rail", "status": "closed", "value": 6.0, "unit": "V"},
        {"gate_id": "motor_harness_continuity", "status": "closed", "method": "DMM"},
    ],
)
print(submit["power_on_authorized"], submit["readiness"])

# 4. Fab inspection (no recompile)
fab = inspect_fab_build_dir(build_dir)
```

### Key artifacts (on disk)

| File | Meaning |
|------|---------|
| `PROJECT_INTAKE.json` | Resolved intake + circuit/donor context |
| `SPLICE_PLAN.json` | Salvage package: splice plan, blocks, bring-up |
| `BRINGUP_CARD.json` / `.md` | Operator checklist |
| `SPLICE_BENCH_SESSION.json` | Open/closed evidence gates (S3) |
| `build_compilation/` | KiCad PCB, BOM, design quality |
| `FABRICATION_INSPECTION.json` | Headless fab review |

## MCP tools

Install: `pip install -r requirements-mcp.txt` then `PYTHONPATH=src python -m hardware_splicer.mcp_server`

| Tool | Purpose |
|------|---------|
| `hs_sdk_info` | Capability boundaries — call first |
| `hs_plan_salvage` | Fast feasibility (no KiCad) |
| `hs_splice_build` | **Primary** splice + compile + bench session |
| `hs_splice_golden_loop` | One-shot S3 loop (optional simulated bench) |
| `hs_splice_bench_status` | Gate status / next actions |
| `hs_splice_bench_submit` | Close gates with measurements |
| `hs_splice_bench_submit_capture` | Close gates from `bench_topology_capture.v1` |
| `hs_donor_board_vision` | Photos/board_evidence → functional_salvage |
| `hs_inspect_fab` | Review fab package on disk |
| `hs_engine_doctor` | KiCad/node/runtime check |

Golden real (no dedicated MCP tool yet): SDK `splice_golden_real()` or `make splice-golden-real`.

See [`docs/MCP.md`](MCP.md) for Cursor/Claude config.

## HTTP API

```bash
python scripts/hardware_splicer.py serve --host 127.0.0.1 --port 8787
```

| Route | Body |
|-------|------|
| `POST /v1/splice-and-build` | `{"intake": {...}, "export_gerber": false}` |
| `POST /v1/splice-golden-loop` | `{"intake": {...}, "simulate_bench": true}` |
| `POST /v1/splice-bench/status` | `{"build_dir": "/path/to/splice/output"}` |
| `POST /v1/splice-bench/submit` | `{"build_dir": "...", "measurements": [...]}` |
| `GET /v1/circuit-synthesis/capability` | topology library card |
| `POST /v1/circuit-synthesis/plan` | `{"intent": {...}}` |
| `POST /v1/circuit-synthesis/compile` | `{"intent": {...}, "export_gerber": false}` |

`splice-and-build` returns `bench_session` summary and `artifacts.bench_session` path.

## Example intakes

| Intake | Tier | Notes |
|--------|------|-------|
| `splice_robot_drive_brief.json` | S2 | Fixture donor → `robot_drive_base` |
| `splice_printer_motion_brief.json` | S2 | Printer motion → `plotter_motion_stage` |
| `splice_robot_drive_vision_brief.json` | S3 | Offline board_evidence + golden loop |
| `splice_robot_drive_vision_repair_brief.json` | S3 | `repair_intake` + PSU ramp gates |
| `splice_robot_drive_golden_real_brief.json` | S3 | Real photo + live Qwen pin + manual capture |

Canonical verify:

```bash
make verify-splice              # S2
make verify-splice-loop         # S3 simulated (3 manifest cases)
make verify-splice-real-bench   # S3 golden real
make pin-golden-live-evidence   # refresh Qwen pin (needs API key)
```

See `docs/SPLICE_BEST_PRACTICES.md`, `docs/COMPETITIVE_LANDSCAPE.md`, `docs/COMPETITION_HANDOFF.md`.

## Truth model (do not skip)

- **KiCad ERC/DRC** = compile truth for the **carrier board**
- **Evidence gates** = bench truth for **donor harnesses** (voltage, polarity, continuity)
- Default copper = **cosmetic preview** (`copper_tier: cosmetic_preview`); FreeRouting off unless `HARDWARE_SPLICER_AUTOROUTE=1`

## Product docs

- [`docs/SPLICE_PRODUCT.md`](SPLICE_PRODUCT.md) — maturity S0–S5, personas, gaps
- [`docs/CIRCUIT_SYNTHESIS_LAYER_PLAN.md`](CIRCUIT_SYNTHESIS_LAYER_PLAN.md) — topology planners + implementation status
- [`docs/DEMO_SPLICE.md`](DEMO_SPLICE.md) — 10-minute walkthrough
- [`examples/splice/manifest.json`](../examples/splice/manifest.json) — CI demo contract

## Environment defaults for agents

```bash
export HARDWARE_SPLICER_AUTOROUTE=0
export HARDWARE_SPLICER_JLC_ENRICH=0
export HARDWARE_SPLICER_DRC_FIX_LOOP=1
```

Call `hs_engine_doctor` before long compile loops.
