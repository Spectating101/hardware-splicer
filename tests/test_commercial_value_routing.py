"""Commercial value routing: never infer authorization from a positive spread."""
from __future__ import annotations

from copy import deepcopy
import json
import csv
from pathlib import Path
import subprocess
import sys

from hardware_splicer.commercial_value_routing import (
    evaluate_commercial_case, evaluate_route, evaluate_portfolio,
    normalize_product_factory_run, normalize_salvage_opportunities,
    normalize_donor_discovery, normalize_salvage_purchase_screen,
)
from hardware_splicer.commercial_outcomes import append_outcome, SCHEMA as OUTCOME_SCHEMA
from hardware_splicer.commercial_materials import evaluate_material_plan


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
            "logistics_and_tax", "fees", "warranty_cash_spent")
    return {
        "transaction_id": "accepted-001", "candidate_id": "benchhmi-v0",
        "route_id": "refurbish", "currency": "TWD",
        "acceptance_status": "ACCEPTED", "acceptance_reference": "acceptance-signed-1",
        "payment_status": "SETTLED", "payment_reference": "bank-reconciliation-1",
        "revenue": money(10000, "MEASURED", "invoice-1"),
        "costs": {k: money(100, "MEASURED", "receipts-1") for k in keys},
    }


def test_measured_outcomes_append_once_without_mutating_source():
    ledger = {"schema_version": OUTCOME_SCHEMA, "transactions": []}
    original = deepcopy(ledger)
    first = append_outcome(ledger, transaction())
    assert first["status"] == "RECORDED"
    assert len(first["ledger"]["transactions"]) == 1
    assert first["transaction"]["collected_contribution_to_date"] == 9200
    assert first["transaction"]["warranty_liability_finalized"] is False
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


def test_mixed_operating_npv_and_sales_do_not_rank_without_comparable_horizon():
    r = route(action="operate", p=1)
    del r["sale_proceeds"]
    del r["failure_proceeds"]
    r["monthly_net_cashflows"] = [money(500)]
    r["terminal_value"] = money(0)
    r["monthly_discount_rate"] = 0
    screen = case()
    screen["routes"] = [route(), r]
    screen["routes"][1]["route_id"] = "operate"
    x = evaluate_commercial_case(screen)
    assert x["best_screening_route"] is None
    assert x["screening_rank"] == []
    assert "mixed_operating_npv_and_sales_contribution" in x["comparability_blockers"]


def test_portfolio_keeps_cny_and_twd_rankings_separate():
    tw = case(route())
    cn = case(route(currency="CNY"))
    cn["candidate_id"] = "CN-LOT-01"
    cn["currency"] = "CNY"
    x = evaluate_portfolio([tw, cn])
    assert set(x["native_currency_rankings"]) == {"TWD", "CNY"}
    assert x["native_currency_rankings"]["TWD"][0]["candidate_id"] == "TW-USED-001"
    assert x["native_currency_rankings"]["CNY"][0]["candidate_id"] == "CN-LOT-01"
    assert x["purchase_authorized"] is False


def test_source_convergence_cli_reads_actual_circuit_ai_report():
    root = Path(__file__).resolve().parents[1]
    command = [
        sys.executable, str(root / "scripts" / "converge_commercial_sources.py"),
        "--case", str(root / "examples" / "commercial_value_case_twd.json"),
        "--salvage-report", str(root / "apps" / "circuit-ai" / "eval" / "salvage_workflow_report.json"),
    ]
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=45)
    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["schema_version"] == "hardware_splicer.commercial_convergence_dossier.v0"
    assert report["purchase_authorized"] is False
    assert report["commercial_cases"]["cases"][0]["currency"] == "TWD"
    assert len(report["salvage_discovery_reports"]) == 1


