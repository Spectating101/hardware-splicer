# Hardware Splicer — Software Freeze and External-Proof Handoff

**Checkpoint date:** 2026-08-12 (Asia/Taipei)  
**Purpose:** durable resume point after the dual-agent cleanroom integration closure. This document exists so later work does not repeat the July/August software-cleanup loop or mistake a skipped live probe for live-model evidence.

## Frozen software checkpoint

- Integration PR: **#56 — Build dual-agent cleanroom and remove semantic script brain**
- #56 branch: `agent/dual-agent-cleanroom-20260808`
- Frozen branch head: `0a55515cc683abccce6308c918f679199d5ebf87`
- Integrated staging PR: **#57 — CI staging: repair, replay, and physical proof authority**
- #57 merged into #56 at **2026-08-12T11:18:21Z** / **2026-08-12 19:18:21 +08:00**
- Merge commit on the #56 branch: `0a55515cc683abccce6308c918f679199d5ebf87`
- PR test merge ref observed by GitHub Actions: `52b603d8cf3cc306f75b575578f5bd509a9c5bfc`

The branch checkpoint and the synthetic PR merge ref are intentionally recorded separately. Do not cite the PR merge ref as the frozen source revision.

## What is frozen

The following software direction is considered closed unless new external evidence identifies a concrete defect:

- dual-agent cleanroom: outer System Engineer / Observer vs source-blind Embedded Engineer / Operator;
- model-first semantic boundaries with no keyword or fixture-label authority;
- strict identity vs capability vs missing-capability separation;
- unresolved-identity propagation instead of representative-SKU substitution;
- repair proposals that cannot silently mutate verified physical/design truth;
- cross-surface model-first truth audit;
- revision, provenance, evidence and authority boundaries;
- pin-faithful KiCad evidence and normalized ERC handling;
- deterministic adversarial replay and retrospective taxonomy;
- fail-closed fabrication / flash / power / motion / operation / release authority.

This checkpoint is **not** a claim of physical readiness, independent-user success, or live-model competence.

## Exact-head CI evidence

After #57 was folded into #56, the PR integration state completed successfully across the important bars, including:

| Workflow | Run | Result |
|---|---:|---|
| Hardware-Splicer | 1893 | success |
| Core Diagnostics | 692 | success |
| Model-First Truth Bar | 204 | success |
| Cleanroom DUT Replay | 189 | success* |
| Pin-Faithful Schematic Staging | 65 | success |
| Golden Rover JARVIS E2E | 97 | success |
| Golden Semiconductor Fixture E2E | 100 | success |
| Electronics Foundation Benchmark | 139 | success |
| Discrete Electronics Staging | 67 | success |
| Robot Arm Engineering Experiment | 89 | success |
| Engineering Package Export | 268 | success |

`*` The deterministic cleanroom job passed. The live embedded-operator step did **not** run; see below.

## Deterministic cleanroom evidence

GitHub Actions run `31591252971` produced artifact `cleanroom-dut-deterministic` with artifact ZIP digest:

`sha256:f20fd657a2dfd1f37550fed4ec8419601094ad53c6b8c3e86300f18b159e9acd`

The persisted deterministic report recorded:

- `pass=true`
- `case_count=10`
- compliant equivalence stability: pass
- compliant truth audit: pass
- label-sensitive script-brain behavior detected
- invented evidence detected
- forced guessing detected
- deterministic tool failure included
- plausible wrong analogy included
- stale-revision evidence included

Challenge kinds include conflicting evidence, partial evidence, deterministic tool failure, plausible wrong analogy and stale-revision evidence.

## Live embedded-operator evidence gap

The workflow job named **Live embedded operator probe** completed with a green job conclusion, but its actual model-execution step was skipped because neither provider secret was configured.

Persisted artifact `cleanroom-dut-live` contained only:

`live probe skipped: no QWEN_API_KEY or DASHSCOPE_API_KEY secret`

Artifact ZIP digest:

`sha256:9218177d8a2dcee484a51aa123434af8417bc85fde55e4d23a4bf232f1462873`

Therefore the correct state is:

- deterministic evaluator: **proven at this checkpoint**
- live provider wiring: **not exercised**
- live embedded-model behavior: **not proven**
- external value / physical correctness: **not proven**

A future green Cleanroom DUT Replay run must not be counted as live-model evidence unless `LIVE_DUT_EXPERIMENT.json` and `LIVE_SUMMARY.txt` were actually produced by the model-execution step.

## Resume sequence — do not restart product development

The next work is a proof tranche, in this order:

1. **Live embedded-operator run** — execute the existing cleanroom through a genuinely configured provider. Keep the operator source-blind and preserve the current evaluator and authority contracts.
2. **Fresh unseen adversarial case** — use a project not sculpted around the rover or DUT goldens; perturb labels, ordering, equivalent parts, stale/partial/conflicting evidence and plausible analogies without adding canned answer logic.
3. **Fresh independent checkout** — run from the frozen revision, not a developer working tree with untracked conveniences.
4. **Real project/components** — ingest actual component identities and evidence, generate the normal revisioned Engineering Package and preserve every blocker/failure.
5. **Physical loop** — fabrication/assembly as appropriate, powered-off checks, controlled power-up, measurements, flashing/function/motion where relevant, failures/repairs and final outcome, all bound to exact revision/artifact hashes.
6. **Independent operator attempt** — a user without repository/source knowledge operates the actual product surface.
7. **Outer truth audit** — compare what the embedded operator believed, what deterministic tools said and what the bench actually showed.

## Explicit non-actions

Until the proof tranche produces a concrete defect, do **not**:

- restore fake production authority to satisfy historical fixtures;
- manually patch a local environment and call it repository evidence;
- add another semantic routing layer, keyword dispatcher or fixture-specific recognizer;
- add canned cases merely to raise a score;
- reopen generic feature development because a live provider secret is missing;
- treat software CI as physical proof;
- treat an optional/skipped live-provider job as live-model evidence.

Unknown hardware stays unknown. Proposals stay proposals. Physical authority stays evidence-based.

## Resume rule

A future agent should begin from this document and the machine-readable checkpoint beside it, verify that the #56 branch still points at the recorded frozen revision (or explicitly document any successor), and continue the proof sequence from the first genuinely incomplete gate. Do not replay the pre-freeze cleanup unless a new failing artifact demonstrates that it is necessary.
