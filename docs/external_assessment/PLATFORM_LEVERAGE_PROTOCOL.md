# Platform Leverage Proof Protocol

**Status:** executable experiment protocol  
**Purpose:** test whether Hardware-Splicer converts a validated hardware capability into derivative products with materially lower marginal engineering effort **without weakening evidence or authority rules**.

This protocol turns the commercial-arbitrage thesis into a falsifiable Hardware-Splicer experiment. It is not a market forecast and it does not assume that platform reuse is valuable merely because components are shared.

## Research and asset question

> Can a validated Hardware-Splicer capability core produce distinct hardware products while preserving enough artifacts and evidence to reduce marginal engineering effort, and can the system correctly identify what does **not** survive the change?

A positive result strengthens four claims at once:

1. **research:** evidence-aware reuse and invalidation work across hardware variants;
2. **application:** the product supports a real derivative-engineering workflow;
3. **arbitrage:** validated capabilities lower the cost of entering adjacent niches;
4. **gauntlet:** one physical evidence core can support multiple externally legible demonstrations.

A negative result is also evidence. If derivative variants require almost complete re-engineering, the platform-arbitrage thesis must be narrowed or rejected.

## First family: vision core

Use a deliberately simple, non-safety-critical family so commercial-platform economics are measured before adding difficult mechanics or regulation.

### Core A — TinyML / embedded-vision training station

Baseline capability:

- camera + edge inference;
- known power/interface contract;
- reproducible capture/train/deploy path;
- fixture/enclosure interface;
- physical validation record;
- revision-bound evidence inventory.

### Variant B — package/presence checker

Distinct value proposition: one bounded visual inspection at a workstation.

### Variant C — parts counter / inventory checker

Distinct value proposition: count or presence verification for a bounded tray/bin/work surface.

The variants must not be made artificially similar just to improve reuse metrics. Customer-visible function and validation task must genuinely differ.

## Freeze before derivative work

Before Variant B starts, freeze and persist:

- exact Core A repository/project revision;
- BOM and component identities;
- firmware/model/runtime artifacts;
- mechanical/fixture artifacts;
- interfaces and operating envelope;
- deterministic verification results;
- physical evidence records;
- known failures and repairs;
- all unresolved facts;
- engineering effort already spent on Core A.

Before each derivative starts, freeze its requirements. Do not rewrite requirements after observing which route would maximize reuse.

## Required derivative ledger

Each derivative must record every required artifact as one of:

- `core / unchanged`
- `core / revalidated`
- `core / modified`
- `core / replaced`
- `variant / new`

Each inherited evidence item must be one of:

- `core / survived`
- `core / revalidated`
- `core / invalidated`

New evidence is:

- `variant / new`

Do not call evidence "reused" if its relevant revision, interface, operating envelope or physical claim changed and was not revalidated.

## Engineering-effort counterfactual

Engineering compression is only meaningful relative to a comparator. Use this preference order:

1. `measured_parallel` — a genuine independent build or controlled parallel path;
2. `historical_comparator` — a prior sufficiently similar build with recorded engineering effort;
3. `estimated` — explicit estimate only.

An `estimated` counterfactual is exploratory and cannot by itself support a strong commercial-efficiency claim.

The executable report is produced by:

```bash
python scripts/run_platform_leverage_experiment.py \
  experiments/platform_leverage/<variant>.json \
  --thresholds experiments/platform_leverage/thresholds.v1.json \
  --out artifacts/platform-leverage/<variant>.report.json
```

## Primary measurements

Hardware-Splicer reports the dimensions separately rather than hiding them in a weighted score:

- **marginal engineering ratio**  
  derivative engineering hours / independent-build comparator hours

- **engineering compression ratio**  
  1 - marginal engineering ratio

- **core artifact share**  
  required derivative artifacts originating in the validated core / all derivative artifacts

- **core artifact retention**  
  inherited core artifacts not replaced / inherited core artifacts

- **evidence reuse ratio**  
  inherited evidence that survives or is explicitly revalidated / inherited evidence considered

