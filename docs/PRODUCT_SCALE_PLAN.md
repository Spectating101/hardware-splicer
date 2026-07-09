# Product scale plan — Splice Agent (2026–2027)

**Purpose:** Define what we are building, at what depth, in what order — for founder, agents, and future contributors.

**Status:** Active · July 2026  
**Anchor tag:** `v1.1.0-alpha.12` (cold-internal dry-run bar)  
**Related:** [`SPLICE_PRODUCT.md`](SPLICE_PRODUCT.md) · [`INTERNAL_MATURITY_PLAN.md`](INTERNAL_MATURITY_PLAN.md) · [`DESIGN_STUDIO_DRC_AGENT.md`](DESIGN_STUDIO_DRC_AGENT.md) · [`AGENT_QUICKSTART.md`](AGENT_QUICKSTART.md) · [`AGENT_DRY_RUN_CHECKLIST.md`](AGENT_DRY_RUN_CHECKLIST.md)

---

## 1. North star (one sentence)

**An agent-native hardware workbench** where natural language or canvas graphs become KiCad carriers, **DRC and bench measurement are the judge**, and humans inspect the same spine in Design Studio.

**Not:** hosted Flux clone, full schematic editor, JLC checkout SaaS.  
**Yes:** Flux-class **first mile** + auditable **last mile** + salvage/bench moat.

---

## 2. Product spine (do not fork)

```text
Describe (phrase / canvas / donor intake)
    → compose_dispatch (canvas | scratch | llm_first)
    → compose_agent_loop (bounded manual DRC rounds)
    → KiCad compile + drc_fix_loop
    → PROJECT_PACKAGE + bench_session
    → gates → fab / bring-up
```

| Surface | Role |
|---------|------|
| **MCP / HTTP / SDK** | Primary — agents drive the product |
| **Design Studio** | Human legibility on the same endpoints |
| **Salvage / circuit-ai** | Donor intake → same compile path (Phase 2) |
| **KiCad** | Source of schematic/PCB truth — we do not replace it |

**Rule:** No second compile path. UI features call `POST /v1/compose/agent-loop` or `hs_compose_drc_agent`.

---

## 3. Maturity map (honest)

| Tier | Name | Today (alpha.12) |
|------|------|------------------|
| **S2** | Carrier compile (CI) | ✅ `make verify-splice` |
| **S3** | Bench gates | ✅ Simulated compose bench-loop + **golden-real** manual capture path |
| **S5 partial** | Greenfield compose | 🟡 Phrase/canvas → 0 DRC; copper still `cosmetic_preview` by default |
| **Agent spine** | MCP = HTTP = SDK = UI | ✅ Catalog 50, async jobs, agent-loop parity; Design Studio on same spine |
| **Salvage unified** | Donor → same agent loop | ✅ `donor_context` on agent-loop / MCP / HTTP |
| **Bench + vision** | Capture assist | 🟡 Draft from photos (`vision-assist`); does **not** close gates |
| **External readiness** | Zero-help dry-run | 🟡 **Cold-internal** (optiplex archive + FGEDHGV) substitutes for strangers |

---

## 4. Phased execution

### Phase 0 — Alpha stabilize (now → ~4 weeks)

**Goal:** Spine boringly reliable for you + one external agent operator.

| # | Deliverable | Status |
|---|-------------|--------|
| 0.1 | Tag `v1.1.0-alpha.5`, push `main` | ✅ (superseded by later alphas) |
| 0.2 | `docs/PRODUCT_SCALE_PLAN.md` (this file) | ✅ |
| 0.3 | `docs/AGENT_QUICKSTART.md` — 3 curls + 3 MCP calls | ✅ |
| 0.4 | `docs/AGENT_BUILD_DIR_POLICY.md` — MCP `hs_design_quality` paths | ✅ |
| 0.5 | Design Studio: AI phrase → agent-loop + package | ✅ |
| 0.6 | `make verify-product-internal` green | ✅ |
| 0.7 | Canvas catalog → 50 modules + pin contract tests | ✅ |
| 0.8 | Cold-internal dry-run bar (archive + alien) | ✅ alpha.12 |

**Exit criteria:** Fresh archive → agent loop + salvage + bench + vision draft in &lt;15 min without author hand-holding. See [`AGENT_DRY_RUN_CHECKLIST.md`](AGENT_DRY_RUN_CHECKLIST.md).

---

### Phase 1 — Beta workbench (1–3 months)

**Goal:** Agents are the primary customer; UI is inspection + override.

