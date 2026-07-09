# Agent dry-run checklist — zero verbal help

**Purpose:** Prove the public install + agent spine without author hand-holding.  
**Primary path today:** **cold-internal** (maintainer on a second machine / fresh archive — treat yourself as a stranger).  
**External strangers:** welcome when available; not required to raise the bar.

**Time budget:** 15 minutes (offline) · 20 minutes (with Qwen curl 3)

---

## Cold-internal rules (external proxy)

1. Use a **fresh** tree: `git archive` / alien deploy / clean clone — not your dirty optiplex checkout.
2. Follow **only** [`AGENT_QUICKSTART.md`](AGENT_QUICKSTART.md) + this checklist. No Slack, no “just set X”.
3. If blocked, write the failure into an install report (or GitHub issue) **before** fixing from memory.
4. Pass = automated `scripts/agent_quickstart_verify.sh` **and** a filled `INSTALL_REPORT_<host>_<date>.md`.

**Alien shortcut (from optiplex):** `bash scripts/deploy_alien_quickstart.sh v1.1.0-alpha.16`  
**With Qwen on alien:** `HS_ALIEN_QWEN=1 bash scripts/deploy_alien_quickstart.sh v1.1.0-alpha.16`

---

## Prerequisites (you must have)

- [ ] Linux or WSL2 with Python 3.11+
- [ ] KiCad 9+ CLI (`kicad-cli --version`)
- [ ] Node 18+ and npm
- [ ] Git
- [ ] (Optional) `QWEN_API_KEY` in `.env.local` for AI phrase path

---

## Steps — follow [`AGENT_QUICKSTART.md`](AGENT_QUICKSTART.md) only

| # | Action | Pass criterion |
|---|--------|----------------|
| 1 | Clone `https://github.com/Spectating101/hardware-splicer.git` | Repo on disk |
| 2 | `bash scripts/install_splice_v1.sh` | Exit 0 |
| 3 | `source .venv/bin/activate && hs-doctor` | `ok=True` |
| 4 | Start API per quickstart | `/health` → `"ok": true` |
| 5 | Curl 1 — module catalog | `count` ≥ **50** |
| 6 | Curl 2 — canvas agent-loop | `agent_loop.resolved=true`, `final_kicad_drc_errors=0`, `project_package` present |
| 7 | Curl 2b — salvage `donor_context` agent-loop | `mode=salvage_catalog`, `build_id=robot_drive_base`, 0 DRC, `salvage_package` + `project_package` |
| 8 | (Optional) Curl 3 — Qwen phrase | `qwen_configured=true`, 0 DRC errors |
| 9 | Async job — `POST /v1/jobs/compose-agent-loop` + poll result | `ok=true`, package present |
| 10 | `POST /v1/compose/bench-loop` salvage + `simulate_bench` | `bench_loop.passed=true`, `power_on_authorized=true`, 0 DRC |
| 11 | `POST /v1/splice-bench/vision-assist` on open gates + golden photo | `ok=true`, `gates_unchanged=true`, draft present, **not** power-on |
| 12 | `scripts/splice_golden_real.py` (manual capture JSON) | `passed=true`, `simulated=false`, `power_on_authorized=true` |
| 12b | `scripts/public_web_bench_capture.py` (Wikimedia DMM photos) | `passed=true`, `public_web_is_not_this_board=true` |
| 13 | `POST /v1/donor-board-vision` offline | `applied_board_count≥1`, `functional_salvage` blocks |
| 14 | Copper honesty (autoroute off) | `copper_tier` preview/placement; `fabrication_ready` not true |
| 15 | (Keyed) Live photo → donor-board-vision | `mode=live`, blocks ≥1 |
| 16 | (Keyed) Live vision-assist | `live=true`, `gates_unchanged` |

**Automated equivalent:** `bash scripts/agent_quickstart_verify.sh` (steps 1–5e; Qwen + live vision auto when `.env.local` present).

**Operator real-bench (live DMM):** [`REAL_BENCH_OPERATOR.md`](REAL_BENCH_OPERATOR.md)

**Alien shortcut (from optiplex):** `bash scripts/deploy_alien_quickstart.sh v1.1.0-alpha.16`  
**With Qwen + live vision on alien:** `HS_ALIEN_QWEN=1 bash scripts/deploy_alien_quickstart.sh v1.1.0-alpha.16`

---

## Record results

Copy [`INSTALL_REPORT_TEMPLATE.md`](INSTALL_REPORT_TEMPLATE.md) → `INSTALL_REPORT_<hostname>_<date>.md` and fill:

- Wall time (minutes)
- Git tag tested
- Pass/fail per step
- Manual fixes required (if any)

---

## Fail criteria → report only these

Do **not** ask for help first. File what blocked you:

1. Install script failure (paste `hs-doctor` output)
2. API won't start
3. Agent-loop not resolved or DRC errors > 0
4. Missing `project_package`

Cosmetic `copper_tier: cosmetic_preview` with **0 DRC errors** is **not** a failure.

---

## Maintainer triage

| Blocker | Likely fix |
|---------|------------|
| Clone hangs on lab network | `git archive` + `scp` (see FGEDHGV install report) |
| Catalog count < 50 | Old tag — use `main` or latest alpha |
| Qwen not configured | Expected on offline path; skip curl 3 |
| Async job timeout | Increase poll; check KiCad on PATH |
