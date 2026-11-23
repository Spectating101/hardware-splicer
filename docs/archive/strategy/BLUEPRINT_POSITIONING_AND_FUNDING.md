# Blueprint positioning, assets, and Taiwan funding — session handoff

**Date:** June 2026  
**Status:** Strategic decision record — **do not kill Hardware-Splicer because of Blueprint.am**  
**Audience:** You, future you, next agent, competition reviewers, potential partners

**Related:**

- [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) — how to run the engine
- [`HANDOFF_UPDATE.md`](HANDOFF_UPDATE.md) — technical delta since May
- [`COMPETITION_HANDOFF.md`](COMPETITION_HANDOFF.md) — 5-minute judge entry
- [`COMPETITION_PROPOSAL.md`](COMPETITION_PROPOSAL.md) — full competition narrative
- [`competition/YZU_AI_Agent_競賽提案書_2026.md`](competition/YZU_AI_Agent_競賽提案書_2026.md) — 元智大學 AI Agent 競賽提案草稿
- [`COMPETITIVE_LANDSCAPE.md`](COMPETITIVE_LANDSCAPE.md) — vs Flux / Quilter / salvage shops

---

## Executive decision

| Question | Answer |
|----------|--------|
| Is HS dead because Blueprint exists? | **No** |
| Same game board? | **Yes** on project-package shape (INFO / BOM / WIRING / INSTRUCTIONS); **we add GATES** |
| Same company scale? | **No** — see §2 |
| Kill the project? | **No** — different wedge + proven backend |
| Use competition / grant funding to develop? | **Yes** — primary near-term capital path in Taiwan |

**One line:** Blueprint sells *possibility*; Hardware-Splicer sells *operability* (compile truth, bench gates, salvage). Competition and TW industrial funding fit HS better than a head-on consumer race with Blueprint.

---

## 1. What Blueprint.am actually is

Blueprint is **not** a solo side project and **not** a large established ECAD company. It is a product of **3E8 Robotics Inc.**

