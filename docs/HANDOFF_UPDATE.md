# Handoff update — what changed since last time

**Date:** July 2026 (updated after alpha.6 agent ops hardening on `main`)
**Audience:** You, ChatGPT, or the next agent — continuity without re-reading the whole repo
**Operational entry:** [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) · **Quickstart:** [`AGENT_QUICKSTART.md`](AGENT_QUICKSTART.md) · **Scale plan:** [`PRODUCT_SCALE_PLAN.md`](PRODUCT_SCALE_PLAN.md)
**Previous baseline:** [`apps/circuit-ai/docs/HANDOFF_CIRCUIT_AI_HARDWARE_SPLICER_2026-05-24.md`](../apps/circuit-ai/docs/HANDOFF_CIRCUIT_AI_HARDWARE_SPLICER_2026-05-24.md) (Circuit-AI salvage focus; pre-unified splice spine)

---

## July 2026 — Alpha.6 agent ops + alien proof complete

| Surface | What shipped |
|---------|----------------|
| **HTTP** | `POST /v1/jobs/compose-agent-loop` — async agent spine |
| **Alien** | FGEDHGV Track B: offline curls 1–2 (36s) + Qwen curl 3 (3072 tokens, 0 DRC) |
| **Ops** | `scripts/deploy_alien_quickstart.sh`, upgraded `agent_quickstart_verify.sh` (sync + async) |
| **CI** | Live smoke includes compose-agent-loop job; canvas pin contract tests (**50 modules**) |
| **Security** | Qwen `.env.local` scrubbed from lab node after test |
| **Tag** | `v1.1.0-alpha.6` |

---

## July 2026 — Alpha.5 product scale + agent quickstart

| Surface | What shipped |
|---------|----------------|
| **Docs** | `PRODUCT_SCALE_PLAN.md` (Phase 0–3), `AGENT_QUICKSTART.md`, `AGENT_BUILD_DIR_POLICY.md` |
| **UI** | Design Studio agent-loop emits package when goal set; modules picked shown in DRC panel; React Flow selection fix |
| **Tests** | Phrase-only `compose/agent-loop` HTTP test |
| **Tag** | `v1.1.0-alpha.5` |

**Live verified:** Qwen phrase compose, canvas agent-loop, MCP `hs_compose_drc_agent` + `hs_design_quality` (with `ALLOW_ARBITRARY_OUT_DIR` for local MCP).

---

## July 2026 — Design Studio + agent DRC loop (`4775e1c` → `fb3584e`)

| Surface | What shipped |
|---------|----------------|
| **UI** | Design Studio — React Flow canvas, module library, visible DRC agent panel, auto-fix & recompile |
| **HTTP** | `GET /v1/modules/catalog`, `drc_fixup` on `POST /v1/compose` |
| **MCP** | `hs_modules_catalog`, `hs_compose` accepts `drc_fixup` + `allow_llm_first` |
| **SDK** | `compose_design(..., drc_fixup=, allow_llm_first=)` |
| **Tests** | `tests/test_design_studio_agent.py` — agent spine without browser |

**Product framing:** Agentic KiCad-truth workbench — agents and humans share compose → DRC fix loop → `PROJECT_PACKAGE` → bench gates. UI is legibility, not a separate product.

---

## One-paragraph delta

