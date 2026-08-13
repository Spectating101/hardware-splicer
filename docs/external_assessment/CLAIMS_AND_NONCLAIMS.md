# Claims and Nonclaims

This document is the canonical judge-facing claim boundary for the current Hardware-Splicer evidence package.

## Proven at the frozen software checkpoint

### Exact-head software reproducibility

At PR #59 source head:

`0164d47e25bfea8179073e46e869a8725ca03b83`

completed successful aggregate runs include:

- Hardware-Splicer #1902;
- Core Diagnostics #699;
- Model-First Truth Bar #211.

### Deterministic cleanroom behavior

The deterministic cleanroom evidence passed its persisted challenge corpus, including cases involving:

- conflicting evidence;
- partial evidence;
- deterministic tool failure;
- plausible wrong analogy;
- stale-revision evidence;
- invented evidence;
- forced guessing;
- label-sensitive script-brain behavior.

### Evidence/authority architecture

The repository contains explicit boundaries between:

- model reasoning and deterministic truth;
- proposal and verified state;
- bench collection and revision-bound physical evidence;
- physical evidence and human authorization;
- one candidate revision/artifact boundary and another.

### Fail-closed proof correction

A present bench capture cannot count as explicitly real physical evidence merely because simulation status is omitted. Missing simulation status is blocking; real evidence must explicitly declare `simulated: false`.

## Pending — do not present as proven

### Live embedded-model competence

**Pending.**

The previous cleanroom workflow did not execute the live model step because a supported provider credential was not configured. A green workflow label is not live-model proof.

### Fresh unseen-project generalization

**Pending.**

A deliberately unfamiliar case outside the established golden family still needs to be run and preserved.

### Physical correctness

**Pending.**

Software jobs whose names contain “bench” do not prove that real hardware was assembled, powered or measured.

### Independent-operator usability

**Pending.**

A technically competent outsider has not yet completed the canonical independent-user protocol.

## Explicitly not claimed

Hardware-Splicer does not currently claim:

- autonomous production certification;
- industrial deployment readiness;
- universal hardware correctness;
- zero hallucination;
- replacement of a qualified hardware engineer;
- chip/wafer-process design automation;
- that CI constitutes physical evidence;
- that a model may authorize its own proposal;
- that authorization survives arbitrary design revisions;
- that a skipped provider job proves live-model competence.

## Preferred evaluator language

When asked “What happens when Hardware-Splicer is wrong?” the intended answer is not merely “we are accurate.”

> **The system is designed so that being wrong does not automatically grant physical authority.**

That is a stronger and more defensible claim than promising model infallibility.
