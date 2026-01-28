# Circuit-AI: Hardware Inspiration → Commerce/Profitability Lens

This repo can generate/design/diagnose a lot of “cool” electronics work, but **cool ≠ profitable**.
This document defines a repeatable way to evaluate Hackster/Hackaday-style inspirations *as products*,
using Circuit-AI’s existing commerce hooks (payments + API keys + quotas) where relevant.

## The 3 Monetizable “Shapes” (ranked by passivity)

1) **Digital deliverable (best for “publish once”)**
- What you sell: `PDF guide + wiring + BOM + firmware + KiCad files + validation report`.
- Margins: high (near-zero COGS), but support/chargebacks can still kill you.
- Circuit-AI leverage: very high (it already generates/validates/docs).

2) **Service deliverable (best for Upwork cash)**
- What you sell: “design review / debug / schematic + PCB iteration / BOM optimization / test plan”.
- Margins: high, but not passive; you’re trading time for money.
- Circuit-AI leverage: high (preflight + iterative revision loop + artifacts).

3) **Physical kit / assembled unit (hardest to make passive)**
- What you sell: shipped hardware.
- Margins: often worse than expected (COGS, shipping, returns, QA time).
- Circuit-AI leverage: medium (BOM + instructions help, but ops dominates).

If you want near-zero marketing and near-zero ongoing ops: **bias toward (1)**.

## “Profitability Scorecard” (how we rank inspirations)

Each idea gets a 0–100 score using conservative heuristics. Anything not evidenced is marked “low confidence”.

**A) Gross margin potential (0–25)**
- Digital: starts high; subtract support/chargeback risk.
- Kit: `price - platform fee - COGS - assembly labor - packaging - support`.

**B) Support burden (0–20)**
- Fewer “it doesn’t work” tickets = higher score.
- Anything involving Wi‑Fi provisioning, phone compatibility, RF tuning, or mains power is a support magnet.

**C) Regulatory / platform risk (0–15)**
- RF, Li‑ion charging, mains power, medical claims, safety-critical: huge penalty.

**D) Differentiation (0–15)**
- “Another weather station” is low unless there’s a unique wedge (calibration, reliability, install time, etc).

**E) Build complexity / failure rate (0–15)**
- More calibration steps, tighter tolerances, or mechanical alignment → more returns and support.

**F) Circuit‑AI leverage (0–10)**
- If Circuit‑AI can output the sellable artifact (files + report) with high reliability, it scores higher.

## Pricing patterns that fit Circuit‑AI (no brand/domain required)

**Digital products**
- $9–$29: single “recipe” (BOM + wiring + firmware + test checklist)
- $39–$99: “pro pack” (KiCad files + validation report + variants + troubleshooting)
- $199+: “bundle” (multiple projects + reusable libraries + templates)

**Upwork services**
- Fixed-price mini: $50–$150 (review + issues list + “next steps”)
- Medium: $200–$600 (schematic iteration + BOM + validation + handoff notes)
- Large: $1k+ (full design, requirements, PCB, test plan) — this is where mistakes are expensive.

## How commerce maps to this repo (today)

- Payments/commerce entrypoints (checkout/verify/access/analytics): `api_server.py` (`/api/payment/*`)
- Multi-gateway strategy (PayPal/Wise/Crypto/ECPay/manual + Lemonsqueezy/Paddle stubs): `src/intelligence/global_payment_service.py`
- API-key + quota monetization (developer/agent usage): `.env.example` + `/api/v2/admin/keys/*`

## Tooling: auto-score inspirations

Use `scripts/idea_economics.py` to pull RSS ideas and generate a ranked list with a rough profit model.

- Best practice: treat script output as a *triage list*, then do a human pass on the top 10.
- If you know BOM/assembly/support estimates, provide overrides via `--overrides`.

Example:
- `python3 scripts/idea_economics.py --days 14 --limit 40 --out /tmp/idea_scores.md`
- `python3 scripts/idea_economics.py --days 30 --format json --out /tmp/idea_scores.json`
- `python3 scripts/idea_economics.py --days 30 --overrides data/idea_economics/overrides.example.json --out /tmp/idea_scores.md`
