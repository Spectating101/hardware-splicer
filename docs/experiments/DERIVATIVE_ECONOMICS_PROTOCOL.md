# Derivative Economics — Cleanroom Comparator Protocol

**Status:** protocol / no economic result claimed  
**Purpose:** determine whether platform/evidence reuse reduces real development cost rather than merely increasing code/artifact reuse.

## Research and commercial question

> For the same frozen derivative requirements and exit criteria, does the HS reuse path require materially less human intervention and development-variable cost than a cleanroom blank-slate path?

This is the causal comparison behind the arbitrage claim. Artifact reuse alone is not sufficient.

## 1. Freeze the task before either path runs

Persist and hash:

- derivative requirements;
- allowed public/manufacturer source set;
- deterministic toolchain/version policy;
- required product-facing functions;
- deterministic verification obligations;
- physical-test obligations;
- exact exit criteria;
- measurement policy;
- allowed model/tool budget policy.

The same requirements hash and exit-criteria hash must bind both paths.

## 2. Two isolated engineering paths

### A. HS reuse path

May receive:

- the frozen validated-core capability manifest;
- inherited evidence inventory;
- artifact-unit inventory;
- `hs-derive` prediction/retest plan;
- explicitly reusable implementation/artifacts permitted by that plan.

### B. Cleanroom blank-slate path

May receive:

- the same derivative requirements and exit criteria;
- the same allowed public/manufacturer sources;
- the same general engineering tools available to the reuse path.

Must **not** receive:

- the validated-core artifacts;
- inherited core evidence;
- HS's derivative prediction;
- implementation details or debugging discoveries from the reuse path;
- the other path's intermediate/final result.

The blank-slate path is not required to avoid ordinary public libraries or manufacturer examples. The comparison is against building the derivative without the private validated platform/evidence asset, not against intentionally primitive engineering.

## 3. Isolation and ordering

Preferred evidence quality is **parallel cleanroom**:

1. freeze both path inputs;
2. launch both before either result is revealed to the other;
3. keep workspaces and context isolated;
4. log every cross-boundary intervention;
5. outer-evaluate both after the precommitted exit point.

A sequential recreation after the reuse result is known is weaker because the operator/model may inherit answer knowledge. Record it as `sequential_nonblind`; it must not earn the strong cleanroom-comparator claim.

## 4. Same exit criteria

The clock does not stop because one path produces a plausible demo. Both paths stop only when they reach the same frozen exit state, for example:

- product-facing workflow executes;
- required deterministic checks complete;
- required evidence package exists;
- required physical test scope completes or fails definitively;
- failures and repairs are recorded;
- claim/authority state is explicit.

A path that cannot reach the exit criteria is recorded as incomplete rather than assigned an invented completion time.

## 5. Measure effort and cost separately

For each path record:

- wall-clock elapsed hours;
- active human engineering/intervention hours;
- model/API/tool cost;
- external-service cost;
- development-only prototype/consumable spend;
- number and duration of physical retests;
- failed attempts and repair cycles;
- model/tool calls if available;
- final completion state.

Use one precommitted labor-rate assumption to translate human hours into comparable development cost. Keep raw human hours and direct cash cost visible so the result does not depend only on the chosen rate.

Do **not** mix production BOM/COGS with development cost. Production unit economics are a later product-market measurement.

## 6. Primary economics metrics

Let `R` be the HS reuse path and `B` the blank-slate comparator.

- `human_intervention_ratio = R human hours / B human hours`
- `elapsed_time_ratio = R elapsed hours / B elapsed hours`
- `development_cash_cost_ratio = R direct development cash / B direct development cash`
- `development_variable_cost_ratio = R development variable cost / B development variable cost`
- `physical_retest_ratio = R physical retest effort / B physical retest effort`

Direct development cash is:

`model/tool cost + external-service cost + development consumables`

Development variable cost is:

`human hours × frozen labor rate + direct development cash`

The cash-cost ratio is reported as sensitivity evidence; the initial hard economics gate remains human intervention + total development-variable cost.

## 7. Labor-rate sensitivity

A single chosen labor rate must not be able to create a favorable story by itself. Report the human-hours and direct-cash deltas separately and classify the comparison over **all nonnegative labor rates**:

- reuse uses no more human time **and** no more direct cash → `reuse_weakly_dominates_for_all_nonnegative_labor_rates`;
- blank-slate uses no more human time **and** no more direct cash → `baseline_weakly_dominates_for_all_nonnegative_labor_rates`;
- both are equal → equal for all nonnegative labor rates;
- one path saves human time but spends more cash → labor-rate tradeoff.

For a tradeoff, calculate the break-even labor rate where total development-variable costs are equal. Also report whether reuse becomes cheaper **above** or **below** that rate.

This sensitivity result is descriptive rather than a separate initial pass/fail gate. It exists to show whether the primary cost conclusion is robust or assumption-dependent.

## 8. Initial precommitted hypotheses

For the first Vision Core derivative family, before results are observed:

- human intervention ratio <= **0.40**;
- development variable cost ratio <= **0.50**;
- authority violations = **0**.

These are project hypotheses, not industry-standard thresholds. Keep them fixed for the first registered experiment even if the result is unfavorable.

Elapsed-time, direct-cash and physical-retest ratios are reported but not initial hard pass/fail thresholds. Queueing/fabrication can distort wall-clock time, and cash-vs-labor tradeoffs are retained explicitly through the sensitivity analysis.

## 9. Validity requirements for a strong arbitrage claim

A proof-grade comparator requires:

- identical frozen requirements hash;
- identical frozen exit-criteria hash;
- both paths launched without result leakage;
- blank-slate path isolated from private platform/reuse assets;
- interventions logged;
- complete raw cost/effort accounting;
- explicit authority-violation accounting for both paths;
- same currency and positive precommitted labor-rate policy;
- both outcomes preserved, including failure.

If these do not hold, the economics may still be exploratory evidence but not a strong causal arbitrage result.

## 10. Interpretation

Possible outcomes are intentionally symmetric:

- **High reuse + low cost:** strong platform/arbitrage evidence.
- **High reuse + high cost:** platform artifacts exist but do not yet create economic leverage.
- **Low reuse + low cost:** AI/tool compression may matter more than platform accumulation; revise the business thesis.
- **Low reuse + high cost:** kill/redefine the platform-arbitrage claim for that product family.

A failed economic hypothesis remains useful research evidence. It must not be rewritten into a commercial success by changing the comparator after observation.
