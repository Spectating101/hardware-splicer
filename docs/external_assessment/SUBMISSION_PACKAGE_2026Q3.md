# Hardware-Splicer — 2026 Q3 Submission Package

This is the clean external boundary for competitions, papers, grants, mentors, judges and prospective design partners.

**Do not ask an evaluator to reconstruct Hardware-Splicer from historical PRs, old release notes or internal engineering diaries.** This page is the front door.

## 1. Project in one line

**Hardware-Splicer lets a general-purpose AI agent do bounded hardware-engineering work while deterministic evidence and authority controls prevent the agent from silently turning guesses into physical truth.**

## 2. The problem

General-purpose AI can produce plausible hardware advice before component identity, voltage compatibility, source provenance, revision state or physical behavior is actually established.

That is materially different from an ordinary software hallucination. In hardware, a fluent mistake can become:

- a fabricated mistake;
- a powered mistake;
- damaged equipment;
- an unsafe bench action;
- a false engineering sign-off.

Most AI-engineering demos optimize for producing an answer. Hardware-Splicer asks a different question:

> **What evidence and authority should be required before an AI-generated answer is allowed to become a physical action?**

## 3. The solution

Hardware-Splicer separates four things that are often collapsed together:

1. **Model reasoning** — semantic interpretation, planning, proposing and revising.
2. **Deterministic engineering constraints** — identity, electrical/interface rules, exact revision state and invariant checks.
3. **Evidence** — provenance-bearing software, source and physical records tied to exact artifacts/revisions.
4. **Authority** — explicit scoped human permission after the relevant evidence is valid.

Core doctrine:

> **AI proposes → deterministic systems constrain → bench evidence decides → human authorizes.**

## 4. What exists today

Hardware-Splicer is not a concept deck. The repository contains a working engineering platform with:

- canonical FastAPI backend;
- Web/API/CLI/MCP surfaces;
- project/revision persistence;
- source and evidence ingestion;
- semantic circuit planning;
- electrical/interface constraint handling;
- KiCad carrier and DRC-related flows;
- engineering-package generation;
- revision-bound physical-evidence records;
- authorization ledger/state;
- adversarial cleanroom/evaluation corpus;
- model-independent MCP gateway generated from canonical product OpenAPI;
- external-agent trace/replay infrastructure.

The current MCP surface exposes **193 canonical backend operations** through a four-tool discovery/dispatch contract. Real stdio and Streamable HTTP MCP clients have completed canonical stateful write/read/delete flows while the MCP layer itself remained unable to grant physical authority.

## 5. What has been proven

### Software / transport

- frozen software checkpoint with exact-head CI evidence;
- deterministic adversarial truth/evaluation behavior;
- ten-case frozen unseen SPI corpus and corpus validation;
- canonical OpenAPI-to-MCP coverage;
- real MCP stdio client session;
- real MCP Streamable HTTP client session;
- stateful canonical project write → read → delete through MCP;
- external-agent proof runner and trace audit execute in CI;
- MCP physical-authority grant remains false.

### Evidence discipline

- ambiguous real-vs-simulated evidence fails closed;
- revision/artifact boundaries constrain evidence reuse;
- authorization is separate from model proposal;
- failures and unresolved states are representable rather than forced into fabricated certainty.

## 6. What is deliberately still pending

The package does **not** hide unfinished external proof.

- A live external model has not yet run the unchanged full ten-case SPI corpus through MCP.
- The fresh adversarial SPI candidate has not yet completed its revision-bound real physical bench proof.
- A technically competent independent human operator has not yet completed the outsider protocol.
- Industrial/platform economics remain hypotheses until external use establishes them.

These are the next evidence tranches, not missing generic software features.

## 7. Why the MCP layer matters

The original engineering insight becomes stronger when the model is replaceable.

Instead of:

`one embedded AI model → hardware output`

Hardware-Splicer now supports the architecture:

`general-purpose agent → MCP → Hardware-Splicer → deterministic engineering/evidence gates → candidate/evidence → human authority → physical world`

That makes Hardware-Splicer useful as both:

### Product infrastructure

> **Bring your own agent. Hardware-Splicer gives it an auditable engineering environment.**

### Research infrastructure

> **Can different general-purpose agents work through hardware-engineering problems without being able to silently manufacture physical truth or self-authorize physical action?**

## 8. Primary bounded application

The clean primary story is **semiconductor test and validation support hardware**, including:

- adapter boards;
- validation fixtures;
- lab/NPI support hardware;
- carrier boards;
- related electromechanical preparation.

The project should not be presented as chip design, wafer-process automation or autonomous production certification.

## 9. Demonstration story

The preferred demonstration is intentionally not “watch the AI instantly succeed.”

1. Give the agent an engineering task and imperfect evidence.
2. The agent operates the canonical Hardware-Splicer surface through MCP/API.
3. Hardware-Splicer preserves exact identity/source/revision constraints.
4. Unsupported assumptions remain unresolved or are blocked.
5. The agent can inspect, revise and retry.
6. The system emits an auditable candidate/evidence trail.
7. Physical authority remains closed without the required real evidence and human authorization.

A correctly blocked failure is a successful demonstration of the safety architecture.

## 10. Competitive differentiation

Hardware-Splicer is not primarily differentiated by having an LLM in an EDA workflow. General-purpose copilots can already generate suggestions.

Its differentiators are the engineering boundaries around the model:

- model-independent agent interface;
- provenance-bearing evidence;
- exact revision/artifact binding;
- unresolved-state propagation;
- deterministic constraint re-entry after model reasoning;
- explicit physical-evidence requirements;
- scoped human authority;
- replayable adversarial agent traces;
- a claim ceiling that prevents CI/model confidence from being presented as physical correctness.

## 11. External claim boundary

A judge should be able to distinguish three states immediately:

### Proven

Software architecture, deterministic checks, adversarial corpus/protocol, canonical MCP transport, remote stateful operation, evidence/authority boundaries and external-agent proof infrastructure.

### Pending

Live external-model unseen result, fresh SPI physical result, independent human-operator result, industrial economics.

### Not claimed

Universal correctness, autonomous certification, zero hallucination, qualified-engineer replacement or production readiness.

## 12. Submission assets

Use these sources rather than rebuilding material per opportunity:

- [`MASTER_DECK_12_SLIDES.md`](MASTER_DECK_12_SLIDES.md) — canonical 12-slide narrative;
- [`SUBMISSION_COPY_BANK.md`](SUBMISSION_COPY_BANK.md) — short/medium/long descriptions and abstracts;
- [`MEDIA_CAPTURE_CHECKLIST.md`](MEDIA_CAPTURE_CHECKLIST.md) — screenshots/video shots to capture once;
- [`CLAIMS_AND_NONCLAIMS.md`](CLAIMS_AND_NONCLAIMS.md) — current truth boundary;
- [`EVIDENCE_LEDGER.md`](EVIDENCE_LEDGER.md) — evidence mapping;
- [`demos/`](demos/) — timed demo scripts;
- [`overlays/`](overlays/) — venue-specific emphasis;
- [`SOLO_ROUTING_2026.md`](SOLO_ROUTING_2026.md) — where this package should be sent and what eligibility dependency remains.

## 13. Submission rule

> **Do not build a different Hardware-Splicer for every competition.**

Change only:

- title/subtitle;
- problem emphasis;
- judging-criteria mapping;
- word/page limits;
- use-case framing;
- requested next step.

Do not change:

- evidence state;
- proof status;
- authority boundaries;
- nonclaims;
- underlying technical truth.