| Fact | Detail |
|------|--------|
| Entity | [3E8 Robotics](https://www.3e8robotics.com/about) — San Francisco, founded **2025** |
| Founders | David Feldt (CEO), Ari Wasch (CTO), Sajeel Purewal (COO), Pranav Seelam — Waterloo / Queen’s backgrounds |
| Team size | ~**3–4** core ([Founders Inc. portfolio](https://f.inc/portfolio/3e8-robotics/)) |
| Funding | Venture-backed — Founders Inc. accelerator + angel investors |
| **Primary business** | **Elly** — indoor multi-floor delivery robot (hotels, condos, hospitals) |
| Blueprint’s role | Community / prototyping tool spun from internal workflow; credits model (`10 free credits/week` on site) |
| Human review | They still require human review — not “magic and ship” |

**Implication:** Comparing solo you vs Blueprint is **not** solo vs Google. It is closer to **solo vs a small funded robotics startup’s secondary product**, while their main engineering focus is likely Elly (pilots, elevator vision, sales).

---

## 2. Competitive positioning (honest)

### Two stories in the market

| Story | Blueprint-style | Hardware-Splicer |
|-------|-----------------|------------------|
| Hero line | “I can build all this easily from a prompt” | “If you run **business X**, this is your verified spine” |
| Buyer | Maker, student, hobbyist | Operator, lab, refurb shop, agent builder, NPI-adjacent team |
| Product | Project page + instructions | Compile + gates + casefiles + agent API |
| Success metric | Inspiring, buildable-looking | DRC clean, bench authorized, traceable |
| Moat | UX, generative breadth, catalog polish | Salvage path, verification discipline, headless MCP/SDK |

### Tab-by-tab benchmark (we can score ourselves)

```text
INFO           — clarifier exists; expand breadth
BOM            — lines yes; LCSC/cost/thumbs weaker
WIRING         — netlist data yes; diagram/prose weaker
INSTRUCTIONS   — templates exist
PAGE POLISH    — deferred (markdown/JSON today)
GATES          — ahead (they don’t productize this)
SALVAGE        — ahead (they don’t have this)
```

**Positioning line for pitches:**

> Same project-package tabs as Blueprint — plus **GATES**, KiCad compile proof, and salvage. Not “easier magic”; **harder truth**.

### vs Hack Club Blueprint

**Different product.** User meant **Blueprint.am** (3E8 Robotics), not Hack Club’s funding/education platform.

---

## 3. What we built — sophistication worth pride

| Asset | Why it is not “toy” level |
|-------|---------------------------|
| Splice spine | Donor → plan → carrier → bench gates; manifest + CI |
| S2/S3 verification | `verify-splice`, golden loop, real bench capture |
| Headless KiCad compile | DRC as pass bar |
| Circuit synthesis | Bounded planners + compile bridge (`88f1db8`) |
| PROJECT_PACKAGE | Blueprint-shaped output + **GATES** (`project_package.py`) |
| Agent surfaces | SDK / MCP / HTTP on same functions |
| Honest limits | Cosmetic copper; vision proposes / bench closes |

**Sophistication vs polish:**

- **Sophistication** (pipeline, schemas, CI, gates) — **ahead** in salvage + compile + gates  
- **Polish** (gallery, thumbnails, onboarding) — **behind** — deliberately deferred  

Being able to benchmark tab-for-tab against Blueprint **while solo** is a strong signal, not a consolation prize.

---

## 4. Backend catch-up vs packaging vs full product

| Layer | Difficulty | Worth prioritizing? |
|-------|------------|---------------------|
| PROJECT_PACKAGE schema parity | Easy | **Yes** — done in progress |
| Clarifier + bounded planners | Easy–medium | **Yes** |
| BOM enrichment (LCSC/Octopart) | Medium | **Yes** for demos |
| Wiring diagram (Mermaid / ReactFlow) | Medium | Medium |
| OSS adapters (SchGen, boardsmith patterns) | Medium–hard | When planners block |
| Thin tab viewer (no full SaaS) | Easy–medium | For judges / partners only |
| Blueprint-parity consumer UX | Hard | **Defer** |
| Open-ended “any prompt” breadth | Hard / ongoing | Adapter strategy, not rewrite |

### Open-source levers (catch-up without cloning Blueprint)

| Project | Use |
|---------|-----|
| [microsoft/SchGen](https://github.com/microsoft/SchGen) | NL → KiCad schematic code → our compile spine |
| [ForestHubAI/boardsmith](https://github.com/foresthubai/boardsmith) | Constraint-checked pipeline reference |
| [YuGu0358/hardware-foundry](https://github.com/YuGu0358/hardware-foundry) | Full artifact agent layout to benchmark |
| pcbGPT (research) | HITL + validation patterns |
| In-repo Circuit-AI | ReactFlow, vision, frontend shells |

### Architecture: play both games on one spine

```text
                    ┌─────────────────────┐
         prompt ──► │ intent_clarifier    │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
        splice path    bounded synthesis   OSS adapter
        (donor junk)   (motor, power, …)   (optional)
              │                │                │
              └────────────────┼────────────────┘
                               ▼
                    compile spine (KiCad DRC)
                               ▼
                    PROJECT_PACKAGE + GATES
```

---

## 5. Monetization and valuable asset

### What monetizes

| Model | HS fit |
|-------|--------|
| Consumer subscription (“prompt → projects”) | Weak |
| B2B ops / agent API | **Strong** |
| Services / pilot (repair café, lab, EMS) | **Strong** |
| Grants / competition | **Strong** (near term) |
| White-label engine | **Strong** (later) |

### What is the asset

**Valuable bundle:**

```text
salvage intake + KiCad compile (CI-proven) + bench gates + agent API + PROJECT_PACKAGE
```

**Commodity alone:** prompt → BOM + wiring markdown without gates.

The viewer is **proof of the pipeline**, not the product. Acquirers and partners care about repeatable manifests, gate semantics, and headless API — not gallery polish alone.

### Packaging worth doing?

| Scope | Verdict |
|-------|---------|
| Thin PROJECT_PACKAGE viewer for demos | **Yes** — low cost, high narrative ROI |
| Full Blueprint consumer product | **Not yet** — different company shape |

---

## 6. Solo (Taiwan) vs 3E8 (funded startup)

| Dimension | 3E8 / Blueprint | Hardware-Splicer (you) |
|-----------|-----------------|------------------------|
| Headcount | ~3–4 founders + investors | Solo |
| Primary bet | Delivery robot + pilots | Compiler + splice + gates |
| Blueprint focus | Part of eng + GTM | Whole focus when working on HS |
| Backend depth (public) | Thinner on verification | **Demonstrably deep** in-repo |
| Frontend | Their strength | Deferred |
| Age | ~1 year as company | Comparable project maturity in engine |

**Pride is justified** with evidence (CI green, artifacts on disk, gate verdicts) — not with claiming equal polish or GTM.

---

## 7. Funding — 3E8 method vs Taiwan method

### What 3E8 actually did

```text
1. Four co-founders + physical hero product (Elly)
2. SF → Founders Inc. accelerator
3. Angels + venture
4. Building pilots + press
5. Blueprint as side product / community surface
```

Investors bought **robotics + pilots**; Blueprint supports “we ship fast” narrative.

### Taiwan path (better fit for HS)

| Channel | Fit | Notes |
|---------|-----|-------|
| **元智 YZU AI Agent 競賽** | Closed (2026 proposal) | See [`competition/YZU_AI_Agent_2026_提案回顧與學習.md`](competition/YZU_AI_Agent_2026_提案回顧與學習.md) |
| **Commercial product path** | **Primary after v1.0** | [`MONETIZATION_AND_PRODUCT_ASSESSMENT.md`](MONETIZATION_AND_PRODUCT_ASSESSMENT.md) |
| **SBIR** (中小企業處) | High | Phase 1 ~NT$1M, Phase 2 up to ~NT$10M — needs **台灣公司** |
| **Taiwan Tech Arena (TTA)** | Medium–high | Deep tech, international |
| **StarFab / 新竹 AIoT** | High | Hardware, AI, corporate POC 獎勵金 |
| **Mighty Net** (盟立) | High | Smart manufacturing, factory validation |
| **AppWorks / SparkLabs TW** | Medium | AI / deep tech |
| **Corporate POC** | Very high | EMS, repair, lab — “reduce bad Gerber / bad bring-up” |

### Pitch for Taiwan (not “Taiwan’s Blueprint”)

> **Verified hardware agent for prototyping and salvage** — KiCad DRC, bench gates, auditable casefiles. For labs and NPI-adjacent teams who cannot afford “looks good” schematics.

Aligns with: semiconductor-adjacent tooling, 不要浪費打樣, agent competitions, B2B buyers.

### Fixable blockers before serious funding

| Blocker | Mitigation |
|---------|------------|
| Solo | Co-founder, advisor, or named pilot partner |
| No 公司 | Register when pursuing SBIR / accelerator |
| No pilot site | One repair café / lab / school shop letter |
| Consumer UI | Thin demo sufficient for grants |

---

## 8. Competition funding → development capital

**YZU 2026 提案結果：** 未入圍決賽（7 組晉級，決賽 2026-09-02）。回顧見 [`competition/YZU_AI_Agent_2026_提案回顧與學習.md`](competition/YZU_AI_Agent_2026_提案回顧與學習.md)。**落選 ≠ 專案無價值** — 半導體書院評審偏好與 Fab-Truth 敘事未對齊；SBIR / StarFab / POC 路徑不變。

**Plan (if similar funding lands later):**

| Priority | Use of funds / time |
|----------|---------------------|
| P0 | Engine hardening — splice↔synthesis merge on one golden path, `make verify-*` green |
| P0 | One real pilot partner (repair café / lab) + case write-up |
| P1 | BOM enrichment + wiring guide quality |
| P1 | Thin PROJECT_PACKAGE viewer (demo only, not full SaaS) |
| P2 | SBIR / StarFab / Mighty Net application with pilot evidence |
| P2 | Optional OSS adapter spike (SchGen) behind `blocked` fallback |
| Defer | Full Blueprint-parity consumer UX |

**Competition demo = Taiwan version of 3E8’s elevator video:**

```bash
make verify-splice-loop          # or live hs_splice_golden_loop
# Show: PROJECT_PACKAGE + GATES verdict + MCP agent path
```

Judges should see: **agent does work → KiCad truth → gates → auditable failure on bad input**.

---

## 9. Twelve-month playbook (when resuming)

```text
Now–Q1   Submit / compete YZU AI Agent; polish Fab-Truth demo
Q2       One POC partner (repair café, 創客, EMS lab)
Q2       Register 公司 if pursuing SBIR or corporate accelerator
Q2–Q3    Apply: SBIR Phase 1 OR StarFab / Mighty Net / TTA
Q3       Publish one verified case study (PROJECT_PACKAGE + gates)
Parallel Expand bounded synthesis + package quality
Optional AppWorks / international after TW pilot story exists
```

---

## 10. Commands and artifacts (resume checklist)

```bash
make setup
make doctor
make verify-splice              # S2
make verify-splice-loop         # S3 simulated
make verify-splice-real-bench   # S3 real capture path
make test-project-package       # PROJECT_PACKAGE layer

# Agent demo
PYTHONPATH=src python -m hardware_splicer.mcp_server
# or SDK: splice_build, synthesize_circuit, clarify_hardware_intent, render_project_package
```

**Key artifacts per build:**

- `PROJECT_PACKAGE.json`, `PROJECT_PAGE.md`, `WIRING_GUIDE.md`, `ASSEMBLY_GUIDE.md`
- `SPLICE_BENCH_SESSION.json` — gate status
- `build_compilation/` — KiCad outputs

---

## 11. What not to overclaim

| Don’t say | Do say |
|-----------|--------|
| “We beat Blueprint” | “We compete on verified packages; they win polish and breadth” |
| “Any prompt works” | “Proven on golden paths; expanding bounded domains” |
| “UI doesn’t matter forever” | “Backend and gates ahead of presentation; thin viewer for demos” |
| “Production-ready for everything” | “CI-proven on manifest cases; field validation is next” |

---

## 12. Session conclusion (June 2026)

1. **Blueprint does not kill Hardware-Splicer** — different layer, overlapping tabs, we are stronger on gates + salvage + compile CI.  
2. **3E8 is a small young company** — comparison is flattering to solo depth, not disqualifying.  
3. **Backend catch-up is feasible** — package layer + planners + optional OSS adapters; full consumer UX is not required for wedge.  
4. **Taiwan funding path is real** — competition → pilot → SBIR / accelerator / corporate POC.  
5. **Competition prize is valid development budget** — engine + one pilot + business narrative, not a Blueprint clone.  
6. **Be proud of the asset** — sophistication is real; polish can follow money and partners.

**Stop point:** Engine and strategy documented. Next session: YZU submission, live demo script, pilot outreach — not killing the repo because of Blueprint.

---

## References (external)

- [Blueprint.am](https://blueprint.am/)
- [3E8 Robotics](https://www.3e8robotics.com/)
- [Founders Inc. — 3E8 portfolio](https://f.inc/portfolio/3e8-robotics/)
- [StarFab Accelerator](https://starfabx.com/)
- [Mighty Net Innovation Program](https://www.might.com.tw/en/news/2026-11th-mighty-net-innovation-program-now-open-for-applications-accelerating-the-future-of-smart-manufacturing/)
- [microsoft/SchGen](https://github.com/microsoft/SchGen)
