# HS Commercial Value Convergence — v0

Status: **code implemented on review branch; no acquisition, merge, fabrication, sale, or profitability proof**.

This is a routing/evidence layer *over* HS's existing engineering and salvage intelligence, not a new competing market-prediction engine. It connects economic hypotheses to actionable verification work and measured outcomes.

## Reality check: what already existed

| Source | Existing capability | Current location and integration boundary |
| --- | --- | --- |
| Circuit-AI | Salvage opportunity scoring, component recovery, e-commerce listing screening, workflow reports | `apps/circuit-ai/src/intelligence/salvage_opportunity_engine.py`; `apps/circuit-ai/docs/SALVAGE_TO_PRODUCT_WORKFLOW.md` on main |
| Derivative economics | Frozen engineering-reuse vs blank-slate **development-cost** comparison | `src/hardware_splicer/derivative_economics.py` on main; **do not reinterpret as production profit** |
| Commercial readiness and factory protocol | Authority gates, external proof distinctions, product COGS and demand evidence ledger | `docs/commercial/PRODUCT_FACTORY_PROTOCOL.md`, `CONVERSION_READINESS_MATRIX.md` and `COMMERCIAL_EVIDENCE_LEDGER.template.json` on main |
| Product Factory PF-001 | ProofPod engineering and commercial hypothesis | PR #109, open, head `experiment/proofpod-commercial-arbitrage-v0` |
| Product Factory PF-002 | Taiwan Flytech POS462 / BenchHMI donor-remanufacturing hypothesis | PR #110, open, **base PR #109 branch** |
| Product Factory PF-003 | Taiwan Advantech AIM8I / FieldDeck donor-remanufacturing hypothesis | PR #111, open, **base PR #109 branch** |
| Taiwan purchase economics | Fail-closed per-unit expected return / maximum bid / salvage yield sensitivities | PR #147, open, based on `agent/salvage-investigation-queue-v0` |
| Taiwan donor listings | 17 individual Ruten listing source URLs across 10 families, separate from measured transaction prices | PR #148, open, based on `agent/salvage-investigation-queue-v0` |

**Integration caution:** The source PRs have distinct bases and physical-proof boundaries. Do not merge #110 or #111 directly onto main while #109 is unresolved. Do not copy #147's purchase-specific model into a separate fork of business arithmetic; keep it the detailed purchase evaluator and use the present layer as an option-routing envelope.

## What this branch actually implements

- `commercial_value_routing.evaluate_commercial_case`: compare **resell / refurbish / parts recovery / build / operate / replicate / recycle** for the same candidate and native currency, with explicit costs and evidence classes.
- Expected resale contribution uses success probability and failure recovery value, not the full asking price. It computes sensitivity to sale-price changes and a break-even/target-contribution acquisition ceiling. These are **screens**, not purchase approval.
- Operating assets have a separate discounted monthly net-cashflow calculation. It is labeled NPV, not gross sales margin, and needs explicit terminal value and discount assumptions.
- `normalize_product_factory_run`: read actual PF run snapshots while preserving target MSRP and modeled COGS as **hypotheses**, not sales or measured cost.
- `normalize_salvage_opportunities`: read actual Circuit-AI workflow report nesting and scores as discovery inputs. A score does not imply verified yield or a transaction.
- `normalize_donor_discovery` and `normalize_salvage_purchase_screen`: ingest PR #148's 17 Taiwan donor observations and PR #147's already-computed bid screens once exported, without reopening their math or promoting listings to real inventory.
- `commercial_outcomes.append_outcome`: append-only **accepted and settled** transaction ledger with payment reconciliation and receipt-referenced **measured** values and explicit costs. It refuses unpaid invoices, unaccepted deposits and estimates. Its collected contribution is provisional while future warranty liability remains open.
- Native price/cost units: **TWD** (Taiwan), **CNY** (mainland China), **IDR** (Indonesia), **USD**. No invisible FX conversion or cross-currency ranking.
- Every proposed route has `purchase_authorized: false`, including when modeled inputs would otherwise pass margin and evidence checks. Human authority and legal/technical checks are external to this routing code.

## Quick run

```bash
PYTHONPATH=src python scripts/evaluate_commercial_value.py examples/commercial_value_case_twd.json
PYTHONPATH=src python scripts/converge_commercial_sources.py --case examples/commercial_value_case_twd.json --salvage-report apps/circuit-ai/eval/salvage_workflow_report.json
# Once PR #147/#148 exports are available locally, add:
# --donor-discovery path/to/tw_donor_discovery.json
# --purchase-screen path/to/a_completed_salvage_purchase_screen_result.json\nPYTHONPATH=src python -m pytest -q tests/test_commercial_value_routing.py
```

The example contains **hypothetical**, not scraped/quoted, Taiwanese monetary inputs and compares *refurbish-and-sell* with *operate the asset*. The router deliberately does **not** select an overall best option when operating NPV and completed-sale contribution have incomparable time horizons. An apparently positive screen must **not** be used for purchasing. The convergence command accepts repeated `--pf-run`, `--salvage-report`, `--donor-discovery`, `--purchase-screen` and `--case` paths and produces a read-only consolidated dossier. Source PR files must be exported from their branches first; no silent cherry-picking.