def test_taiwan_donor_discovery_stays_advertised_not_purchased():
    rows = {
        "schema_version": "hardware_splicer.commerce_donor_discovery.v1",
        "records": [{
            "listing_id": "qnap-650", "family": "network_board",
            "status": "DISCOVERY_ONLY", "source_url": "https://www.ruten.com.tw/item/example/",
            "advertised_ask_twd_min": 650, "advertised_ask_twd_max": 650,
            "parts_hypotheses_unverified": ["ethernet"],
        }],
    }
    out = normalize_donor_discovery(rows, source_ref="HS #148 discovery export")
    assert out[0]["advertised_ask_range"] == [650, 650]
    assert out[0]["ask_evidence_class"] == "HYPOTHESIS"
    assert out[0]["purchase_authorized"] is False
    rows["records"][0]["status"] = "TESTED"
    try:
        normalize_donor_discovery(rows, source_ref="HS #148")
    except ValueError as exc:
        assert "cannot promote" in str(exc)
    else:
        raise AssertionError("unverified donor incorrectly promoted")


def test_salvage_purchase_screen_preserves_own_bid_math():
    base = {
        "schema_version": "hardware_splicer.salvage_purchase_screen.v1",
        "id": "tw-thermal-printer",
        "expected_net_per_acquired_unit_twd": 339,
        "break_even_max_purchase_twd": 839,
        "max_purchase_for_target_profit_twd": 539,
        "acquisition_price_basis": "advertised_asking_price",
        "purchase_authorized": False,
    }
    out = normalize_salvage_purchase_screen(base, source_ref="PR147-model-output")
    assert out["priced_outcome"]["target_profit_max_bid"] == 539
    assert out["priced_outcome"]["evidence_class"] == "ESTIMATED"
    assert out["purchase_authorized"] is False
    base["purchase_authorized"] = True
    try:
        normalize_salvage_purchase_screen(base, source_ref="PR147")
    except ValueError as exc:
        assert "purchase authority" in str(exc)
    else:
        raise AssertionError("purchase authorization silently accepted")