Since the May handoff, the repo grew a **unified headless compiler** (`src/hardware_splicer/`), a **splice product spine** (donor → plan → carrier → bench gates), **agent surfaces** (SDK / MCP / HTTP), **S3 golden verification**, a **bounded circuit synthesis layer** (intent → topology operators → candidate → compile), and a **Blueprint-shaped project package** (INFO/BOM/WIRING/INSTRUCTIONS/**GATES** emitted from splice and synthesis builds). The honest bar: **S2/S3 proven in CI** for splice; synthesis planners are **test-covered**; project packages auto-emit on successful builds but **UI is still markdown/JSON**.

---

## Baseline vs now

| Area | Last handoff (May 2026) | Now (June 2026) |
|------|-------------------------|-----------------|
| Primary work location | `apps/circuit-ai/` salvage intelligence | **`src/hardware_splicer/`** — compiler + splice + bench |
| Product wedge | Salvage → product workflow (docs-heavy) | **Splice spine** with manifest + verify targets |
| Agent access | Circuit-AI API, scattered scripts | **`sdk.py` + MCP + HTTP** — same functions everywhere |
| Compile truth | Module-graph bootstrap | **+ netlist IR**, catalog verify, geometry gates, fab inspection |
| Donor vision | Qwen in Circuit-AI, not on splice path | **`board_vision_salvage`** wired into `splice_build` |
| Bench / power-on | Authority casefiles (CH340C showcase) | **`SPLICE_BENCH_SESSION`** + capture bridge on splice builds |
| CI bar | Tests + pan-tilt scenario | **`verify-splice`**, **`verify-splice-loop`**, **`verify-splice-real-bench`** |
| Builder-without-junk | Not addressed | **Golden artifacts** — real Wikimedia photo + pinned Qwen + manual capture |
| Greenfield circuit planning | Module pick + heuristics only | **`circuit_synthesis/`** — bounded topology planners + operator lowering (`88f1db8`) |
| Human-readable project page | Not addressed | **`project_package.py`** — PROJECT_PACKAGE.json + PROJECT_PAGE.md + wiring/assembly guides + **GATES** tab |

---

## What was built (by layer)

### 1. Headless compile engine (Sprint A–C)

Commits from `97f05a4` through `6a1d08a` established the engine under `src/hardware_splicer/`:

| Capability | Where | Verify |
|------------|-------|--------|
| Catalog KiCad DRC (18 builds) | `build_compiler.py`, `verify_engine.py` | `make verify-engine` |
| Netlist IR compile | `compile_from_netlist`, `plan_to_graph.py` | `make verify-netlist-engine`, `tests/test_netlist_fixtures.py` |
| Honest fab gates | `design_quality.py`, `fabrication_inspection.py` | `make verify-fab`, `hs_inspect_fab` |
| Geometry snapshots | `geometry_snapshot.py` | `make verify-geometry` |
| Tier C product bar | compose dispatch, casefiles | `make verify-tier-c` |
| Async jobs | `jobs.py` | `POST /v1/jobs/splice-build` |
| Netlist HTTP API | `api.py` | `POST /v1/netlist-compile` |

**Still true:** default copper is **cosmetic preview** (`HARDWARE_SPLICER_AUTOROUTE=0`). KiCad DRC validates the **carrier**, not donor harness safety.

### 2. Splice product spine (S0–S2)

| Piece | File / path |
|-------|-------------|
| Intake → splice package | `salvage_bridge.py`, `project_intake.py` |
| Manifest contract | `examples/splice/manifest.json` |
| S2 verify | `scripts/verify_splice_demos.py` → `make verify-splice` |
| Demo CLI | `scripts/splice_demo.py` → `make splice-demo` |

**Manifest cases (S2 compile):**

- `robot_drive_from_rc_toy` → `robot_drive_base`
- `printer_motion_stage` → `plotter_motion_stage`

### 3. S3 bench layer (new)

| Piece | File | Role |
|-------|------|------|
| Bench session + gates | `splice_bench.py` | Opens gates after `splice_build`; tracks `power_on_authorized` |
| Capture bridge | `bench_capture_bridge.py` | `bench_topology_capture.v1` → gate closure |
| Standard gates | `standard_bench_gates.py` | Injects **PSU current-limit ramp** (critical), optional **thermal baseline** |
| Repair-café intake | `repair_intake.py` | `symptoms`, `when_it_fails`, `device_hint` on intake |
| Donor vision → salvage | `board_vision_salvage.py` | Photos / `board_evidence` → `functional_salvage` blocks |

**Policy unchanged:** vision → candidates only; bench capture → gate closure.

### 4. Golden loop (S3 CI — simulated bench)

| Piece | Path |
|-------|------|
| Orchestrator | `src/hardware_splicer/golden_loop.py` |
| CLI | `scripts/splice_golden_loop.py`, `scripts/verify_splice_golden_loop.py` |
| SDK | `splice_golden_loop()` |
| MCP / HTTP | `hs_splice_golden_loop`, `POST /v1/splice-golden-loop` |
| Make | `make splice-golden-loop`, `make verify-splice-loop` |

**Manifest S3 cases (simulated closure in CI):**

- `robot_drive_vision_junk` — offline `board_evidence`, no static donor fixture
- `robot_repair_cafe_s3` — `repair_intake` + PSU ramp + synthetic photo path

### 5. Golden real S3 (non-simulated capture)

For builders **without personal junk hardware**:

| Artifact | Path |
|----------|------|
| Real donor photo | `tests/data/golden/rc_toy_motor_board.jpg` (Wikimedia, CC BY-SA) |
| Pinned live Qwen output | `tests/data/golden/rc_toy_live_board_evidence.json` + `.meta.json` |
| Hand-filled bench capture | `tests/data/golden/rc_motor_manual_bench_capture.v1.json` (`simulated: false`) |
| Golden intake | `examples/intakes/splice_robot_drive_golden_real_brief.json` |

| Piece | Path |
|-------|------|
| Orchestrator | `src/hardware_splicer/golden_real_bench.py` |
| Pin script | `scripts/pin_golden_live_board_evidence.py` |
| Verify | `scripts/verify_splice_real_bench.py` → `make verify-splice-real-bench` |
| SDK | `splice_golden_real()` (no MCP tool yet) |

Refresh live Qwen pin: `make pin-golden-live-evidence` (needs API key, ~$0.0002/call).

### 6. Agent surfaces (primary handoff)

All call into `src/hardware_splicer/sdk.py`:

| Surface | Start |
|---------|-------|
| Python SDK | `from hardware_splicer.sdk import splice_build, splice_golden_loop, …` |
| MCP | `PYTHONPATH=src python -m hardware_splicer.mcp_server` |
| HTTP | `python scripts/hardware_splicer.py serve` |

**Key MCP tools added for splice:**

- `hs_splice_build`, `hs_splice_golden_loop`
- `hs_splice_bench_status`, `hs_splice_bench_submit`, `hs_splice_bench_submit_capture`
- `hs_splice_bench_capture_template`
- `hs_donor_board_vision`, `hs_vision_capabilities`
- `hs_inspect_fab`, `hs_engine_doctor`

### 7. Documentation added this arc

| Doc | Purpose |
|-----|---------|
| `docs/AGENT_HANDOFF.md` | Agent-first operational entry |
| `docs/SPLICE_PRODUCT.md` | Tiers S0–S5, roadmap |
| `docs/DEMO_SPLICE.md` | Walkthrough |
| `docs/SPLICE_BEST_PRACTICES.md` | Operator norms |
| `docs/COMPETITIVE_LANDSCAPE.md` | vs Flux, repair cafés |
| `docs/REAL_WORLD_PARALLELS.md` | Rossmann-style bench, salvage shops |
| `docs/MCP.md` | MCP setup |
| `tests/data/golden/README.md` | Golden artifact contract |

### 8. Circuit synthesis layer (`88f1db8` — Codex)

Bounded planning between NL/intent and the existing netlist compile spine. **Not** arbitrary schematic synthesis — produces `SynthesisCandidate` + blockers, then optionally compiles through `candidate_bridge.py`.

```text
CircuitIntent
  → topology planner (motor, H-bridge, power rail, level shift, sensor, relay, battery, analog)
  → TopologyOperator + Constraint + bench gates
  → SynthesisCandidate
  → operator_lowering → CircuitNetlist → KiCad compile
```

| Planner | Domain |
|---------|--------|
| `motor_driver_planner` | MCU-controlled DC motor / pump / fan |
| `h_bridge_planner` | Reversible DC motor (L298N, DRV8833, TB6612, …) |
| `power_rail_planner` | Buck/LDO rails from catalog |
| `level_shift_planner` | 3.3V ↔ 5V logic |
| `sensor_interface_planner` | I2C / 1-Wire / digital / analog modules |
| `relay_switch_planner` | Low-voltage relay loads (blocks mains) |
| `battery_power_planner` | Li-ion charge + boost + 3.3V paths |
| `analog_conditioning_planner` | Divider + RC filter → ADC |
| `planner.py` | Safe dispatcher — unsupported goals return blocked candidates |

| Surface | Entry |
|---------|-------|
| SDK | `plan_circuit_synthesis()`, `synthesize_circuit()`, per-domain `plan_*_circuit()` |
| HTTP | `POST /v1/circuit-synthesis/plan`, `/compile`, `/capability`, per-domain `/motor-driver`, … |
| MCP | **Wired** — `hs_plan_circuit_synthesis`, `hs_synthesize_circuit`, `hs_clarify_hardware_intent`, `hs_render_project_package` |
| Docs | `docs/CIRCUIT_SYNTHESIS_LAYER_PLAN.md`, `docs/CIRCUIT_LOGIC_AUDIT.md` |
| Tests | `pytest tests/test_circuit_synthesis_*.py tests/test_motor_driver_planner.py tests/test_topology_*.py` |

**Policy:** blocked candidates refuse compile. Ready candidates compile with claim boundaries preserved. Topology authority report via `evaluate_topology_authority()`.

**Not wired yet:** splice manifest cases still use fixture donors + catalog builds — synthesis is a **parallel greenfield path**, not merged into `verify-splice-loop`.

### 9. Project package layer (Blueprint-shaped front-half)

Closes the gap vs Blueprint.am-style **project pages** without copying their closed product. Every splice build and synthesis compile (or plan-only with `out_dir`) can emit a unified package:

| Artifact | Purpose |
|----------|---------|
| `PROJECT_PACKAGE.json` | INFO, BOM, WIRING, INSTRUCTIONS, **GATES** (our differentiator) |
| `PROJECT_PAGE.md` | Human-readable tabbed summary |
| `WIRING_GUIDE.md` | Harness / net wiring steps |
| `ASSEMBLY_GUIDE.md` | Build order + bench checklist |

| Piece | Path |
|-------|------|
| Clarifier | `intent_clarifier.py` — questions for vague goals; `clarification_answers` enrichment |
| Builder | `project_package.py` — `build_project_package()`, `write_project_package_artifacts()` |
| Splice hook | `project_intake.py` — auto-writes on `splice_and_build_from_intake()` |
| Synthesis hook | `circuit_synthesis/candidate_bridge.py` + `synthesize_circuit()` |
| CLI | `scripts/build_project_package.py` |
| Tests | `make test-project-package` → `tests/test_project_package.py` |

| Surface | Entry |
|---------|-------|
| SDK | `clarify_hardware_intent()`, `render_project_package()` |
| HTTP | `POST /v1/intent/clarify`, `POST /v1/project-package/render` |
| MCP | `hs_clarify_hardware_intent`, `hs_render_project_package`, `hs_plan_circuit_synthesis`, `hs_synthesize_circuit` |

**Gate verdicts** map compile DRC, bench session, and blocked synthesis into plain-language statuses (`COMPILE_READY_REVIEW_BENCH`, `BLOCKED`, …).

---

## Maturity snapshot (honest)

| Tier | Meaning | Status |
|------|---------|--------|
| **S0** | Inventory → module suggestion | ✅ |
| **S1** | Splice plan + blocks + evidence gates | ✅ |
| **S2** | DRC-clean carrier compile | ✅ `make verify-splice` |
| **S3** | Bench gates closed with measurements | ✅ golden CI + golden real; **field café = future** |
| **S4** | Mech envelope + field validation | 🟡 parallel apps, not splice-first UX |
| **S5** | Greenfield editor + splice unified | ❌ |

**Do not claim:** field-proven on your own junk pile; Flux-class interactive editor; production repair shop replacement.

---

## Verify matrix (run these to confirm state)

```bash
make setup

# Engine / compile bar
make verify-engine          # 18 catalog builds, KiCad DRC
make verify-tier-c          # Tier C gates
make verify-geometry        # geometry snapshots

# Splice bar
make verify-splice          # S2 — manifest compile cases
make verify-splice-loop     # S3 — 3 cases, simulated bench
make verify-splice-real-bench   # S3 — real photo + manual capture

# Optional live vision
make vision-donor-smoke     # Qwen dry-run on golden photo
make pin-golden-live-evidence   # refresh pinned evidence (API key)

# Circuit synthesis (unit bar)
pytest tests/test_circuit_synthesis_ir.py tests/test_circuit_synthesis_planners.py \
  tests/test_circuit_synthesis_bridge.py tests/test_motor_driver_planner.py \
  tests/test_topology_library.py tests/test_topology_operator_lowering.py
```

Full regression: `make verify` (includes splice + smoke; slower).

---

## Recommended agent flow (post-upgrade)

```text
hs_sdk_info
  → hs_donor_board_vision        # if starting from photo only
  → hs_splice_build              # plan + compile + open bench session
  → hs_splice_bench_capture_template
  → fill capture OR hs_splice_bench_submit
  → hs_splice_bench_submit_capture
  → hs_inspect_fab
```

**CI shortcut:** `hs_splice_golden_loop` (simulated bench).
**Golden real:** SDK `splice_golden_real()` or `make verify-splice-real-bench`.

**Greenfield synthesis (parallel path):**

```text
plan_circuit_synthesis(intent)     # or per-domain plan_h_bridge_circuit, etc.
  → review candidate.blocked / blockers
synthesize_circuit(intent)         # plan + compile if not blocked
  → hs_inspect_fab
```

---

## Key new / changed files (quick map)

```text
src/hardware_splicer/
  sdk.py                    # agent API surface
  golden_loop.py            # S3 simulated loop
  golden_real_bench.py      # S3 real golden path
  splice_bench.py           # bench sessions + gates
  bench_capture_bridge.py   # capture → gate closure
  standard_bench_gates.py   # PSU ramp, thermal
  repair_intake.py          # repair-café fields
  board_vision_salvage.py   # donor vision → salvage
  mcp_server.py             # MCP tools (splice; synthesis not yet)
  circuit_synthesis/        # topology planners + bridge (88f1db8)
  intent_clarifier.py       # vague goal → clarifying questions
  project_package.py        # Blueprint-shaped PROJECT_PACKAGE + guides
  api.py                    # HTTP routes (+ golden loop, bench, netlist, project package)

scripts/
  build_project_package.py
  verify_splice_demos.py
  verify_splice_golden_loop.py
  verify_splice_real_bench.py
  splice_golden_loop.py
  splice_golden_real.py
  pin_golden_live_board_evidence.py

examples/
  splice/manifest.json
  intakes/splice_robot_drive_*.json   # S2, S3, repair, golden real

tests/
  test_golden_loop.py
  test_golden_real_bench.py
  test_golden_live_board_evidence.py
  test_standard_bench_gates.py
  test_circuit_synthesis_*.py
  test_project_package.py
  test_motor_driver_planner.py
  test_topology_*.py
```

---

## What is still open (do not assume done)

| Gap | Notes |
|-----|-------|
| **UI / capture form** | Next phase — bench template is JSON on disk; project page is markdown today |
| **Synthesis → splice merge** | Planners exist; RC golden path still uses fixtures + catalog `robot_drive_base` |
| `hs_splice_golden_real` MCP tool | SDK + make targets only |
| Multi-photo fuse on MCP path | `multi_view_capture.py` exists in Circuit-AI, not wired |
| Serial DMM / PSU auto-fill | Schema ready; no instrument driver |
| Field validation session | Repair café / lab partner — strengthens S3 claim, not required for spine |
| CH340C showcase + splice in one UI | Both exist; unified narrative still manual |

---

## Next phase (agreed direction)

**Splice spine:** done enough — stop extending unless merging synthesis.

**Interface (still primary for humans):**

1. Web form for `BENCH_CAPTURE_TEMPLATE`
2. Bilingual EN / Traditional Chinese demo layer

**Optional backend follow-ups:**

3. Wire `h_bridge_planner` into RC splice intake (replace static fixture assumptions)
4. Static HTML renderer from `PROJECT_PACKAGE.json` (optional)
5. `hs_splice_golden_real` MCP tool

---

## Environment defaults (agents)

```bash
export HARDWARE_SPLICER_AUTOROUTE=0
export HARDWARE_SPLICER_JLC_ENRICH=0
export HARDWARE_SPLICER_DRC_FIX_LOOP=1
# Live Qwen pin refresh:
export VISION_MONTHLY_USD_LIMIT=5
export QWEN_DISABLED=0
```

Call `hs_engine_doctor` before long compile loops.

---

## Related docs (read order)

1. **This file** — what changed
2. [`BLUEPRINT_POSITIONING_AND_FUNDING.md`](BLUEPRINT_POSITIONING_AND_FUNDING.md) — **why HS is not dead vs Blueprint; Taiwan funding + competition plan**
3. [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) — how to drive it
4. [`SPLICE_PRODUCT.md`](SPLICE_PRODUCT.md) — product tiers and roadmap
5. [`ENGINE_DONE.md`](ENGINE_DONE.md) — compile engine completion gates
6. [`CIRCUIT_SYNTHESIS_LAYER_PLAN.md`](CIRCUIT_SYNTHESIS_LAYER_PLAN.md) — synthesis planners + status
7. May baseline: [`HANDOFF_CIRCUIT_AI_HARDWARE_SPLICER_2026-05-24.md`](../apps/circuit-ai/docs/HANDOFF_CIRCUIT_AI_HARDWARE_SPLICER_2026-05-24.md)
