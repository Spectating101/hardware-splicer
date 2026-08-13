# 3-Minute Demo

## Purpose

Demonstrate that Hardware-Splicer's refusal behavior is part of the product rather than a limitation to hide.

## 0:00–0:30 — problem and identity

> AI can generate engineering output faster than an engineer can verify every assumption. In hardware, that creates a dangerous gap between a plausible answer and a physically defensible one.

> Hardware-Splicer is an evidence-constrained AI engineering agent for pre-fabrication hardware readiness.

## 0:30–1:15 — inner agent vs deterministic truth

Show the embedded operator receiving normal engineering material and reasoning about it.

Call out that the embedded operator does not receive hidden source/golden truth.

Then show at least two of the following behaviors:

- exact component identity remains unresolved when evidence is insufficient;
- a similar component is not promoted to identical by analogy;
- a missing driver/controller/interface remains a blocker;
- conflicting evidence remains visible;
- a deterministic tool failure is preserved instead of rewritten by the model.

Narration:

> The model is allowed to reason. It is not allowed to turn uncertainty into verified identity or electrical truth.

## 1:15–2:00 — engineering package and closed authority

Show the revisioned Engineering Package and the relevant deterministic/evidence output.

Highlight that a generated package does **not** automatically mean fabrication/power/motion/release authority is open.

> A software-success state and a physical-success state are deliberately different claims.

## 2:00–2:35 — physical-evidence boundary

Show the bench capture / physical-proof surface and the current fail-closed rule:

- `simulated: false` must be explicit for a real capture;
- missing simulation status is blocking.

Use the line:

> **Even the evidence proving the hardware is real has to prove that it is real.**

Then show the canonical chain:

`PhysicalEvidenceRecord → hash-bound envelope → exact revision → human authorization`.

## 2:35–3:00 — close

> Hardware-Splicer does not promise that an AI will never be wrong. It is designed so that being wrong does not automatically grant physical authority.

End with:

> **AI proposes → deterministic systems constrain → bench evidence decides → human authorizes.**

## Proof-status disclosure

If this demo is recorded before the pending proof phases are completed, state explicitly:

- deterministic/software baseline: proven;
- live embedded-model competence: pending unless a genuine live run has been preserved;
- real physical correctness: pending unless a revision-bound physical case has been completed;
- independent operator: pending unless the outsider protocol has been completed.
