# Claims and Nonclaims

This is the canonical judge-facing claim boundary for the 2026 Q3 Hardware-Splicer submission package.

The rule is simple: **claim only what an exact artifact, revision, workflow or physical record can support.**

## Proven

### 1. Frozen software architecture and reproducible software checkpoint

At the software-freeze checkpoint in PR #59, source head:

`0164d47e25bfea8179073e46e869a8725ca03b83`

successful exact-head aggregate evidence included:

- Hardware-Splicer #1902;
- Core Diagnostics #699;
- Model-First Truth Bar #211.

This supports software-baseline and regression claims. It does not constitute physical proof.

### 2. Deterministic evidence/authority separation

Hardware-Splicer maintains explicit boundaries between:

- model reasoning and deterministic truth;
- proposal and verified state;
- exact/unresolved component identity;
- evidence provenance and unsupported assertion;
- one project revision and another;
- bench collection and revision-bound physical evidence;
- physical evidence and scoped human authorization.

Relevant revision/artifact changes can invalidate prior evidence or authority rather than silently carrying it forward.

### 3. Fail-closed treatment of ambiguous physical evidence

A bench capture cannot count as explicitly real merely because simulation state is omitted. Missing simulation status is blocking; real evidence must explicitly declare `simulated: false`.

### 4. Frozen adversarial unseen SPI corpus exists and validates

The repository contains an unchanged ten-case SPI-flash cleanroom corpus covering a baseline plus source-order and adversarial variants including:

- source reversal and rotation;
- neutral labels and mission paraphrase;
- partial evidence;
- component-identity conflict;
- parser/tool failure;
- plausible wrong analogy;
- stale-revision evidence.

The corpus/protocol itself is validated. **This does not mean a live external model has passed it.**

### 5. Canonical MCP engineering surface is real

On PR #70 head `bb313f283fc25ad75ea1ce0dd384ebb36d0d6911`, Canonical MCP Backend Contract run #15 completed successfully. The gateway:

- is generated from the canonical FastAPI/OpenAPI product backend rather than a second engineering implementation;
- exposes 193 canonical operations through a four-tool MCP gateway contract;
- works through a real MCP stdio client;
- works through a real MCP Streamable HTTP client;
- supports canonical stateful project write → read → delete across the MCP boundary;
- preserves the backend's revision/evidence/authority rules;
- does not independently grant physical authority.

### 6. External-agent proof harness is executable infrastructure

The exact-head CI validates the external-model runner, frozen ten-case inventory and non-golden external trace audit. The runner can persist model requests, provider responses, MCP calls, per-case state and replay manifests while keeping live competence `UNADJUDICATED` until an actual provider call occurs.

## Pending — do not present as proven

### Live external-model unseen competence

**PENDING.**

No paid/live external model has yet executed the unchanged full ten-case corpus through the current MCP proof harness. A green harness/transport workflow is not model-competence evidence.

To change this claim, preserve at minimum:

- exact code/evaluator/corpus revision;
- model/provider/configuration;
- actual model inputs and outputs;
- actual MCP calls and responses;
- trace-audit result;
- outer adjudication result;
- failures as well as successes.

### Fresh SPI physical correctness

**PENDING.**

The project has exercised real-bench infrastructure in a golden-real verification path, but that does not close the fresh adversarial SPI candidate's revision-bound physical proof chain.

A fresh claim requires exact component/package identity, candidate hashes, preassembly checks, assembly/substitutions, powered-off measurements, controlled power-up, bounded functional/signal evidence and preserved failure→repair→revision history.

### Independent human-operator usability

**PENDING.**

A technically competent outsider who did not author the candidate/evaluator has not yet completed the canonical independent-operator protocol.

### Demonstrated industrial economics or partner value

**PENDING.**

Platform reuse, intervention ratios, development-cost ratios and commercial value remain measurement hypotheses until real external cases establish them.

## Explicitly not claimed

Hardware-Splicer does not currently claim:

- autonomous production certification;
- industrial deployment readiness;
- universal hardware correctness;
- zero hallucination;
- replacement of a qualified hardware engineer;
- chip or wafer-process design automation;
- that CI constitutes physical evidence;
- that a model may authorize its own proposal;
- that authorization survives arbitrary design revisions;
- that a skipped or unrun provider step proves live-model competence;
- that MCP transport safety proves engineering correctness;
- that the ten-case corpus has been passed by a live model;
- that a prior golden-real bench path proves the fresh SPI case physically correct.

## Preferred evaluator language

If asked, “What happens when Hardware-Splicer is wrong?” the answer is not “the model is always right.”

> **The system is designed so that being wrong does not automatically grant physical authority.**

That is the project’s core safety and engineering claim.
