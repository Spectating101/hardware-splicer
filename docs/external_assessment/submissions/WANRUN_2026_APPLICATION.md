# WanRun 2026 — Hardware-Splicer Application Packet

**Primary category:** AI Smart Systems  
**Fallback category:** Engineering Applications  
**Project title:** Hardware-Splicer: Auditable AI Agent for Semiconductor Validation Hardware

This file is intended as copy-ready source for the registration form and any proposal/deck fields. Do not change evidence state to make the entry sound more complete.

## Project summary — short

Hardware-Splicer is an auditable AI-agent environment for semiconductor test and validation support hardware. General-purpose AI can accelerate engineering reasoning, but model confidence alone cannot establish component identity, electrical compatibility, evidence provenance, revision freshness, or physical correctness. Hardware-Splicer separates AI proposals from deterministic constraints, provenance-bearing evidence, exact project/revision state, and scoped human physical authority. The current platform exposes 193 canonical backend operations through MCP and includes a frozen ten-case adversarial SPI-flash evaluation corpus. The goal is not an infallible autonomous engineer; it is a practical engineering workflow in which uncertainty cannot silently become fabrication or power-on authority.

## Project summary — medium

AI-generated engineering output can look complete before its underlying physical assumptions are actually established. In semiconductor validation and lab-support workflows, a plausible mistake can become an incorrectly fabricated adapter, an unsafe power-on decision, damaged equipment, or wasted engineering time.

Hardware-Splicer addresses this by separating four layers that ordinary AI assistants often collapse together: model reasoning, deterministic engineering constraints, provenance-bearing evidence, and human physical authority. A general-purpose agent can inspect evidence, propose engineering changes, and operate the canonical Hardware-Splicer backend through MCP/API. However, exact component identity, project/revision state, deterministic constraints, physical-evidence status, and authorization remain independently enforced outside the model.

The current external-proof checkpoint validates a frozen ten-case adversarial SPI-flash corpus, a real MCP stdio client, a real Streamable HTTP MCP client, stateful canonical project write/read/delete, 193 canonical backend operations, and an external-agent trace/replay harness that cannot independently grant physical authority. Live external-model execution on the unchanged corpus, fresh revision-bound SPI physical correctness, and independent human-operator completion remain pending and are not overstated.

## Problem / motivation

Generative AI is increasingly capable of writing code, controlling tools, and producing engineering artifacts. Hardware creates a stronger consequence boundary than ordinary text generation because a convincing but unsupported answer can trigger fabrication, power-on, or release decisions.

A typical hardware copilot may answer questions such as “Which component is this?” or “Can these interfaces be connected?” in fluent prose. But an engineering workflow also needs to know:

- which exact component/package is present;
- which source supports that identity;
- whether the source is authoritative and current;
- whether electrical/interface constraints pass;
- which project revision the evidence belongs to;
- whether a claimed measurement came from real hardware or simulation;
- who is permitted to authorize the next physical action.

Hardware-Splicer treats these as explicit system states instead of leaving them implicit inside model text.

## Innovation

The innovation is not simply “LLM + PCB design.” Hardware-Splicer makes the AI model replaceable and keeps engineering truth and physical authority outside the model.

Key mechanisms include:

1. **Model-independent MCP/API access.** A general-purpose agent can operate the same canonical engineering backend rather than a model-specific script.
2. **Exact or unresolved identity.** Similar components are not silently promoted to identical components when evidence is incomplete.
3. **Provenance-bearing evidence.** Engineering claims remain linked to their source and project revision.
4. **Deterministic constraint re-entry.** Model reasoning returns to explicit engineering checks rather than becoming authoritative merely because it is plausible.
5. **Revision/artifact-bound physical evidence.** Real measurements are tied to the candidate they actually validate.
6. **Fail-closed real-vs-simulated evidence.** Missing simulation status cannot be interpreted optimistically; real evidence must explicitly declare `simulated: false`.
7. **Scoped human authority.** The model and MCP layer cannot grant themselves fabrication/power-on authority.
8. **Adversarial trace/replay evaluation.** Agent behavior can be preserved and compared across frozen cases.

