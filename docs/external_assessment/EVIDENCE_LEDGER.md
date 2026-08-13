# Evidence Ledger

This ledger records what evidence exists, what it supports, and what it explicitly does **not** support.

## Software baseline

### Architecture baseline

- PR #56: `Build dual-agent cleanroom and remove semantic script brain`
- branch: `agent/dual-agent-cleanroom-20260808`
- frozen head: `0a55515cc683abccce6308c918f679199d5ebf87`

### Proof-tranche baseline

- PR #59: `Freeze software baseline and open external-proof tranche`
- branch: `agent/software-freeze-external-proof-20260812`
- source head for this package: `0164d47e25bfea8179073e46e869a8725ca03b83`

Completed successful exact-head aggregate evidence includes:

| Workflow | Run | Supports |
|---|---:|---|
| Hardware-Splicer | #1902 | aggregate repository software verification |
| Core Diagnostics | #699 | changed-test bar, persistence regressions, complete Python suite and diagnostics |
| Model-First Truth Bar | #211 | model-first semantic/truth boundary regression |

These runs support software-baseline claims only. They do not constitute physical proof.

## Deterministic cleanroom

Previously persisted deterministic cleanroom evidence recorded a passing challenge corpus with ten cases and checks covering:

- equivalence stability;
- cross-surface truth audit;
- label-sensitive script-brain behavior;
- invented evidence;
- forced guessing;
- deterministic tool failure;
- plausible wrong analogy;
- stale-revision evidence.

This supports the claim that the deterministic evaluator can distinguish several important failure modes at the frozen checkpoint.

It does **not** prove live embedded-model competence.

## Live cleanroom

**Status: PENDING.**

The previous live-provider job did not run the actual model-execution step because neither supported Qwen/DashScope provider secret was configured.

A future live-model success claim requires actual persisted live experiment artifacts, not merely a green workflow/job wrapper.

## Proof-schema correction

PR #59 corrected an ambiguity at the physical-proof boundary:

- omitted `capture.simulated` no longer defaults favorably;
- missing simulation state is blocking;
- generated capture templates require an explicit declaration;
- real evidence must explicitly state `simulated: false`.

This supports the claim that evidence provenance itself fails closed when real-vs-simulated status is ambiguous.

## Canonical physical-evidence path

Bench-session/capture surfaces are evidence-collection and claim-ceiling tools. Durable physical proof uses the existing revision-bound path:

1. `hardware_splicer.physical_evidence.v1` record;
2. `hardware_splicer.physical_evidence_envelope.v1` with content hashes;
3. exact stored project revision via `expected_revision` audited persistence;
4. explicit human `AuthorizationDecision`;
5. chained `hardware_splicer.authorization_ledger.v1` history;
6. revalidation against candidate revision, artifact hashes, evidence kinds and scope.

Authorization does not automatically survive revision or artifact-hash changes.

## Proof still required

| Proof | Current state | Evidence required before claim changes |
|---|---|---|
| Live embedded model | PENDING | actual live run, provider/model/config, inputs/outputs/tool calls/evaluator result, exact code revision |
| Fresh unseen case | PENDING | unfamiliar case + preserved perturbations and outcome |
| Physical correctness | PENDING | real components/assembly/measurements/failures/repairs bound to revision and artifact hashes |
| Independent operator | PENDING | outsider protocol, task, completion/interventions/confusion/result |
| Industrial value | PENDING / NOT YET ESTABLISHED | legitimate external engineering user or partner case with observable workflow value |

## Evidence discipline

A failure is not deleted because it weakens the demo. A correctly blocked or repaired failure is potentially stronger evidence than an unrealistically perfect run.
