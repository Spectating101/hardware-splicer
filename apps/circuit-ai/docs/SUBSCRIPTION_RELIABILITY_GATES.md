# Subscription Reliability Gates

Use these gates before pushing Circuit-AI as a recurring subscription offer.

## Gate A: Infrastructure Proof (must pass)

Pass condition:
- Key issuance, plan quotas, fulfillment logging, revoke, and webhook guard path are verified.

Current proof script:
- `python3 /home/phyrexian/Downloads/llm_automation/project_portfolio/Molina-Optiplex/scripts/ops/circuit_subscription_proof.py`

Required result:
- verdict `subscription_primitives_proven`

## Gate B: Product Narrative Clarity (must pass)

Pass condition:
- One primary niche is stated clearly (KiCad revision + handoff operators).
- Messaging avoids broad/generic "for everyone" claims.
- Scope boundaries are explicit (what Circuit-AI does and does not do).

Evidence files:
- `mcp_server/README.md`
- `docs/NICHE_SUBSCRIPTION_POSITIONING.md`

## Gate C: Repeat-Usage Value (must pass)

Pass condition over a rolling 30 days:
- At least 3 paying users
- At least 2 users with repeat weekly usage
- At least 1 renewal (or second billing cycle) without manual discount rescue

Why:
- Subscription should be validated by recurring behavior, not first purchase only.

Tracking command:
- `python3 scripts/subscription_kpi_report.py --usage-db /path/to/circuit-ai-usage.sqlite`

## Gate D: Delivery Reliability (must pass)

Pass condition:
- No unresolved critical failure in intake -> validation -> package flow
- Clear operator fallback path for missing constraints (CLARIFY -> revised intake -> rebuild)
- Customer-facing workflow docs are usable without handholding

Evidence:
- API endpoint behavior in `api_server.py`
- Operator runbooks in `Molina-Optiplex` status docs

## Gate E: Offer Discipline (must pass)

Pass condition:
- One-off jobs sold as milestones/service or prepaid credits
- Subscription offered only for recurring revision workflows
- Specialized high-risk scopes (RF/high-speed/compliance-critical) are scoped with explicit constraints

## Go/No-Go Rule

Go subscription-first only when:
- A + B + C + D + E all pass.

If C fails (repeat behavior not proven):
- Stay service/credits-first and continue validating repeat usage.
