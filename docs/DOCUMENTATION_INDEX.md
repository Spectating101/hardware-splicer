# Documentation index — Hardware-Splicer repo

**Purpose:** Map **all documentation**, say what is **canonical**, what is **legacy**, what is **missing for v1.0**, and **which doc to read for which job**.

**Rule:** If two docs disagree, precedence is:

1. [`ENGINE_DONE.md`](ENGINE_DONE.md) — engine completion / terms  
2. [`SPLICE_PRODUCT.md`](SPLICE_PRODUCT.md) — splice product tiers  
3. [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) — how to run (agents)  
4. [`HANDOFF_UPDATE.md`](HANDOFF_UPDATE.md) — what changed recently  
5. Everything else  

---

## 1. Documentation health (honest assessment)

| Dimension | Grade | Notes |
|-----------|-------|-------|
| **Technical depth** | **A** | Engine, splice, synthesis, gates well documented |
| **Agent operability** | **A-** | `AGENT_HANDOFF`, `MCP.md`, SDK surfaces |
| **Single entry point** | **B-** | README long; this index fixes navigation |
| **v1.0 product clarity** | **A-** | Quickstart, support/liability, ops runbook — v1.0.1 |
| **Beginner onboarding** | **B+** | `QUICKSTART_SPLICE_v1` + `SETUP` |
| **Chinese B2B** | **C+** | Competition docs 中文; product docs mostly EN |
| **API reference** | **C** | Scattered in `api.py` / `sdk.py`; no OpenAPI single page |
| **Monorepo coherence** | **C** | `apps/circuit-ai/docs/` parallel universe |
| **Stale / duplicate risk** | **Medium** | `COMPETITION_PROPOSAL`, `LAUNCH_PLAN`, long README |

**Bottom line:** Documentation is **strong for builders and agents**, **weaker for customers and strangers**. Good enough to **ship v1.0** after a small **index + trim** pass — not good enough for mass self-serve SaaS without more work.

---

## 2. Start here (by audience)

### GitHub / ChatGPT / external reviewer

| Read | Why |
|------|-----|
| [`GITHUB_START_HERE.md`](GITHUB_START_HERE.md) | **Single landing page** — links to all canonical docs on GitHub |

### You (founder) — strategy & ship

| Read | Why |
|------|-----|
| [`RELEASE_V1.md`](RELEASE_V1.md) | Finish line, tag, deploy |
| [`MONETIZATION_AND_PRODUCT_ASSESSMENT.md`](MONETIZATION_AND_PRODUCT_ASSESSMENT.md) | Buyers, pricing, risks, workbook |
| [`BLUEPRINT_POSITIONING_AND_FUNDING.md`](BLUEPRINT_POSITIONING_AND_FUNDING.md) | vs Blueprint, Taiwan funding |
| [`competition/YZU_AI_Agent_2026_提案回顧與學習.md`](competition/YZU_AI_Agent_2026_提案回顧與學習.md) | Competition loss lessons |
| [`COMPETITIVE_PACKAGING_STRATEGY.md`](COMPETITIVE_PACKAGING_STRATEGY.md) | **Internal** — vs Flux/Blueprint/Quilter (after Tier I–III) |
| [`COMPETITOR_SCORECARD_v1.0.2.md`](COMPETITOR_SCORECARD_v1.0.2.md) | **Internal** — layer-5 scorecard + do-not-compete axes |
| [`COMPARISON_DEMO_CASE_robot_repair_cafe.md`](COMPARISON_DEMO_CASE_robot_repair_cafe.md) | **Internal** — artifact-to-artifact vs release sample zip |
| [`ROADMAP_FROM_COMPETITOR_GAPS.md`](ROADMAP_FROM_COMPETITOR_GAPS.md) | **Internal** — do now / do if / do not after comparison |
| [`CLAIMS_BOUNDARY.md`](CLAIMS_BOUNDARY.md) | **Internal + outbound** — allowed vs forbidden claims |
| [`ENGINE_VS_INTERFACE.md`](ENGINE_VS_INTERFACE.md) | **Internal** — under-interfaced vs under-powered |
| [`OSS_INTERFACE_INTEGRATION_STRATEGY.md`](OSS_INTERFACE_INTEGRATION_STRATEGY.md) | **Internal** — OSS embed map + P0 spike |
| [`INTERNAL_MATURITY_PLAN.md`](INTERNAL_MATURITY_PLAN.md) | **Internal product maturity** — `verify-product-internal` |
| [`HANDOFF_UPDATE.md`](HANDOFF_UPDATE.md) | Technical delta since May |

### Agent / MCP / CI

| Read | Why |
|------|-----|
| [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) | **Primary runbook** |
| [`MCP.md`](MCP.md) | MCP install + tool list |
| [`DEMO_SPLICE.md`](DEMO_SPLICE.md) | Splice walkthrough + make targets |
| [`SPLICE_BEST_PRACTICES.md`](SPLICE_BEST_PRACTICES.md) | Operator norms |

