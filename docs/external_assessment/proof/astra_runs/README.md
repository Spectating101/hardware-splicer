# Published Astra runs

This directory preserves sanitized, hash-accounted evidence from live clean-room Astra
runs. Each bundle states its own acceptance result and nonclaims. A passing run is evidence
that the model satisfied the tested process and persistence contracts for that case; it is
not proof of electrical correctness, source truth, fabrication readiness, or physical
authority.

## 2026-09-12 sequence

1. `2026-09-12-sellable-baseline` — passing baseline run on the original declared-evidence
   case.
2. The first primary-source attempt stopped before model inference because the governor was
   launched with a Python environment in which Hardware Splicer was not importable. It used
   no model tokens and produced no trace, so there is no full proof bundle to publish.
3. `2026-09-12-primary-source-runtime-mismatch` — Astra reasoned about the new case, but the
   isolated backend was a stale installation without the pre-fabrication-plan endpoint.
   Its attempted state transition failed and the provenance contract correctly rejected the
   unchanged project state.
4. `2026-09-12-primary-source-pass` — after reinstalling the isolated backend from the frozen
   repository commit, all four acceptance contracts and the preregistered document-grounded
   adjudication passed.

The failed attempt is retained because it demonstrates that persuasive model reasoning alone
does not earn credit when the claimed engineering state was not persisted.
