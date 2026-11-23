# Hardware-Splicer Asset Convergence Program

**Status:** active execution doctrine  
**Branch anchor:** `agent/unseen-spi-flash-cleanroom-20260813` head `0004b644b8d6e2632fd8d87a24c6d1fec9953626`

## Objective

Hardware-Splicer is not being optimized as four loosely related stories. The target is one underlying capability that is simultaneously strong as:

1. research infrastructure;
2. an engineering application;
3. a hardware-arbitrage / product-family engine;
4. an external-validation / gauntlet asset;
5. a capability-accumulation system.

The weakest major dimension is treated as the current asset bottleneck.

## Asset-strength doctrine

Do not maximize average polish. Prefer work that raises multiple dimensions from the same evidence-producing action.

A development task should normally improve at least two of:

- **R — Research:** falsifiable contribution, benchmarkability, interpretable failure modes;
- **P — Product:** useful workflow for a technically competent operator;
- **A — Arbitrage:** lower marginal engineering cost for related variants;
- **E — External validation:** evidence legible to judges, partners, users, or reviewers;
- **C — Capability accumulation:** validated knowledge that remains reusable across future projects.

Highest-priority work improves three or more dimensions while preserving claim discipline.

## Current strategic hypothesis

The strongest Hardware-Splicer thesis is not generic AI hardware generation.

> **Validated hardware capabilities can be adapted into adjacent products with materially lower marginal engineering effort when identity, provenance, interface contracts, evidence invalidation, deterministic verification, and physical authority are explicitly managed.**

The research and commercial hypotheses are therefore intentionally coupled:

- research asks whether useful agent reasoning can remain bounded under incomplete, stale, conflicting, or misleading evidence;
- product asks whether an engineer can operate that workflow effectively;
- arbitrage asks whether validated capabilities can be reused across product variants at materially lower marginal cost;
- external validation asks whether independent judges/users accept the resulting evidence and utility;
- capability accumulation asks whether every validated project makes the next related project cheaper and safer to engineer.

## Core experimental programme

### Tranche 1 — Live unseen operator

Use the existing SPI-flash cleanroom corpus without changing it after model behavior is observed.

Required persisted evidence:

- exact code SHA;
- provider/model/configuration;
- exact case corpus identity;
- model inputs/outputs;
- tool calls;
- evaluator result;
- authority-contract result;
- failures and unresolved states.

A green workflow wrapper does not count if the live model step is skipped.

### Tranche 2 — Revision-bound physical proof

Freeze the candidate produced after the unseen run and evaluate real hardware without introducing a hidden golden solution into the agent task.

Required persisted evidence:

- exact candidate revision and artifact hashes;
- exact physical component/package identity;
- assembly/substitution record;
- powered-off checks;
- controlled power-up limits derived from defensible candidate evidence;
- measurements and functional/signal observations;
- failure/repair/revision history;
- `PhysicalEvidenceRecord` and hash-bound envelope;
- human authorization decision and ledger state.

### Tranche 3 — Independent operator

A technically competent outsider performs a bounded real task using product-visible materials only.

Measure:

- completion outcome;
- elapsed time;
- intervention count and type;
- blocked/unsafe attempted actions;
- unresolved-state handling;
- confusion points;
- evidence interpretation errors;
- package usability;
- whether HS prevented unjustified confidence.

### Tranche 4 — Platform-to-derivative experiment

Use one reusable technical core to create at least three market-facing variants.

Recommended first family:

1. Vision Core A — TinyML / embedded-vision training station;
2. Vision Core B — package/presence QC checker;
3. Vision Core C — parts counter / simple inventory checker.

The objective is not three demos. The objective is to quantify inheritance.

For each derivative record:

- inherited vs new BOM lines;
- inherited vs changed firmware modules;
- inherited vs new mechanical interfaces;
- inherited vs invalidated evidence contracts;
- inherited vs new tests;
- inherited vs new dataset/model pipeline work;
- engineering hours by task class;
- failures introduced by the variant;
- physical retest scope;
- final validated state.

## Reuse metrics

The following are experimental metrics, not claims of industry-standard thresholds.

### Engineering reuse ratio

`shared validated engineering artifacts / total required validated engineering artifacts`

### Evidence reuse ratio

`valid inherited evidence items / total evidence items required for the derivative`

### Marginal engineering ratio

`measured derivative engineering effort / measured independent-build baseline or defensible estimated baseline`

When an independent-build baseline cannot be measured, the estimate must be explicitly marked as estimated and broken down by task class.

### Invalidation precision

`correctly invalidated inherited evidence / all inherited evidence that should have been invalidated`

### Unnecessary invalidation rate

`valid inherited evidence unnecessarily discarded / all valid inherited evidence`

### Physical retest compression

`tests safely reused or waived with evidence / total physical tests required under a blank-slate process`

## Initial success/failure hypotheses

These thresholds are deliberately provisional and must not be retrofitted after results are known.

For at least two derivatives after the baseline platform:

- target engineering reuse ratio: **>= 0.70**;
- target evidence reuse ratio: **>= 0.65**;
- target marginal engineering ratio: **<= 0.40**;
- target invalidation precision: **>= 0.95**;
- authority violations: **0 tolerated**.

Failure to meet these thresholds is a research/commercial result, not a reason to hide or rewrite the run.

## Component-substitution experiment

A second arbitrage-critical experiment should test controlled substitution.

Given a validated platform and a substituted component, HS must determine:

1. what identity facts changed;
2. which interface/electrical assumptions remain supported;
3. which evidence is invalidated;
4. which deterministic checks must rerun;
5. which physical tests must rerun;
6. which artifacts can remain unchanged;
7. whether fabrication/power authority remains closed.

Candidate substitution classes:

- camera module revision;
- regulator or power module;
- level translator;
- MCU board variant;
- motor/actuator driver;
- display module.

This experiment simultaneously tests provenance reasoning, revision invalidation, supply-chain/BOM flexibility, derivative economics, and gauntlet-legible safety discipline.

## Evidence-core rule

Every run should emit one canonical evidence manifest. Papers, competitions, pilots, and commercial analysis may select different views of that manifest but may not alter proof status or underlying facts.

Preferred canonical fields:

- project/core identity;
- parent platform revision;
- derivative revision;
- inherited artifacts;
- changed artifacts;
- evidence retained;
- evidence invalidated;
- deterministic checks;
- physical evidence;
- human authorization;
- effort accounting;
- failures/repairs;
- external-user/judge result if applicable.

## Work-selection gate

Before undertaking significant HS work, ask:

1. Does this produce new evidence rather than merely presentation?
2. Does it improve at least two asset dimensions?
3. Does it make the platform more reusable or more externally falsifiable?
4. Is there a cheaper way to obtain the same evidence?
5. Does it preserve identity/evidence/authority discipline?

If the answer is mostly no, deprioritize it.

## Immediate execution order

1. execute the real live unseen SPI run;
2. restore and execute physical-proof protocol;
3. run one independent operator;
4. instantiate Vision Core A;
5. derive Vision B and C while logging reuse metrics;
6. run at least one controlled component substitution;
7. update research paper and gauntlet overlays only from the resulting evidence.

## End-state criterion

HS should be considered a strong strategic asset only when the same underlying engineering capability has demonstrated:

- rigorous live/physical research evidence;
- useful outsider-operable application behavior;
- measured derivative engineering compression;
- reusable validated capability accumulation;
- credible external judgment or real-user adoption.

The programme therefore ends neither at a paper nor at a demo. It ends when the system's technical, economic, and external claims are supported by the same evidence-producing workflow.