### Engineer — engine internals

| Read | Why |
|------|-----|
| [`ENGINE_DONE.md`](ENGINE_DONE.md) | Phases, PASS/OPEN, terms |
| [`ENGINE.md`](ENGINE.md) | Pipeline map |
| [`CIRCUIT_SYNTHESIS_LAYER_PLAN.md`](CIRCUIT_SYNTHESIS_LAYER_PLAN.md) | Synthesis planners |
| [`CIRCUIT_LOGIC_AUDIT.md`](CIRCUIT_LOGIC_AUDIT.md) | Logic / lowering audit |
| [`INTEGRATION.md`](INTEGRATION.md) | Runtime flow, env vars |
| [`TESTING.md`](TESTING.md) | Test strategy |

### Judge / reviewer (5 min)

| Read | Why |
|------|-----|
| [`COMPETITION_HANDOFF.md`](COMPETITION_HANDOFF.md) | One sentence + commands |
| [`COMPETITION_PROPOSAL.md`](COMPETITION_PROPOSAL.md) | Full narrative (longer) |

### Customer / pilot

| Read | Status |
|------|--------|
| [`QUICKSTART_SPLICE_v1.md`](QUICKSTART_SPLICE_v1.md) | **Core** — install + run |
| [`DEMO_5_MIN_UI.md`](DEMO_5_MIN_UI.md) | **Core** — demo script |
| [`EXTERNAL_PROOF_CHECKLIST.md`](EXTERNAL_PROOF_CHECKLIST.md) | **Post-maturity** — release, 5 conversations |
| [`SUPPORT_AND_LIABILITY_v1.md`](SUPPORT_AND_LIABILITY_v1.md) | Support & power-on boundary |
| [`INSTALL_REPORT_TEMPLATE.md`](INSTALL_REPORT_TEMPLATE.md) | External machine proof |
| [`INSTALL_REPORT_dev-linux_2026-07-06.md`](INSTALL_REPORT_dev-linux_2026-07-06.md) | Dev machine validation log |
| [`INSTALL_REPORT_desktop-fgedhgv-wsl_2026-07-07.md`](INSTALL_REPORT_desktop-fgedhgv-wsl_2026-07-07.md) | **Alien machine** — lab Windows + WSL2 |
| [`OPERATIONS_RUNBOOK_v1.md`](OPERATIONS_RUNBOOK_v1.md) | Lab ops |
| [`PACKAGING_AND_DEPLOYMENT.md`](PACKAGING_AND_DEPLOYMENT.md) | Install + deploy plan |
| [`DEPLOY_PRODUCT_FUNDING_PLAYBOOK.md`](DEPLOY_PRODUCT_FUNDING_PLAYBOOK.md) | Deploy → product → funding |
| [`deploy/DEPLOY.md`](../deploy/DEPLOY.md) | Short deploy quickstart |
| [`DEMO_SPLICE.md`](DEMO_SPLICE.md) | CLI splice walkthrough |

---

## 3. Full map — `docs/` (canonical spine)

### Product & ship

| Doc | Role | v1.0 |
|-----|------|------|
| [`SPLICE_PRODUCT.md`](SPLICE_PRODUCT.md) | Product thesis, S0–S5 tiers | **Core** |
| [`RELEASE_V1.md`](RELEASE_V1.md) | Finish line, checklist | **Core** |
| [`PACKAGING_AND_DEPLOYMENT.md`](PACKAGING_AND_DEPLOYMENT.md) | Install, deploy, systemd, release artifacts | **Core** |
| [`DEPLOY_PRODUCT_FUNDING_PLAYBOOK.md`](DEPLOY_PRODUCT_FUNDING_PLAYBOOK.md) | Deploy → product → funding, 90-day plan, pitch scripts | **Core** |
| [`MONETIZATION_AND_PRODUCT_ASSESSMENT.md`](MONETIZATION_AND_PRODUCT_ASSESSMENT.md) | Buyers, pricing, risks, workbook | **Core** |
| [`COMPETITIVE_PACKAGING_STRATEGY.md`](COMPETITIVE_PACKAGING_STRATEGY.md) | **Internal** — vs competitors (external phase) | Reference |
| [`INTERNAL_MATURITY_PLAN.md`](INTERNAL_MATURITY_PLAN.md) | **Internal gate** — Tier I–III before external | **Core** |
| [`BLUEPRINT_POSITIONING_AND_FUNDING.md`](BLUEPRINT_POSITIONING_AND_FUNDING.md) | Strategy, funding | **Core** |
| [`LAUNCH_PLAN.md`](LAUNCH_PLAN.md) | Phases A–C engine launch | Reference (mostly met) |
| [`FLUX_TARGET.md`](FLUX_TARGET.md) | vs Flux positioning | Reference |
| [`COMPETITIVE_LANDSCAPE.md`](COMPETITIVE_LANDSCAPE.md) | vs ECAD tools | Reference |

