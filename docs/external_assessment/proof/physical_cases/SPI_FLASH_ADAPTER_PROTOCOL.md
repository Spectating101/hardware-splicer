# SPI Flash Adapter — Revision-Bound Physical Proof Protocol

**Status:** prepared / not executed  
**Upstream experiment:** fresh unseen SPI-flash cleanroom case  
**Critical rule:** this protocol must not leak a golden engineering solution into the source-blind run.

The protocol defines **how a frozen candidate is physically evaluated**, not what circuit the candidate should be.

## Preconditions

Do not begin physical proof until:

1. the source-blind unseen run is frozen;
2. the candidate Engineering Package/revision is fixed;
3. exact model/provider/config and code revision are recorded;
4. unresolved facts from the unseen run remain visible;
5. all candidate-specific limits used below are traceable to accepted evidence.

This document intentionally does not prescribe a translator, regulator, package pinout, current limit, signal threshold or expected model answer.

## 1. Candidate identity

Persist:

- candidate project/revision ID;
- artifact hashes;
- declared DUT identity;
- physical DUT marking/photo/reference;
- exact package identity evidence;
- translator/regulator identities if selected;
- BOM substitutions;
- relevant manufacturer evidence revisions.

Any unresolved identity remains blocking for claims that depend on it.

## 2. Deterministic pre-assembly checks

Run all applicable deterministic checks from the frozen candidate package.

Record:

- command/tool version;
- input artifact hashes;
- pass/fail;
- warnings;
- failure output.

A deterministic failure remains evidence. Do not rewrite it into a model explanation and call it resolved.

## 3. Assembly record

Record:

- physical components actually used;
- lot/package/marking where available;
- wiring/PCB revision;
- substitutions from the candidate;
- rework;
- photographs sufficient to identify the assembly.

A substitution that changes relevant electrical/interface assumptions creates a new candidate revision before authority-bearing claims continue.

## 4. Powered-off checks

Use candidate-defined checks justified by its evidence.

Examples may include continuity, shorts, orientation and resistance checks, but this protocol does not supply acceptance values.

Persist raw observations and instrument identity where material.

## 5. Controlled power-up

Power-up parameters must come from the frozen candidate and its accepted evidence, not this protocol.

Record:

- source/instrument;
- configured limits;
- initial observations;
- measured rails;
- unexpected current/temperature/behavior;
- aborts.

If the candidate cannot defensibly specify a safe power-up envelope, the correct result is **blocked**, not improvisation.

## 6. Functional / signal validation

Perform the candidate's intended bounded programming/validation task.

Persist:

- exact firmware/tool version;
- command sequence;
- raw device response;
- signal captures or measurements where required by the candidate;
- success/failure;
- repeat count;
- anomalies.

Do not promote software recognition of a device into proof of all electrical claims.

## 7. Failure → repair → revision

Every repair that changes a relevant artifact produces:

- new revision;
- updated hashes;
- explicit statement of which prior evidence remains valid;
- explicit invalidation/revalidation of affected evidence;
- new physical run where needed.

Never overwrite the failed run.

## 8. Durable evidence path

A successful physical claim must flow through the canonical Hardware-Splicer evidence path:

1. `hardware_splicer.physical_evidence.v1`;
2. hash-bound `hardware_splicer.physical_evidence_envelope.v1`;
3. exact expected project revision;
4. audited persistence;
5. explicit human `AuthorizationDecision`;
6. authorization ledger;
7. revalidation against later revisions/artifact hashes.

Missing or ambiguous simulated/real status is blocking.

## 9. Completion states

The physical run ends in exactly one of:

- `BLOCKED_BEFORE_POWER`
- `FAILED_PHYSICAL`
- `PARTIAL_FUNCTION`
- `FUNCTIONAL_BUT_UNAUTHORIZED`
- `AUTHORIZED_FOR_RECORDED_SCOPE`

A green software workflow cannot substitute for these outcomes.

## Claim boundary

This protocol alone proves nothing physical. Only completed, revision-bound artifacts from an executed run may change the physical evidence state.
