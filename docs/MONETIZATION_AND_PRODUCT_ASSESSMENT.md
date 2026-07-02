# Monetization & product assessment — Hardware-Splicer v1.0

**Purpose:** Give you enough structure to **assess** whether finishing v1.0 is worth treating as a **commercial product** — not hype, not “guarantee,” but a decision workbook.

**Audience:** You (founder), future you, advisors, potential pilot customers.

**Related:**

- [`RELEASE_V1.md`](RELEASE_V1.md) — what “finished” means technically  
- [`BLUEPRINT_POSITIONING_AND_FUNDING.md`](BLUEPRINT_POSITIONING_AND_FUNDING.md) — vs Blueprint, Taiwan grants  
- [`SPLICE_PRODUCT.md`](SPLICE_PRODUCT.md) — tiers S0–S5, personas (short)  
- [`competition/YZU_AI_Agent_2026_提案回顧與學習.md`](competition/YZU_AI_Agent_2026_提案回顧與學習.md) — competition misfit lessons  

**Last updated:** June 2026  

---

## Executive summary (read this first)

| Question | Short answer |
|----------|--------------|
| Can v1.0 be monetized? | **Yes** — primarily **B2B / ops / services / vertical**, not mass consumer |
| Is the engine strong enough to sell? | **Yes** — CI-proven splice + gates + agent API is sellable **infrastructure** |
| Does “finished” = automatic revenue? | **No** — you still need buyer, offer, price, delivery |
| Best first dollar path? | **Services or pilot license** using v1.0 on a real splice job |
| Worst first dollar path? | Consumer subscription vs Blueprint |
| Taiwan fit? | **Good** for EMS-adjacent, repair, lab, grant — weak for US-style VC consumer |
| Should you stake your future on it? | **Stake the next release + one commercial experiment** — not all-in without pilot/revenue signal |
| Guarantee? | **Never** — but **optionality is real** |

---

## 1. What you are actually selling

### 1.1 Product definition (v1.0)

**Name:** Hardware-Splicer Splice Agent v1.0  

**Category:** Headless **hardware bring-up / splice** agent — not ECAD editor, not generic chatbot.

**Core job-to-be-done:**

> Before I spend money on fab or power on unknown donor wiring, give me a **carrier compile**, **auditable gates**, and a **project package** I can defend to my team or client.

**Deliverables the customer receives:**

| Artifact | Customer value |
|----------|----------------|
| `SPLICE_PLAN.json` | What to keep, connect, measure |
| KiCad carrier + DRC report | Third-party compile truth |
| `SPLICE_BENCH_SESSION.json` | What must be measured before power-on |
| `PROJECT_PACKAGE.json` + guides | Human-readable BOM / wiring / instructions / **GATES** |
| `COMPILE_CASEFILE.json` (on failure) | Debuggable, non-hand-wavy failure |

### 1.2 What you are NOT selling (v1.0)

- Unlimited “prompt → any PCB” magic  
- Production autorouted copper (default is cosmetic preview)  
- Donor harness safety certification  
- Mechanical enclosure design as primary SKU  
- Stock tips, ESG reports, fab yield ML (competition winners’ zone)  

### 1.3 Value equation (use in sales)

```text
Customer pain $  ≈  bad Gerber run + wasted week + bench fire risk + no audit trail
Your value      ≈  structured splice + KiCad pass + gate checklist + casefile on fail
Your price      ≪  one failed fab spin or one week senior EE time (if positioned right)
```

---

## 2. Buyer personas (deep)

### Persona A — Salvage maker / repair café operator

| | |
|--|--|
| **Pain** | Dead toys, printers, gadgets; wants robot/fixture from junk; afraid of power-on |
| **Budget** | Low–medium; time > software subscription |
| **Buys** | Workshop kit, training, **done-for-you splice session** |
| **v1.0 fit** | **High** — splice + bench gates match safety culture |
| **Price sensitivity** | High — services + OSS self-host may beat SaaS |
| **Taiwan** | 創客、修補團體、社大 — good pilot targets |

### Persona B — Small EMS / prototype house (打樣坊)

