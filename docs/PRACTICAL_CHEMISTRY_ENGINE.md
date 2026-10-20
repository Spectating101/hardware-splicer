# HS Practical Chemistry and Materials Decision Engine

Status: source-indexed, locally tested decision-support prototype.
Branch: agent/chemical-engineering-v0 / draft PR #169.

## Objective

Handle deep *practical* chemistry for product repair, fabrication, bonding,
cleaning and protection. Scientific solvers stay optional, not the main UI.

Core capabilities:
- Materials identity, grade, adjacent materials and coating-aware decisions.
- Cleaning: PCB flux, electrical contact cleaners, corrosion triage.
- Bonding: low-surface-energy PP/PE adhesive families, ABS/PC exploratory
  bonding, reworkability, joint loading and environmental conditions.
- PCB protection: acrylic vs silicone-modified conformal coats, mask keep-outs.
- Polymer finish: ASA surface sensitivity to solvents, specialist review.
- Economic repair-versus-replacement calculations with explicit failure paths.
- Evidence-scoped manufacturer claims, missing evidence and hard stop conditions.

## Canonical HS interfaces

GET /v1/engineering/chemical/practical/catalog
POST /v1/engineering/chemical/practical/assess

These appear in HS product OpenAPI and its canonical backend MCP task manifest:
practical_chemistry_repair. They do not create independent project storage.

The structured assessment includes input state, approach IDs, manufacturer
source URLs and claim scopes, hard blockers, research conditions, failure modes,
test criteria and a seven-stage independent validation workflow.

## Source-indexed methods

The v1 catalog contains 11 public manufacturer/repair guidance references
and 10 scoped methods:

| Task | Candidate | Crucial caveat |
|---|---|---|
| PCB flux cleaning | MG 4140 | Most-plastics compatibility does not prove all seals, labels or coatings |
| Contact cleaning | MG 801B | PPE contact-protection film remains after application |
| Zero-residue contact cleaning | MG 409B | Need nearby-material compatibility validation |
| PP/PE bonding | 3M DP8010 | Some PP/PE grades, not every formulation or load configuration |
| ABS/PC bonding assessment | 3M DP100 | General plastics claim only; grade-specific data missing |
| PCB conformal coating | MG 419D | Mask connectors, contacts, test points, switches and sensors |
| Flexible PCB protective coating | MG 422B | Test environment, cleaning, adhesion and rework |
| ASA finish | Prusa acetone sensitivity | Aggressive solvent, specialist safety review, dimensional risk |
| Moisture/corrosion triage | iFixit damage guidance | Battery isolation and hidden corrosion risk |
| Alternative | Replacement/physical repair | Part fit and total economics unverified |

Evidence is manually indexed, NOT re-fetched or independently experimentally
validated on every job. Source-page updates require review.

## Strict decisions

Top-level outputs are:
- stop_and_escalate — powered/unknown power, damaged battery, installed
  battery on cleaning jobs, safety-critical duty, unidentified primary material.
- research_or_replace — only evidence-deficient or unsuitable methods available.
- options_for_validation — one or more methods deserve representative testing.

Each approach is:
- candidate_for_validation: possible subject to source, coupon and full
  verification; never permission for physical application.
- research_required: important missing information (grade, service temperature,
  neighboring material, coating mask, solvent controls, adhesive product fit).
- blocked: unsupported substrate, incompatible rework requirement, unsafe
  conditions or prohibited residue.

Zero-residue contact requirements reject 801B but may allow investigation of
409B. The advisor blocks aggressive ASA solvent finishing near dissimilar
materials and never automatically authorizes a solvent trial.

Input electrical state and battery state default to UNKNOWN, not implicitly
safe. Product claims do not override any hard safety blockers.

## Illustrative request

POST /v1/engineering/chemical/practical/assess

    {
      "task": "bond_joint",
      "primary_material": "PP",
      "material_identity": "verified",
      "electrical_state": "off",
      "battery_status": "none",
      "duty": "normal",
      "exposure": ["moisture", "vibration"],
      "rework_required": false
    }

Output: 3M DP8010 candidate_for_validation, generic DP100 blocked for
unestablished PP compatibility, replacement research_required. It lists
actual source pointers, substrate/cure/joint validation criteria, and no
automatically selected best product. No physical release is authorized.

## Economic threshold with failure-path transparency

All money inputs must come from a user-supplied per-method quote.

    attempt_cost =
        consumables_cost + testing_cost + equipment_allocation
        + labor_minutes * hourly_labor_cost / 60

    expected_total_cost =
        attempt_cost + (1 - assumed_success_probability)
        * (replacement_cost + failed_attempt_disposal_cost)

The strict cost-saving break-even condition is:

    assumed_success_probability >
        (attempt_cost + failed_attempt_disposal_cost)
        / (replacement_cost + failed_attempt_disposal_cost)

Example, HYPOTHETICAL user quotes, NOT live Taiwan pricing:
attempt TWD 500; replacement TWD 700; failure disposal TWD 40.
Break-even probability > 0.72973. At assumed p=0.80 expected cost is
TWD 648; at p=0.50 it is TWD 870.

Unknown probabilities remain unknown; they are never silently estimated from
manufacturer marketing. When insufficient quote fields exist, the calculation
fails closed. A favorable cost calculation NEVER overrides compatibility
or electrical/battery safety.

## Practical validation sequence

1. Identify actual material/grade, contamination/failure, and hazards.
2. Match product-specific evidence rather than broad chemistry classes.
3. Verify current TDS/SDS, adjacent parts, local rules and relevant conditions.
4. Select a representative, controlled coupon trial with qualified supervision.
5. Check task-specific evidence: residue/contact resistance, joint fatigue,
   corrosion, dimensions, coating masking/adhesion/cure, thermal performance.
6. Compare quoted full failure-path costs to part replacement.
7. Keep product release and physical work subject to independent review.

No automatic material identification, solvent procedure, chemical application,
manufacturing, bench actuation, safety certification or repair release.

## Current evaluation

Run the authored case benchmark:
PYTHONPATH=src python eval/practical_chemistry/decision_benchmark_v1.py

31/31 synthetic decision scenarios passed in the local development run. These
are tests of screening logic, not laboratory proof or a blind repair dataset.
The separate unit/integration suite also tests canonical API/MCP invocation,
cost arithmetic, nonfinite inputs and fail-closed hazardous cases.

Next practical work should focus on independent real-product evidence: actual
repair records with measured failures, manufacturer datasheet variations,
corrosion imaging and classification, representative bonding coupons, PCB
coating masking and real supplier pricing. Deep practical capability needs
good empirical coverage, not just additional named chemical solvers.
