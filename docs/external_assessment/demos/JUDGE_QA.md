# Judge Q&A

The preferred answer style is short, evidence-specific and willing to say “not yet proven.”

## 1. Why isn't this just Claude/Cursor generating a schematic?

Because model generation is only one layer. Hardware-Splicer separately tracks identity, evidence provenance, electrical/interface constraints, exact revisions, physical evidence and scoped human authorization. The model may propose; it does not own those truth/authority layers.

## 2. Why does an engineer need this instead of ChatGPT + KiCad?

The intended value is the evidence/authority workflow around AI reasoning: unresolved identities remain unresolved, deterministic constraints remain independent of model confidence, revision changes invalidate stale evidence, and physical authorization requires revision-bound real evidence.

## 3. What is AI and what is deterministic?

AI handles semantic engineering judgment: interpreting intent, reasoning about alternatives, proposing and identifying missing information. Deterministic systems handle identity/evidence state, constraints, revision/provenance checks and consequences. Physical reality and explicit human review decide physical authority.

## 4. What prevents hallucinated parts?

The model is not allowed to convert a plausible analogy into verified identity. If evidence cannot resolve an exact component, the correct state is unresolved rather than substitution with a familiar SKU.

## 5. What prevents the AI from declaring its own output safe?

Authority is a separate subsystem. The model cannot self-promote a proposal into fabrication/power/motion/release authorization. Physical evidence and human authorization are separate gates.

## 6. What happens when evidence conflicts?

Conflict remains visible and can block progress. The model is not supposed to erase deterministic conflict by writing a more confident explanation.

## 7. What happens when the component cannot be identified?

It remains unresolved. Hardware-Splicer should ask for or expose the missing evidence rather than inventing identity.

## 8. What happens if the model fails?

A model failure is allowed to remain a model failure. Deterministic truth/evidence must not be rewritten to make the model look successful, and physical authority must remain closed where required.

## 9. Why is green CI not physical proof?

CI proves software behavior under the tested environment. It does not prove that a particular physical assembly was built, powered, measured or worked. Physical claims require physical evidence.

## 10. What proves that the hardware actually worked?

At the current checkpoint, that proof is still pending unless `proof/PHYSICAL_PROOF.md` has been updated with a completed real case. The required path includes real observations, revision/artifact binding and the canonical physical-evidence chain.

## 11. Does authorization survive a design revision?

Not automatically. Authorization is revalidated against the candidate revision and artifact-hash boundary. Relevant revision/artifact changes can invalidate prior authority.

## 12. Can it work on an unseen case?

That is an explicit pending proof gate until a fresh unfamiliar adversarial case is completed and preserved. Do not answer this with a synthetic benchmark claim alone.

## 13. Can another engineer use it without the developer?

Independent-operator usability is a separate proof gate and should remain `PENDING` until the outsider protocol is actually completed.

## 14. How does it scale beyond one fixture?

The architecture is intentionally based on general evidence/identity/revision/authority boundaries rather than fixture-specific semantic recognizers. Generalization still needs to be demonstrated with fresh unseen cases and external users.

## 15. Which semiconductor workflow does it improve?

The bounded target is pre-fabrication readiness for semiconductor testing/validation support hardware such as fixtures, adapter/validation boards and lab/NPI support hardware—not wafer-process or chip-design automation.

## 16. What time/cost/error burden does it reduce?

The architectural hypothesis is that explicit unresolved-state/evidence handling reduces hidden assumptions reaching fabrication and improves engineering handoff. Quantified time/cost/error reduction is **not yet claimed** without an external measured case.

## 17. What is commercially defensible?

The defensible system idea is not “we have an LLM.” It is the evidence-constrained workflow separating semantic reasoning from identity, deterministic constraints, revision-bound physical proof and accountable authorization. Commercial value still needs external pilot evidence.

## 18. Why should a semiconductor company trust it?

They should not trust it merely because an AI sounds confident. The product is designed to make the basis of a claim inspectable and to keep authority closed when required evidence is missing. Industrial trust still has to be earned through real partner cases.

## 19. What happens when Hardware-Splicer is wrong?

> **The system is designed so that being wrong does not automatically grant physical authority.**

## 20. What does Hardware-Splicer explicitly refuse to do?

It refuses to treat unknown hardware as known, model confidence as verification, CI as physical proof, stale evidence as current authorization, or a proposal as permission to fabricate/power/move/release hardware.

## Questions we should ask ourselves before every submission

- Which claims in this answer are backed by exact artifacts?
- Which proof slot is still pending?
- Did venue-specific wording accidentally upgrade a pending proof?
- Can a judge reproduce the evidence path without trusting our narrative?
- Are we presenting a failure honestly rather than hiding it?