| | |
|--|--|
| **Pain** | Clients send bad schematics; NPI rework; “can we fab this?” arguments |
| **Budget** | Medium — tools that reduce rework ROI fast |
| **Buys** | Per-project report, API integration, **bring-up checklist** |
| **v1.0 fit** | **Medium–high** — if framed as **NPI gate**, not salvage hobby |
| **Price sensitivity** | Medium — will pay if tied to fewer respins |
| **Taiwan** | Strong — manufacturing culture understands 沉沒成本 |

### Persona C — University / research lab

| | |
|--|--|
| **Pain** | Students burn boards; need reproducible projects; grant audit |
| **Budget** | Grant lines, lab software |
| **Buys** | Site license, curriculum kit, golden intakes |
| **v1.0 fit** | **Medium** — CI + casefiles sell to lab managers |
| **Taiwan** | 元智、科大、專題 — competition loss doesn’t block this |

### Persona D — Agent / automation integrator

| | |
|--|--|
| **Pain** | Needs **tools** for hardware agents, not slides |
| **Budget** | Developer tooling |
| **Buys** | MCP server, HTTP API, self-host license |
| **v1.0 fit** | **High** — your differentiation vs LLM-only agents |
| **Global** | Cursor ecosystem, indie agent shops |

### Persona E — Test / fixture engineer (semi-adjacent)

| | |
|--|--|
| **Pain** | Interface board bring-up; probe safety; documentation |
| **Budget** | Higher if tied to program schedule |
| **Buys** | Validated package + gate workflow |
| **v1.0 fit** | **Medium** — needs **re-costumed** examples (治具、驗證板), not RC toy pitch |
| **Taiwan** | 欣銓鏈結長期 — short-term competition path closed |

### Persona F — Consumer maker (Blueprint-shaped)

| | |
|--|--|
| **Pain** | “I want a weekend project from a prompt” |
| **Budget** | $0–10/mo |
| **v1.0 fit** | **Low** — wrong UX, wrong breadth |
| **Strategy** | **Do not pursue** as primary v1.0 GTM |

---

## 3. Monetization models (full comparison)

### 3.1 Model matrix

| Model | What customer pays for | You deliver | Solo feasible? | Time to $ | Ceiling | v1.0 ready? |
|-------|------------------------|-------------|----------------|-----------|---------|-------------|
| **1. Done-for-you splice** | Your labor + engine | Intake → build dir + walkthrough | **Yes** | Weeks | Medium | **Yes** |
| **2. Workshop / training** | Day rate + materials | Teach splice + gates on their junk | **Yes** | Months | Low–med | **Yes** |
| **3. Site license (self-host)** | Annual fee | v1.0 + updates + email support | **Yes** | Months | Medium | **Yes** after tag |
| **4. Per-compile API credits** | Per `splice_build` | Hosted HTTP | Medium | Months | High *if* volume | Needs deploy + billing |
| **5. OEM / white-label API** | Integration fee + royalty | Engine behind their UI | Hard solo | 6–12 mo | High | Partial |
| **6. Vertical kit** | Hardware + docs + license | Carrier template + HS workflow | Medium | Months | Medium | Partial |
| **7. Open core + support** | Free OSS, paid support SLA | Priority fixes, onboarding | **Yes** | Slow | Low–med | **Yes** |
| **8. Grant / SBIR** | Non-dilutive R&D $ | Milestones + reports | **Yes** (with 公司) | 3–6 mo | Project-sized | Needs narrative |
| **9. Consumer SaaS** | Monthly sub | Pretty project gallery | **No** (v1.0) | — | Uncertain | **No** |

### 3.2 Recommended sequence (solo, Taiwan-friendly)

```text
Phase 0  Ship v1.0 tag                    (credibility)
Phase 1  Model 1 — 1–3 paid splice jobs   (first revenue signal)
Phase 2  Model 3 — 1 site license pilot   (recurring hint)
Phase 3  Model 8 — SBIR / StarFab         (runway for v2)
Phase 4  Model 4 — hosted API             (only if Phase 1–2 prove demand)
```

**Do not start at Phase 4.**

### 3.3 Pricing sketches (NT$ — adjust after first quote)

*These are **hypotheses** to test, not recommendations. First customer sets the market more than spreadsheets.*