- **evidence invalidation ratio**  
  inherited evidence correctly invalidated / inherited evidence considered

The invalidation ratio is not automatically "bad": a derivative that genuinely changes many physical claims should invalidate them. The important failure is **silent survival of evidence that should have been invalidated**.

## Pre-registered first-family dominance bar

Use these as the initial commercial/research target for **Variants B and C**. Do not lower them after seeing results.

```json
{
  "max_marginal_engineering_ratio": 0.40,
  "min_core_artifact_share": 0.60,
  "min_core_artifact_retention_ratio": 0.75,
  "min_evidence_reuse_ratio": 0.60
}
```

Interpretation:

- derivative engineering should cost no more than 40% of a credible independent-build comparator;
- at least 60% of required artifacts should derive from the core;
- at least 75% of inherited core artifacts should remain useful rather than be replaced;
- at least 60% of inherited evidence should survive or be defensibly revalidated.

These are **experimental targets**, not established industry thresholds.

A commercially strong result should also have:

- no hidden/manual work omitted from the engineering ledger;
- no authority-boundary violation;
- no false physical claim;
- a genuinely distinct customer task;
- a plausible BOM and deployment path for the target niche.

## Operator test

At least one derivative should be attempted by a technically competent person who did not build Core A.

Record:

- time to understand the core;
- interventions from the maintainer;
- places where inheritance was unclear;
- evidence that the operator incorrectly expected to survive;
- evidence HS correctly invalidated;
- total completion time;
- final physical outcome.

This converts platform leverage from creator-only productivity into application/usability evidence.

## Physical proof

For each derivative:

1. freeze candidate revision;
2. persist component/package identity evidence;
3. run deterministic pre-assembly checks;
4. record assembly and substitutions;
5. perform powered-off checks;
6. use bounded controlled power-up;
7. collect task-specific physical/functional evidence;
8. record failures and repairs as new revisions;
9. persist revision-bound physical evidence;
10. require explicit human authorization for any authority-bearing release.

Software success is not physical success.

## Commercial probe

Only after a derivative is physically defensible, perform a bounded market probe:

- one target user class;
- one concrete workflow;
- one target price range based on actual BOM/support burden;
- direct comparison to manual workflow or incumbent alternative;
- record responses, objections and willingness to pilot/pay.

Do not infer demand from technical elegance.

## Falsification conditions

Narrow or kill the platform-arbitrage claim if:

- both B and C exceed the marginal-engineering bar with credible comparators;
- commonality requires distorting the variants into effectively the same product;
- inherited evidence repeatedly survives when it should be invalidated;
- physical validation workload grows almost linearly with each variant;
- support/regulatory burden dominates the apparent engineering savings;
- external users cannot operate the derivative workflow without maintainer intervention.

## Why this is a research contribution

Product-family engineering literature has long studied commonality, modularity and cost trade-offs. Hardware-Splicer adds a different object to that tradition: **revision-bound engineering evidence and AI authority**. The experiment asks not only what components are common, but what engineering claims, measurements and authorizations remain valid when a platform becomes a derivative product.

Useful background:

- Alizon, Shooter & Simpson, *Improving an existing product family based on commonality/diversity, modularity, and cost*, Design Studies 28(4), 2007. DOI: 10.1016/j.destud.2007.01.002
- AlGeddawy & ElMaraghy, *Reactive design methodology for product family platforms, modularity and parts integration*, CIRP Journal of Manufacturing Science and Technology 6(1), 2013. DOI: 10.1016/j.cirpj.2012.08.001
- Jiang et al., *Exploration and implementation of commonality valuation method in commercial aircraft family design*, Chinese Journal of Aeronautics 32(8), 2019. DOI: 10.1016/j.cja.2019.05.005

## Claim boundary

Passing this protocol would support:

> Hardware-Splicer demonstrated evidence-aware product-family reuse on the tested family, with measured derivative engineering compression under the stated comparator.

It would **not** establish that every hardware category has the same economics, that market demand exists, or that the derivatives are production-certified.
