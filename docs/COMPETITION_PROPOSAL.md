# Competition proposal — Hardware Splicer (Circuit.AI family)

**Updated:** June 2026
**Status:** Spine complete for agent-first demo; **UI phase next**
**Canonical agent entry:** [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md)
**Judge / reviewer quick start:** [`COMPETITION_HANDOFF.md`](COMPETITION_HANDOFF.md)

---

## Project title

**Hardware Splicer:** an evidence-gated AI agent for donor board understanding, functional reuse, carrier PCB compile, and bench-validated bring-up.

## Applicant (fill in)

| Field | Value |
|-------|-------|
| Applicant name | `<fill in>` |
| School / department | `<fill in>` |
| Student ID | `<fill in>` |
| Email | `<fill in>` |
| Team size | solo |

---

## Abstract

Hardware Splicer helps turn **unknown or partially documented donor hardware** into reusable engineering assets with **auditable safety gates**. Unlike a PCB image labeler or a greenfield ECAD copilot, the system runs a full loop:

**donor evidence → splice plan → KiCad carrier compile → bench measurement closure → power-on authorization**

Vision (Qwen VL) produces **candidate** `board_evidence`; only structured **bench_topology_capture** closes evidence gates. KiCad DRC validates the **new** carrier board — it does not imply donor harness safety.

The June 2026 prototype is **agent-first** (Python SDK, MCP, HTTP): judges and collaborators can drive the splice product without a custom UI. A **golden real S3 path** demonstrates a real donor photo, live-pinned Qwen output, and hand-authored bench capture — without requiring the builder to own junk hardware.

**Next phase (post-spine):** bilingual measurement/capture **interface** on top of the existing artifact model.

---

## Problem

Electronics repair and reuse fail when useful functions on a board are hard to identify **safely**:

- Undocumented connectors and voltage domains
- Missing schematics and incomplete labels
- Visual AI that overstates confidence
- Greenfield ECAD tools (e.g. Flux) that do not model **donor dissection** or **bench provenance**

Students, makerspaces, and repair cafés can *see* parts but lack a disciplined path from observation → measurement plan → splice contract → safe energize.

---

## Proposed solution

### Three levels of truth

| Level | Source | Authorizes |
|-------|--------|------------|
| **Candidate** | Photos, OCR, Qwen VL, markings, public refs | Measurement queue only |
| **Measured** | DMM, PSU, continuity, thermal, capture JSON | Bench gate closure |
| **Release** | All critical gates closed + scoped claim | `power_on_authorized` |

### Splice spine (product wedge)

```text
PROJECT_INTAKE (+ repair_intake symptoms)
  → donor board_evidence / Qwen vision → functional_salvage blocks
  → SPLICE_PLAN + BRINGUP_CARD
  → splice-build → KiCad carrier (DRC-clean, S2)
  → SPLICE_BENCH_SESSION + BENCH_CAPTURE_TEMPLATE
  → bench_topology_capture submit → power_on_authorized (S3)
```

### What makes this different from Flux-class ECAD

| | Flux / greenfield ECAD | Hardware Splicer |
|--|------------------------|----------------|
| Starting point | Blank schematic | **Donor hardware** |
| Validity | In-editor ERC/DRC | Carrier DRC **+** donor bench gates |
| Agent surface | Browser copilot | **SDK / MCP / HTTP** + disk artifacts |
| Wedge | New board design | **Salvage → splice → carrier** |

See [`COMPETITIVE_LANDSCAPE.md`](COMPETITIVE_LANDSCAPE.md) and [`REAL_WORLD_PARALLELS.md`](REAL_WORLD_PARALLELS.md).

---

## Current prototype state (June 2026 — honest)

### Maturity tiers

| Tier | Capability | Status |
|------|------------|--------|
| **S0** | Inventory → module suggestion | ✅ |
| **S1** | Splice plan, blocks, evidence gates | ✅ |
| **S2** | DRC-clean carrier compile | ✅ `make verify-splice` |
| **S3** | Bench sessions + capture closure | ✅ plumbing + golden paths |
| **S4** | Mech envelope + field validation | 🟡 parallel apps, not splice-first UX |
| **S5** | Greenfield editor + splice unified | ❌ future |