| Offer | Hypothesis range | Notes |
|-------|------------------|-------|
| Single splice session (you operate) | NT$15k–60k | Depends on hours, travel, KiCad hand-holding |
| Half-day workshop | NT$8k–25k | 創客 / school |
| Site license (1 lab, self-host) | NT$30k–120k / year | Support boundary critical |
| Per API compile (hosted) | NT$50–500 / job | Needs cost model vs KiCad CPU |
| SBIR Phase 1 | up to ~NT$1M | R&D, not revenue — see funding doc |

**Anchor against customer cost:** one bad 4-layer respin + week delay often exceeds your annual license hypothesis for a small shop.

---

## 4. Unit economics (rough — fill in your numbers)

### 4.1 Done-for-you splice (Model 1)

| Line | Estimate |
|------|----------|
| Your hours | 8–24 h (first jobs higher) |
| Your opportunity cost | NT$___ / h |
| Software marginal cost | ~0 (self-host) |
| LLM optional cost | NT$0–500 if offline-first |
| **Price floor** | hours × cost × 1.5 margin |
| **Value ceiling** | client’s avoided respin + fire risk |

### 4.2 Hosted API (Model 4) — only if you build it

| Cost driver | Notes |
|-------------|-------|
| KiCad compile CPU | seconds–minutes per job |
| Storage | build artifacts |
| Support | dominates at low volume |
| **Break-even** | usually needs **many** compiles/month or high per-job price |

**Solo warning:** hosted API is a **second product** (ops + billing + abuse). v1.0 source release avoids this until demand proves it.

### 4.3 Open source + paid support (Model 7)

| Pros | Cons |
|------|------|
| Low friction adoption | Hard to enforce payment |
| Portfolio + community | Support time can eat you |
| Good with **services upsell** | Not passive income early |

---

## 5. Competitive alternatives (what customer does if not you)

| Alternative | Their appeal | Your counter |
|-------------|--------------|--------------|
| **Blueprint.am** | Easy project page, prompt | No KiCad gate proof, no salvage, no bench authorization |
| **Flux / ECAD** | Editor, parts | No donor splice, no bench casefiles |
| **Senior EE consultant** | Trusted human | Expensive, not reproducible, no MCP |
| **Student + ChatGPT** | Free | Hallucinated “ready to fab” |
| **Manual KiCad** | Full control | Slow, no splice plan, no gate schema |
| **Do nothing** | $0 | Respins, bench risk |

**Win message:** “We don’t replace your EE — we give you **machine-checkable bring-up** and **refusal with casefiles**.”

---

## 6. What v1.0 proves commercially

| Claim | Evidence you have | Buyer cares? |
|-------|-------------------|--------------|
| Compiles real carriers | `make verify-splice` | High |
| Bench gate model exists | `verify-splice-loop` | Medium–high (safety labs) |
| Agent-callable | MCP + HTTP + SDK | High (integrators) |
| Auditable failure | casefiles | Medium–high (B2B) |
| Project package output | PROJECT_PACKAGE | Medium (deliverable) |
| Production copper | **No** (default) | Low for preview use cases |
| Field validation at scale | **No** | Medium for enterprise |

**Sales honesty:** sell **S2+S3 workflow + gates**; do not sell **fab-ready production copper** without autoroute + human review.

---

## 7. Gaps that block revenue (priority order)

| Gap | Blocks | Fix effort | When |
|-----|--------|------------|------|
| No `v1.0.0` tag | “Is this a product?” | Low | Before any sale |
| No price / offer one-pager | Can’t close | Low | Before outreach |
| No pilot customer | No proof | Medium | Phase 1 |
| No 公司 (TW B2B invoice) | Some TW buyers | Medium | Before SBIR / formal B2B |
| No support SLA doc | License fear | Low | Before site license |
| No hosted uptime | API buyers | High | Phase 4 only |
| Weak semi examples | Persona E | Medium | If chasing 治具 |
| Solo bandwidth | Scale | Co-founder / partner | After first revenue |

---

## 8. Taiwan-specific commercial paths

### 8.1 Still viable after YZU loss