## Case contract (minimal)

```json
{
  "schema_version": "hardware_splicer.commercial_value_case.v1",
  "candidate_id": "TW-ASSET-001",
  "currency": "TWD",
  "market": "Taiwan",
  "target_contribution_margin": 0.30,
  "routes": [
    {
      "route_id": "repair-and-resell",
      "action": "refurbish",
      "currency": "TWD",
      "success_probability": 0.70,
      "probability_evidence": "HYPOTHESIS",
      "sale_proceeds": {"amount": 10000, "evidence_class": "HYPOTHESIS"},
      "failure_proceeds": {"amount": 500, "evidence_class": "HYPOTHESIS"},
      "expenses": {
        "acquisition": {"amount": 1000, "evidence_class": "HYPOTHESIS"},
        "material_and_fab": {"amount": 2000, "evidence_class": "HYPOTHESIS"},
        "engineering": {"amount": 1000, "evidence_class": "HYPOTHESIS"},
        "labor": {"amount": 500, "evidence_class": "HYPOTHESIS"},
        "quality": {"amount": 200, "evidence_class": "HYPOTHESIS"},
        "freight_and_tax": {"amount": 300, "evidence_class": "HYPOTHESIS"},
        "sales_and_payment": {"amount": 500, "evidence_class": "HYPOTHESIS"},
        "warranty_and_returns": {"amount": 500, "evidence_class": "HYPOTHESIS"}
      }
    }
  ]
}
```

For all eight expenses, zero must be explicitly represented, never inferred. The mean resale proceeds are `p * realized-sale-price-assumption + (1-p) * failed-item-recovery-assumption`; total expense is deducted once. Returns/yield and labor are mandatory screens, not zero defaults.

Operating routes supply `monthly_net_cashflows` (negative amounts explicitly permitted), `terminal_value`, `monthly_discount_rate`, and `success_probability: 1`; uncertainty should be represented as separately documented operating scenarios. Operating readiness requires referenced `site_or_use_rights_cleared` and `operational_benefit_verified` gates, NOT a customer sale or `buyer_committed`. Do not compare operating NPV with sale margins, and never compare different horizons without adjustment.

Evidence classes: `UNKNOWN`, `HYPOTHESIS`, `ESTIMATED`, `QUOTED`, `MEASURED`, `INVALID`. A quoted or measured input needs a nonempty reference. Only the latter two can advance core cost evidence. An accepted transaction needs measured cost receipts AND payment status `SETTLED` with a reconciliation reference to enter the outcome ledger; it records `warranty_cash_spent`, not a speculative reserve. Future claims make this provisional cash contribution, not final lifetime product profit. Evidence labels are not a substitute for validating sources.

## Merge sequencing

1. **Current PR:** Land routing, adapters, ledger, tests, and this lineage mapping after CI verifies them. No purchase authority.
2. **PR #147/#148 upstream check:** Reconcile the shared salvage-investigation branch first. Run tests against existing purchase-screen and donor-import functionality. Connect per-purchase bid ceilings and actual listing provenance to this router without duplicating purchase arithmetic.
3. **PR #109 before #110/#111:** Reconcile Product Factory stage/evidence mapping and verify the common run schema. Merge only after its engineering gates pass; then rebase #110/#111, preserving donor model identity and safety gates.
4. **Outcome closure:** Record actual supplier quotes, tested yields, qualified buyers, cash expenses, customer acceptance, and operation logs. Compare estimated vs actual on a per-case basis, including failure cases. **None of these have been measured by the current branch**.
5. **Cross-market support:** Store quoted supplier TWD/CNY/IDR locally. Any FX comparison must include the dated source rate, spread, duty, freight and tax separately; this initial router deliberately refuses currency mixing.

## Known limitations / next engineering work

- The router does not fetch live Taiwan/China/Indonesia marketplaces, bid on e-commerce listings, contact suppliers, assert ownership of customer data, operate hardware, or independently verify legal compliance.
- It does not replace PR #147's more detailed per-acquisition salvage statistics. Store purchase-screen output as associated evidence when that PR is reconciled.
- Pre-purchase gross-value ranking can favor high upside with low probability; use downside thresholds, inspection opportunity cost and available capital before committing.
- Operating NPV depends on a common horizon, utilization, terminal-value evidence, measured output and discount assumptions.
- No automatic sale/release gate. A positive computed result is only **ready for human commercial review** when supported by evidence and references; it still has `purchase_authorized: false`.
- Actual purchase/recycling compliance, buyer contracts, and export/consumer-protection/warranty obligations remain external decisions. The accepted-sales ledger requires a separately confirmed payment, but deferred warranty/return exposure must still be measured later.
- PF-001/002/003 prices, COGS, and regional source observations are hypotheses, not established manufacturing margins.

## Real success criteria

A first physical donor or hardware-product case needs: exact device identity, legitimate ownership, acquisition receipt, qualified technical assessment, physical acceptance evidence, all-in costs in native currency, documented customer sale/acceptance **or** measured operating output, recorded yield/failure, and reconciled actual contribution. Only then can HS claim that its integrated intelligence identified and delivered real economic value.