### Handoff & continuity

| Doc | Role |
|-----|------|
| [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) | Agent entry — **read first for automation** |
| [`HANDOFF_UPDATE.md`](HANDOFF_UPDATE.md) | Changelog narrative |
| [`COMPETITION_HANDOFF.md`](COMPETITION_HANDOFF.md) | Short judge entry |
| [`COMPETITION_PROPOSAL.md`](COMPETITION_PROPOSAL.md) | Long competition doc |

### Run & demo

| Doc | Role |
|-----|------|
| [`SETUP.md`](SETUP.md) | Install, KiCad, venv |
| [`DEMO_SPLICE.md`](DEMO_SPLICE.md) | Splice product demo |
| [`DEMO_10_MIN.md`](DEMO_10_MIN.md) | Authority / fab demo |
| [`MCP.md`](MCP.md) | MCP server |
| [`LLM_OPS.md`](LLM_OPS.md) | Qwen, quota, cache |
| [`MATERIAL_MODES.md`](MATERIAL_MODES.md) | Scratch vs salvage |

### Engine & integration

| Doc | Role |
|-----|------|
| [`ENGINE_DONE.md`](ENGINE_DONE.md) | **Canonical engine gates** |
| [`ENGINE.md`](ENGINE.md) | Pipeline diagram |
| [`INTEGRATION.md`](INTEGRATION.md) | Env + runtime |
| [`INTEGRATIONS_RESEARCH.md`](INTEGRATIONS_RESEARCH.md) | OSS integration research |
| [`INCORPORATION_RESEARCH.md`](INCORPORATION_RESEARCH.md) | OSS stack — don’t rebuild |
| [`CIRCUIT_SYNTHESIS_LAYER_PLAN.md`](CIRCUIT_SYNTHESIS_LAYER_PLAN.md) | Greenfield synthesis |
| [`CIRCUIT_LOGIC_AUDIT.md`](CIRCUIT_LOGIC_AUDIT.md) | Netlist / lowering |
| [`TESTING.md`](TESTING.md) | Tests |
| [`CLUSTER.md`](CLUSTER.md) | Cluster / scale notes |
| [`GIT_MIGRATION.md`](GIT_MIGRATION.md) | Repo history |

### Operator & context

| Doc | Role |
|-----|------|
| [`SPLICE_BEST_PRACTICES.md`](SPLICE_BEST_PRACTICES.md) | Bench / splice norms |
| [`REAL_WORLD_PARALLELS.md`](REAL_WORLD_PARALLELS.md) | Repair café, lab parallels |

### Competition archive (`docs/competition/`)

| Doc | Role |
|-----|------|
| [`YZU_AI_Agent_競賽提案書_2026.md`](competition/YZU_AI_Agent_競賽提案書_2026.md) | Submitted proposal draft |
| [`YZU_AI_Agent_2026_提案回顧與學習.md`](competition/YZU_AI_Agent_2026_提案回顧與學習.md) | Loss retrospective |
| [`YZU_AI_Agent_決賽簡報大綱.md`](competition/YZU_AI_Agent_決賽簡報大綱.md) | Unused finals outline |
| [`YZU_AI_Agent_授權同意書_填寫範本.md`](competition/YZU_AI_Agent_授權同意書_填寫範本.md) | Legal template |

---

## 4. Outside `docs/` — satellite documentation

### Monorepo apps (separate products / legacy depth)

| Path | What | Relationship to v1.0 |
|------|------|----------------------|
| [`apps/circuit-ai/docs/`](../apps/circuit-ai/docs/) | Circuit-AI workflows, repair, vision | **Imported modules**; not v1.0 install path |
| [`apps/circuit-ai/docs/README.md`](../apps/circuit-ai/docs/README.md) | Circuit-AI index | Use for vision/salvage depth |
| [`apps/circuit-ai/README.md`](../apps/circuit-ai/README.md) | Full Circuit-AI platform | **Broader** than splice v1.0 |
| [`apps/mecha-splicer/docs/`](../apps/mecha-splicer/docs/) | Mechanical splice | S4 / future |
| [`apps/README.md`](../apps/README.md) | Monorepo vs v1 product boundary | **Core** |
| [`apps/splice-ui/README.md`](../apps/splice-ui/README.md) | **v1.0 product UI** — live splice workbench | **Ship with v1.0** |
| [`docs/UI_V1.md`](UI_V1.md) | UI scope and architecture | **Core** |
| [`apps/hardware-splicer-demo/README.md`](../apps/hardware-splicer-demo/README.md) | React demo shell (static sample data) | Legacy / reference |
| [`tests/data/golden/README.md`](../tests/data/golden/README.md) | Golden S3 artifacts contract | **Important for CI narrative** |
| [`mcp/hardware-splicer.mcp.json`](../mcp/hardware-splicer.mcp.json) | MCP config sample | Ship with v1.0 |

