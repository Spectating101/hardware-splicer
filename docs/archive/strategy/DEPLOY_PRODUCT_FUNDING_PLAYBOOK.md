# Deploy · Product · Funding — practical playbook

**Purpose:** How to push Hardware-Splicer Splice Agent v1.0 from **working engine** → **deployable product** → **revenue or non-dilutive capital** — without pretending you are Blueprint or a funded SF robotics startup.

**Audience:** You, advisors, pilot partners, grant reviewers, accelerator screeners.

**Prerequisites (engine):** Run `make verify-splice-v1` green on the machine you demo from.

**Related:** [`MONETIZATION_AND_PRODUCT_ASSESSMENT.md`](MONETIZATION_AND_PRODUCT_ASSESSMENT.md) · [`PACKAGING_AND_DEPLOYMENT.md`](PACKAGING_AND_DEPLOYMENT.md) · [`BLUEPRINT_POSITIONING_AND_FUNDING.md`](BLUEPRINT_POSITIONING_AND_FUNDING.md) · [`RELEASE_V1.md`](RELEASE_V1.md)

**Last updated:** July 2026

---

## 1. Executive thesis

| Question | Answer |
|----------|--------|
| What are you selling? | **Auditable hardware bring-up** — splice plan + KiCad carrier + bench gates + project package — not “prompt → pretty page” |
| What is deployable today? | Self-host **CLI + MCP + HTTP API** on a KiCad machine; optional thin UI |
| Best near-term money? | **Paid pilot / services** → **site license** → **SBIR Phase 1** (with 公司) |
| Best near-term credibility? | `verify-splice-v1` + one **field letter** from a lab/café/EMS |
| Worst path? | Consumer SaaS race vs Blueprint |
| YZU 2026 lesson | Semi **Agent vocabulary + in-fab narrative** wins proposal rounds; your **engine** wins POC rounds — pick the room |

**One line for decks:**

> Hardware-Splicer is a **verified hardware agent**: salvage intake → KiCad DRC truth → bench gates before power-on — for teams who cannot afford “looks good” schematics.

---

## 2. What you can showcase today (proof stack)

Reviewers and pilots should see **evidence**, not slides.

### 2.1 CI bar (reproducible)

```bash
make verify-splice-v1
```

| Step | Proves |
|------|--------|
| `doctor` | KiCad, Node, Python, API deps |
| `test-project-package` | Blueprint-shaped artifacts |
| `verify-splice` | 4/4 manifest S2 compile |
| `verify-splice-loop` | 3/3 S3 bench closure |
| `verify-splice-real-bench` | Real photo + manual capture → `power_on_authorized` |

### 2.2 Live demo (5–10 min)

```bash
bash scripts/install_splice_v1.sh
hs-doctor
hs-serve --host 127.0.0.1 --port 8787
# optional: make splice-ui-dev
```

**Show in order:**

1. `GET /health` — version, roots OK  
2. Example intake → `POST /v1/jobs/splice-build` → poll → **PROJECT_PACKAGE**  
3. **GATES** tab: verdict `BLOCKED` / `COMPILE_READY_REVIEW_BENCH` — honest  
4. **Bench**: submit one measurement → gate closes  
5. On failure: **COMPILE_CASEFILE** — not hand-wavy LLM excuse  
6. MCP in Cursor: `hs_splice_build` — same spine as HTTP  

### 2.3 Artifacts to hand someone

Zip from `GET /v1/jobs/{id}/bundle` or folder:

- `PROJECT_PACKAGE.json` + `PROJECT_PAGE.md`  
- `SPLICE_PLAN.json`  
- `SPLICE_BENCH_SESSION.json`  
- `build_compilation/*.kicad_pcb` + DRC report  
- `COMPILE_CASEFILE.json` (if blocked — shows maturity)

### 2.4 Numbers that matter in pitches

| Metric | Order of magnitude (this repo) |
|--------|--------------------------------|
| Engine Python | ~37k LOC |
| Tests | 576+ passing |
| MCP tools | 25 |
| Splice manifest cases | 4 S2 + 3 S3 loop |
| Team | Solo (disclose; mitigate with pilot partner) |

---

## 3. Product ladder — what to sell when

