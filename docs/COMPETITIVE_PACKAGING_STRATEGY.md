# Competitive packaging & completion strategy (internal)

**Purpose:** How to **complete and package** Hardware-Splicer Splice Agent as a **monetisable / fundable system product** — honest positioning vs competitors, gap closure priorities, and what **not** to build.

**Audience:** Founder, advisors, agents. **Not** for customer distribution as-is (contains competitive bluntness).

**Status:** July 2026 · Post v1.0.1 packaging release  
**Related:** [`COMPETITIVE_LANDSCAPE.md`](COMPETITIVE_LANDSCAPE.md) · [`BLUEPRINT_POSITIONING_AND_FUNDING.md`](BLUEPRINT_POSITIONING_AND_FUNDING.md) · [`MONETIZATION_AND_PRODUCT_ASSESSMENT.md`](MONETIZATION_AND_PRODUCT_ASSESSMENT.md) · [`DEPLOY_PRODUCT_FUNDING_PLAYBOOK.md`](DEPLOY_PRODUCT_FUNDING_PLAYBOOK.md)

---

## 1. Executive thesis

| Question | Answer |
|----------|--------|
| What market are we in? | **Auditable hardware bring-up** — not browser ECAD, not autonomous routing SaaS |
| Who pays first? | Labs, prototype shops, repair/salvage operators, agent integrators — **not** prompt hobbyists |
| What is the SKU? | Self-hosted **Splice Agent**: intake → KiCad DRC → bench gates → PROJECT_PACKAGE |
| What is the moat? | Salvage path + compile truth + gate semantics + headless API — **not** prettier project pages |
| What loses? | Head-on vs Flux/Blueprint on greenfield UX, vs Quilter on dense autoroute |

**One line (external):**

> We make hardware bring-up **auditable and gate-driven** — donor intake, KiCad compile truth, measurement checklist before power-on.

**One line (internal):**

> We own the **splice + verify + handoff** wedge; we rent nothing from the ECAD editor wars.

---

## 2. Competitive map (2026) — categories, not logos only

The market splits into **five buckets**. We only fight in one bucket today; we **integrate with or ignore** the rest.

```text
┌─────────────────────────────────────────────────────────────────┐
│ A. Greenfield AI ECAD (browser)     Flux, EasyEDA, PCB Designer AI │
│ B. Autonomous layout/routing        Quilter, DeepPCB, Cadence X AI │
│ C. AI schematic capture             ProtoFlow, SchGen-style tools  │
│ D. Project package / inspiration    Blueprint.am (3E8), Hackaday   │
│ E. Bring-up / splice / NPI truth    ★ Hardware-Splicer (target)   │
└─────────────────────────────────────────────────────────────────┘
```

### Bucket A — Greenfield AI ECAD (Flux et al.)

| | Them | Us |
|--|------|-----|
| **Job** | Idea → schematic → layout in browser | Donor/splice → carrier → gates |
| **Buyer** | Teams designing new boards | Teams reusing physical hardware |
| **Strength** | UX, collaboration, live BOM, 300k+ users (Flux claim), no KiCad install |
| **Weakness** | No donor harness truth; no bench gate product | KiCad install; no browser editor |
| **Threat level** | **Low** if we stay in salvage/NPI; **fatal** if we pitch "Flux competitor" |

Flux (2026): browser ECAD + Copilot, continuous ERC/DRC, supply chain in flow, steerable multi-step agent, enterprise tier. **Does not** productize salvage dissection or bench authorization JSON.

### Bucket B — Autonomous routing (Quilter, DeepPCB)

| | Them | Us |
|--|------|-----|
| **Job** | Place/route dense PCBs from constraints | Carrier compile for **adapter** boards around kept donor blocks |
| **Buyer** | Professional layout teams | Salvage/maker/NPI-adjacent |
| **Strength** | Physics RL, multi-candidate layouts, enterprise/on-prem options | Splice plan + DRC on **carrier** + gates |
| **Weakness** | Not salvage; not power-on checklist | Cosmetic/default copper; not production router |
| **Threat level** | **None** for wedge; **partnership** potential (export carrier → route in Quilter) |

