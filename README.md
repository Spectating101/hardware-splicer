# Hardware-Splicer

[![Splice Agent v1](https://github.com/Spectating101/hardware-splicer/actions/workflows/hardware-splicer.yml/badge.svg)](https://github.com/Spectating101/hardware-splicer/actions/workflows/hardware-splicer.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Auditable agentic hardware engineering under bounded physical authority.**

> **AI proposes → deterministic systems constrain → bench evidence decides → human authorizes.**

Hardware-Splicer lets a general-purpose AI agent perform bounded hardware-engineering work while deterministic constraints, provenance-bearing evidence, exact revision state and scoped human authority remain independently authoritative.

It is **not** a claim that an LLM can safely replace a hardware engineer. The design goal is narrower and more defensible:

> **When the AI is uncertain or wrong, that uncertainty should not silently acquire physical authority.**

## Evaluators / competitions / research reviewers

**Start here:** [`docs/external_assessment/SUBMISSION_PACKAGE_2026Q3.md`](docs/external_assessment/SUBMISSION_PACKAGE_2026Q3.md)

Then use:

- [`PROJECT_IDENTITY.md`](docs/external_assessment/PROJECT_IDENTITY.md) — bounded project identity;
- [`CLAIMS_AND_NONCLAIMS.md`](docs/external_assessment/CLAIMS_AND_NONCLAIMS.md) — exact claim boundary;
- [`EVIDENCE_LEDGER.md`](docs/external_assessment/EVIDENCE_LEDGER.md) — what evidence supports each claim;
- [`MASTER_DECK_12_SLIDES.md`](docs/external_assessment/MASTER_DECK_12_SLIDES.md) — canonical external narrative;
- [`SOLO_ROUTING_2026.md`](docs/external_assessment/SOLO_ROUTING_2026.md) — current solo-first submission routing;
- [`demos/DEMO_3_MINUTES.md`](docs/external_assessment/demos/DEMO_3_MINUTES.md) — canonical short demonstration.

## Current state

**SOFTWARE ARCHITECTURE FROZEN / EXTERNAL PROOF + SUBMISSION PACKAGING ACTIVE**

| Evidence layer | State |
|---|---|
| frozen software architecture | **PROVEN** |
| deterministic adversarial cleanroom | **PROVEN** |
| frozen ten-case unseen SPI corpus | **PROVEN AS CORPUS/PROTOCOL** |
| canonical MCP gateway | **PROVEN** |
| external-agent runner / trace audit | **PROVEN AS INFRASTRUCTURE** |
| live external-model run on unchanged corpus | **PENDING** |
| fresh revision-bound SPI physical correctness | **PENDING** |
| independent human operator | **PENDING** |
| production / industrial deployment readiness | **NOT CLAIMED** |

The project is therefore **evidence-blocked, not feature-blocked**. Generic feature development should remain frozen unless a live, unseen, physical or independent-operator experiment exposes a concrete defect.

## Architecture

```text
General-purpose AI / agent
          │
          ▼
       MCP / API
          │
          ▼
┌─────────────────────────────────────────┐
│            HARDWARE-SPLICER             │
│                                         │
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

### Model independence

The current external-agent path exposes the canonical product backend through a four-tool MCP discovery/dispatch gateway rather than duplicating engineering logic in the adapter.

At the current external-proof checkpoint, exact-head CI has exercised:

- a real MCP stdio client;
- a real MCP Streamable HTTP client;
- canonical stateful project write → read → delete through MCP;
- the installed canonical MCP entry point;
- frozen ten-case external corpus inventory;
- the non-golden external trace audit;
- **193 canonical backend operations**;
- `physical_authority_granted = false` at the MCP boundary.

This proves the engineering surface and proof harness exist. It does **not** prove a live external model has passed the corpus.

## Primary bounded application

The clean external application is **semiconductor test and validation support hardware**, including:

- adapter boards;
- carrier boards;
- validation fixtures;
- lab/NPI support hardware;
- related electromechanical preparation.

Hardware-Splicer is not presented as:

- chip design;
- wafer-process automation;
- autonomous production certification;
- universal EDA replacement;
- a system that treats model confidence as verification.

## What makes the system different

A generic AI assistant can propose an answer. Hardware-Splicer additionally preserves independent structures for:

- exact or unresolved component identity;
- evidence provenance;
- deterministic electrical/interface constraints;
- exact project/revision/artifact state;
- stale-evidence invalidation;
- explicit real-vs-simulated physical evidence;
- scoped human authorization;
- replayable adversarial agent traces.

The system therefore evaluates not only **whether the AI is right**, but also **what happens when it is wrong**.

## Adversarial external proof

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

The external-agent runner can preserve model requests/responses, MCP calls, case-scoped state and replay material while the trace audit checks for incomplete calls, foreign project scope, unsupported evidence identity and attempts to open physical authority.

**The actual live provider run remains pending.** Frozen cases must not be rewritten after results are visible.

## Physical evidence and authority

Software success is not physical success.

Real physical evidence must explicitly identify itself as real (`simulated: false`) and remain tied to the relevant project revision/artifact boundary. Missing or ambiguous simulation state is blocking. Authorization is an explicit human-scoped decision and does not automatically survive relevant revision or artifact changes.

A prior golden-real bench path demonstrates that the evidence/authority machinery can consume explicitly real evidence. It does not close the fresh adversarial SPI physical proof chain.

## Product surfaces

Hardware-Splicer contains Web UI, HTTP API, MCP and CLI surfaces around the same engineering truth core.

The repository also retains earlier Splice/Circuit/mechanical lineage and internal engineering documentation. Those materials are useful for development history but are **not the recommended evaluator entry point**.

## Developer quick start

```bash
git clone https://github.com/Spectating101/hardware-splicer.git
cd hardware-splicer
bash scripts/install_splice_v1.sh
source .venv/bin/activate
hs-doctor
make splice-ui-serve
```

For internal/developer navigation, see [`docs/GITHUB_START_HERE.md`](docs/GITHUB_START_HERE.md) and the broader [`docs/`](docs/) tree.

## Canonical generated artifacts

Representative durable outputs include:

- `PROJECT_PACKAGE.json`;
- KiCad carrier / DRC evidence;
- `SPLICE_PLAN.json`;
- `SPLICE_BENCH_SESSION.json`;
- `COMPILE_CASEFILE.json` on failure;
- revision-bound evidence and authorization records;
- external-agent trace/replay artifacts when a live run is executed.

## Submission doctrine

> **One evidence core → multiple external verdicts.**

Competitions, papers, grants and partner reviews may receive different emphasis and formatting. They may not receive different truth states.

See [`docs/external_assessment/`](docs/external_assessment/) for the controlled external package.

## License

Software license: **MIT** — see [`LICENSE`](LICENSE).

The system assists engineering and evidence workflows; **physical authorization remains explicitly bounded and human-scoped.**
