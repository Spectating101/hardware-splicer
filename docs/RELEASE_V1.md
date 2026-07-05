# Release v1.0 — finish line & deployment

**Purpose:** Stop infinite “demo mode.” Ship **one finished product** you can tag, deploy, and walk away from (maintenance-only) until you deliberately start v2.

**Status (July 2026):** **v1.0.1** packaging polish on **v1.0.0** engine. Git tag `v1.0.1` after doc/deploy pass. GitHub **splice-v1** CI job proves the product bar on push.

**Product name (ship as):** **Hardware-Splicer Splice Agent v1.0**  
**One sentence:** Donor intake → splice plan → KiCad carrier compile → bench gates → PROJECT_PACKAGE — with a **real web UI**, plus CLI/MCP/HTTP for agents.

**Not in v1.0:** Flux editor, Blueprint consumer UI, full Circuit-AI frontend, mech splice product, field café validation, open-ended NL parity, cloud SaaS accounts.

---

## 1. What “done” means

v1.0 is **done** when all of these are true:

| # | Gate | Verify |
|---|------|--------|
| 1 | **S2 compile** — manifest splice cases pass KiCad DRC | `make verify-splice` → exit 0 |
| 2 | **S3 bench** — golden loop closes gates in CI | `make verify-splice-loop` → exit 0 |
| 3 | **S3 real** — golden real bench path passes | `make verify-splice-real-bench` → exit 0 |
| 4 | **Project package** — artifacts emit on splice build | `make test-project-package` → exit 0 |
| 5 | **Full test suite** — no regressions | `make test` → exit 0 |
| 6 | **Install story** — stranger can run from README in &lt;30 min | peer or past-you follows `docs/SETUP.md` |
| 7 | **Four surfaces documented** | CLI + MCP + HTTP + **splice-ui** with copy-paste commands |
| 8 | **Git tag** | `v1.0.0` on `main` | ✅ |
| 9 | **Release notes** | `RELEASE_NOTES_v1.0.md` — what’s in / out | ✅ |
| 10 | **Deployment artifact** | `install_splice_v1.sh` + `requirements-splice-v1.txt` | ✅ |
| 11 | **GitHub CI (splice bar)** | `splice-v1` job in `.github/workflows/hardware-splicer.yml` | ✅ |

You do **not** need for v1.0:

- Competition win  
- Paying customer  
- Pretty web gallery *(full Circuit-AI canvas — not required; **splice-ui** is the v1 product UI)*
- Synthesis merged into every splice case  
- PyPI publish (optional nice-to-have)

---

## 2. Product boundary (call it a day here)

### IN — the shippable surface

```text
src/hardware_splicer/          # engine + sdk + mcp + api
scripts/hardware_splicer.py    # CLI entry
examples/splice/manifest.json  # supported splice cases
examples/intakes/splice_*.json # golden intakes
docs/AGENT_HANDOFF.md          # operator manual
docs/DEMO_SPLICE.md            # human walkthrough
mcp/hardware-splicer.mcp.json  # MCP config sample
```

**Capabilities shipped:**

- `splice_build` / `hs_splice_build`
- `splice_golden_loop` / bench status / submit / capture
- `inspect_fab`, `engine_doctor`, `sdk_info`
- `clarify_hardware_intent`, `render_project_package`
- Bounded `plan_circuit_synthesis` / `synthesize_circuit`
- Outputs: KiCad dir, `PROJECT_PACKAGE.json`, `SPLICE_BENCH_SESSION.json`, casefiles

### OUT — explicitly future / separate repos or v2

| Area | Status |
|------|--------|
| `apps/circuit-ai/circuit-ai-frontend/` | Separate app; not v1 blocker |
| `apps/mecha-splicer/`, `apps/3d-splicer/` | S4; not v1 |
| Consumer Blueprint UI | v2 or never |
| FreeRouting default on | deferred per `LAUNCH_PLAN.md` |
| Multi-tenant cloud auth | v2 |
| YZU competition narrative | archived — see `competition/YZU_AI_Agent_2026_提案回顧與學習.md` |

---

## 3. Deployment options (pick one primary)

### Option A — **Source release** (simplest, recommended)

**What:** Tagged GitHub release + documented install. User brings KiCad 9 + Python 3.12.

```bash
git clone …
make setup
make doctor
make verify-splice-loop
PYTHONPATH=src python scripts/hardware_splicer.py serve --port 8787
```

**Finish tasks:**

- [ ] Pin `requirements.txt` versions tested on release
- [ ] `RELEASE_NOTES_v1.0.md`
- [ ] GitHub Release with asset: golden demo output zip (optional)
- [ ] README “Quick start” ≤ 10 commands

**Good for:** portfolio, self-host, MCP in Cursor, no ops burden.

