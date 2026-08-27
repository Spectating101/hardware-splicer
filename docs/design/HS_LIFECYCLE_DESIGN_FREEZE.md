# Hardware-Splicer Lifecycle Extension — Design Freeze

**Status:** consolidated design checkpoint; no implementation authorized  
**Date:** 2026-08-28  
**Branch:** `design/refurb-lifecycle-blueprint-20260828`

## Decision

Pause lifecycle-platform development here.

The design is sufficiently coherent to support gauntlet/commercialization narrative work, but the next material proof should come from a real Hardware-Splicer physical transformation rather than additional platform code.

## Authoritative design documents

1. `HS_LIFECYCLE_PLATFORM_BLUEPRINT.md` — architecture, domain model, trust model, APIs, rollout phases, risks, and first physical pilot.
2. `HS_LIFECYCLE_RESEARCH_MATRIX.md` — external validation against refurb certification, repair knowledge, DPP/lifecycle standards, traceability, provenance, sanitization, and Taiwan commercial constraints.

## Synthetic design fixture

`examples/keyboard_split/` is a **paper prototype only**.

It contains:

- a synthetic unit passport;
- a synthetic donor→output transformation record;
- a synthetic recipe instance;
- a synthetic buyer/listing projection;
- a synthetic passport-aware service-agent walkthrough.

These files validate schema/view consistency only. They do **not** prove that a keyboard has been transformed, tested, sold, warranted, certified, or physically verified.

## Frozen architecture

```text
Hardware-Splicer engineering/evidence truth
                ↓
        append-only lifecycle registry
          ↙                     ↘
   unit passport             recipe registry
          ↓                     ↓
 public/service/agent      HS transfer/reuse
          ↓
 listing/warranty projections
          ↓
 existing commerce channels
```

Core invariants:

- HS Core remains authoritative.
- Lifecycle history is append-only.
- Major transformations may create a new output-unit identity while preserving donor lineage.
- Public/commercial claims must resolve to revision-bound evidence and cannot promote weaker evidence states.
- Recipes are versioned decision/evidence protocols, not fixed tutorials.
- One completed unit can make a recipe `OBSERVED`; replication requires additional sufficiently independent units.
- External agents are read-only by default.
- Regulatory certification is separate from HS engineering verification.
- Marketplace/payment/logistics infrastructure is deferred.

## Legitimate gauntlet claim

The project may state that Hardware-Splicer has a researched and architected expansion path in which real hardware transformations can produce persistent unit passports, reusable transformation recipes, and unit-specific service context for humans or AI agents.

It may also state that the design has been exercised with a synthetic split-keyboard lifecycle fixture to test identity, lineage, evidence projection, recipe maturity, listing projection, and service-context coherence.

It must **not** claim:

- a deployed lifecycle/passport platform;
- a working marketplace;
- real buyer adoption;
- real warranty economics;
- DPP regulatory compliance;
- a completed split-keyboard transformation;
- physical validation of the synthetic fixture;
- production certification.

## Resume trigger

Do not reopen implementation merely because the design exists.

Resume when at least one of these is true:

1. a real HS-controlled transformation is ready to generate the first genuine unit lifecycle record;
2. a concrete gauntlet/pilot/customer route materially requires a passport/recipe capability;
3. an external refurb/service partner requests item-level traceability or unit-aware service context;
4. real completed transformations provide enough repeated evidence to justify a persistent recipe registry.

Preferred first resume event: **commodity keyboard → physically verified split keyboard**.

At that point, replace—not merely supplement—the synthetic assumptions with evidence from the actual donor, transformation, failures/repairs, test runs, and resulting output unit.

## Next work belongs elsewhere

Until a resume trigger occurs, priority should remain on:

- consolidating current HS proof and external packaging;
- completing real physical evidence;
- external submissions/pilots;
- preserving the lifecycle design as a bounded commercialization/scale path.

No further lifecycle-platform feature work is required at this checkpoint.
