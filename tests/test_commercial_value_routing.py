"""Commercial value routing: never infer authorization from a positive spread."""
from __future__ import annotations

from copy import deepcopy

from hardware_splicer.commercial_value_routing import (
    evaluate_commercial_case, evaluate_route,
    normalize_product_factory_run, normalize_salvage_opportunities,
)
from hardware_splicer.commercial_outcomes import append_outcome, SCHEMA as OUTCOME_SCHEMA


def money(amount, evidence_class="ESTIMATED", reference=None):
    record = {"amount": amount, "evidence_class": evidence_class}
    if reference is not None:
        record["reference"] = reference
    return record


def route(*, currency="TWD", action="refurbish", p=0.8):
    return {
        "route_id": "repair-and-sell",
        "action": action,
        "currency": currency,
        "success_probability": p,
        "probability_evidence": "HYPOTHESIS",
        "sale_proceeds": money(600, "HYPOTHESIS"),
        "failure_proceeds": money(20, "ESTIMATED"),
        "expenses": {
            "acquisition": money(100), "material_and_fab": money(100),
            "engineering": money(50), "labor": money(20),
            "quality": money(10), "freight_and_tax": money(10),
            "sales_and_payment": money(10), "warranty_and_returns": money(10),
        },
    }


def case(r=None):
    return {
        "schema_version": "hardware_splicer.commercial_value_case.v1",
        "candidate_id": "TW-USED-001", "currency": "TWD", "market": "Taiwan",
        "routes": [r or route()],
    }


def test_expected_value_uses_failure_proceeds_and_all_costs():
    result = evaluate_commercial_case(case())
    priced = result["routes"][0]
    assert priced["expected_proceeds"] == 484.0
    assert priced["total_cost"] == 310.0
    assert priced["net_value"] == 174.0
    assert priced["break_even_bid"] == 274.0
    assert priced["bid_ceiling_at_target_margin"] == 128.8
    assert priced["sale_price_minus_20pct"] == 78
    assert priced["sale_price_plus_20pct"] == 270
    assert priced["status"] == "SCREENING_ONLY"
    assert priced["purchase_authorized"] is False
    assert result["best_screening_route"] == "repair-and-sell"


def test_missing_expense_cannot_become_zero():
    r = route()
    del r["expenses"]["quality"]
    result = evaluate_commercial_case(case(r))["routes"][0]
    assert "missing_money:expenses.quality" in result["errors"]
    assert result["net_value"] is None


def test_explicit_zero_is_allowed_when_recorded():
    r = route()
    r["expenses"]["quality"] = money(0, "ESTIMATED")
    assert evaluate_commercial_case(case(r))["routes"][0]["net_value"] == 184


def test_invalid_price_and_nonfinite_values_fail_closed():
    for price in [float("nan"), float("inf"), -1, True, "nope"]:
        r = route()
        r["sale_proceeds"] = money(price)
        x = evaluate_commercial_case(case(r))["routes"][0]
        assert x["status"] == "INVALID"
        assert x["purchase_authorized"] is False


def test_missing_probability_is_not_assumed_one():
    r = route()
    del r["success_probability"]
    x = evaluate_commercial_case(case(r))["routes"][0]
    assert "missing_fraction:success_probability" in x["errors"]


def test_currency_is_not_silently_converted():
    r = route(currency="CNY")
    x = evaluate_commercial_case(case(r))["routes"][0]
    assert "currency_mismatch" in x["errors"]
    assert x["status"] == "INVALID"


def test_positive_margin_does_not_authorize_purchase():
    x = evaluate_commercial_case(case())["routes"][0]
    assert x["net_value"] > 0
    assert "unproven_gate:physical_test_passed" in x["blockers"]
    assert "unquoted_core_cost" in x["blockers"]
    assert "unverified_buyer_price" in x["blockers"]


def test_full_receipted_case_remains_human_review_only():
    r = route()
    r["success_probability"] = 0.8
    r["probability_evidence"] = "MEASURED"
    r["sale_proceeds"] = money(600, "QUOTED", "buyer-po-004")
    for key in ("acquisition", "material_and_fab"):
        r["expenses"][key] = money(r["expenses"][key]["amount"], "QUOTED", "supplier-quote-2")
    gates = ("physical_test_passed", "rights_cleared", "compliance_cleared",
             "buyer_committed", "procurement_verified")
    r["gates"] = {gate: True for gate in gates}
    r["gate_references"] = {gate: f"evidence-{gate}" for gate in gates}
    x = evaluate_commercial_case(case(r))["routes"][0]
    assert x["status"] == "REVIEW_READY"
    assert x["ready_for_human_commercial_review"] is True
    assert x["purchase_authorized"] is False


def test_unreferenced_measured_price_is_invalid():
    r = route()
    r["sale_proceeds"] = money(600, "MEASURED")
    x = evaluate_commercial_case(case(r))["routes"][0]
    assert "missing_reference:sale_proceeds" in x["errors"]


def test_operating_value_is_discounted_cashflow_not_sale_margin():
    r = route(action="operate", p=1)
    del r["sale_proceeds"]
    del r["failure_proceeds"]
    r["probability_evidence"] = "HYPOTHESIS"
    r["monthly_net_cashflows"] = [money(20), money(-5)]
    r["terminal_value"] = money(390)
    r["monthly_discount_rate"] = 0
    x = evaluate_commercial_case(case(r))["routes"][0]
    assert x["metric"] == "net_present_value"
    assert x["net_value"] == 95  # 20 - 5 + 390 - 310
    assert x["margin"] is None
    assert x["purchase_authorized"] is False