Do **not** skip rungs. Each rung produces evidence for the next.

```text
Rung 0  Tag v1.0 + verify-splice-v1 green     → credibility
Rung 1  1–3 paid splice jobs (you operate)    → first revenue + case study
Rung 2  Site license (lab / EMS self-host)    → recurring hint
Rung 3  SBIR Phase 1 or accelerator           → runway
Rung 4  Hosted API + credits                    → only if Rung 1–2 prove demand
```

### Rung 0 — Credibility SKU (free / OSS)

**Offer:** `Hardware-Splicer Splice Agent v1.0` — MIT or source-available + docs.

**Buyer gets:** `install_splice_v1.sh`, MCP config, manifest cases, `make verify-splice-v1`.

**You get:** GitHub tag, reproducible bar, something to link in grants.

### Rung 1 — Done-for-you splice (fastest $)

**Buyer:** Repair café, 創客空間, university lab, indie robotics team.

**Deliverable:**

| Item | Description |
|------|-------------|
| Intake session | 1–2 h — parts on table, donor photo optional |
| Build | You run engine; customer watches or async |
| Handoff | PROJECT_PACKAGE zip + 30 min walkthrough |
| Bench | They close gates; you review first power-on |

**Price hypothesis:** NT$15k–60k per project (hours × margin; anchor vs one bad fab week).

**Contract line:** Engine assists; **customer owns power-on decision** after gates.

### Rung 2 — Site license (self-host)

**Buyer:** Lab manager, small EMS NPI desk, agent shop.

**Deliverable:** v1.0 install on **their** Linux + email support + quarterly update.

**Price hypothesis:** NT$30k–120k / year.

**Support boundary:** You fix engine bugs; they own KiCad install and donor safety.

### Rung 3 — Engine / API license (B2B)

**Buyer:** Agent integrator, internal tools team.

**Deliverable:** MCP + HTTP on their infra; optional white-label.

**Requires:** Stable job API, changelog, SLA — after Rung 2 pain is understood.

### Rung 4 — Hosted SaaS (defer)

Needs: auth, billing, KiCad worker pool, abuse controls, legal. **Not v1.0.**

---

## 4. Deployment models (honest)

KiCad **must** run where compile runs. There is no magic serverless KiCad.

### Model A — Bench laptop (default v1)

```text
[Operator laptop]
  KiCad 9 + Node 18 + hs-serve :8787
  Browser optional (splice-ui or curl)
  Artifacts → local disk / USB handoff
```

**Best for:** Rung 1 services, demos, repair café on-site.

**Cost:** $0 infra.

### Model B — Lab server (site license)

```text
[Lab Linux box on LAN]
  systemd: hardware-splicer.service
  nginx TLS + API key (you configure)
  Engineers on VPN/LAN only
```

See `deploy/systemd/hardware-splicer.service.example`, `deploy/DEPLOY.md`.

**Best for:** Rung 2 university / EMS.

**Cost:** existing hardware or ~NT$15k mini PC.

### Model C — Private VPS (integrator)

```text
[VPS 4+ vCPU]
  hs-serve + KiCad in same VM (Ubuntu)
  Job queue (built-in SQLite backend)
  No public marketing site — IP allowlist
```

**Best for:** Agent integrator pilot.

**Cost:** ~US$20–80/mo + your maintenance.

**Risk:** KiCad in cloud is fragile; document reboot/recovery.

### Model D — Public multi-tenant SaaS

**v2+.** Do not promise in grants until Model C has one paying integrator.

---

## 5. Showcase scripts by audience

### 5.1 Repair café / 創客 (Rung 1)

**Hook:** “We won’t tell you to power on until the checklist is green.”

**Show:** RC toy → robot drive example → open gates → one fake measurement close.

**Ask:** One paid pilot with their dead printer / toy; photo + case write-up.

### 5.2 EMS / 打樣坊 (Rung 2)

**Hook:** “NPI gate before Gerber — auditable casefile when compile fails.”

**Reframe:** Not “junk salvage hobby” — **bring-up documentation + DRC truth**.

**Show:** `verify-splice` report JSON + PROJECT_PACKAGE gates verdict.

