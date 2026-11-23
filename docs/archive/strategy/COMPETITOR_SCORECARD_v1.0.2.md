# Competitor scorecard — v1.0.2 (internal)

**Purpose:** One-page internal matrix — **what job each category solves** and where Hardware-Splicer wins **only layer 5** (bring-up / NPI / power-on proof).

**Status:** July 2026 · Post `v1.0.2` release  
**Deeper reference:** [`COMPETITIVE_PACKAGING_STRATEGY.md`](COMPETITIVE_PACKAGING_STRATEGY.md)  
**Demo proof:** [`COMPARISON_DEMO_CASE_robot_repair_cafe.md`](COMPARISON_DEMO_CASE_robot_repair_cafe.md) · release zip `sample-splice-sprint-robot-repair-cafe.zip`

---

## A. Five layers (where we fight)

| Layer | Job | Who leads | HS stance |
|-------|-----|-----------|-----------|
| 1 | Greenfield design | Flux, EasyEDA | **Do not compete** |
| 2 | Layout/routing automation | Quilter, DeepPCB | **Integrate later; do not lead** |
| 3 | Code/simulation EDA | JITX | **Aspirational cousin; different buyer** |
| 4 | Build package / maker presentation | Blueprint.am, Hackaday | **Adequate tabs; win on truth + gates** |
| 5 | **Bring-up / NPI / power-on verification** | PDF, Notion, tribal EE | **★ Own this** |

**Spine sentence:**

> We do not compete with ECAD on designing boards. We compete with **unstructured bring-up** on making hardware reuse **auditable**.

---

## B. Direct vs adjacent

| Bucket | Examples | vs HS |
|--------|----------|-------|
| **Direct substitute** | KiCad + manual checklist, Notion/PDF NPI | Same job, worse artifacts |
| **Adjacent (wrong pitch)** | Flux, EasyEDA | Greenfield ECAD — different starting point |
| **Adjacent (partners)** | Quilter | Route our carrier; we own gates/handoff |
| **Adjacent (intake)** | SINA, PCBSchemaGen, ProtoFlow | May feed **intake**; we own package + gates |
| **Substrate** | KiCad | Engine truth, not competitor |

**Real enemy:** manual bring-up chaos — not Flux logos.

---

## C. Comparison dimensions

| Dimension | Why it matters | HS v1.0.2 target |
|-----------|----------------|------------------|
| Starting point | Defines category | Donor / splice / repair / prototype |
| Primary user | Defines buyer | Lab operator, repair café, prototype shop |
| Input | Friction | Intake JSON/UI, donor fixtures, KiCad artifacts |
| Output artifact | Defines value | `PROJECT_PACKAGE` zip |
| Verification | Defines trust | KiCad DRC + bench gates + `COMPILE_CASEFILE` |
| Failure behavior | Seriousness | Gate blockers, casefile JSON — not vague errors |
| Power-on boundary | Safety posture | Operator authorizes energization |
| Deployment | Fundability | Self-hosted Linux/WSL, HTTP + MCP |
| Reproducibility | Maturity | `make verify-product-internal`, install reports |
| Revenue wedge | First money | Splice Sprint / site license |

---

## D. Scorecard (1–5, directional)

**Not “we beat everyone.”** “We win where the job is donor bring-up + gates + handoff.”

| Capability | Flux | Quilter | JITX | KiCad/manual | Notion/PDF | **HS v1.0.2** |
|------------|:----:|:-------:|:----:|:------------:|:----------:|:-------------:|
| Greenfield PCB UX | 5 | 2 | 3 | 3 | 1 | **1** |
| Routing/layout automation | 3 | **5** | 4 | 3 | 1 | **1–2** |
| Donor/salvage workflow | 1 | 1 | 1 | 2 | 1 | **5** |
| Bench gate tracking | 1–2 | 2 | 2–3 | 1 | 2 | **5** |
| `PROJECT_PACKAGE` handoff | 2–3 | 3 | 3 | 1–2 | 1 | **5** |
| Failure casefile / gate blocker | 2 | 3 | 4 | 1 | 1 | **4–5** |
| Self-host lab pilot | 1–2 | 2–3 | 2 | **5** | 5 | **4** |
| Maker/prototype affordability | 2–3 | 1–2 | 1 | **5** | 5 | **3–4** |
| Fundable verification infra story | 3 | 4 | **5** | 2 | 1 | **4** |

---

## E. Do-not-compete axes

Do **not** pitch or roadmap against:

- Browser ECAD polish (Flux)
- Dense autoroute leadership (Quilter)
- HF/enterprise SI (JITX)
- Component cloud depth (EasyEDA/LCSC)
- “AI designs any board” consumer SaaS

---

## F. One-line counters (sales / grant)

| They say | Say |
|----------|-----|
| “Like Flux?” | “Flux is **idea → PCB**. We're **donor/splice → carrier + gates + handoff**.” |
| “Like Quilter?” | “Quilter is **schematic → routed PCB**. We structure **bring-up before power-on**.” |
| “Like JITX?” | “JITX is **code/sim → validated design**. We're **physical reuse → auditable package**.” |
| “Like KiCad?” | “We're a **workflow layer on KiCad**, not better KiCad.” |
| “Like Blueprint?” | “Same package **shape** — we add **DRC proof, bench gates, salvage path**.” |

---

## G. Roadmap implication (summary)

See [`ROADMAP_FROM_COMPETITOR_GAPS.md`](ROADMAP_FROM_COMPETITOR_GAPS.md).

**Only build what comparison exposes as wedge weakness** — not competitor feature parity.

---

## H. Repo tension (honest)

[`FLUX_TARGET.md`](FLUX_TARGET.md) frames engine ambition (“beat Flux on compile truth”). This scorecard frames **v1 GTM wedge** (layer 5). Both stand — see [`ENGINE_VS_INTERFACE.md`](ENGINE_VS_INTERFACE.md): **under-interfaced, not under-powered**; plug OSS editors rather than chase Flux UX from scratch.

[`FLUX_TARGET.md`](FLUX_TARGET.md) “kill Flux” language is **engine thesis**, not pilot SKU copy.

---

*Internal only. Last updated: 2026-07-07 · v1.0.2*
