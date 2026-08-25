# Hardware-Splicer — External Assessment Package

**Package status:** submission-preparation layer on top of a frozen software architecture and active external-proof tranche  
**Submission-package branch:** `agent/submission-package-2026q3`  
**Current package base:** `bb313f283fc25ad75ea1ce0dd384ebb36d0d6911` (PR #70 head when this package was opened)  
**Frozen software proof checkpoint:** PR #59 source head `0164d47e25bfea8179073e46e869a8725ca03b83`

## One-sentence identity

**Hardware-Splicer is model-independent infrastructure that lets a general-purpose AI agent perform bounded hardware-engineering work while deterministic evidence and authority controls prevent the agent from silently manufacturing physical truth.**

A product-facing equivalent is:

> **Bring your own agent. Hardware-Splicer gives it an auditable engineering environment.**

## The evaluator story

Do not evaluate Hardware-Splicer as “an AI that generates hardware.” Its differentiator is the separation between reasoning, verification, evidence and authority:

> **AI proposes → deterministic systems constrain → bench evidence decides → human authorizes.**

The model may reason, propose, ask, revise, block and remain unresolved. It may not silently promote confidence into component identity, verified electrical truth, physical evidence, fabrication readiness, power-on permission or release authority.

## Start here

For an evaluator, judge, reviewer, mentor or potential design partner, read in this order:

1. [`SUBMISSION_PACKAGE_2026Q3.md`](SUBMISSION_PACKAGE_2026Q3.md) — the clean external entry point.
2. [`PROJECT_IDENTITY.md`](PROJECT_IDENTITY.md) — what Hardware-Splicer is and is not.
3. [`CLAIMS_AND_NONCLAIMS.md`](CLAIMS_AND_NONCLAIMS.md) — exact current claim boundary.
4. [`ARCHITECTURE_FOR_EVALUATORS.md`](ARCHITECTURE_FOR_EVALUATORS.md) — system boundary and authority model.
5. [`EVIDENCE_LEDGER.md`](EVIDENCE_LEDGER.md) — evidence supporting each claim.
6. [`MASTER_DECK_12_SLIDES.md`](MASTER_DECK_12_SLIDES.md) — reusable competition/pitch deck source.
7. [`SUBMISSION_COPY_BANK.md`](SUBMISSION_COPY_BANK.md) — reusable abstracts, descriptions and form copy.
8. [`SOLO_ROUTING_2026.md`](SOLO_ROUTING_2026.md) — opportunity routing with solo/faculty-signoff constraints.
9. [`demos/`](demos/) — 30-second, 3-minute and 10-minute narratives plus hostile Q&A.
10. [`proof/`](proof/) — artifact slots for software, live-model, physical and independent-operator proof.
11. [`overlays/`](overlays/) — venue-specific emphasis without changing underlying truth.

## Current phase

> **SOFTWARE ARCHITECTURE FROZEN / SUBMISSION PACKAGE ACTIVE / EXTERNAL PROOF PENDING**

Do not reopen generic feature development unless a live, unseen, physical or independent-operator experiment exposes a concrete defect.

## Current evidence state

| Evidence layer | State | What may be said externally |
|---|---|---|
| Frozen software architecture | **PROVEN** | Reproducible software baseline and fail-closed authority architecture exist. |
| Deterministic adversarial cleanroom | **PROVEN** | The deterministic truth/evaluation layer has persisted adversarial coverage. |
| Frozen unseen SPI corpus | **PROVEN AS CORPUS/PROTOCOL** | Ten-case adversarial corpus exists and validates; this is not live-model competence. |
| Canonical MCP gateway | **PROVEN** | Stdio and Streamable HTTP clients reach the canonical backend; 193 operations are exposed from canonical OpenAPI; stateful write/read/delete succeeds; MCP itself grants no physical authority. |
| External-agent proof harness | **PROVEN AS INFRASTRUCTURE** | The runner, trace persistence, frozen-case inventory and non-golden trace audit validate on exact-head CI. |
| Live external-model unseen competence | **PENDING** | Do not claim until a real model call runs on the unchanged corpus and artifacts are preserved. |
| Fresh SPI physical correctness | **PENDING** | A prior golden-real bench consumer path is not closure of this fresh SPI proof chain. |
| Independent human operator | **PENDING** | Do not claim independent usability until the outsider protocol is completed. |
| Production / industrial deployment | **NOT CLAIMED** | Partner or industrial-value hypotheses remain hypotheses. |

## What the MCP changes

Hardware-Splicer no longer depends conceptually on one embedded model. The current external proof path is:

`general-purpose model → MCP → canonical Hardware-Splicer backend → deterministic engineering/evidence gates → revision-bound candidate/evidence → scoped human authority`

This supports a stronger research and product question:

> **Can a general-purpose agent work through hardware-engineering problems inside Hardware-Splicer without being able to silently manufacture physical truth or grant itself physical authority?**

The live answer to that question is still pending; the infrastructure required to test it is present.

## Canonical rule

This directory is a presentation and evidence-routing layer. It is not a second source of engineering truth.

- Software facts come from repository code, exact revisions and exact-head test/workflow evidence.
- Physical facts come only from revision-bound physical evidence.
- Authorization remains explicit, human-scoped and invalidated by relevant revision/artifact changes.
- Unknown remains unknown.
- Failures remain in the record.
- Venue-specific language may change emphasis but may not change truth state.

## Packaging doctrine

> **One evidence core → multiple external verdicts.**

The goal is to make each additional competition, paper, grant, pilot or partner review cheap. We should adapt framing, word count, deck length and demonstration emphasis—not create a different project for each venue.
