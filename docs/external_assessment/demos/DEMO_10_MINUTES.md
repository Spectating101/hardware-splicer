# 10-Minute Evaluator Demo

This is the canonical long-form competition/demo flow. It is designed to expose both product value and evidence discipline without drowning the evaluator in repository internals.

## 0:00–0:45 — the risk

> AI-generated hardware can look convincing long before it is safe to fabricate.

Explain the gap between fluent engineering output and defensible physical truth:

- uncertain component identity;
- incomplete/conflicting sources;
- hidden electrical incompatibility;
- stale revision evidence;
- generated confidence without bench validation.

## 0:45–1:30 — product identity

> Hardware-Splicer is an evidence-constrained AI engineering agent that helps prepare real hardware for fabrication while refusing to turn guesses into physical authority.

Bound the scope to test/validation support hardware, fixtures, adapter/validation boards, lab/NPI support and related electromechanical preparation.

State what it is not: chip design, wafer-process automation, production certification or autonomous engineer replacement.

## 1:30–3:15 — embedded operator

Run or replay the normal product-visible interaction.

The embedded operator should demonstrate useful semantic engineering reasoning while remaining source-blind to hidden evaluator truth.

Show at least three distinct reasoning outcomes:

1. a useful proposal;
2. an unresolved state or request for evidence;
3. a blocked action due to identity/electrical/interface uncertainty.

Point out that the operator does not receive hidden tests, source-as-answer, golden conclusions or fixture labels that encode truth.

## 3:15–4:30 — deterministic/evidence constraints

Open the evidence/provenance view and explain what is not delegated to model confidence:

- component identity resolution;
- exact-revision state;
- electrical/interface checks;
- evidence provenance;
- stale-evidence invalidation;
- authority gates.

Demonstrate one anti-script-brain property where label/order perturbation does not legitimately change equivalent semantic truth, or explain the preserved deterministic cleanroom evidence if live reproduction is unsuitable for the venue.

## 4:30–5:30 — revisioned engineering package

Show the normal Engineering Package generated for the candidate.

Important narration:

> A complete-looking engineering package is not automatically a physically authorized package.

Expose the current authority status and the specific evidence still required.

## 5:30–6:30 — physical-proof architecture

Show the collection surface and the canonical durable chain:

```text
bench observation
    ↓
PhysicalEvidenceRecord
    ↓
hash-bound PhysicalEvidenceEnvelope
    ↓
exact expected_revision persistence
    ↓
human AuthorizationDecision
    ↓
authorization ledger + revalidation
```

Explain that authorization does not automatically carry across candidate revisions or artifact hashes.

Use the concrete PR #59 correction:

> A capture with omitted simulation state cannot quietly count as real evidence. Real evidence must explicitly declare `simulated: false`.

## 6:30–7:45 — failures as evidence

Show a compact failure ledger or replay covering several of:

- unknown hardware remains unknown;
- plausible wrong analogy rejected;
- missing driver/interface remains missing;
- conflicting evidence stays conflicting;
- deterministic tool failure is preserved;
- stale revision invalidates evidence;
- ambiguous/simulated physical capture cannot be promoted.

Explain:

> The goal is not a demo where nothing ever fails. The goal is a system where failure is visible before it becomes physical authority.

## 7:45–8:45 — evidence status

Present the exact current proof matrix:

| Layer | State |
|---|---|
| Exact-head software | PROVEN |
| Deterministic cleanroom | PROVEN |
| Genuine live embedded model | update from `proof/LIVE_MODEL_PROOF.md` |
| Fresh unseen case | update from `proof/UNSEEN_CASE_PROOF.md` |
| Real physical case | update from `proof/PHYSICAL_PROOF.md` |
| Independent operator | update from `proof/INDEPENDENT_OPERATOR_PROOF.md` |

Never verbally upgrade a `PENDING` proof slot.

## 8:45–9:30 — why this matters industrially

Frame the practical value as reducing the gap between AI-assisted design intent and engineering evidence readiness:

- fewer hidden assumptions reaching fabrication;
- clearer unresolved items;
- traceable sources and revisions;
- explicit bring-up requirements;
- preservation of failures/repairs;
- safer handoff between AI assistance and accountable human engineering.

Do not claim quantified cost/time savings until an external case has measured them.

## 9:30–10:00 — close

> Hardware-Splicer does not need the AI to be infallible. It needs the system to know the difference between a proposal, evidence and authority.

End on:

> **AI proposes → deterministic systems constrain → bench evidence decides → human authorizes.**