### Bucket C — Schematic capture AI (ProtoFlow, NL→KiCad adapters)

| | Them | Us |
|--|------|-----|
| **Job** | NL → schematic entry | Intake → splice plan → compile spine |
| **Strength** | Faster greenfield capture | Bounded planners + OSS adapter path (SchGen) already mapped |
| **Threat level** | **Medium** only if we chase "any English → PCB" consumer story |

### Bucket D — Project package / inspiration (Blueprint.am)

| | Them | Us |
|--|------|-----|
| **Job** | Inspiring buildable-looking project pages | Defensible compile + gates + casefiles |
| **Entity** | 3E8 Robotics (~3–4 core), VC-backed, Elly robot primary | Solo, engine-deep |
| **Overlap** | INFO / BOM / WIRING / INSTRUCTIONS tabs | Same shape + **GATES** + salvage + KiCad proof |
| **Threat level** | **High for mindshare** among makers; **low for B2B/NPI** if we stay on truth |

Blueprint wins: onboarding, gallery, credits, "build anything" narrative.  
We win: `verify-splice-v1`, `COMPILE_CASEFILE`, `power_on_authorized`, MCP/self-host, donor fixtures.

### Bucket E — Bring-up / NPI (our target)

| | "Competition" today | Us |
|--|---------------------|-----|
| **Actual substitute** | PDF checklists, Notion, senior EE tribal knowledge | Structured gates + session JSON + package zip |
| **Software** | Almost **no** dedicated SKU at maker price point | Splice Agent v1 |
| **Enterprise** | Sheridan-style NPI consultancies, DFM checklists, ICT fixtures | Too heavy for first wedge |

**Key insight:** Our real competitors are **unstructured process**, not Flux. Flux is the wrong comparison in sales calls unless the buyer is choosing greenfield tools.

---

## 3. Positioning matrix (use in pitch)

| If buyer says… | Don't say… | Say… |
|----------------|------------|------|
| "Is this like Flux?" | "Yes but local" | "Flux is greenfield ECAD. We're bring-up verification for salvage and NPI — gates before power-on." |
| "Is this like Blueprint?" | "We're better AI" | "Same package tabs — we add KiCad DRC proof and bench gates they don't ship." |
| "Is this like Quilter?" | "We route too" | "We compile the **carrier** around donor blocks; you can route elsewhere if needed." |
| "Can AI design my board?" | "Yes anything" | "Engine assists; operator measures and authorizes energization." |
| EMS / 打樣坊 | "Junk robots" | "NPI bring-up gate — auditable package before Gerber arguments." |
| Grant / TW | "Consumer AI hardware" | "可稽核硬體導入：量測關卡、KiCad compile truth、PROJECT_PACKAGE" |

---

## 4. Tab-by-tab completion vs Blueprint (product parity lens)

Honest scorecard for **demo credibility**, not consumer parity.

| Tab / capability | Blueprint (est.) | HS v1.0.1 | Close gap priority | How |
|------------------|------------------|-----------|-------------------|-----|
| INFO / clarifier | Strong UX | ✅ JSON + clarifier API | P2 | UI polish only |
| BOM | Cost, thumbs, sourcing | Lines + estimate | **P1** | LCSC/JLC enrich hook (partial in engine) |
| WIRING | Diagrams + prose | Markdown + netlist data | P1 | Mermaid in package / UI |
| INSTRUCTIONS | Polished steps | Markdown templates | P2 | Template quality |
| PAGE polish | Gallery, thumbnails | splice-ui workbench | P2 | Not blocking B2B |
| **GATES** | ❌ | ✅ **ahead** | — | **Lead pitch** |
| **SALVAGE / donor** | ❌ | ✅ **ahead** | P1 | Real junk photos in pilot |
| **KiCad DRC proof** | Unclear / thin | ✅ CI-backed | — | **Lead pitch** |
| **Agent API** | Thin | ✅ MCP + HTTP + jobs | — | B2B wedge |

**Packaging rule:** Lead demos with **GATES + DRC + zip download**, not BOM prettiness.

---

