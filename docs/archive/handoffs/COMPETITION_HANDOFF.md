# Competition handoff — judges & reviewers (5 minutes)

**Full proposal:** [`COMPETITION_PROPOSAL.md`](COMPETITION_PROPOSAL.md)  
**YZU 提案結果:** 2026 提案階段未入圍 — [`competition/YZU_AI_Agent_2026_提案回顧與學習.md`](competition/YZU_AI_Agent_2026_提案回顧與學習.md)  
**Strategy / funding / vs Blueprint:** [`BLUEPRINT_POSITIONING_AND_FUNDING.md`](BLUEPRINT_POSITIONING_AND_FUNDING.md)  
**Agent / developer entry:** [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md)

---

## One sentence

**Hardware Splicer** splices real donor hardware: vision proposes salvage blocks, KiCad compiles a carrier board, and **bench measurements** (not AI alone) authorize power-on.

---

## What to run (no UI required)

```bash
make setup
make doctor                    # optional: runtime check

# S2 — compile bar (2 manifest cases, KiCad DRC)
make verify-splice

# S3 — full agent loop with simulated bench (CI)
make verify-splice-loop

# S3 — golden REAL path: Wikimedia photo + live Qwen pin + manual bench capture
make verify-splice-real-bench
```

Expected: all commands exit 0. Reports under `/tmp/hs_splice_*`.

---

## What each verify proves

| Command | Proves |
|---------|--------|
| `verify-splice` | Donor fixture → splice plan → **DRC-clean carrier** |
| `verify-splice-loop` | Vision junk + **bench gate closure** (simulated readings in CI) |
| `verify-splice-real-bench` | Real photo + **hand-filled** capture (`simulated: false`) → `power_on_authorized` |

---

## Golden artifacts (inspect on disk)

```
tests/data/golden/
  rc_toy_motor_board.jpg              # real donor photo (CC BY-SA)
  rc_toy_live_board_evidence.json     # pinned Qwen VL output
  rc_toy_live_board_evidence.meta.json
  rc_motor_manual_bench_capture.v1.json   # operator bench session
```

Intake: `examples/intakes/splice_robot_drive_golden_real_brief.json`

---

## Agent demo (MCP / SDK)

```bash
pip install -r requirements-mcp.txt
PYTHONPATH=src python -m hardware_splicer.mcp_server
```

Key tools: `hs_sdk_info` → `hs_splice_build` → `hs_splice_bench_capture_template` → `hs_splice_bench_submit_capture`

One-shot: `hs_splice_golden_loop` (simulated bench) or SDK `splice_golden_real()` / `make splice-golden-real` (real photo path).

---

## Truth model (do not skip)

| Check | Means | Does NOT mean |
|-------|-------|----------------|
| KiCad `drc_pass` | New **carrier** board is electrically consistent | Donor harness is safe |
| `board_evidence` | Vision **candidates** | Verified pinout |
| `power_on_authorized` | Critical **bench gates** closed | Fab-ready for production |

---

## Maturity (honest)

| Tier | Status |
|------|--------|
| S2 compile | **Proven** in CI |
| S3 bench model | **Proven** in golden paths; field café session = future |
| UI | **Next phase** |
| vs Flux editor | **Different niche** — salvage, not greenfield |

---

## Competitive position (30 seconds)

- **Flux:** browser ECAD + AI for **new** boards
- **Hardware Splicer:** headless **donor splice** + bench provenance + **agents first**
- **Repair cafés:** informal checklists → we encode as JSON gates + capture packets

---

## What we do NOT claim yet

- Field-proven on a builder's personal junk pile
- Better than Flux for interactive layout
- Production repair shop replacement
- UI polish (deferred to interface phase)

---

## Architecture (one diagram)

```text
┌─────────────────────────────────────────────────────────┐
│  INTAKE: goal, parts, repair_intake, donor board        │
└───────────────────────────┬─────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────┐
│  VISION: Qwen VL → board_evidence.v1 (candidate)        │
└───────────────────────────┬─────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────┐
│  PLAN: functional_salvage → SPLICE_PLAN + BRINGUP_CARD  │
└───────────────────────────┬─────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────┐
│  COMPILE: KiCad carrier + DRC (S2)                      │
└───────────────────────────┬─────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────┐
│  BENCH: gates → capture template → submit → power_on    │
└─────────────────────────────────────────────────────────┘
         ▲                              │
         └──────── SDK / MCP / HTTP ────┘
```

---

## Next phase (competition period)

1. Measurement capture **web UI**
2. Bilingual demo
3. CH340C authority showcase + splice golden in one story
4. Optional: one repair-café measured session

---

## Contact / fill-ins

| Field | Value |
|-------|-------|
| Applicant | `<fill in>` |
| Repo root | `Hardware-Splicer/` |
| Primary docs | `docs/COMPETITION_PROPOSAL.md`, `docs/AGENT_HANDOFF.md` |