| Path | Type | Fit |
|------|------|-----|
| SBIR 中小企業處 | Grant | R&D on bring-up / NPI gate |
| StarFab / 新竹 AIoT | Accelerator + POC $ | Hardware + AI narrative |
| Mighty Net 盟立 | Industrial validation | Smart mfg, real line POC |
| TTA | International exposure | Deep tech |
| Corporate POC letter | Commercial precursor | EMS, 創客, school lab |
| 政府 AI 新創基金 | Long cycle | After 公司 + traction |

### 8.2 Taiwan GTM angles (language)

| Angle | 一句話 |
|-------|--------|
| NPI 閘門 | 打樣前用 KiCad DRC + 案卷回答「能不能上」 |
| 減少沉沒成本 | 錯誤 Gerber 比軟體貴 |
| 修復／再造 | 死玩具、舊設備 → 載板拼接 |
| Agent 員工 | MCP 可接自動化，不是聊天機器人 |
| 可稽核 | 失敗有 casefile，不是幻覺 |

### 8.3 What Taiwan buyers may not care about

- US VC story  
- Blueprint-style gallery  
- English-only docs (add 1-pager 中文 for B2B)  

---

## 9. Revenue scenarios (illustrative, not forecast)

*Assumptions spelled out so you can stress-test.*

### Scenario A — Side income (conservative)

| Assumption | Value |
|------------|-------|
| Model | 2 splice jobs / year + occasional workshop |
| Avg job | NT$25k |
| **Annual gross** | ~NT$50–80k + workshops |
| Your effort | Part-time |
| **Verdict** | Validates skill; not livelihood |

### Scenario B — Serious side business

| Assumption | Value |
|------------|-------|
| Model | 1 site license + 6 jobs / year |
| License | NT$60k/yr |
| Jobs | NT$30k avg |
| **Annual gross** | ~NT$240k |
| **Verdict** | Plausible solo with v1.0 + reputation |

### Scenario C — Small company trajectory

| Assumption | Value |
|------------|-------|
| Model | 3 licenses + hosted API + grant |
| Team | 2 people by year 2 |
| **Annual gross** | NT$1M+ (wide variance) |
| **Verdict** | Needs pilots + 公司 + deliberate GTM — not v1.0 tag alone |

### Scenario D — Grant-funded R&D (not revenue)

| Assumption | Value |
|------------|-------|
| SBIR Phase 1 | ~NT$1M |
| **Effect** | 6–12 mo runway to build v2 + pilots |
| **Verdict** | Common TW path; milestone pressure |

**Use these to ask:** “Which scenario am I actually trying for?” — not “which is guaranteed.”

---

## 10. Risk register (commercial)

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| No one pays | Medium | High | Phase 1 services; narrow persona |
| KiCad env support burden | High | Medium | `doctor`, Docker doc, clear “BYO KiCad” |
| Liability (bad advice → fire) | Low–med | Very high | Gates, disclaimers, **no power-on authorization marketing** without bench |
| Blueprint / Flux “good enough” | Medium | Medium | Sell salvage + gates, not greenfield UX |
| Solo burnout | High | High | v1.0 scope freeze; paid support limits |
| Open source copied | Medium | Low | Speed, support, pilots, vertical know-how |
| Competition/grant rejection | Happened | Medium | Already documented; other paths remain |

### Liability language (include in any offer)

- KiCad DRC validates **carrier**, not donor harness  
- `power_on_authorized` requires **closed bench gates**  
- Customer responsible for final fab and safety decisions  
- Software is **decision support**, not certification  

---

## 11. Offer templates (copy and adapt)

### 11.1 “Splice Bench Kit” pilot (recommended first SKU)

**Includes:**

- v1.0 install on their machine or your laptop demo  
- 1 live splice case from their donor or golden intake  
- `PROJECT_PACKAGE` + gate checklist walkthrough  
- 30-day email Q&A (bounded hours)  

**Excludes:**

- Custom feature dev  
- 24/7 support  
- Production autoroute  
- Legal certification  

### 11.2 Site license (after one successful pilot)

**Includes:**

- Git tag / release access  
- MCP + HTTP setup guide  
- Quarterly update for 12 months  
- N hours support / year  

### 11.3 Grant milestone framing (SBIR-style)

