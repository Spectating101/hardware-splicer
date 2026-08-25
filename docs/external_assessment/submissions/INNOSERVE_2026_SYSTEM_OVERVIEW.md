# InnoServe 2026 — Hardware-Splicer System Overview

**Preferred route:** ADIAI — Industrial AI Innovation  
**Project:** Hardware-Splicer: Evidence-Constrained Agentic Engineering for Semiconductor Test and Validation Support Hardware

## 1. Project overview

Hardware-Splicer is a model-independent AI-assisted engineering environment for semiconductor test and validation support hardware. A general-purpose AI agent can reason, inspect evidence, propose changes, and operate engineering workflows through MCP/API, while deterministic constraints, provenance-bearing evidence, exact project/revision state, physical-proof records, and scoped human authorization remain independently authoritative.

The problem is not simply that generative AI can be wrong. In hardware, a fluent but unsupported answer can become a fabricated adapter, an unsafe power-on decision, damaged equipment, or wasted engineering time. Hardware-Splicer is therefore designed around a bounded-authority doctrine:

> **AI proposes → deterministic systems constrain → bench evidence decides → human authorizes.**

The AI is allowed to be useful without being treated as the source of physical truth.

## 2. Target application

The initial bounded application is semiconductor test and validation support hardware, including:

- adapter boards;
- carrier boards;
- validation fixtures;
- lab/NPI support hardware;
- related inspection/test tooling.

These workflows are attractive for AI assistance because they contain repeated preparation and evidence-integration work, but errors can also have direct physical cost.

Hardware-Splicer is not presented as chip design, wafer-process automation, autonomous production certification, or a universal EDA replacement.

## 3. Industry pain point

A generic AI assistant can answer “how should I connect this?” or generate an engineering proposal, but a real engineering workflow must also answer:

- Which exact component and package are present?
- Which source supports that identity?
- Is the source current for this project revision?
- Are voltage, interface, and dependency constraints satisfied?
- Did deterministic tools actually succeed?
- Is a measurement simulated or from real hardware?
- Which candidate revision did the evidence validate?
- Who has authority to authorize fabrication or power-on?

If those questions remain buried inside model prose, a plausible answer can acquire more authority than the evidence supports.

## 4. Solution architecture

```text
General-purpose AI / agent
          │
          ▼
       MCP / API
          │
          ▼
┌──────────────────────────────────────────┐
│             HARDWARE-SPLICER             │
│                                          │
│ exact project + revision state           │
│ source / evidence provenance             │
│ semantic engineering planning            │
│ deterministic interface constraints      │
│ engineering artifacts / package          │
│ revision-bound physical evidence         │
│ scoped authorization ledger              │
└──────────────────────────────────────────┘
          │
          ▼
      candidate / package
          │
      evidence gates
          │
          ▼
      human authority
          │
          ▼
       physical world
```

Hardware-Splicer separates four layers:

1. **AI reasoning** — semantic interpretation, planning, proposal, revision.
2. **Deterministic engineering state** — exact/unresolved identity, interface constraints, project/revision truth.
3. **Evidence** — provenance-bearing records tied to the revisions/artifacts they support.
4. **Authority** — explicit human-scoped permission after relevant evidence is valid.

## 5. System capabilities

The current repository includes:

- Web UI, HTTP API, CLI, and MCP surfaces;
- project and exact-revision persistence;
- source/evidence ingestion;
- semantic engineering planning;
- deterministic electrical/interface constraints;
- KiCad/DRC-related carrier and engineering flows;
- Engineering Package generation;
- physical-evidence records and envelopes;
- authorization ledger/state;
- adversarial cleanroom/evaluation infrastructure;
- model-independent external-agent trace/replay infrastructure.

The current MCP gateway is generated from the canonical product OpenAPI surface instead of duplicating engineering logic in a model-specific adapter.

## 6. AI Agent implementation

Hardware-Splicer treats the model as replaceable. A general-purpose agent can discover and operate the canonical backend through four generic MCP discovery/dispatch tools. At the current external-proof checkpoint, exact-head verification establishes:

- real MCP stdio client session — PASS;
- real MCP Streamable HTTP client session — PASS;
- canonical stateful project write → read → delete — PASS;
- canonical backend operation count — 193;
- frozen ten-case external-corpus inventory — PASS;
- external trace-audit infrastructure — PASS;
- MCP physical-authority grant — FALSE.

This proves the agent-facing engineering surface and audit harness exist. It does not imply that a live external model has already passed the engineering benchmark.

## 7. Adversarial evaluation

