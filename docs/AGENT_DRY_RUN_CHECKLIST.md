# Agent dry-run checklist — zero verbal help

**Purpose:** External operator or agent proves Phase 0 without author assistance.  
**Time budget:** 15 minutes (offline) · 20 minutes (with Qwen curl 3)

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
| 10 | (Optional) `POST /v1/compose/bench-loop` salvage + `simulate_bench` | `bench_loop.submitted_capture=true`, 0 DRC |

**File blockers:** [`EXTERNAL_DRY_RUN_ISSUE_GUIDE.md`](EXTERNAL_DRY_RUN_ISSUE_GUIDE.md)

**Alien shortcut (from optiplex):** `bash scripts/deploy_alien_quickstart.sh v1.1.0-alpha.11`

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
