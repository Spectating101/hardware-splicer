# Hardware-Splicer — Canonical 12-Slide Deck Source

This is the single master deck narrative. Competition-specific decks should shorten/reorder this source rather than invent new claims.

## Slide 1 — Hardware-Splicer

**Subtitle:** Auditable agentic hardware engineering under bounded physical authority

**One-line value:**

General-purpose AI can reason about hardware. Hardware-Splicer determines what that reasoning is allowed to become.

**Footer claim:**

`AI proposes → deterministic systems constrain → bench evidence decides → human authorizes`

---

## Slide 2 — The failure mode we care about

### Fluent engineering output can outrun engineering truth

A model can produce a convincing adapter-board answer while one or more of these remain unknown:

- exact component identity;
- voltage/domain compatibility;
- source provenance;
- revision freshness;
- tool/check success;
- physical behavior.

**Hardware consequence:** a plausible mistake can become a fabricated or powered mistake.

**Visual:** model answer flowing toward a PCB/power icon, interrupted by evidence/authority gates.

---

## Slide 3 — The design principle

### Separate reasoning from authority

Hardware-Splicer treats four layers independently:

1. **Reasoning** — model proposes and revises.
2. **Constraints** — deterministic engineering rules and exact state.
3. **Evidence** — provenance/revision-bound records.
4. **Authority** — explicit scoped human permission.

**Key sentence:** Model confidence never substitutes for missing evidence.

---

## Slide 4 — System architecture

```text
General-purpose AI / agent
          │
          ▼
      MCP / API
          │
          ▼
┌───────────────────────────────────────┐
│          HARDWARE-SPLICER             │
│                                       │
│ project + revision state              │
│ source/evidence provenance            │
│ semantic engineering planning         │
│ deterministic interface constraints   │
│ KiCad / DRC / engineering artifacts   │
│ physical-evidence records             │
│ authorization ledger                  │
└───────────────────────────────────────┘
          │
          ▼
 candidate / engineering package
          │
     evidence gates
          │
          ▼
    human authorization
          │
          ▼
      physical world
```

**Current MCP fact:** 193 canonical backend operations are reachable through the canonical discovery/dispatch gateway.

---

## Slide 5 — A concrete bounded use case

### Semiconductor test / validation support hardware

Example mission: prepare an adapter/carrier path around an SPI-flash device with incomplete or conflicting evidence.

The agent must distinguish:

- what component is actually present;
- what voltage/interface assumptions are supported;
- what source/revision the facts came from;
- what checks passed or failed;
- what is still unresolved;
- whether fabrication/power-on authority is justified.

**Do not frame HS as chip design or wafer-process automation.**

---

## Slide 6 — Adversarial evaluation instead of a happy-path demo

The frozen unseen SPI corpus contains ten cases:

- baseline;
- source reverse;
- source rotate;
- neutral labels;
- mission paraphrase;
- partial evidence;
- identity conflict;
- parser failure;
- analogy trap;
- stale revision.

**Why:** we want to know whether the engineering process remains auditable when the evidence gets awkward, not merely whether one curated prompt looks good.

**Current state:** corpus/protocol validated; live external-model execution remains pending.

---

## Slide 7 — MCP makes the model replaceable

### Hardware-Splicer is the engineering shell, not the model

Instead of hard-wiring engineering truth to one model:

`general-purpose model → MCP → HS → deterministic/evidence/authority controls`

The current MCP proof establishes:

- real stdio client session;
- real Streamable HTTP client session;
- canonical stateful write/read/delete;
- 193 canonical operations;
- no MCP physical-authority grant;
- external trace/replay harness.

**Product framing:** Bring your own agent. HS gives it an auditable engineering environment.

---

## Slide 8 — What happens when the AI is wrong?

### Wrong does not automatically become authorized

Hardware-Splicer can preserve:

- unresolved identity;
- unsupported source claims;
- failed deterministic checks;
- stale evidence;
- blocked fabrication/power readiness;
- revision invalidation;
- failure → repair → revalidation history.

**Headline answer:**

> Being wrong does not automatically grant physical authority.

This is a more defensible engineering objective than claiming zero hallucination.

---

## Slide 9 — Evidence state today

| Layer | State |
|---|---|
| frozen software architecture | **PROVEN** |
| deterministic adversarial cleanroom | **PROVEN** |
| frozen ten-case unseen corpus | **PROVEN AS CORPUS** |
| canonical remote-capable MCP surface | **PROVEN** |
| external-agent runner / trace audit | **PROVEN AS INFRASTRUCTURE** |
| live model on unchanged corpus | **PENDING** |
| fresh SPI physical correctness | **PENDING** |
| independent human operator | **PENDING** |
| production readiness | **NOT CLAIMED** |

**Design choice:** pending proof is shown, not hidden.

---

## Slide 10 — Why this is useful beyond one adapter

The platform can support a family of bounded hardware-engineering workflows where the expensive asset is not merely generated geometry but **reusable engineering evidence and authority discipline**.

Potential extension surfaces include:

- validation fixtures;
- carrier boards;
- lab/NPI support hardware;
- inspection/test tooling;
- embedded-vision support hardware;
- derivative product families where evidence reuse can be measured.

**Do not claim platform economics until measured.**

---

## Slide 11 — What is technically different

Generic AI hardware assistants primarily optimize the proposal.

Hardware-Splicer also maintains independent structures for:

- exact/unresolved physical identity;
- provenance-bearing evidence;
- deterministic engineering constraints;
- exact revision/artifact binding;
- selective evidence invalidation;
- explicit real-vs-simulated status;
- scoped human authorization;
- replayable agent traces.

**Research contribution:** a testable separation between model reasoning and physical authority.

---

## Slide 12 — The next proof, not the next feature

The software architecture is frozen unless external evidence exposes a defect.

### Next evidence sequence

1. run one frozen external model/config on the unchanged ten-case corpus;
2. preserve exact MCP/model traces and outer adjudication;
3. physicalize the exact defensible candidate;
4. capture revision-bound real measurements;
5. run the independent human-operator protocol;
6. update claims only from the canonical evidence record.

**Closing:**

> Hardware-Splicer is not trying to make an AI sound like a hardware engineer. It is trying to make AI-assisted hardware engineering auditable enough that uncertainty cannot silently become physical authority.