---

### Option B — **Docker API** (finishable in ~1 week)

**What:** One container with Python deps + **documented** host KiCad mount (KiCad in Docker is heavy; honest approach: API container + `kicad-cli` on host via volume).

```text
docker compose up api   # FastAPI on :8787
# KICAD_CLI on host or sidecar — document clearly
```

**Finish tasks:**

- [ ] `Dockerfile` + `docker-compose.yml` (API only)
- [ ] `docs/DEPLOY.md` — env vars, volume mounts, limits
- [ ] Health check: `GET /health` + `hs_engine_doctor` json

**Good for:** “it’s deployed,” remote agents, demo server.

---

### Option C — **MCP-only distribution**

**What:** v1.0 = MCP server + config snippet; no public HTTP.

**Finish tasks:**

- [ ] `docs/MCP.md` complete tool list (already mostly done)
- [ ] `mcp/hardware-splicer.mcp.json` tested in Cursor
- [ ] One-page “install MCP” in README

**Good for:** agent developers; smallest surface.

---

**Recommendation:** **A + C** together (source release + MCP). Add **B** only if you want a public URL.

---

## 4. Release checklist (execution order)

### Week 1 — Freeze scope

- [ ] Read this doc; agree v1.0 = Splice Agent only
- [ ] Run full verify bar (all commands in §1)
- [ ] Fix any red CI / flaky tests
- [ ] Remove or mark WIP anything that breaks `make doctor` on clean machine

### Week 2 — Packaging

- [ ] Add `src/hardware_splicer/__version__ = "1.0.0"`
- [ ] `sdk_info()` reports version
- [ ] Write `RELEASE_NOTES_v1.0.md`
- [ ] Trim README to v1.0 story (splice + gates + agent); move rest to docs/
- [ ] Optional: 3–5 min release video (screen recording)

### Week 3 — Deploy artifact

- [ ] Pick Option A/B/C
- [ ] If Docker: compose + DEPLOY.md
- [ ] Tag `v1.0.0`, GitHub Release
- [ ] Update `BLUEPRINT_POSITIONING_AND_FUNDING.md` → “v1.0 shipped; maintenance mode”

### Week 4 — Call it a day

- [ ] One external smoke test (friend machine or fresh VM)
- [ ] Archive open ambitions in `docs/ROADMAP_v2.md` (backlog only)
- [ ] **Stop** feature work unless bugfix

---

## 5. What you tell the world

**Elevator (EN):**

> Hardware-Splicer v1.0 is a headless splice agent: donor intake → carrier KiCad compile → bench gates → auditable project package. MCP, HTTP, and CLI. Proven in CI.

**電梯（中文）:**

> Hardware-Splicer v1.0：捐贈板／零件 intake → 拼接規劃 → KiCad 載板編譯 → 量測閘門 → 可稽核專案包。支援 MCP／HTTP／CLI，CI 驗證通過。

**Honest limits (always say):**

- Cosmetic copper by default  
- KiCad DRC ≠ donor harness safety until bench gates close  
- Not a browser ECAD competitor  

---

## 6. After v1.0 — maintenance vs v2

| Mode | Rule |
|------|------|
| **Maintenance** | Bugfixes, KiCad version bumps, dependency security |
| **v2** | Only if you **choose** a new bet: hosted SaaS, semi Test-Ready costume, or synthesis-splice merge |

No guilt for stopping after v1.0. A tagged, deployable, CI-green agent compiler **is** a finished project.

**Commercial assessment:** [`MONETIZATION_AND_PRODUCT_ASSESSMENT.md`](MONETIZATION_AND_PRODUCT_ASSESSMENT.md) — buyers, models, pricing hypotheses, risks, fill-in workbook.  
**Documentation map:** [`DOCUMENTATION_INDEX.md`](DOCUMENTATION_INDEX.md) — all repo docs, gaps, canonical order.

---

## 7. Related docs

| Doc | Role |
|-----|------|
| [`SPLICE_PRODUCT.md`](SPLICE_PRODUCT.md) | S0–S5 tiers — v1.0 = **S2+S3 proven** |
| [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) | Runbook |
| [`LAUNCH_PLAN.md`](LAUNCH_PLAN.md) | Engine phases A–C (already met) |
| [`BLUEPRINT_POSITIONING_AND_FUNDING.md`](BLUEPRINT_POSITIONING_AND_FUNDING.md) | Strategy after competition |
| [`SETUP.md`](SETUP.md) | Install |

---

## 8. Decision log

| Date | Decision |
|------|----------|
| 2026-06 | YZU proposal not shortlisted — pivot from competition funding to **shippable v1.0** |
| 2026-06 | v1.0 product = **Splice Agent** (headless), not full monorepo UI |
