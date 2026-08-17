# HS conversion readiness matrix

Purpose: prevent internal technical progress from being upgraded into commercial, research, or product claims before the corresponding evidence exists.

This matrix covers both **HS-as-product** and **HS-as-factory**. A higher state does not erase lower-state evidence requirements.

## Readiness states

### R0 — SOFTWARE_BASELINE

Required:

- exact-head software/harness campaign green;
- frozen experiment and claim boundaries identified.

Allowed:

- describe implemented architecture and deterministic behavior actually exercised by the campaign;
- prepare internal product/research/commercial materials.

Forbidden:

- live unseen competence;
- physical correctness;
- independent usability;
- platform economics;
- external usefulness or willingness-to-pay.

Current frozen HS is at least here.

### R1 — LIVE_UNSEEN_SEALED

Required:

- genuine provider-backed frozen unseen run completed without answer-bearing pre-tuning;
- raw response/result preserved;
- PASS or FAIL analyzed symmetrically;
- candidate/result revision and hashes frozen.

Allowed:

- report what the model did on that frozen unseen case;
- report containment/authority behavior actually observed.

Forbidden:

- general model competence from one case;
- physical correctness without physical evidence;
- tuning history that rewrites the sealed first result.

### R2 — PHYSICAL_CASE_CLOSED

Required:

- candidate physical protocol executed;
- physical evidence bound to revision/artifact hashes;
- failures/repairs retained in lineage;
- explicit authorization revalidation performed.

Allowed:

- bounded claims about that physical case and operating envelope.

Forbidden:

- generalized production reliability;
- independent usability;
- economic advantage from a single physical success.

### R3 — INDEPENDENT_OPERATOR_CLOSED

Required:

- eligible outsider executes frozen runbook;
- interventions and forbidden information exposure logged;
- usability/safety outcomes preserved.

Allowed:

- bounded independent-operator claims for the executed task.

Forbidden:

- broad market/product usability from one outsider;
- customer demand or willingness-to-pay.

### R4 — REUSABLE_CAPABILITY_PROVEN

Required:

- physically validated baseline capability frozen;
- at least the preregistered number of derivative cases executed;
- reuse prediction frozen before result leakage;
- outer adjudication complete;
- preregistered reuse/invalidation/authority metrics reported unchanged.

Allowed:

- measured capability-reuse claims within the tested derivative family.

Forbidden:

- universal hardware reuse claims;
- cost advantage unless comparator economics are complete.

### R5 — DEVELOPMENT_ECONOMICS_PROVEN

Required:

- controlled reuse and blank-slate paths satisfy frozen comparator protocol;
- human time/direct cash/retest measured;
- labor-rate sensitivity reported;
- authority violations recorded;
- development-economics result sealed.

Allowed:

- bounded claims about marginal **development** effort/cost in the tested derivative family.

Forbidden:

- production COGS, gross margin, demand, or profitability claims without separate evidence.

### R6 — INTERNAL_CONVERSION_READY

Required for HS-as-product:

- R1–R3 closed;
- packaging/deployment boundary reproducible internally;
- known support/operation requirements documented.

Required for HS-as-factory:

- derivative has physical closure;
- product economics separated from development economics;
- internal acceptance/packaging test repeatable;
- no unresolved authority/safety blocker.

Allowed:

- internally treat the asset as ready for bounded conversion planning.

Forbidden:

- external usefulness, demand, and commercial repeatability until externally observed.

### R7 — EXTERNAL_PILOT_READY

Required:

- R6 closed;
- bounded external task, risk boundary, evidence policy, and stop conditions prepared;
- only claims justified by prior evidence are used.

Allowed:

- seek bounded external validation when external conversion is authorized.

Forbidden:

- describing readiness-to-pilot as a successful pilot.

### R8 — EXTERNAL_VALUE_OBSERVED

Required:

- real external operator/customer executes a bounded case;
- outcome, interventions, costs, and feedback preserved;
- any payment/willingness-to-pay evidence recorded separately from technical success.

Allowed:

- report the specific external value evidence observed.

Forbidden:

- repeat-market demand from one case;
- production-scale claims.

### R9 — REPEAT_COMMERCIAL_EVIDENCE

Required:

- repeated external use or purchases under comparable value propositions;
- support, delivery, COGS, pricing, and failure burden measured sufficiently for the claimed commercial model.

Allowed:

- stronger product/company claims bounded by observed population and operating conditions.

Forbidden:

- industrial/production readiness beyond the evidence actually accumulated.

## Mode-specific interpretation

| Evidence event | HS-as-product | HS-as-factory |
|---|---|---|
| software campaign green | product architecture internally coherent | factory machinery internally coherent |
| sealed unseen model run | model/containment evidence | candidate-generation evidence |
| physical case | bounded physical workflow evidence | first validated capability seed |
| independent operator | usability/safety evidence | evidence factory can be operated beyond builder |
| derivative reuse | platform repeatability evidence | capability compounding evidence |
| comparator economics | possible buyer ROI evidence | internal engineering arbitrage evidence |
| product COGS/price | SaaS/appliance/deployment economics as applicable | derivative unit economics |
| external pilot | external workflow value | external derivative value |
| repeat purchase/use | commercial product evidence | repeatable product/factory arbitrage evidence |

## Claim-state rule

A claim is allowed only when its required state is closed **and** the underlying evidence is valid for the specific revision, artifact, operator, operating envelope, and product family being discussed.

A later failure does not erase history. It changes the current evidence state and must remain visible.

## Current authoritative boundary

Frozen campaign head: `8d687da6e29e110bdc969d9632385f3f31239e5c`.

Current authoritative wording remains:

> **NO DEMONSTRATED SOFTWARE BLOCKER REMAINS ON THE FROZEN HEAD / LIVE-UNSEEN EVIDENCE BLOCKED BY PROVIDER CREDENTIAL**

Therefore HS must not be represented here as having crossed R1 until a genuine unchanged provider-backed run is actually sealed.