### Root README

[`README.md`](../README.md) — **v1.0.1 product-first** (quick start, verify, doc map). Engine depth → [`README_MONOREPO_DEPTH.md`](README_MONOREPO_DEPTH.md).

---

## 5. Gaps (documentation debt)

| Gap | Priority | Status |
|-----|----------|--------|
| **`RELEASE_NOTES_v1.0.md`** | P0 | ✅ |
| **`RELEASE_NOTES_v1.0.1.md`** | P0 | ✅ |
| **`QUICKSTART_SPLICE_v1.md`** | P0 | ✅ |
| **`SUPPORT_AND_LIABILITY_v1.md`** | P1 | ✅ |
| **`OPERATIONS_RUNBOOK_v1.md`** | P1 | ✅ |
| **`OFFER_SPLICE_BENCH_KIT_v1.md`** | P1 | ✅ |
| **`INSTALL_REPORT_TEMPLATE.md`** | P1 | ✅ (fill on external test) |
| **`CHANGELOG.md`** | P1 | ✅ |
| **Fresh VM install report** | P1 | ❌ — use template when testing |
| **`ROADMAP_v2.md`** | P2 | Not written |
| **OpenAPI export in release** | P2 | Use `/docs` live |
| **`docs/zh-TW/` one-pager** | P2 | Optional |
| **Stale banner on `LAUNCH_PLAN`** | P3 | Add “Phases A–C met; see RELEASE_V1” |

---

## 6. Suggested README structure (v1.0)

```markdown
# Hardware-Splicer Splice Agent

One sentence + 3 commands (setup, verify-splice, mcp)

## Documentation
→ docs/DOCUMENTATION_INDEX.md

## v1.0 scope
→ docs/RELEASE_V1.md

## Quick demo
→ docs/DEMO_SPLICE.md

## License / limits
Cosmetic copper; KiCad truth; bench gates
```

Everything else → index.

---

## 7. Documentation vs monetization

| Buyer stage | Doc they need | Exists? |
|-------------|---------------|---------|
| Curious engineer | README + QUICKSTART + DEMO_5_MIN_UI | ✅ |
| Agent integrator | AGENT_HANDOFF + MCP | ✅ |
| Pilot customer | OFFER + QUICKSTART | ✅ |
| Legal/procurement | SUPPORT_AND_LIABILITY | ✅ |
| Grant reviewer | MONETIZATION §11 + HANDOFF_UPDATE | ✅ |
| You assessing business | MONETIZATION full | ✅ |

**Finishing the product** requires **finishing the doc set** for the **buyer you chase** — not documenting the whole monorepo.

---

## 8. Maintenance rules (after v1.0)

1. **One changelog narrative:** update `HANDOFF_UPDATE.md` for big arcs; don’t spawn new handoff files unless needed.  
2. **Product truth:** `SPLICE_PRODUCT.md` tiers — update when S3/S4 moves.  
3. **Engine truth:** `ENGINE_DONE.md` wins on conflicts.  
4. **Competition / grant:** archive under `docs/competition/`, don’t delete.  
5. **apps/circuit-ai/docs:** don’t merge into spine; link as “depth / legacy workflows.”  
6. **Version:** `sdk_info()` + `RELEASE_NOTES` must match git tag.

---

## 9. Quick command → doc map

| Command | Doc |
|---------|-----|
| `make setup` | SETUP.md |
| `make verify-splice` | DEMO_SPLICE.md, SPLICE_PRODUCT.md |
| `make verify-splice-v1` | DEMO_SPLICE.md, INTERNAL_MATURITY_PLAN.md §Tier I |
| `make verify-product-internal` | INTERNAL_MATURITY_PLAN.md (full internal bar) |
| `make verify-product-v1` | INTERNAL_MATURITY_PLAN.md §Tier II |
| `make splice-ui-serve` | QUICKSTART_SPLICE_v1.md, DEMO_5_MIN_UI.md |
| `python -m hardware_splicer.mcp_server` | MCP.md, AGENT_HANDOFF.md |
| `scripts/hardware_splicer.py serve` | AGENT_HANDOFF.md, INTEGRATION.md |
| `make test-project-package` | HANDOFF_UPDATE.md §9 |

---

## 10. Changelog

| Date | Change |
|------|--------|
| 2026-07 | v1.0.1 doc set: quickstart, support, ops, demo, install template |
| 2026-07 | `COMPETITIVE_PACKAGING_STRATEGY.md` — internal monetisation/competitor completion map |
| 2026-06 | Initial documentation index |