def test_convergence_cli_ingests_donor_catalog_and_purchase_screen(tmp_path):
    donor = tmp_path / "donor.json"
    donor.write_text(json.dumps({
        "schema_version": "hardware_splicer.commerce_donor_discovery.v1",
        "records": [{
            "listing_id": "unused-printer", "status": "DISCOVERY_ONLY",
            "advertised_ask_twd_min": 50, "advertised_ask_twd_max": 100
        }],
    }), encoding="utf-8")
    screen = tmp_path / "screen.json"
    screen.write_text(json.dumps({
        "schema_version": "hardware_splicer.salvage_purchase_screen.v1",
        "id": "unused-printer",
        "purchase_authorized": False,
        "expected_net_per_acquired_unit_twd": 10,
    }), encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([
        sys.executable, str(root / "scripts" / "converge_commercial_sources.py"),
        "--donor-discovery", str(donor), "--purchase-screen", str(screen),
    ], cwd=root, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stderr
    doc = json.loads(result.stdout)
    assert len(doc["donor_discovery_catalogs"][0]["listings"]) == 1
    assert doc["salvage_purchase_screens"][0]["purchase_authorized"] is False


def test_accepted_but_unpaid_invoice_never_counts_as_collected_revenue():
    ledger = {"schema_version": OUTCOME_SCHEMA, "transactions": []}
    transaction_data = transaction()
    transaction_data["payment_status"] = "INVOICED"
    result = append_outcome(ledger, transaction_data)
    assert result["status"] == "INVALID"
    assert "unsettled_revenue" in result["errors"]
    transaction_data["payment_status"] = "SETTLED"
    del transaction_data["payment_reference"]
    assert "missing_payment_reference" in append_outcome(ledger, transaction_data)["errors"]


def test_perfect_information_value_is_a_ceiling_not_an_authorization():
    r = evaluate_commercial_case(case())["routes"][0]
    assert r["success_net_if_acquired"] == 290
    assert r["failure_net_if_acquired"] == -290
    assert r["evpi_upper_bound"] == 58  # .8 * 290 - max(0, expected 174)
    assert r["purchase_authorized"] is False
    certain = route(p=1)
    certain["failure_proceeds"] = money(0)
    assert evaluate_commercial_case(case(certain))["routes"][0]["evpi_upper_bound"] == 0


def test_huge_finite_line_items_cannot_create_infinite_cost_or_profit():
    r = route()
    for name in r["expenses"]:
        r["expenses"][name] = money(1e308)
    x = evaluate_commercial_case(case(r))["routes"][0]
    assert x["status"] == "INVALID"
    assert "nonfinite_aggregated_cost" in x["errors"]
    assert x["net_value"] is None


def test_actual_17_donor_snapshot_is_ingested_only_as_discovery():
    root = Path(__file__).resolve().parents[1]
    donor = json.loads((
        root / "examples" / "commercial_tw_donor_discovery_snapshot_2026-10-19.json"
    ).read_text(encoding="utf-8"))
    imported = normalize_donor_discovery(donor, source_ref=donor["source_pr_url"])
    assert len(imported) == 17
    assert all(row["currency"] == "TWD" for row in imported)
    assert all(row["commercial_status"] == "DISCOVERY_ONLY" for row in imported)
    assert all(not row["purchase_authorized"] for row in imported)
    assert all(row["listing_url"].startswith("https://www.ruten.com.tw/item/") for row in imported)


def test_real_branch_snapshots_flow_into_action_queue():
    root = Path(__file__).resolve().parents[1]
    command = [
        sys.executable, str(root / "scripts" / "converge_commercial_sources.py"),
        "--pf-run", str(root / "examples" / "commercial_pf002_benchhmi_snapshot.json"),
        "--donor-discovery", str(root / "examples" /
                               "commercial_tw_donor_discovery_snapshot_2026-10-19.json"),
        "--case", str(root / "examples" / "commercial_value_case_twd.json"),
    ]
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=45)
    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    queue = report["investigation_queue"]
    assert queue["purchase_authorized"] is False
    assert queue["status"] == "EVIDENCE_GATHERING_ONLY"
    assert sum(x["origin"] == "taiwan_donor_discovery" for x in queue["tasks"]) == 17
    pf = [x for x in queue["tasks"] if x["origin"] == "product_factory"]
    assert len(pf) == 1
    assert pf[0]["candidate_id"] == "benchhmi-v0"
    assert pf[0]["earliest_unclosed_stage"] == "SELECT"
    assert report["product_factory_experiments"][0]["physical_status"] == "UNPROVEN"


def test_pf002_source_bom_sum_exposes_original_summary_arithmetic_error():
    root = Path(__file__).resolve().parents[1]
    with (root / "examples" / "commercial_pf002_screening_bom_source_snapshot.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    lines = [r for r in rows if r["category"] != "TOTAL"]
    asserted = next(r for r in rows if r["category"] == "TOTAL")
    one_unit = sum(int(r["qty"]) * int(r["screening_unit_twd_1up"]) for r in lines)
    ten_unit = sum(int(r["qty"]) * int(r["screening_unit_twd_10up"]) for r in lines)
    assert len(lines) == 13
    assert one_unit == 1936
    assert ten_unit == 1462
    assert int(asserted["screening_unit_twd_1up"]) == 1726
    assert int(asserted["screening_unit_twd_10up"]) == 1357
    assert one_unit - int(asserted["screening_unit_twd_1up"]) == 210
    assert ten_unit - int(asserted["screening_unit_twd_10up"]) == 105


def test_itemized_pf002_financial_screen_exposes_assumptions_and_loss():
    root = Path(__file__).resolve().parents[1]
    scenario = json.loads((
        root / "examples" / "commercial_pf002_itemized_scenario_twd.json"
    ).read_text(encoding="utf-8"))
    r = evaluate_commercial_case(scenario)["routes"][0]
    assert r["total_cost"] == 6436
    assert r["expected_proceeds"] == 6383
    assert r["net_value"] == -53
    assert r["material_plan"]["total"] == 1936
    assert r["material_plan"]["parts_count"] == 13
    assert r["material_plan"]["status"] == "SCREENING_ONLY"
    assert "unverified_material_quotes" in r["blockers"]
    assert "economics_below_gate" in r["blockers"]
    assert r["purchase_authorized"] is False
    assert r["evpi_upper_bound"] == 1787.8


def test_owned_hardware_requires_reconciled_itemized_material_plan():
    owned = route(action="build_product")
    first = evaluate_commercial_case(case(owned))["routes"][0]
    assert first["status"] == "INVALID"
    assert "missing_material_plan" in first["errors"]
    owned["material_plan"] = {
        "currency": "TWD",
        "line_items": [{"part_id": "board", "quantity": 1,
                        "unit_cost": money(80), "material_state": "new"}],
        "fabrication_service": money(20),
    }
    assert evaluate_commercial_case(case(owned))["routes"][0]["material_plan"]["total"] == 100
    owned["material_plan"]["line_items"][0]["unit_cost"] = money(40)
    unmatched = evaluate_commercial_case(case(owned))["routes"][0]
    assert unmatched["status"] == "INVALID"
    assert "material_total_does_not_reconcile" in unmatched["errors"]


def test_unverified_salvaged_materials_require_donor_provenance_and_test():
    plan = {
        "currency": "TWD",
        "line_items": [{
            "part_id": "used-fan", "quantity": 1, "unit_cost": money(40),
            "material_state": "salvaged_unverified", "donor_asset_ref": "donor-001",
        }],
        "fabrication_service": money(60),
        "recovery_labor_cost_location": "expenses.labor",
    }
    report = evaluate_material_plan(plan, currency="TWD", expected_cost=100)
    assert report["status"] == "SCREENING_ONLY"
    assert "salvaged_component_unverified:0" in report["blockers"]
    plan["line_items"][0]["material_state"] = "salvaged_bench_verified"
    plan["line_items"][0]["test_reference"] = "bench-record-17"
    assert "salvaged_component_unverified:0" not in evaluate_material_plan(
        plan, currency="TWD", expected_cost=100
    )["blockers"]


def test_pf002_mismatched_material_total_cannot_be_silent():
    root = Path(__file__).resolve().parents[1]
    raw = json.loads((
        root / "examples" / "commercial_pf002_itemized_scenario_twd.json"
    ).read_text(encoding="utf-8"))
    raw["routes"][0]["expenses"]["material_and_fab"]["amount"] = 1726
    x = evaluate_commercial_case(raw)["routes"][0]
    assert x["status"] == "INVALID"
    assert "material_total_does_not_reconcile" in x["errors"]
    assert x["purchase_authorized"] is False


def test_all_three_source_branch_product_factory_runs_are_preserved():
    root = Path(__file__).resolve().parents[1]
    names = [
        "commercial_pf001_proofpod_snapshot.json",
        "commercial_pf002_benchhmi_snapshot.json",
        "commercial_pf003_fielddeck_snapshot.json",
    ]
    products = {}
    for name in names:
        payload = json.loads((root / "examples" / name).read_text(encoding="utf-8"))
        report = normalize_product_factory_run(payload, source_ref=name)
        products[report["run_id"]] = report
        assert report["commercial_status"] == "DISCOVERY_ONLY"
        assert report["purchase_authorized"] is False
        assert report["stage_states"]["PROVE"] != "PASS"
    assert set(products) == {"PF-001", "PF-002", "PF-003"}
    assert products["PF-001"]["price_hypotheses"]["target_board_msrp_usd"]["evidence_class"] == "HYPOTHESIS"
    assert products["PF-002"]["price_hypotheses"]["target_msrp_twd"]["evidence_class"] == "HYPOTHESIS"
    assert products["PF-003"]["price_hypotheses"]["target_msrp_twd"]["evidence_class"] == "HYPOTHESIS"
