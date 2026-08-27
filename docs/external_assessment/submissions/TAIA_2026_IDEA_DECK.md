# TAIA 2026 — Graduate Track Idea Deck

**Project:** Hardware-Splicer  
**Submission identity:** *A Bounded Engineering Environment for Tool-Using AI Agents*  
**Target emphasis:** Graduate AI Agent Architecture / Smart Manufacturing  
**Length:** 15 slides maximum

This is submission-ready content. Render visually; do not add claims beyond the canonical evidence ledger.

---

## Slide 1 — Hardware-Splicer

### A Bounded Engineering Environment for Tool-Using AI Agents

**Auditable agentic hardware engineering under bounded physical authority**

> AI proposes → deterministic systems constrain → bench evidence decides → human authorizes.

**One-line value:**

Hardware-Splicer lets general-purpose AI agents perform hardware-engineering work without letting model confidence silently become physical truth.

**Visual:** clean product hero + four-layer architecture mini-strip.

---

## Slide 2 — The problem is not that AI can be wrong

### The problem is when a plausible answer becomes a physical action too early

A model may produce a convincing hardware answer before we actually know:

- the exact component identity;
- voltage/interface compatibility;
- which source supports the claim;
- whether that source is current for this revision;
- whether deterministic checks succeeded;
- whether anything was measured on real hardware.

**Hardware consequence:** a fluent mistake can become a fabricated or powered mistake.

**Visual:** AI answer → PCB/power icon, interrupted by missing-evidence warning cards.

---

## Slide 3 — Design principle: separate reasoning from authority

Hardware-Splicer treats four layers independently:

### 1. Model reasoning
Interpret, plan, propose, revise.

### 2. Deterministic engineering constraints
Identity, interface rules, exact project/revision state, invariant checks.

### 3. Evidence
Provenance-bearing records tied to exact revisions/artifacts.

### 4. Authority
Explicit scoped human permission after relevant evidence is valid.

**Key rule:** Model confidence never substitutes for missing evidence.

---

## Slide 4 — System architecture

```text
General-purpose AI / agent
          │
          ▼
       MCP / API
          │
          ▼
┌─────────────────────────────────────────┐
│            HARDWARE-SPLICER             │
│ project + exact revision state          │
│ source/evidence provenance              │
│ semantic engineering planning           │
│ deterministic interface constraints     │
│ engineering artifacts / package         │
│ revision-bound physical evidence        │
│ authorization ledger                    │
└─────────────────────────────────────────┘
          │
          ▼
      candidate / package
          │
      evidence gates
          │
          ▼
     human authorization
          │
          ▼
       physical world
```

**Current proof:** 193 canonical backend operations are reachable through the MCP gateway.

---

## Slide 5 — Why make the model replaceable?

### Hardware-Splicer is the engineering shell, not the AI model

A single embedded AI makes it difficult to distinguish:

- model quality;
- engineering-system quality;
- safety/authority behavior.

Hardware-Splicer instead supports:

> **Bring your own agent. Give it an auditable engineering environment.**

A GPT/Claude/Qwen/other agent can enter through MCP while engineering state, evidence and authority remain outside the model.

**Research benefit:** compare agents under the same engineering constraints.

**Product benefit:** model choice can evolve without rebuilding the engineering truth layer.

---

## Slide 6 — A real bounded use case

### Semiconductor test and validation support hardware

Representative workflow:

- adapter boards;
- carrier boards;
- validation fixtures;
- lab/NPI support hardware.

Example task:

**Prepare an SPI-flash adapter path from incomplete or conflicting evidence.**

The system must distinguish what is known from what merely looks plausible before any fabrication/power authority is opened.

**Not claimed:** chip design, wafer-process automation, autonomous production certification.

---

## Slide 7 — What Hardware-Splicer actually does

The repository contains working surfaces for:

- project/revision persistence;
- source and evidence ingestion;
- semantic engineering planning;
- deterministic electrical/interface checks;
- KiCad/DRC-related engineering flows;
- engineering-package generation;
- physical-evidence records;
- authorization state/ledger;
- Web / HTTP API / CLI / MCP access.

**Difference from a chatbot:** the durable output is structured engineering state and evidence, not just prose.

**Visual:** project workflow screenshot sequence.

---

## Slide 8 — Adversarial evaluation, not only a happy path

### Frozen 10-case SPI-flash corpus

1. baseline
2. source reverse
3. source rotate
4. neutral labels
5. mission paraphrase
6. partial evidence
7. identity conflict
8. parser failure
9. analogy trap
10. stale revision