**Honest bar:** **S2 is CI-proven.** **S3 is architecturally complete** with golden artifacts; field validation on community junk is a **future** partner step, not a blocker for the spine demo.

### Verification commands (reproducible)

```bash
make setup
make verify-splice              # S2 — all manifest compile cases
make verify-splice-loop         # S3 — simulated bench closure (CI)
make verify-splice-real-bench   # S3 — real photo + manual capture (not simulator)
make vision-donor-smoke         # Qwen dry-run on golden photo
```

### Golden artifacts (builder-without-junk)

| Artifact | Role |
|----------|------|
| `tests/data/golden/rc_toy_motor_board.jpg` | Real RC donor photo (Wikimedia, CC BY-SA) |
| `tests/data/golden/rc_toy_live_board_evidence.json` | **Live Qwen** output pinned (~$0.0002/call) |
| `tests/data/golden/rc_motor_manual_bench_capture.v1.json` | Hand-filled bench capture (`simulated: false`) |
| `examples/intakes/splice_robot_drive_golden_real_brief.json` | End-to-end golden intake |

### Agent surfaces (primary handoff)

| Surface | Entry |
|---------|-------|
| **Docs** | [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) |
| **MCP** | `python -m hardware_splicer.mcp_server` — `hs_splice_build`, `hs_splice_golden_loop`, … |
| **SDK** | `hardware_splicer.sdk` — `splice_build`, `splice_golden_real`, … |
| **HTTP** | `POST /v1/splice-and-build`, `/v1/splice-golden-loop`, `/v1/splice-bench/*` |

### Circuit-AI layer (parallel)

Production authority casefiles, CH340C showcase, bilingual frontend experiments live under `apps/circuit-ai/`. The **competition spine** for splice + bench is unified in `src/hardware_splicer/` with board vision imported from Circuit-AI's Qwen module.

---

## AI agent design

### 1. Visual and reference intake

- `board_evidence.v1` from fixtures, embedded JSON, or **Qwen VL** (`pin_golden_live_board_evidence.py`)
- `repair_intake` — symptoms, when-it-fails, device hint (repair-café model)
- Policy: **vision alone does not authorize power-on**

### 2. Splice planning

- `functional_salvage.v1` → reusable blocks, extractability classes, missing evidence
- `SPLICE_PLAN.json` — harness reuse, do-not-connect-until, required measurements

### 3. Carrier compile (external truth)

- Headless KiCad ERC/DRC on **new** carrier
- `DESIGN_QUALITY.json`, `fab_recommendation` — honest preview copper by default

### 4. Bench authority

- Auto gates: voltage, continuity, **PSU current-limit ramp** (Rossmann-style), optional thermal
- `BENCH_CAPTURE_TEMPLATE.json` → operator or agent fills → `submit_bench_capture`
- `power_on_authorized` only when critical gates close

### 5. Model role

| Model | Use | Cannot do |
|-------|-----|-----------|
| Qwen VL | Board photo → candidates | Close gates or authorize power |
| LLM (compose/intake) | Planning assistance | Replace KiCad DRC |
| Deterministic gates | Block unsafe claims | — |

---

## Demonstration scenarios

### A. Primary — RC golden real S3 (agent-driven)

1. Intake with repair symptoms + golden photo + pinned live Qwen evidence
2. `make verify-splice-real-bench` or SDK `splice_golden_real()`
3. Artifacts: `SPLICE_PLAN.json`, carrier KiCad, `SPLICE_BENCH_SESSION.json`, manual capture
4. Show `power_on_authorized: true` only after capture submit

### B. Secondary — manifest S2 cases

- `robot_drive_from_rc_toy` — fixture donor → `robot_drive_base`
- `printer_motion_stage` — inkjet motion salvage

### C. Circuit-AI authority showcase (legacy competition thread)