**Ask:** 3-month site license trial on one NPI desk; metric = fewer “can we fab this?” arguments.

### 5.3 University lab (Rung 2 + grant co-author)

**Hook:** “Students get reproducible project packages + CI-like gates, not one-off Fritzing.”

**Show:** Golden intakes + `make verify-splice-v1` in README.

**Ask:** Letter of collaboration for SBIR; curriculum kit later.

### 5.4 Grant reviewer (SBIR Phase 1)

**Hook:** **創新服務** — AI-assisted hardware NPI with **deterministic verification layer**.

**Must include:**

| Section | Content |
|---------|---------|
| Innovation | Gate semantics + KiCad compile spine; not LLM-only agent |
| Difference | vs generative ECAD: **salvage + bench truth** |
| KPIs | e.g. DRC pass rate on manifest; gate closure time; pilot N projects |
| Market | TW EMS, labs, repair economy, agent tooling |
| Team gap | Solo → hire 1 FT or named university/EMS partner |
| Budget | Phase 1 ≤ NT$150万 / 6 mo (115年度 SBIR) |

**Do not lead with:** “80% no LLM” — lead with **Agentic loop: plan → compile → measure → authorize**.

### 5.5 Accelerator (StarFab TAI1, AppWorks)

**Hook:** **AI × hardware × manufacturing** — soft-hard co-validation for prototyping.

**Fit keywords:** smart manufacturing, LLM Agent, industrial POC, NVIDIA stack (if you add GPU bench vision later).

