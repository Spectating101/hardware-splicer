# Derivative opportunity scorecard

Purpose: decide whether an adjacent product deserves an internal experiment before HS spends fabrication, inventory, or market effort.

This is not a weighted market score. It is a fail-closed gate plus an ordinal hypothesis record and must not be tuned to rescue a favored candidate.

## Gate 0 — eligibility

A candidate is `INELIGIBLE` if it:

- requires unresolved core identity to be treated as known;
- requires authority the baseline capability does not possess;
- lacks a repeatable acceptance test;
- has safety/regulatory burden incompatible with a bounded internal prototype;
- requires material speculative inventory before core uncertainty can be resolved;
- depends on hidden/golden answers contaminating the comparator;
- is too weakly adjacent to validated capability for reuse to be measurable; or
- cannot support a meaningful blank-slate comparison when economics is part of the claim.

Ineligible means kill or hold. That is useful evidence because it prevents low-information spend.

## Gate 1 — evidence prerequisites

Record each as `CLOSED`, `OPEN`, or `NOT_APPLICABLE`:

- baseline physical identity closed;
- baseline manifest/revision/hash frozen;
- baseline evidence inventory available;
- derivative requirements can be frozen before build;
- acceptance criteria can be frozen before build;
- changed dependencies can be stated without a golden answer;
- bounded physical test method exists;
- authority boundary is explicit;
- reuse prediction can be frozen before result leakage.

Any required `OPEN` item means `HOLD`.

## Gate 2 — hypotheses

Use `HIGH`, `MEDIUM`, `LOW`, or `UNKNOWN`. Do not sum these into a magic score.

- **Capability adjacency** — genuinely reusable engineering obligation.
- **Evidence reuse potential** — evidence likely to remain valid under bounded change.
- **Validation tractability** — reproducible correctness testing with bounded equipment/judgment.
- **Physical complexity** — new power, signal, mechanical, optical, thermal, RF, or firmware uncertainty.
- **Safety / authority risk** — consequence of an incorrect candidate escaping the bounded workflow.
- **Supply / BOM dependence** — scarcity, volatility, counterfeit/identity risk.
- **Time to first physical evidence** — ability to test the key hypothesis cheaply.
- **Development-cost measurability** — attributable hours, tool cost, services, consumables, retest.
- **Customer-value hypothesis** — concrete operator/job burden plausibly removed.
- **Distribution-access hypothesis** — plausible low-fixed-cost route to users.
- **Differentiation / evidence moat** — advantage created by validated capability/evidence reuse.
- **Regulatory / legal complexity** — certification, liability, privacy, export, medical, automotive, or related burdens.

Customer value and distribution remain hypotheses until observed externally.

## Gate 3 — decision

Allowed decisions:

- `KILL` — do not spend further.
- `HOLD` — unresolved prerequisite or unknown dominates.
- `QUALIFY_FOR_INTERNAL_EXPERIMENT` — eligible for the product-factory protocol; not commercially validated.

Qualification does not authorize fabrication. First freeze requirements, evidence, acceptance criteria, comparator rules, and spend cap.

## Anti-bias rules

- Do not treat market enthusiasm as engineering evidence.
- Do not treat engineering reuse as willingness-to-pay.
- Do not treat prototype BOM as production COGS.
- Do not treat estimated labor savings as measured economics.
- Do not buy inventory merely to create commitment.
- Prefer the cheapest experiment that can change the decision.

## Candidate record

```yaml
candidate_id: null
baseline_capability_manifest_sha256: null
decision: HOLD
gate_0_eligible: null
gate_0_reasons: []
evidence_prerequisites: {}
hypotheses:
  capability_adjacency: UNKNOWN
  evidence_reuse_potential: UNKNOWN
  validation_tractability: UNKNOWN
  physical_complexity: UNKNOWN
  safety_authority_risk: UNKNOWN
  supply_bom_dependence: UNKNOWN
  time_to_first_physical_evidence: UNKNOWN
  development_cost_measurability: UNKNOWN
  customer_value: UNKNOWN
  distribution_access: UNKNOWN
  differentiation_evidence_moat: UNKNOWN
  regulatory_legal_complexity: UNKNOWN
cheapest_information_gain_experiment: null
spend_cap: null
kill_condition: null
notes: []
```