**Problem:** NPI/bring-up waste on prototype boards  
**Solution:** Agentic compile + gate casefiles  
**Innovation:** Salvage splice + KiCad truth + bench authorization schema  
**Milestones:** v1.0 release → 2 field pilots → metrics on avoided respin (even qualitative)  

---

## 12. Assessment workbook (fill this in)

### 12.1 Personal goals

| Question | Your answer |
|----------|-------------|
| Primary goal in 12 months? | ☐ income ☐ portfolio ☐ company ☐ research |
| Minimum monthly income from HS? | NT$ ______ |
| Hours/week available? | ______ |
| Willing to do client-facing services? | ☐ yes ☐ no |
| Willing to register 公司? | ☐ yes ☐ no ☐ later |
| Accept “side income” ceiling for 2 years? | ☐ yes ☐ no |

### 12.2 Product–market fit signals (track honestly)

| Signal | Status (date) |
|--------|----------------|
| v1.0 tagged | ☐ |
| 3 outreach emails sent | ☐ |
| 1 discovery call | ☐ |
| 1 paid pilot (any amount) | ☐ |
| 1 written testimonial | ☐ |
| 1 repeat customer | ☐ |

**Rule of thumb:** If you can’t get **one paid pilot** in 6 months after v1.0 + outreach, revisit persona or offer — not necessarily kill engine.

### 12.3 Go / no-go decision tree

```text
Ship v1.0?
  └─ Yes (low cost, high optionality)
       └─ Try Model 1 (services) for 3 months
            ├─ Paid pilot? → expand license / grant
            └─ No takers? → narrow persona OR portfolio-only OR v2 costume (semi 治具)
```

**Kill criteria (only if multiple true):**

- You hate client-facing work **and** refuse grants **and** no integrator interest **and** portfolio value insufficient  

**Not kill criteria:**

- YZU loss  
- Blueprint exists  
- No consumer SaaS traction  

---

## 13. Relationship: finish v1.0 vs monetize

| Stage | Technical | Commercial |
|-------|-----------|------------|
| **Now** | Close to v1.0 bar | Competition path closed |
| **+2 weeks** | Tag `v1.0.0` | One-pager offer (中/EN) |
| **+1 month** | Maintenance | 5 outreach messages |
| **+3 months** | v1.0.x bugfixes | 1 pilot or explicit “no market” data |
| **+6 months** | v2 only if pilot/grant | SBIR or license renewal decision |

**Finished product enables monetization** because buyers purchase **bounded, versioned capability** — not a moving GitHub main branch.

---

## 14. Comparison: monetize vs other end states

| End state | When it makes sense |
|-----------|---------------------|
| **Commercial product (this doc)** | You want income/company option; willing to sell pilots |
| **Portfolio / job asset** | Income from employment; HS as proof |
| **Open source hobby** | No sales appetite; maintain for reputation |
| **Acqui-hire story** | Rare; engine as interview depth |
| **Abandon** | Only if kill criteria in §12.3 met — **not** because of YZU/Blueprint alone |

---

## 15. Recommended decision (author’s synthesis)

**For you, today:**

1. **Finish v1.0** — it is the **commercializable unit**.  
2. **Monetize via Model 1 → Model 3**, not consumer SaaS.  
3. **Taiwan:** services + POC + SBIR/StarFab — not YZU retry as primary bet.  
4. **Set a 6-month commercial experiment** after tag — one paid pilot = continue; zero outreach = failure of GTM not engine.  
5. **Do not require “guarantee”** — require **clear signals**.

**One sentence:**

> v1.0 is worth finishing as a **product** because it can be **sold as bring-up infrastructure**; money comes from **who you sell it to and how**, not from tagging alone.

---

## 16. Next documents to create (when ready)

| Doc | Purpose |
|-----|---------|
| `OFFER_SPLICE_BENCH_KIT_v1.md` | 1-page customer-facing offer |
| `SUPPORT_AND_LIABILITY_v1.md` | License boundaries |
| `RELEASE_NOTES_v1.0.md` | Ship with tag |
| `ROADMAP_v2.md` | Ideas **after** commercial signal |

---

## 17. Changelog

| Date | Note |
|------|------|
| 2026-06 | Initial assessment post-YZU; ties to RELEASE_V1 |
