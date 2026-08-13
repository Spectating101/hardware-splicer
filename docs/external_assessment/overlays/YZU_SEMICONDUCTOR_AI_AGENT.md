# YZU Semiconductor AI-Agent Competition — Home-Field Overlay

**Status:** primary / home-field route

Hardware-Splicer was originally framed around semiconductor testing/validation support-hardware readiness. This route should therefore present the project in its native bounded domain rather than broadening it into generic robotics or generic AI tooling.

## Administrative authority

Use the team's existing internal competition brief, email and organizer instructions as the source of truth for:

- final schedule;
- exact judging rubric;
- deliverable format;
- token/subsidy administration;
- venue and presentation mechanics.

Public academy material is useful context but should not override the internal competition instructions.

## Evaluator identity

Use:

> **Hardware-Splicer is an evidence-constrained AI engineering agent for pre-fabrication readiness of semiconductor testing and validation support hardware.**

Then immediately make the authority boundary concrete:

> **AI proposes → deterministic systems constrain → bench evidence decides → human authorizes.**

## What to emphasize

### Agent task quality

Show that the embedded agent performs genuine engineering reasoning rather than merely filling a form or calling a fixed script.

Evidence to surface:

- source-blind embedded operator;
- useful proposal generation;
- unresolved-state preservation;
- response to conflicting/partial evidence;
- safe behavior when a tool/model fails.

### Harness engineering

The harness is not a generic orchestration wrapper. It enforces the epistemic and authority boundaries around the model.

Show:

- identity vs capability vs missing-capability separation;
- evidence provenance;
- exact revision state;
- deterministic electrical/interface checks;
- stale evidence invalidation;
- physical authority gates;
- outer truth audit.

### Semiconductor relevance

Keep examples tied to:

- test/validation fixtures;
- adapter boards;
- validation boards;
- lab/NPI support hardware;
- related pre-fabrication and bring-up preparation.

Do not imply wafer-process or chip-design automation.

### Live demonstration

The ideal sequence is:

1. give normal engineering intent/materials to Hardware-Splicer;
2. let the embedded operator reason;
3. expose one useful proposal;
4. expose one blocker/unresolved item;
5. show deterministic evidence/revision state;
6. show the Engineering Package;
7. show that physical authority remains closed where proof is absent;
8. if available, show the revision-bound real physical case.

## Strongest judge moment

Use a failure/refusal that is easy to understand.

Best currently available software example:

> A physical capture that does not explicitly declare whether it is simulated cannot quietly count as real evidence.

Then say:

> **Even the evidence proving the hardware is real has to prove that it is real.**

This is a compact demonstration of why the system is more than “LLM + KiCad.”

## Fresh unseen-case proof

The prepared SPI-flash adapter corpus should be used only after a genuine source-blind model run exists.

Until then, describe it precisely as:

> a fresh unseen adversarial corpus whose evidence invariants and artifact persistence are validated, with live model execution still pending.

Do not call corpus construction itself unseen-model success.

## Physical proof

If the physical case is ready before judging, make it the center of the demonstration:

```text
intent
  ↓
AI reasoning
  ↓
engineering proposal
  ↓
deterministic checks
  ↓
revisioned package
  ↓
real assembly/bring-up
  ↓
measurements / failures / repairs
  ↓
revision-bound physical evidence
  ↓
human authorization
```

A real caught failure is preferable to a synthetic flawless demo.

## Questions to answer cold

- Why is this not ChatGPT/Cursor plus KiCad?
- What exactly is AI and what is deterministic?
- What stops hallucinated parts becoming verified parts?
- What happens when the exact hardware identity is unknown?
- What happens when evidence conflicts?
- Why is CI not physical proof?
- What makes this specifically valuable to semiconductor test/validation support work?
- What happens when Hardware-Splicer is wrong?

Preferred final answer to the last question:

> **The system is designed so that being wrong does not automatically grant physical authority.**

## Non-actions for this route

Do not:

- broaden HS into generic robotics to make the demo more visually exciting;
- weaken identity/evidence gates to produce a smooth demo;
- use fixture-specific keyword semantics;
- describe software “real-bench” jobs as actual physical hardware evidence;
- claim live-model proof from a skipped provider job;
- rewrite the architecture around the competition rubric.

If the competition rewards the real system, show the real system. If a presentation constraint forces a shorter story, compress the evidence—not the truth boundary.