**Purpose:** test whether the engineering process stays auditable under incomplete, conflicting and misleading evidence.

**Protocol discipline:** cases are frozen before the live model run and are not rewritten after results are visible.

---

## Slide 9 — What happens when the agent is wrong?

Hardware-Splicer can preserve:

- unresolved identity;
- conflicting evidence;
- deterministic tool failure;
- stale evidence;
- unsupported fabrication/power readiness;
- revision invalidation;
- failure → repair → revalidation history.

### The desired behavior is not “always answer”

It is:

> **Wrong or uncertain does not automatically become authorized.**

**Visual:** one identity-conflict or stale-revision example ending in BLOCKED/UNRESOLVED.

---

## Slide 10 — Real MCP proof exists today

At the current external-proof checkpoint:

- real MCP stdio client: **PASS**;
- real Streamable HTTP MCP client: **PASS**;
- canonical project write → read → delete over MCP: **PASS**;
- canonical operation count: **193**;
- frozen ten-case inventory validation: **PASS**;
- external trace-audit harness: **PASS**;
- MCP physical-authority grant: **FALSE**.

**Important:** this proves the model-independent engineering interface and proof harness. It does **not** claim that a live external model has already passed the ten-case corpus.

---

## Slide 11 — Evidence itself is governed

### Software success ≠ physical success

For real physical evidence:

- real-vs-simulated state must be explicit;
- missing simulation state is blocking;
- evidence is tied to exact revisions/artifacts;
- authorization is a separate human decision;
- relevant revision changes can invalidate previous authority.

**Key line:**

> Even the evidence proving the hardware is real has to prove that it is real.

**Visual:** PhysicalEvidence → hash/revision binding → human authorization chain.

---

## Slide 12 — Current truth state

| Evidence layer | State |
|---|---|
| frozen software architecture | **PROVEN** |
| deterministic adversarial cleanroom | **PROVEN** |
| ten-case unseen corpus/protocol | **PROVEN** |
| canonical MCP transport | **PROVEN** |
| external-agent trace/replay infrastructure | **PROVEN** |
| live external-model unseen result | **PENDING** |
| fresh SPI physical result | **PENDING** |
| independent human operator | **PENDING** |
| production readiness | **NOT CLAIMED** |

### Why show pending proof?

Because trustworthiness begins with refusing to relabel missing evidence as success.

---

## Slide 13 — Why this matters for Smart Manufacturing

AI-assisted engineering can reduce repeated preparation work, but manufacturing environments cannot accept “the model sounded confident” as a release criterion.

Hardware-Splicer is designed for workflows where:

- evidence must survive handoffs;
- revisions matter;
- mistakes have physical cost;
- AI should accelerate preparation without owning final physical authority.

Near-term application surfaces:

- semiconductor validation/support fixtures;
- carrier/adapter boards;
- lab/NPI engineering;
- inspection/test tooling.

**Commercial value remains a measurement hypothesis until external cases validate it.**

---

## Slide 14 — Research and product roadmap

### The next work is evidence, not generic features

1. Freeze one external model/provider/config.
2. Run the unchanged ten-case corpus through MCP.
3. Preserve every model/MCP trace and outer evaluation.
4. Physicalize the exact defensible candidate.
5. Capture revision-bound real physical evidence.
6. Run an independent human-operator protocol.
7. Compare models/derivatives using the same evidence shell.

**Architecture stays frozen unless these experiments expose a concrete defect.**

---

## Slide 15 — Closing

### Hardware-Splicer is not trying to make an AI sound like a hardware engineer.

It is trying to make AI-assisted hardware engineering auditable enough that:

- unknown remains unknown;
- evidence remains attributable;
- revisions remain meaningful;
- failures remain visible;
- physical authority remains bounded.

> **The AI does not need to be infallible. Uncertainty just needs to remain unable to silently become physical authority.**

**Final line:**

**Bring your own agent. Hardware-Splicer gives it an auditable engineering environment.**

---

## Rendering notes

- Use no more than 4–6 bullets on most slides; convert detail into diagrams/cards.
- Use one architecture graphic consistently rather than multiple competing diagrams.
- Use real product screenshots; do not use mockups for proof states.
- Put `PROVEN / PENDING / NOT CLAIMED` labels visibly on evidence slides.
- Avoid legacy branding (`Circuit-AI`, `mecha-splicer`) in the main deck.
- Do not show stacked PR history unless a judge explicitly asks about development lineage.
- Do not claim a live GPT/other model run until it exists.
