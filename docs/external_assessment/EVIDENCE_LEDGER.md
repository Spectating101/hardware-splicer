# Evidence Ledger

This ledger records what evidence exists, what it supports, and what it explicitly does **not** support.

## Evidence hierarchy

Hardware-Splicer separates four evidence classes:

1. **software evidence** — code, tests, deterministic validators, exact-head workflows;
2. **agent evidence** — actual model inputs/outputs/tool traces on frozen cases;
3. **physical evidence** — real measurements tied to exact revision/artifact/component identity;
4. **authority evidence** — explicit scoped human decisions after relevant evidence is valid.

Evidence does not automatically move upward between classes. In particular, green CI is not physical proof and MCP transport success is not live-model competence.

## A. Frozen software baseline

### Architecture baseline

- PR #56: `Build dual-agent cleanroom and remove semantic script brain`
- frozen architecture head: `0a55515cc683abccce6308c918f679199d5ebf87`

### Software-freeze checkpoint

- PR #59: `Freeze software baseline and open external-proof tranche`
- frozen proof checkpoint: `0164d47e25bfea8179073e46e869a8725ca03b83`

Successful exact-head aggregate evidence included:

| Workflow | Run | Supports |
|---|---:|---|
| Hardware-Splicer | #1902 | aggregate repository software verification |
| Core Diagnostics | #699 | changed-test bar, persistence regressions, complete Python suite and diagnostics |
| Model-First Truth Bar | #211 | model-first semantic/truth boundary regression |

**Claim ceiling:** software architecture and regression behavior only.

## B. Deterministic cleanroom and adversarial corpus

The cleanroom/evaluator lineage includes persisted challenge coverage for conflicting/partial evidence, deterministic tool failure, plausible wrong analogy, stale revision, invented evidence, forced guessing and label-sensitive script-brain behavior.

The current external-agent proof consumes a frozen ten-case SPI-flash adversarial corpus:

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

On PR #70 exact-head CI, the harness validates that all ten case IDs are present and the corpus validator passes.

**Claim ceiling:** the corpus, deterministic validation discipline and replay infrastructure exist. This does not prove any live model passed the corpus.

## C. Canonical MCP gateway

### Current proof-harness checkpoint

- PR #70: `Add guarded remote MCP and external-agent proof harness`
- exact source head: `bb313f283fc25ad75ea1ce0dd384ebb36d0d6911`
- Canonical MCP Backend Contract run #15: **SUCCESS**

The successful run establishes:

| Evidence | Result |
|---|---|
| OpenAPI-to-MCP coverage / external truth-audit tests | PASS |
| real MCP stdio client | PASS |
| real MCP Streamable HTTP client | PASS |
| canonical project write/read/delete through MCP | PASS |
| installed canonical MCP entry point | PASS |
| frozen external ten-case inventory validation | PASS |
| canonical operation count | 193 |
| MCP physical-authority grant | `false` |

The gateway exposes four generic MCP operations that discover, describe and call the canonical product API instead of re-implementing engineering logic in the adapter.

**Claim ceiling:** a real remote-capable MCP transport reaches the canonical Hardware-Splicer engineering surface while preserving existing backend authority rules.

It does **not** prove engineering correctness, live-model competence or physical correctness.

## D. External-model proof harness

The runner `scripts/run_external_mcp_agent_proof.py` is designed to:

- use the frozen ten-case SPI corpus;
- keep outer case/equivalence/perturbation metadata away from the model;
- assign separate project/trace scope per case;
- call Hardware-Splicer only through the canonical MCP gateway;
- persist per-case mission/request/provider response/MCP trace/run summary;
- emit aggregate replay material;
- redact credential material from persisted artifacts;
- leave `live_unseen_competence=UNADJUDICATED`, `physical_correctness=UNPROVEN`, and `physical_authority_granted=false` until downstream evidence exists.

The associated non-golden trace audit can fail traces for incomplete/failed MCP calls, foreign project IDs, unsupported source identities, attempts to open physical authority, or unsupported fabrication/power-on readiness. Equivalent-case structural trace drift is a review signal rather than a golden-answer correctness failure.

**Current status:** infrastructure proven; actual paid/live model corpus run **NOT RUN**.

## E. Physical-evidence boundary

PR #59 corrected an ambiguity at the physical-proof boundary:

- omitted `capture.simulated` does not default favorably;
- missing simulation state is blocking;
- real evidence must explicitly state `simulated: false`.

The durable physical path remains revision-bound:

1. physical evidence record;
2. evidence envelope/content hashes;
3. exact stored project revision / expected revision;
4. explicit human authorization decision;
5. authorization-ledger history;
6. revalidation against candidate revision, artifact hashes, evidence kinds and scope.

PR #69 demonstrated a golden-real bench authority consumer path where a native Splice real-bench verification could record `simulated=false`, no open gates and a scoped authorization state. **This is evidence that the real-evidence/authority machinery can consume an explicitly real bench record; it is not physical closure of the fresh adversarial SPI case.**

## F. Proof still required

| Proof | Current state | Evidence required before claim changes |
|---|---|---|
| Live external model on unchanged SPI corpus | **PENDING** | actual provider execution, exact model/config, inputs/outputs, MCP calls, trace audit, outer adjudication, exact SHA |
| Fresh SPI physical correctness | **PENDING** | exact component/package identity, frozen candidate hashes, real assembly and measurements, failures/repairs, revision-bound `simulated:false` evidence |
| Independent human operator | **PENDING** | outsider protocol, task, elapsed time, interventions, tool failures, confusion, result and final authority state |
| Industrial/platform economics | **PENDING** | legitimate external use or controlled derivatives with precommitted reuse/intervention/cost measurements |

## G. Evidence discipline

- A failure is evidence; it is not deleted because it weakens a demo.
- Frozen unseen cases are not rewritten after results are visible.
- One audience may receive a shorter view than another, but no audience receives a different truth state.
- Model confidence is not evidence provenance.
- MCP connectivity is not physical authority.
- Unknown remains unknown.
