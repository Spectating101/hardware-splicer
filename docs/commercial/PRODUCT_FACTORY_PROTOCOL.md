# Hardware-Splicer product-factory protocol

Purpose: convert a physically validated HS capability into an adjacent product experiment without laundering uncertainty, contaminating comparators, or spending ahead of evidence.

This prepares internal conversion only. It does not change the frozen unseen SPI experiment or authorize external claims/sales.

## Authority references

Use the derivative-campaign anchor `8d687da6e29e110bdc969d9632385f3f31239e5c` only to reconstruct this campaign's original implementation context. The architecture freeze (`0a55515cc683abccce6308c918f679199d5ebf87`), software-proof checkpoint (`0164d47e25bfea8179073e46e869a8725ca03b83`), and current canonical software baseline (`3748078847382fa3c838e809d4900b71448994a8`, PR #72 merged 2026-08-28 Asia/Taipei) remain distinct. None upgrades a frozen experiment or physical-evidence claim on its own.

## 0. Candidate

Record the product idea, operator/job, why it appears adjacent to validated capability, and the cheapest experiment that could disprove it.

## 1. Eligibility and adjacency

Apply `DERIVATIVE_OPPORTUNITY_SCORECARD.md`. Allowed outputs are `KILL`, `HOLD`, or `QUALIFY_FOR_INTERNAL_EXPERIMENT`. Qualification does not authorize fabrication.

## 2. Freeze baseline

Bind baseline project/revision, capability-manifest hash, relevant artifact hashes, evidence inventory, physical authority state, and known unresolved items. Only physically validated capability may seed a physical reuse claim.

## 3. Freeze derivative requirements

Before observing the derivative result, freeze user/problem statement, engineering requirements, acceptance criteria, operating envelope, artifact-accounting policy, constraints/nonrequirements, spend cap, and stop condition. A later requirement change creates a new experiment revision.

## 4. Freeze reuse prediction and comparator

Before result leakage:

1. freeze the baseline-to-candidate diff where available;
2. freeze predicted retained/invalidated/blocked evidence;
3. hash the prediction;
4. freeze blank-slate comparator instructions if economics will be claimed.

The blank-slate path receives the same requirements, public evidence access, allowed tools, exit criteria, and physical acceptance test, but not HS private capability, reuse prediction, private discoveries, or derivative-result leakage. Do not prescribe a golden implementation merely to make paths comparable.

## 5. Engineering execution

Capture separately: human active time, elapsed time, model/tool cash, external services, prototype consumables, interventions/causes, deterministic checks, unresolved states, and revisions.

If a concrete defect appears, preserve the failing state before repair. Repair creates a new visible revision.

## 6. Physical closure

Physical correctness is decided only through frozen physical acceptance criteria. Bind physical evidence to revision/artifact hashes, record simulation status explicitly, and revalidate before human authorization. Passing software checks do not upgrade physical authority.

## 7. Outer adjudication and reuse metrics

Compare frozen prediction with observed impact and record engineering/artifact reuse, evidence reuse, invalidation precision/recall, marginal engineering effort, physical-retest compression, and authority violations. Use existing preregistered HS targets; never rewrite them after seeing the result.

## 8. Development economics

Execute the frozen blank-slate path when required without reuse-result leakage. Preserve human hours and direct development cash separately and evaluate labor-rate sensitivity.

Development economics are not production unit economics.

## 9. Product economics and packaging

Only after physical closure assess prototype BOM, prospective production BOM/COGS, assembly/test burden, packaging/fulfillment, warranty/support, selling-price hypothesis, willingness-to-pay evidence, distribution evidence, and regulatory/certification burden.

Label estimates `ESTIMATED`; label observed values `MEASURED` and bind evidence. Do not create speculative inventory to validate demand.

## 10. Conversion decision

Allowed decisions:

- `KILL` — stop conversion work;
- `HOLD` — preserve asset until a named uncertainty becomes cheap to resolve;
- `INTERNAL_DERIVATIVE_READY` — physical product and internal evidence coherent; market value unvalidated;
- `PILOT_CANDIDATE` — enough evidence for bounded external validation once authorized;
- `PRODUCT_CANDIDATE` — repeated evidence may justify commercial packaging; not production readiness.

Every transition states which evidence changed and which claims remain forbidden.

## Contamination firewall

For frozen research/comparator runs:

- never feed expected answers back into prompts/corpus;
- never preselect answer-bearing components unless protocol permits it;
- never tune evaluator thresholds after results;
- never leak reuse-path private discoveries into blank-slate execution;
- preserve negative results/interventions;
- keep `UNKNOWN`, `BLOCKED`, and `FAIL` distinct.

## Factory thesis

HS-as-factory succeeds only if repeated derivative evidence eventually supports:

> Validated capability can reduce marginal engineering effort/cost for adjacent physical products while preserving uncertainty, verification, evidence lineage, and physical-authority boundaries.

Until measured derivatives support it, this remains a hypothesis.
