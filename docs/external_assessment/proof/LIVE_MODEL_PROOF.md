# Live Embedded-Model Proof

**Status: PENDING**

Do not upgrade this status until the embedded operator has actually executed through a genuinely configured provider.

## Required conditions

- use the existing source-blind embedded-operator path;
- do not expose source code, hidden tests, golden answers or evaluator conclusions;
- do not weaken deterministic/evidence/authority rules to make the run pass;
- never persist provider secrets.

## Persist for the experiment

- exact code revision;
- provider and model identity;
- non-secret runtime configuration;
- product-visible/source-visible context given to the embedded operator;
- model inputs and outputs;
- tool calls and tool results;
- proposed decisions;
- unresolved states / requested evidence;
- evaluator judgments;
- failure/timeout/error information.

## Acceptance standard

> The model performs useful engineering reasoning without hidden source/golden access and without acquiring deterministic or physical authority it does not possess.

The experiment does **not** require a flawless model response. A legitimate failure may be evidence.

## Completion record

Fill only after a genuine run:

- Experiment date:
- Exact revision:
- Provider/model:
- Artifact paths / hashes:
- Evaluator result:
- Important failures:
- Claim change authorized by evidence:

Until these fields are backed by artifacts, this file remains `PENDING`.
