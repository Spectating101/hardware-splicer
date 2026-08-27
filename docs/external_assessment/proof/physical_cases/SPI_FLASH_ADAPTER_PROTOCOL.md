# SPI Flash Adapter — Revision-Bound Physical Proof Protocol

**Status:** prepared for execution; no physical-success claim is implied by this document.

## Purpose

Evaluate a real SPI-flash programming/validation adapter candidate produced after the source-blind unseen run while preserving the boundary between model reasoning and physical authority.

This protocol does **not** prescribe a translator choice, regulator choice, schematic, pin mapping, current limit, signal threshold, or expected model answer. Those values must come from the frozen candidate and defensible evidence attached to that candidate revision.

## Preconditions

Before physical work begins, freeze and record:

- repository SHA;
- project ID and candidate revision;
- Engineering Package / generated artifact hashes;
- model/provider/config used for the unseen run;
- component identities claimed by the candidate;
- unresolved evidence and blockers;
- candidate-defined power and signal limits;
- current authorization state, which must remain closed.

If the candidate lacks defensible limits required for safe bench work, the result is **BLOCKED**. Do not invent a value in this protocol.

## Phase 1 — Identity closure

For every physical component relevant to electrical behavior, record:

- manufacturer;
- exact part number / orderable suffix where available;
- package;
- board/module revision where applicable;
- photographs or markings sufficient to bind the physical item to the recorded identity;
- source evidence used for electrical/package facts;
- any mismatch between candidate identity and physical inventory.

An unresolved identity mismatch requires a new candidate revision or explicit blocking state before energization.

## Phase 2 — Deterministic pre-assembly checks

Run all candidate-required deterministic checks against the frozen artifacts.

At minimum capture where applicable:

- schematic/ERC result;
- PCB/DRC result;
- BOM consistency;
- net/interface mapping checks;
- power-domain compatibility checks;
- package/footprint consistency;
- artifact hashes.

Tool failure is evidence and must remain visible. A failed tool may not be replaced by a model assertion that the design is probably correct.

## Phase 3 — Assembly record

Record:

- exact parts assembled;
- substitutions;
- wiring/jumper changes;
- rework;
- soldering defects observed;
- photos sufficient to reconstruct assembly state;
- operator identity/role;
- timestamps.

Any substitution that changes relevant identity/interface/electrical assumptions invalidates affected evidence and must trigger the corresponding revision/retest logic.

## Phase 4 — Powered-off checks

Before applying power, perform candidate-appropriate powered-off verification. Examples may include continuity, short checks, resistance sanity checks, orientation, rail isolation, or connector mapping, but the exact required checks and acceptance criteria must be derived from the candidate/evidence rather than hard-coded here.

Persist raw measurements and instrument identification where practical.

A powered-off failure blocks progression until repaired and revisioned.

## Phase 5 — Controlled power-up

Use only defensible limits attached to the frozen candidate.

Record:

- supply/instrument model;
- configured voltage;
- configured current limit;
- initial current draw;
- rail measurements;
- thermal/visible anomalies;
- unexpected behavior;
- whether power was removed and why.

No model or evaluator may convert an absent measurement into a passing value.

## Phase 6 — Functional and signal evidence

Perform the candidate-defined bounded function needed to support the intended claim.

For the SPI-flash adapter this may include communication/programming/validation behavior and relevant logic-level observations, but exact procedures and acceptance criteria must be bound to the frozen candidate.

Capture:

- programmer/host identity and configuration;
- firmware/tool version;
- command sequence;
- raw output/logs;
- relevant signal measurements or traces;
- pass/fail interpretation and the evidence supporting it.

## Phase 7 — Failure → repair → revision loop

Failures are first-class evidence.

When a defect is found:

1. record the failed observation;
2. identify the proposed repair;
3. create the required new project/candidate revision;
4. invalidate evidence affected by the change;
5. rerun deterministic checks affected by the change;
6. rerun physical tests whose validity no longer survives;
7. preserve both the failed and repaired histories.

Do not overwrite the failed run with the successful repair state.

## Phase 8 — Durable physical evidence

A successful bench session is not yet authority.

Persist physical proof using the canonical revision-bound path:

1. `hardware_splicer.physical_evidence.v1` record;
2. `hardware_splicer.physical_evidence_envelope.v1` with content hashes;
3. exact stored project revision via audited persistence / expected revision;
4. explicit `simulated: false` or equivalent real-evidence declaration;
5. artifact/evidence hashes bound to the candidate.

If real-vs-simulated state is ambiguous, physical proof fails closed.

## Phase 9 — Human authorization

Only after evidence is persisted and revalidated may a human make the scoped authorization decision supported by that evidence.

Record:

- decision;
- scope;
- exact revision;
- exact artifact hashes;
- evidence kinds/hashes;
- authorizing human;
- timestamp;
- ledger linkage.

Authorization does not automatically survive a revision or relevant artifact-hash change.

## Outcome classes

Use one of the following high-level outcomes:

- **BLOCKED_BEFORE_ASSEMBLY** — identity/evidence/tool state prevents defensible construction;
- **BLOCKED_BEFORE_POWER** — pre-power evidence is insufficient or failed;
- **PHYSICAL_FAILURE_RECORDED** — powered/functional test exposed a defect;
- **REPAIRED_NEW_REVISION_REQUIRED** — repair exists but prior evidence cannot simply carry over;
- **PHYSICAL_EVIDENCE_PERSISTED** — required real measurements/function are recorded and bound;
- **AUTHORIZED_WITH_SCOPE** — a human explicitly authorized a bounded action after revalidation.

A physically successful run without durable evidence remains insufficient for the stronger claim.

## Required experiment record

The final experiment package must contain:

- frozen unseen-run reference;
- frozen candidate reference;
- deterministic results;
- identity evidence;
- assembly record;
- powered-off measurements;
- controlled power-up record;
- functional/signal record;
- failures and repairs;
- final physical evidence record/envelope;
- authorization decision/ledger entry, if any;
- explicit nonclaims.

## Nonclaims

Execution of this protocol does not establish certification, production readiness, general hardware correctness, or autonomous physical authority. It supports only the bounded claims actually evidenced on the exact candidate revision tested.
