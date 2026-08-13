# Architecture for Evaluators

## The short version

Hardware-Splicer separates three kinds of judgment that are often collapsed in AI engineering systems:

1. **semantic engineering reasoning**;
2. **deterministic evidence and constraint evaluation**;
3. **physical authority**.

The architecture is intentionally asymmetric.

## 1. Embedded Engineer / Operator

The embedded agent sees the product-visible engineering state and may:

- interpret engineering intent;
- reason about alternatives;
- propose components or repairs;
- identify missing information;
- ask for evidence;
- preserve unresolved state;
- choose not to proceed.

It does **not** receive hidden evaluator truth such as:

- source code as privileged answer material;
- hidden tests;
- golden answers;
- evaluator conclusions;
- fixture labels that secretly encode the expected answer.

The embedded agent reasons. It does not own physical truth.

## 2. System Engineer / Evaluator

The outer evaluation layer can inspect the system rather than merely trusting the model response. It can assess:

- traces and tool use;
- exact revision;
- component/evidence provenance;
- deterministic electrical and interface results;
- stale or conflicting evidence;
- whether an unresolved identity was silently replaced by a familiar SKU;
- whether a proposal crossed an authority boundary;
- whether model behavior changes when labels/order change while meaning remains equivalent.

The outer evaluator therefore judges the embedded agent without becoming a hidden answer oracle for it.

## 3. Physical reality

Neither the inner nor outer agent may declare real-world hardware success merely from software state.

Physical claims require actual evidence bound to the relevant project/candidate revision and artifact hashes. Human authorization remains separate and explicit.

## End-to-end authority flow

```text
Engineering intent
        ↓
Embedded AI engineer
        ↓
Proposal / unresolved state
        ↓
Identity + provenance + electrical/interface checks
        ↓
Revisioned Engineering Package
        ↓
PHYSICAL AUTHORITY CLOSED
        ↓
Real bench observations
        ↓
PhysicalEvidenceRecord
        ↓
Hash-bound PhysicalEvidenceEnvelope
        ↓
Exact-revision audited persistence
        ↓
Human AuthorizationDecision
        ↓
Authorization ledger + revalidation
```

## Why the separation matters

A language model is useful precisely where engineering work is semantic, contextual and open-ended. It is a poor sole authority for facts that must remain reproducible, revision-specific or physically measured.

Hardware-Splicer therefore uses the model where judgment is useful and deterministic/physical systems where consequences matter.

## Failure behavior as a feature

The architecture is expected to preserve cases such as:

- unknown component → remains unknown;
- analogous component → does not become identical by analogy;
- missing driver/interface → remains a blocker;
- stale evidence → becomes invalid for the changed revision;
- failed deterministic tool → failure is preserved rather than rewritten by the model;
- ambiguous or simulated bench evidence → cannot masquerade as real physical evidence.

The goal is not to eliminate failure from engineering. The goal is to make failure visible before confidence becomes authority.