| Track | Deliverables | Status |
|-------|----------------|--------|
| **Agent API** | Versioned `agent_loop` schema; async job for long compiles; webhook optional | ✅ async jobs; webhook deferred |
| **Module graph** | 50+ modules; pin contract validation; LLM picker telemetry | ✅ 50 + pin tests |
| **DRC agent** | Smarter fixup policy; `cosmetic_preview` → `review_required` → `fab_ready` ladder | 🟡 0 DRC path works; copper ladder still soft |
| **Package** | `PROJECT_PACKAGE` schema version; wiring steps ↔ gate checklist | 🟡 package present; deeper gate card wiring ongoing |
| **Salvage bridge** | `donor_context` on `hs_compose_drc_agent` from circuit-ai intake | ✅ |

**Exit criteria:** Cursor/Claude agent designs → fixes DRC → delivers zip + gate card without browser. **Cold-internal proxy:** green on optiplex archive + FGEDHGV.

---

### Phase 2 — Product depth (3–9 months)

**Goal:** Flux-class intake + bench moat — not Flux feature parity.

| Track | Deliverables | Status |
|-------|----------------|--------|
| **Design Studio** | Pin wire editing; live DRC hints; open in KiCad one-click | 🟡 agent-loop wired; deeper ECAD UX deferred |
| **Bench loop** | Capture template → submit → power-on; camera assist | 🟡 `hs_compose_bench_loop` + `vision-assist` draft; golden-real non-sim path |
| **Salvage** | Photo → functional blocks → splice plan → carrier in one session | 🟡 offline salvage on agent-loop; live photo→blocks still optional |
| **Copper truth** | Path from `cosmetic_preview` to autoroute tier when `AUTOROUTE=1` | 🟡 opt-in only |
| **Integrations** | KiCad MCP sidecar; JLC enrich read-only on BOM | ⬜ |

**Exit criteria:** Repair café case: donor photo → carrier PCB → measured gates → fab zip.

---

### Phase 3 — Scale & distribution (9–18 months)

**Goal:** Self-hosted SKU + one vertical wedge — not mass SaaS.

| Option | Shape |
|--------|-------|
| Self-hosted kit | Docker / `hs-serve` for labs and shops |
| Agent hosting | MCP server as product; UI optional |
| Vertical wedge | Pick one: repair refurb, edu makerspace, IoT module carriers |

**Exit criteria:** 3–5 paying labs; case studies with real DRC + bench evidence.

---

## 5. Explicitly deferred

- Full schematic editor (KiCad stays truth)
- Hosted multi-tenant SaaS
- Production autorouting as default
- JLC one-click order
- Mech splice as day-one blocker
- “Beat Flux” marketing

---

## 6. Metrics (not vanity)

| Phase | Metric |
|-------|--------|
| Alpha | Agent loop success rate; time-to-package; DRC rounds to 0 errors |
| Beta | External agent sessions/week without support |
| Product | % packages with gates closed before power-on |
| Commercial | Paid self-hosted installs; salvage cases completed |

---

## 7. Work allocation (internal)

```text
Phase 0–1:  70% agent spine + DRC honesty + tests
            20% Design Studio legibility (not ECAD parity)
            10% docs when code changes
Phase 2+:   shift toward salvage + bench when Phase 1 exit green
```

Competitive essays and outreach templates are **not** internal gates. See [`INTERNAL_MATURITY_PLAN.md`](INTERNAL_MATURITY_PLAN.md).

---

## 8. Architecture (frozen)

```mermaid
flowchart LR
  subgraph entry [Entry]
    A[Agent MCP HTTP SDK]
    B[Design Studio UI]
    C[Salvage intake]
  end
  subgraph spine [Single spine]
    D[compose_dispatch]
    E[compose_agent_loop]
    F[KiCad DRC fix]
    G[PROJECT_PACKAGE]
    H[Bench gates]
  end
  A --> D
  B --> E
  C --> D
  D --> E --> F --> G --> H
```

---

## 9. Next actions (after alpha.12)

1. ~~Cold-internal dry-run bar (archive + alien + vision-assist).~~ ✅ [`install_reports/`](install_reports/)
2. Keep **golden-real** (non-simulated capture) in the automated quickstart bar.
3. Optional: Qwen cold path (`HS_QUICKSTART_QWEN=1`) on FGEDHGV when keyed.
4. Phase 2 depth: live photo → salvage blocks; real instrument capture (not only golden JSON).
5. Copper honesty ladder toward `fab_ready` when autoroute is on.

---

## 10. Changelog

| Date | Change |
|------|--------|
| 2026-07-08 | Initial product scale plan; Phase 0 doc + studio wiring for alpha.5 |
| 2026-07-10 | Refresh maturity to alpha.12; cold-internal readiness; bench/vision status |