## Technical implementation

Hardware-Splicer contains a canonical FastAPI engineering backend with Web UI, HTTP API, CLI, and MCP surfaces. Representative capabilities include:

- project and exact-revision persistence;
- source and evidence ingestion;
- semantic circuit/engineering planning;
- deterministic electrical/interface constraints;
- KiCad/DRC-related carrier and engineering flows;
- engineering-package generation;
- physical-evidence records and envelopes;
- authorization state and ledger;
- adversarial cleanroom/evaluation infrastructure.

The current MCP gateway is generated from the canonical product OpenAPI surface instead of duplicating engineering logic in a separate AI adapter. At the current proof checkpoint, the gateway exposes 193 canonical operations through four discovery/dispatch tools and has been exercised by real stdio and Streamable HTTP MCP clients.

## Adversarial evaluation

The frozen unseen SPI-flash corpus contains ten cases:

1. baseline;
2. source reverse;
3. source rotate;
4. neutral labels;
5. mission paraphrase;
6. partial evidence;
7. identity conflict;
8. parser failure;
9. analogy trap;
10. stale revision.

These cases test whether the engineering process remains auditable when evidence is incomplete, conflicting, stale, misleading, or affected by a tool failure. The cases are frozen before the live external-model run and must not be rewritten after results are visible.

## Application value

The initial bounded application is semiconductor test and validation support hardware:

- adapter boards;
- carrier boards;
- validation fixtures;
- lab/NPI support hardware;
- related inspection/test tooling.

These are practical workflows where repeated engineering preparation can benefit from AI acceleration but where a false assumption also has real physical cost. Hardware-Splicer is intended to make that acceleration auditable rather than replacing qualified engineers.

## Differentiation

Generic AI hardware assistants primarily optimize the quality and speed of the proposed answer. Hardware-Splicer additionally preserves independent structures for evidence provenance, exact revision state, deterministic checks, physical-proof status, and human authority.

Its central question is therefore not only:

> Can an AI agent produce a useful design proposal?

but also:

> If the agent is wrong or uncertain, can the system prevent that uncertainty from silently becoming a physical action?

## Current evidence

### Proven

- frozen software architecture and exact-head software verification;
- deterministic adversarial cleanroom/evaluation discipline;
- validated frozen ten-case SPI corpus;
- real MCP stdio client session;
- real MCP Streamable HTTP client session;
- stateful canonical project write → read → delete through MCP;
- 193-operation canonical backend surface;
- executable external-agent trace/replay infrastructure;
- MCP itself does not grant physical authority.

### Pending

- actual live external-model run on the unchanged ten-case corpus;
- fresh revision-bound physical validation of the adversarial SPI candidate;
- independent human-operator protocol;
- measured platform/industrial economics.

### Not claimed

- universal hardware correctness;
- zero hallucination;
- autonomous production certification;
- replacement of a qualified hardware engineer;
- production readiness.

## Creativity / future potential

The architecture can support a broader family of bounded agentic engineering workflows because the reusable asset is not just generated geometry: it is structured engineering state, evidence, revision lineage, and authority discipline.

Future experiments can measure whether the same evidence shell reduces marginal engineering effort across derivative validation fixtures, inspection/test tooling, or embedded-vision support hardware. These reuse and commercial-economics claims remain hypotheses until measured.

## Demonstration sentence

> Hardware-Splicer does not need the AI to be infallible. It needs uncertainty and error to remain unable to silently become physical authority.

## Intellectual-property wording

If the form asks about IP or patent potential, use:

> Hardware-Splicer contains potentially protectable system and workflow mechanisms around model-independent agent operation, evidence/revision binding, and constrained physical-authority transitions. Patentability has not been asserted and would require dedicated prior-art and legal review.

Do not claim an issued/pending patent unless one actually exists.

## Solo-registration rule

Public material reviewed during packaging states a maximum team size but did not expose a minimum. At the live registration portal:

- if a single-student entry is accepted, proceed;
- if more than one student is mandatory, mark this route KILL;
- do not recruit peers solely to satisfy a roster requirement.