**TAI1 (check current cohort deadlines):** [StarFab TAI1](https://zh.starfabx.com/) — AI accelerator, industry POC, ~NT$300万 investment mention for selected teams (terms vary by cohort).

**Ask:** Corporate POC with one StarFab-linked manufacturer — even unpaid LOI helps.

### 5.6 Semiconductor-adjacent (post-YZU reframe)

YZU finals favored **in-fab / yield / ESG / equipment** Agent stories. Your engine fits **test & verification culture** if you **re-costume**:

| Old pitch | Reframed pitch |
|-----------|----------------|
| RC toy salvage | **Interface / fixture board bring-up** with measurement gates |
| Junk robot | **NPI carrier** for validated interconnect before system power-on |
| “Not really semi” | **Downstream of ATE mindset** — evidence before energize |

**Demo:** Same `verify-splice-loop`; **slides** say 治具、驗證板、開路電壓閘門.

---

## 6. Funding map (Taiwan-first)

| Channel | Type | Fit | Blocker | Next action |
|---------|------|-----|---------|-------------|
| **Paid pilot** | Revenue | ★★★★★ | No customer yet | 3 outreach emails to cafés/labs |
| **SBIR Phase 1** | Grant ~NT$150万 | ★★★★ | 台灣公司 | Register 公司; attend [SBIR 說明會](https://www.sbir.org.tw/) |
| **SBIR Phase 2** | Grant up to ~NT$1200万 | ★★★ | Phase 1 + prototype | After Phase 1 + pilot data |
| **StarFab TAI1** | Accelerator + POC | ★★★★ | Application window | Watch [zh.starfabx.com](https://zh.starfabx.com/) |
| **TTA** | Deep tech | ★★★ | Deck + team | After pilot case study |
| **Mighty Net / 盟立** | Smart mfg POC | ★★★ | Factory partner | Reframe as NPI gate tool |
| **Corporate POC** | Customer $ | ★★★★★ | Warm intro | EMS you already know |
| **YZU-style Agent comp** | Prize / visibility | ★★ | Narrative mismatch | Reframe or skip until team + semi vocabulary |
| **US VC (Blueprint path)** | Equity | ★ | Wrong shape | Defer |

**SBIR practical notes (115年度):**

- Rolling application — [sbir.org.tw](https://www.sbir.org.tw/)  
- Phase 1: **簡報** format (lower friction)  
- 50% match funding; need 中小企業 entity  
- Emphasize **創新服務** + measurable KPIs on compile/gate closure  

---

## 7. Packaging checklist before anyone pays

| Item | Status | Action |
|------|--------|--------|
| `make verify-splice-v1` green | ✅ on dev machine | Run on clean VM |
| Git tag `v1.0.0` | ✅ | Tagged on `main` |
| `RELEASE_NOTES_v1.0.md` | ✅ | Root release notes |
| `install_splice_v1.sh` slim path | ✅ | `INSTALL_DEV=1` for pytest |
| GitHub `splice-v1` CI job | ✅ | `.github/workflows/hardware-splicer.yml` |
| One-page offer PDF | Pending | `OFFER_SPLICE_BENCH_KIT_v1.md` |
| Liability boundary | Pending | `SUPPORT_AND_LIABILITY_v1.md` |
| Pilot case study | Pending | Rung 1 customer |
| LOI from partner | Pending | Lab / EMS / café |

---

## 8. 90-day action plan (solo, realistic)

### Days 1–14 — Freeze & prove

- [ ] Tag `v1.0.0` after `make verify-splice-v1` on clean install  
- [ ] Record **5 min screen capture**: job build → gates → bench submit  
- [ ] Write one-page offer (Rung 1 pricing hypothesis)  

### Days 15–45 — First commercial experiment

- [ ] Outreach: 5 repair cafés / makerspaces / university shops (TW)  
- [ ] Goal: **1 paid splice** or signed pilot MOU  
- [ ] Deliver PROJECT_PACKAGE + short case study (before/after gates)  

### Days 46–70 — License + entity

- [ ] If pilot succeeds: quote site license to same org  
- [ ] If pursuing SBIR: register 公司, draft Phase 1 deck (簡報)  
- [ ] Named advisor or co-founder on deck (mitigate solo risk)  

### Days 71–90 — Funding application

- [ ] Submit SBIR Phase 1 **or** StarFab TAI1 (whichever window open)  
- [ ] Attach: verify report, pilot case, architecture diagram (§4)  
- [ ] Apply with **Agentic verification** language, not “anti-LLM compiler”  

---

## 9. Pitch deck outline (10 slides)

1. **Problem** — Bad bring-up costs more than software; LLM schematics aren’t auditable  
2. **Solution** — Verified hardware agent: splice → KiCad → gates  
3. **Demo screenshot** — PROJECT_PACKAGE + GATES verdict  
4. **How it works** — diagram from §4 Model A  
5. **Proof** — `verify-splice-v1` + manifest table  
6. **Differentiation** — vs Blueprint (breadth) vs Flux (editor) — **truth + salvage**  
7. **Market** — EMS NPI, labs, repair, agent integrators (TW first)  
8. **Business model** — Rung 1 → 2 → SBIR (not SaaS yet)  
9. **Traction** — pilots, CI, commits (honest)  
10. **Ask** — NT$X pilot / Phase 1 / POC partner  

---

## 10. Risks (say them out loud)

| Risk | Mitigation |
|------|------------|
| Solo founder | Pilot partner letter; advisor; hire on SBIR |
| KiCad on customer machine | `install_splice_v1.sh` + doctor; you do first install |
| `ok: false` confuses users | Train: **blocked gates ≠ broken engine** |
| Competition narrative mismatch | Pick funding rooms that want **POC + manufacturing** |
| Blueprint catches salvage | Move faster on **gates + CI proof** moat |
| No revenue by day 90 | Still have OSS + SBIR optionality; don’t go all-in SaaS |

---

## 11. What not to do (learned)

- Don’t lead funding pitches with consumer UI parity  
- Don’t enter semi Agent comps with “junk robot” hero story alone  
- Don’t build hosted SaaS before one paying self-host customer  
- Don’t claim power-on safety certification — you sell **checklists + compile truth**  
- Don’t kill the project because YZU proposal lost — **wrong room**, not wrong engine  

---

## 12. Quick reference commands

```bash
# Credibility
make verify-splice-v1

# Install (customer machine)
bash scripts/install_splice_v1.sh
hs-doctor

# Operate
hs-serve --host 0.0.0.0 --port 8787
hs-mcp   # Cursor agents

# Demo build
make splice-demo
```

---

**Bottom line:** Deploy as **self-host verified agent** on KiCad hardware; product as **services → site license**; fund via **pilot revenue + SBIR/StarFab** with **manufacturing verification** narrative. The engine is ready to support that story — the missing pieces are **tag, pilot customer, and deck in the right vocabulary**.
