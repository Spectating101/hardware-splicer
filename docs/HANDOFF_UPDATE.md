# Handoff update — what changed since last time

**Date:** June 2026
**Audience:** You, ChatGPT, or the next agent — continuity without re-reading the whole repo
**Operational entry:** [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md)
**Previous baseline:** [`apps/circuit-ai/docs/HANDOFF_CIRCUIT_AI_HARDWARE_SPLICER_2026-05-24.md`](../apps/circuit-ai/docs/HANDOFF_CIRCUIT_AI_HARDWARE_SPLICER_2026-05-24.md) (Circuit-AI salvage focus; pre-unified splice spine)

---

## One-paragraph delta

Since the May handoff, the repo grew a **unified headless compiler** (`src/hardware_splicer/`, ~70 modules), then a **splice product spine** (donor → plan → KiCad carrier → bench gates), then **agent surfaces** (SDK / MCP / HTTP), then **S3 golden verification** (simulated CI loop + real-photo path with pinned Qwen evidence). The honest bar moved from “compile demos work” to “**S2 proven in CI, S3 proven in golden paths**.” UI is explicitly **not** done — next phase.

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
  mcp_server.py             # MCP tools
  api.py                    # HTTP routes (+ golden loop, bench, netlist)

scripts/
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
```

---

## What is still open (do not assume done)

| Gap | Notes |
|-----|-------|
| **UI / capture form** | Next phase — bench template is JSON on disk today |
| `hs_splice_golden_real` MCP tool | SDK + make targets only |
| Multi-photo fuse on MCP path | `multi_view_capture.py` exists in Circuit-AI, not wired |
| Serial DMM / PSU auto-fill | Schema ready; no instrument driver |
| Field validation session | Repair café / lab partner — strengthens S3 claim, not required for spine |
| CH340C showcase + splice in one UI | Both exist; unified narrative still manual |

---

## Next phase (agreed stop point)

**Stop adding backend spine.** Next work is **interface**:

1. Web form for `BENCH_CAPTURE_TEMPLATE` (measurements, PSU ramp rows, thermal)
2. Bilingual EN / Traditional Chinese demo layer
3. Optional: wire `hs_splice_golden_real` into MCP for parity

Competition copy / HTML — out of scope for this repo handoff (user handles via ChatGPT).

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
2. [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) — how to drive it
3. [`SPLICE_PRODUCT.md`](SPLICE_PRODUCT.md) — product tiers and roadmap
4. [`ENGINE_DONE.md`](ENGINE_DONE.md) — compile engine completion gates
5. May baseline: [`HANDOFF_CIRCUIT_AI_HARDWARE_SPLICER_2026-05-24.md`](../apps/circuit-ai/docs/HANDOFF_CIRCUIT_AI_HARDWARE_SPLICER_2026-05-24.md)