def test_operating_requires_real_cashflow_inputs():
    r = route(action="operate", p=1)
    del r["sale_proceeds"]
    r["monthly_net_cashflows"] = []
    r["terminal_value"] = money(100)
    r["monthly_discount_rate"] = 0.01
    x = evaluate_commercial_case(case(r))["routes"][0]
    assert x["status"] == "INVALID"
    assert "missing_monthly_net_cashflows" in x["errors"]


def test_duplicate_ids_invalid_even_with_different_routes():
    r1, r2 = route(), route()
    c = case()
    c["routes"] = [r1, r2]
    out = evaluate_commercial_case(c)
    assert "duplicate_route_id" in out["errors"]


def test_product_factory_targets_are_not_counted_as_sales():
    run = {"run_id": "PF-002", "product_id": "benchhmi-v0",
           "metrics": {"target_msrp_twd": 8990, "modeled_effective_cogs_twd": 3841.67},
           "stages": [{"id": "PROVE", "state": "QUEUED_AFTER_PHYSICAL_ARTIFACT"}],
           "authority": {"physical_correctness": "UNPROVEN"}}
    out = normalize_product_factory_run(run, source_ref="HS PR #110")
    assert out["price_hypotheses"]["target_msrp_twd"]["evidence_class"] == "HYPOTHESIS"
    assert out["commercial_status"] == "DISCOVERY_ONLY"
    assert out["purchase_authorized"] is False
    assert out["stage_states"]["PROVE"] == "QUEUED_AFTER_PHYSICAL_ARTIFACT"


def test_salvage_estimated_values_never_become_sold_comps():
    raw = {"opportunities": [{"id": "listing-001", "type": "ecommerce_arbitrage",
                              "estimated_output_value_usd": 150, "score": 0.9}]}
    out = normalize_salvage_opportunities(raw, source_ref="Circuit-AI analysis 1")
    assert out[0]["commercial_status"] == "UNPRICED"
    assert out[0]["value_hypothesis_usd"]["evidence_class"] == "HYPOTHESIS"
    assert out[0]["purchase_authorized"] is False


def transaction():
    keys = ("acquisition", "materials", "engineering", "labor", "quality",
            "logistics_and_tax", "fees", "warranty_reserve")
    return {
        "transaction_id": "accepted-001", "candidate_id": "benchhmi-v0",
        "route_id": "refurbish", "currency": "TWD",
        "acceptance_status": "ACCEPTED", "acceptance_reference": "acceptance-signed-1",
        "revenue": money(10000, "MEASURED", "invoice-1"),
        "costs": {k: money(100, "MEASURED", "receipts-1") for k in keys},
    }


def test_measured_outcomes_append_once_without_mutating_source():
    ledger = {"schema_version": OUTCOME_SCHEMA, "transactions": []}
    original = deepcopy(ledger)
    first = append_outcome(ledger, transaction())
    assert first["status"] == "RECORDED"
    assert len(first["ledger"]["transactions"]) == 1
    assert first["transaction"]["realized_contribution"] == 9200
    assert ledger == original
    second = append_outcome(first["ledger"], transaction())
    assert second["status"] == "INVALID"
    assert second["errors"] == ["duplicate_transaction_id"]


def test_deposit_and_hypothetical_revenue_never_count_as_sale():
    t = transaction()
    t["acceptance_status"] = "DEPOSIT_RECEIVED"
    assert append_outcome({"schema_version": OUTCOME_SCHEMA, "transactions": []}, t)["status"] == "INVALID"
    t = transaction()
    t["revenue"] = money(10000, "ESTIMATED")
    assert "not_measured:revenue" in append_outcome(
        {"schema_version": OUTCOME_SCHEMA, "transactions": []}, t
    )["errors"]


def test_operating_asset_has_use_and_output_gates_not_buyer_gate():
    r = route(action="operate", p=1)
    del r["sale_proceeds"]
    del r["failure_proceeds"]
    r["monthly_net_cashflows"] = [money(400, "MEASURED", "meter-log-1")]
    r["terminal_value"] = money(100, "QUOTED", "disposal-quote-1")
    r["monthly_discount_rate"] = 0
    r["probability_evidence"] = "MEASURED"
    for key in ("acquisition", "material_and_fab"):
        r["expenses"][key] = money(r["expenses"][key]["amount"], "QUOTED", "supplier-quote-3")
    gates = ("physical_test_passed", "rights_cleared", "compliance_cleared",
             "procurement_verified", "site_or_use_rights_cleared", "operational_benefit_verified")
    r["gates"] = {gate: True for gate in gates}
    r["gate_references"] = {gate: f"evidence-{gate}" for gate in gates}
    result = evaluate_commercial_case(case(r))["routes"][0]
    assert result["net_value"] == 190
    assert result["status"] == "REVIEW_READY"
    assert result["purchase_authorized"] is False
    assert "unproven_gate:buyer_committed" not in result["blockers"]


def test_operating_forecasts_do_not_count_as_measured_output():
    r = route(action="operate", p=1)
    del r["sale_proceeds"]
    r["monthly_net_cashflows"] = [money(400, "ESTIMATED")]
    r["terminal_value"] = money(100, "ESTIMATED")
    r["monthly_discount_rate"] = 0
    result = evaluate_commercial_case(case(r))["routes"][0]
    assert "unverified_operating_output" in result["blockers"]


def test_nested_circuit_ai_report_is_ingested_without_price_promotion():
    report = {
        "final_report": {"opportunity_report": {"opportunities": [
            {"id": "donor-2", "type": "build_from_salvage",
             "score": 0.8, "estimated_output_value_usd": 40}
        ]}}
    }
    out = normalize_salvage_opportunities(report, source_ref="salvage_workflow_report.json")
    assert len(out) == 1
    assert out[0]["value_hypothesis_usd"]["amount"] == 40
    assert out[0]["commercial_status"] == "UNPRICED"