## 5. What "complete" means for monetisable product

Completion is **not** feature parity with Flux. It is **conversion-ready**:

| Layer | Complete when… | v1.0.1 status |
|-------|----------------|---------------|
| **Engine** | `verify-splice-v1` green | ✅ |
| **SKU story** | README + quickstart + scope | ✅ |
| **Legal envelope** | Support/liability doc | ✅ |
| **Deploy** | Single-port demo + runbook + nginx example | ✅ |
| **Commercial** | Offer template | ✅ |
| **External proof** | 1 install report, 1 demo video, 1 pilot yes | ❌ **blocking revenue** |
| **Release page** | GitHub Release on tag | ⚠️ tag pushed; release manual |
| **Sample artifact** | PROJECT_PACKAGE zip on release | ❌ |
| **Instrument path** | DMM → gate auto-fill | 🟡 future P1 engineering |

**"Complete" for funding** adds: partner letter, deployment plan, budget, 可重現 verify bar (CI link).

---

## 6. Gap closure roadmap (internal priorities)

### Phase 1 — Conversion kit (now → 14 days) — **no new engine**

| # | Item | Competitor leverage | Effort |
|---|------|---------------------|--------|
| 1 | GitHub Release v1.0.1 + sample zip | Blueprint ships pretty pages; we ship **zip** | Low |
| 2 | 5-min demo video | Flux/Blueprint win on video | Low |
| 3 | One-pager PDF from offer doc | Standard B2B | Low |
| 4 | 5 segmented outreaches | First mover in E bucket | Time |
| 5 | INSTALL_REPORT on one alien machine | Beats "works on my laptop" | Medium |

### Phase 2 — Pilot-hardening (30–60 days) — **only what pilots ask for**

| # | Item | Why | Defer if… |
|---|------|-----|-----------|
| 1 | BOM enrich (LCSC/JLC pricing) | Blueprint/Flux set BOM bar | Pilot doesn't care about cost |
| 2 | Wiring Mermaid in UI | Visual parity | Text is enough for first pilot |
| 3 | DMM/serial instrument → bench submit | Beats static checklists | No lab pilot |
| 4 | Donor photo → vision in UI | Salvage story | Intake JSON enough |
| 5 | API key middleware (light) | Site license LAN | nginx enough |

### Phase 3 — Fundable v1.2 (60–120 days) — **evidence stack**

| # | Item | Funder narrative |
|---|------|------------------|
| 1 | 2 case studies (1 paid) | Market validation |
| 2 | Partner letter (uni/EMS) | Taiwan grant co-author |
| 3 | `ROADMAP_v2.md` (park SaaS) | Scope discipline |
| 4 | Optional zh-TW one-pager | B2B Taiwan |
| 5 | SBIR / StarFab application | Non-dilutive runway |

### Explicit **do-not-build** list (competitive traps)

| Trap | Why competitors win |
|------|---------------------|
| Public multi-tenant SaaS | Flux/Quilter capital + ops |
| Browser schematic editor | Flux 300k-user head start |
| Production autoroute default | Quilter/DeepPCB |
| "Any prompt → any PCB" | Blueprint narrative + LLM breadth |
| Full Circuit-AI merge as v1 SKU | Confuses buyer |
| Windows native installer before first Linux pilot | Distraction |

---

## 7. Packaging vs engineering — resource split

Recommended solo time allocation **after v1.0.1**:

```text
60%  conversion (demos, pilots, outreach, case studies)
25%  pilot-driven engineering (only gaps from Phase 2 that unblock $)
15%  maintenance (KiCad bumps, CI, dependency security)
 0%  new architecture / monorepo expansion / doc sprawl
```

---

## 8. Monetisation fit vs competitive set

| Model | vs Flux/Blueprint | vs Quilter | vs checklists | HS fit |
|-------|-------------------|------------|---------------|--------|
| Splice Sprint (services) | **Strong** — they don't operate your bench | Neutral | **Strong** — replaces ad-hoc | **Start here** |
| Site license | **Strong** — self-host + gates | Neutral | **Strong** | After 1 pilot |
| Grant / SBIR | Neutral | Neutral | **Strong** — R&D narrative | Parallel |
| Hosted API credits | **Weak** — Flux cloud native | Weak | Medium | **Defer** |
| Consumer sub | **Lose** | — | — | **Never v1** |