Rather than relying only on a curated happy-path demonstration, Hardware-Splicer uses a frozen ten-case SPI-flash adapter corpus:

1. baseline;
2. source reverse;
3. source rotate;
4. neutral labels;
5. mission paraphrase;
6. partial evidence;
7. component-identity conflict;
8. parser/tool failure;
9. plausible wrong analogy;
10. stale revision.

The cases deliberately test incomplete, conflicting, misleading, and stale evidence. Cases are frozen before the live model run and are not modified after observing the result.

The external trace audit can detect, among other issues:

- incomplete/failed MCP calls;
- foreign project-scope references;
- unsupported source identities;
- attempts to open physical authority;
- unsupported fabrication/power readiness;
- structural drift across equivalent variants.

## 8. Trustworthy physical-action boundary

Hardware-Splicer explicitly distinguishes software success from physical success.

Real physical evidence must:

- explicitly identify itself as real (`simulated: false`);
- remain bound to the exact project revision/artifact hashes it validates;
- survive the relevant deterministic checks;
- precede any scoped human authorization.

Missing simulation status is blocking rather than treated optimistically. Relevant revision or artifact changes can invalidate prior evidence/authority.

The goal is not “the AI will never hallucinate.” The narrower engineering guarantee is:

> **An unsupported or wrong AI answer should not automatically acquire physical authority.**

## 9. Innovation

Hardware-Splicer differs from generic AI engineering assistants in several ways:

- **model-independent:** engineering truth is not tied to one LLM;
- **evidence-constrained:** claims remain provenance-bearing and revision-aware;
- **fail-closed:** missing evidence remains unresolved rather than guessed into completion;
- **authority-separated:** the model/MCP layer cannot self-authorize physical action;
- **replayable:** agent trajectories can be persisted and compared across frozen cases;
- **physical-proof-aware:** software checks cannot be relabeled as real bench validation.

The technical contribution is therefore an auditable boundary around tool-using AI rather than merely another generative design interface.

## 10. Practical value

For semiconductor validation/support engineering, the intended value is to:

- reduce repeated clerical and evidence-integration work;
- accelerate preparation of structured engineering candidates;
- surface unresolved or unsafe states earlier;
- preserve revision/evidence lineage across handoffs;
- produce auditable Engineering Packages instead of chat-only answers;
- make AI-agent behavior reviewable after the fact;
- reduce the chance that model confidence becomes an expensive physical mistake.

Hardware-Splicer does not currently claim measured industrial savings or proven platform economics. Those remain external-validation targets.

## 11. Current maturity

### Proven

- frozen software architecture and exact-head verification;
- deterministic adversarial evaluation discipline;
- frozen ten-case SPI corpus/protocol;
- real MCP stdio and Streamable HTTP operation;
- 193 canonical backend operations exposed through MCP;
- stateful canonical project operations over MCP;
- external-agent trace/replay infrastructure;
- MCP cannot grant itself physical authority.

### Pending

- actual live external-model execution on the unchanged ten-case corpus;
- fresh revision-bound physical validation of the adversarial SPI candidate;
- independent human-operator completion;
- measured industrial/platform economics.

### Not claimed

- universal hardware correctness;
- zero hallucination;
- autonomous production certification;
- qualified-engineer replacement;
- production readiness.

## 12. Demonstration plan

The canonical three-minute video should show:

1. a plausible AI hardware answer and the missing-evidence questions;
2. the Hardware-Splicer reasoning/evidence/authority architecture;
3. a real project/revision with evidence and an engineering candidate;
4. a deterministic/unresolved blocking state;
5. one real MCP stateful interaction;
6. the ten-case adversarial corpus;
7. explicit PROVEN / PENDING / NOT CLAIMED evidence state;
8. closing statement that physical authority remains human-scoped.

A correctly blocked unsafe progression is a successful demonstration, not a failure to hide.

## 13. Development roadmap

The next work is evidence-producing rather than generic feature development:

1. freeze one external model/provider/config;
2. run the unchanged ten-case corpus through MCP;
3. preserve actual model/MCP traces and outer adjudication;
4. physicalize the exact defensible candidate;
5. capture revision-bound real measurements;
6. run the independent operator protocol;
7. measure reuse/intervention/economics only after real external cases exist.

## 14. Submission claim statement

All readiness and performance statements in this entry follow the canonical Hardware-Splicer evidence ledger. Software and MCP verification are not presented as physical proof. Live-model, fresh physical, independent-operator, and production-readiness claims remain pending until artifact-backed evidence exists.