- CH340C USB-serial board: visual-only → blocked; measured topology → scoped release
- Route: `apps/circuit-ai` showcase / `POST /hardware/production-casefile/run`

---

## July–August development plan (revised)

### Completed in prototype phase (pre-interface)

- [x] Agent-first SDK / MCP / HTTP splice + bench
- [x] Golden loop CI (`verify-splice-loop`)
- [x] Golden **real** S3 (photo + live Qwen pin + manual capture)
- [x] Repair-café intake fields + Rossmann-style PSU/thermal gates
- [x] Competitive + real-world parallel documentation

### Planned for competition period (interface phase)

1. **Measurement / capture UI** — web form for `BENCH_CAPTURE_TEMPLATE` (not raw JSON)
2. **Bilingual EN / Traditional Chinese** demo layer
3. **Multi-photo intake** — fuse `multi_view_capture` into MCP path
4. **CH340C + RC dual demo** — authority casefile + splice golden in one narrative
5. **One external validation** — repair café or lab session (optional; strengthens S3 claim)
6. Demo video + architecture diagram for judges

### Token subsidy use

- Qwen VL on donor photos (golden pin refresh, case corpus)
- Structured reasoning over evidence packets
- UI copy and bilingual refinement
- **Not** spent on claiming field-proven repair without measured sessions

---

## Expected deliverables

| Deliverable | Status |
|-------------|--------|
| Agent handoff docs | ✅ [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md), [`MCP.md`](MCP.md) |
| Headless splice compile (S2) | ✅ `verify-splice` |
| Bench gate model (S3) | ✅ sessions + capture bridge |
| Golden real path | ✅ `verify-splice-real-bench` |
| Live Qwen pin workflow | ✅ `make pin-golden-live-evidence` |
| Live frontend demo | 🔜 interface phase |
| Bilingual UI | 🔜 interface phase |
| 10+ measured board sessions | 🔜 partner / competition period |
| Demo video | 🔜 |

---

## Evaluation metrics

- Refuses unsafe claims when only vision is present
- Converts vision into **actionable measurement tasks**
- Measured capture **changes** `power_on_authorized` correctly
- KiCad DRC pass does **not** auto-authorize donor power-on
- Agent can run full loop without UI
- Artifacts are auditable on disk (git-friendly JSON)

---

## Fit for semiconductor / AI-agent competition

The project applies AI agents to **physical electronics workflow**: board understanding, reuse planning, headless compile, and bench-gated bring-up. It is not a chatbot — it is an **agentic engineering spine** with evidence gates and verifiable state transitions.

Suitable for token subsidy: Qwen VL directly improves donor-photo interpretation; progress is **measurable** via golden pin + gate closure tests.

---

## Risks and safety

- Visual evidence cannot authorize power-on or splice alone
- High-voltage / unknown-power regions remain gated
- `psu_current_limit_ramp` encodes conservative first-energize practice
- Model output is advisory until deterministic gates close
- UI (when built) will surface blockers and claim boundaries

---

## Documentation index

| Doc | Audience |
|-----|----------|
| [`COMPETITION_HANDOFF.md`](COMPETITION_HANDOFF.md) | Judges — 5-minute demo path |
| [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) | Agents / developers |
| [`SPLICE_PRODUCT.md`](SPLICE_PRODUCT.md) | Product tiers, roadmap |
| [`DEMO_SPLICE.md`](DEMO_SPLICE.md) | 10-minute walkthrough |
| [`COMPETITIVE_LANDSCAPE.md`](COMPETITIVE_LANDSCAPE.md) | vs Flux, repair, salvage |
| [`SPLICE_BEST_PRACTICES.md`](SPLICE_BEST_PRACTICES.md) | Operator + engineering norms |
| [`tests/data/golden/README.md`](../tests/data/golden/README.md) | Golden artifact contract |

---

## Summary

Hardware Splicer makes donor hardware **legible, plannable, compilable, and bench-gated**. The June 2026 prototype delivers an **agent-native spine** with honest validity separation (vision vs bench vs KiCad). The competition period focuses on **interface and presentation** atop this foundation — not on reinventing the compile or gate model.