**Pricing anchor (unchanged):** one bad respin or one week EE delay > one Splice Sprint (NT$15k–60k).

---

## 9. Funding narrative (Taiwan-friendly)

**Do not pitch:** "AI PCB generator for everyone."

**Do pitch:**

| Element | Wording |
|---------|---------|
| Problem | NPI / prototype bring-up lacks auditable gate between compile and power-on |
| Solution | Self-hosted agent: splice intake → KiCad DRC → measurement gates → PROJECT_PACKAGE |
| Proof | `verify-splice-v1`, CI, reproducible manifests |
| Differentiation | Not ECAD editor — **verification infrastructure** for small labs and EMS-adjacent desks |
| TW hooks | 可稽核交付、量測關卡、打樣前檢核、治具/載板、salvage 再利用 |
| Ask | Pilot partner + SBIR/加速器 matching funds for field validation + instrument integration |

**Competitive moat for grants:** CI-gated engine is **hard to fake** in a slide deck; Flux/Blueprint slides look better but verify less.

---

## 10. Integration strategy (coexist, don't fight)

| Partner tool | Relationship |
|--------------|--------------|
| **KiCad** | Source of truth for DRC — embrace |
| **Flux** | Export carrier artifacts for collaboration view; not donor validity |
| **Quilter/DeepPCB** | Optional route step after carrier compile |
| **JLCPCB/EasyEDA** | BOM/order downstream |
| **Cursor/MCP agents** | Primary distribution for integrators |

Position as **spine in the bring-up layer**, not replacement EDA.

---

## 11. Competitive intelligence checklist (quarterly)

| Source | Watch for |
|--------|-----------|
| Flux blog / releases | Agent verification, test plans — encroaching on our gate story? |
| Blueprint.am | Gates tab? KiCad export? B2B pivot? |
| Quilter | KiCad import depth, NPI messaging |
| ProtoFlow / SchGen | NL capture eating our intake story |
| TW grants / 創客 | Who gets funded for "hardware agent" — vocabulary theft |

**Trigger to revisit strategy:** If Flux or Blueprint ship **bench gate JSON + KiCad DRC proof** as productized SKU, narrow to **salvage-only** and instrument automation faster.

---

## 12. Decision log (internal)

| Date | Decision |
|------|----------|
| 2026-07 | v1.0.1 = packaging release; stop doc expansion except conversion kit |
| 2026-07 | Primary competitor = unstructured bring-up, not Flux |
| 2026-07 | Next KPI = one paid pilot OR partner letter in 14–30 days |
| 2026-07 | Do not pursue consumer SaaS or editor parity in 2026 |

---

## 13. Immediate action list (this week)

1. [ ] Create GitHub Release `v1.0.1` (body in `RELEASE_NOTES_v1.0.1.md`)
2. [ ] Attach sample `PROJECT_PACKAGE` zip from golden job
3. [ ] Record `docs/DEMO_5_MIN_UI.md` flow
4. [ ] Export one-pager PDF from `OFFER_SPLICE_BENCH_KIT_v1.md`
5. [ ] Name 5 outreach targets (1× maker, 1× lab, 1× EMS-adjacent, 1× robotics, 1× agent shop)
6. [ ] Schedule alien-machine install using `INSTALL_REPORT_TEMPLATE.md`

**Success metric:** One external "yes" — paid, LOI, or signed testimonial.

---

## 14. Bottom line

**Packaging (v1.0.1) is sufficient to sell.**  
**Completion (monetisable/fundable) = external proof + 1–2 pilot-driven engineering gaps — not Flux parity.**

Fight in **bucket E** (bring-up truth). Borrow tab shape from **bucket D** (Blueprint) where it helps demos. **Integrate with** buckets A/B/C. **Ignore** their GTM.

The product is fundable as **NPI/bring-up verification infrastructure**, not as the next Flux. That is a feature, not a consolation prize.
