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
from hardware_splicer.commercial_market_evidence import evaluate_market_evidence
from hardware_splicer.commercial_repair_stress import repair_cost_stress
from hardware_splicer.commercial_external_evidence import evaluate_external_observations
from hardware_splicer.commercial_institutional_auctions import evaluate_disposal_sources
from hardware_splicer.commercial_identity_audit import reconcile_identity_claims
from hardware_splicer.commercial_validation_packets import build_validation_packets
from hardware_splicer.commercial_source_catalog import (normalize_historical_purchase_report, normalize_historical_regional_scan)


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


def test_five_historical_taiwan_salvage_screens_preserve_full_downside():
    root = Path(__file__).resolve().parents[1]
    raw = json.loads((
        root / "examples" / "commercial_tw_salvage_five_screen_snapshot.json"
    ).read_text(encoding="utf-8"))
    screens = normalize_historical_purchase_report(raw)
    assert len(screens) == 5
    assert {r["candidate_id"] for r in screens} == {
        "tsc-ttp244plus-budget-fault", "brother-ql800-untested",
        "hp-p1505n-failed", "acer-sa241y-broken-display",
        "old-parts-only-laptop",
    }
    by_id = {r["candidate_id"]: r for r in screens}
    assert by_id["tsc-ttp244plus-budget-fault"]["modeled_expected_net_twd"] == 339
    assert by_id["brother-ql800-untested"]["modeled_expected_net_twd"] == 24.25
    assert by_id["tsc-ttp244plus-budget-fault"]["original_target_profit_per_acquired_unit_twd"] == 300
    assert by_id["tsc-ttp244plus-budget-fault"]["current_decision"] == "MODELED_TARGET_PASS_UNVERIFIED"
    assert by_id["brother-ql800-untested"]["current_decision"] == "BELOW_PROFIT_TARGET_UNVERIFIED"
    assert by_id["hp-p1505n-failed"]["modeled_expected_net_twd"] == -476
    assert by_id["acer-sa241y-broken-display"]["modeled_expected_net_twd"] == -480
    assert by_id["old-parts-only-laptop"]["modeled_expected_net_twd"] == -667
    assert all(not p["purchase_authorized"] for p in screens)


def test_six_taiwan_china_sourcing_theses_preserve_native_currency():
    root = Path(__file__).resolve().parents[1]
    raw = json.loads((
        root / "examples" / "commercial_tw_cn_regional_scan_snapshot.json"
    ).read_text(encoding="utf-8"))
    routes = normalize_historical_regional_scan(raw)
    assert len(routes) == 6
    assert sum(r["currency"] == "TWD" for r in routes) == 3
    assert sum(r["currency"] == "CNY" for r in routes) == 3
    assert all(r["business_status"] == "UNPRICED_REQUIRES_MATCHED_BOM_AND_BUYER"
               for r in routes)
    assert all(not r["purchase_authorized"] for r in routes)


def test_full_portfolio_replay_has_31_source_records_but_no_verified_sales():
    root = Path(__file__).resolve().parents[1]
    args = [
        sys.executable, str(root / "scripts" / "converge_commercial_sources.py"),
        "--donor-discovery",
        str(root / "examples" / "commercial_tw_donor_discovery_snapshot_2026-10-19.json"),
        "--purchase-report",
        str(root / "examples" / "commercial_tw_salvage_five_screen_snapshot.json"),
        "--regional-scan",
        str(root / "examples" / "commercial_tw_cn_regional_scan_snapshot.json"),
        "--pf-run", str(root / "examples" / "commercial_pf001_proofpod_snapshot.json"),
        "--pf-run", str(root / "examples" / "commercial_pf002_benchhmi_snapshot.json"),
        "--pf-run", str(root / "examples" / "commercial_pf003_fielddeck_snapshot.json"),
        "--case", str(root / "examples" / "commercial_pf002_itemized_scenario_twd.json"),
    ]
    replay = subprocess.run(args, cwd=root, capture_output=True, text=True, timeout=45)
    assert replay.returncode == 0, replay.stderr
    doc = json.loads(replay.stdout)
    cohort = doc["cohort_review"]
    assert cohort["total_source_records"] == 31
    assert cohort["distinct_named_concepts_after_known_lineage_aliases"] == 30
    assert cohort["by_source_class"] == {
        "historical_regional_product_route": 6,
        "product_factory": 3,
        "salvage_economics": 5,
        "used_equipment_marketplace": 17,
    }
    assert cohort["historically_priced_salvage_screens"] == 5
    assert cohort["positive_modeled_salvage_screens"] == 2
    assert cohort["historical_models_meeting_original_profit_target"] == 1
    assert cohort["nonpositive_modeled_salvage_screens"] == 3
    assert cohort["purchase_authorized"] is False
    assert doc["investigation_queue"]["task_count"] == 32
    decisions = [t for t in doc["investigation_queue"]["tasks"]
                 if t["origin"] == "historical_salvage_economics"]
    assert sum(t["status"] == "TARGET_PAPER_PASS_NO_PURCHASE" for t in decisions) == 1
    assert sum(t["status"] == "BELOW_TARGET_HOLD" for t in decisions) == 1
    assert sum(t["origin"] == "historical_salvage_economics"
               for t in doc["investigation_queue"]["tasks"]) == 5
    assert sum(t["origin"] == "regional_product_concept"
               for t in doc["investigation_queue"]["tasks"]) == 6
    assert sum(1 for r in cohort["records"] if r["modeled_net"] is not None) == 5
    assert all(v == 0 for v in cohort["explicitly_unsupported_proofs"].values())


def test_portfolio_report_runner_produces_two_real_artifacts(tmp_path):
    root = Path(__file__).resolve().parents[1]
    execution = subprocess.run([
        sys.executable, str(root / "scripts" / "replay_hs_commercial_portfolio.py"),
        "--output-dir", str(tmp_path),
    ], cwd=root, capture_output=True, text=True, timeout=60)
    assert execution.returncode == 0, execution.stderr
    result = json.loads(execution.stdout)
    assert result["source_records"] == 31
    assert result["unique_named_concepts"] == 30
    assert result["priced_salvage_models"] == 5
    assert result["purchase_authorized"] is False
    markdown = (tmp_path / "commercial_cohort_replay.md").read_text(encoding="utf-8")
    dossier = json.loads((tmp_path / "commercial_cohort_replay.json").read_text(encoding="utf-8"))
    assert "tsc-ttp244plus-budget-fault" in markdown
    assert "CN-PF-EDGE-001" in markdown
    assert "ls2208" in markdown
    assert "not a market forecast" in markdown
    assert dossier["investigation_queue"]["task_count"] == 32
    assert dossier["cohort_review"]["positive_modeled_salvage_screens"] == 2


def test_historical_tsc_listing_is_not_a_settled_sold_comparable():
    root = Path(__file__).resolve().parents[1]
    record = json.loads((root / "examples" / "commercial_market_evidence_tsc_historical.json").read_text(encoding="utf-8"))
    screen = evaluate_market_evidence(
        record, candidate_id=record["candidate_id"], market="Taiwan",
        currency="TWD", exact_model="TSC TTP-244 Plus", latest_day="2026-10-25",
    )
    assert screen["status"] == "NO_VERIFIED_SOLD_COMPS"
    assert screen["sold_median"] is None
    assert screen["excluded_evidence"][0]["reason"] == "model_or_variant_unverified"
    assert screen["purchase_authorized"] is False


def test_actual_settled_exact_model_comp_is_scoped_and_still_review_required():
    base = {
        "schema_version": "hardware_splicer.market_evidence.v1",
        "records": [
            {"evidence_id": "sale-1", "event_kind": "verified_settled_sale",
             "unit_price": 1800, "currency": "TWD", "market": "Taiwan",
             "exact_model": "Test Model 123", "variant_verified": True,
             "condition_class": "working_tested", "observed_date": "2026-10-18",
             "source_ref": "receipt-test-1", "settlement_verified": True,
             "settlement_reference": "bank-test-1"},
            {"evidence_id": "sale-2", "event_kind": "verified_settled_sale",
             "unit_price": 2200, "currency": "TWD", "market": "Taiwan",
             "exact_model": "Test Model 123", "variant_verified": True,
             "condition_class": "working_tested", "observed_date": "2026-10-19",
             "source_ref": "receipt-test-2", "settlement_verified": True,
             "settlement_reference": "bank-test-2"},
        ],
    }
    result = evaluate_market_evidence(
        base, candidate_id="test-only", market="Taiwan", currency="TWD",
        exact_model="Test Model 123", latest_day="2026-10-25",
    )
    assert result["sold_median"] == 2000
    assert result["status"] == "SOLD_COMPS_TO_AUDIT"
    assert result["independent_receipt_review_complete"] is False
    assert result["purchase_authorized"] is False


def test_market_comps_fail_closed_on_sold_badge_wrong_variant_and_fx():
    records = []
    for i, attrs in enumerate([
        {"event_kind": "sold_marker_without_price_proof"},
        {"event_kind": "verified_settled_sale", "settlement_verified": False},
        {"event_kind": "verified_settled_sale", "exact_model": "Different Model"},
        {"event_kind": "verified_settled_sale", "currency": "CNY"},
        {"event_kind": "verified_settled_sale", "observed_date": "2025-01-01"},
    ]):
        record = {
            "evidence_id": f"x-{i}", "event_kind": "advertised_ask",
            "unit_price": 500, "currency": "TWD", "market": "Taiwan",
            "exact_model": "Target A", "variant_verified": True,
            "condition_class": "working_tested", "observed_date": "2026-10-20",
            "source_ref": f"listing-or-receipt-{i}",
            "settlement_verified": True, "settlement_reference": f"receipt-{i}",
        }
        record.update(attrs)
        records.append(record)
    result = evaluate_market_evidence(
        {"schema_version": "hardware_splicer.market_evidence.v1", "records": records},
        candidate_id="test", market="Taiwan", currency="TWD",
        exact_model="Target A", latest_day="2026-10-25",
    )
    assert result["sold_median"] is None
    assert len(result["excluded_evidence"]) == 5
    assert len(result["ask_observations"]) == 0
    assert any(row["reason"] == "unverified_sold_marker" for row in result["excluded_evidence"])
    assert result["purchase_authorized"] is False


def test_market_evidence_invalid_duplicate_and_nonfinite_prices():
    sample = {
        "schema_version": "hardware_splicer.market_evidence.v1",
        "records": [
            {"evidence_id": "a", "event_kind": "advertised_ask",
             "unit_price": 100, "currency": "TWD", "market": "Taiwan",
             "exact_model": "A", "variant_verified": True,
             "condition_class": "untested", "observed_date": "2026-10-20",
             "source_ref": "seller-link"},
            {"evidence_id": "a", "event_kind": "advertised_ask",
             "unit_price": float("inf"), "currency": "TWD", "market": "Taiwan",
             "exact_model": "A", "variant_verified": True,
             "condition_class": "untested", "observed_date": "2026-10-20",
             "source_ref": "seller-link"},
        ],
    }
    x = evaluate_market_evidence(
        sample, candidate_id="a", market="Taiwan", currency="TWD",
        exact_model="A", latest_day="2026-10-25",
    )
    assert x["status"] == "INVALID"
    assert "missing_or_duplicate_id:1" in x["errors"]


def test_backlog_covers_all_concepts_and_diversifies_first_evidence_wave(tmp_path):
    root = Path(__file__).resolve().parents[1]
    x = subprocess.run([
        sys.executable, str(root / "scripts" / "replay_hs_commercial_portfolio.py"),
        "--output-dir", str(tmp_path),
    ], cwd=root, capture_output=True, text=True, timeout=60)
    assert x.returncode == 0, x.stderr
    result = json.loads(x.stdout)
    assert result["deduplicated_validation_cases"] == 30
    assert result["first_evidence_wave_count"] == 8
    doc = json.loads((tmp_path / "commercial_cohort_replay.json").read_text(encoding="utf-8"))
    backlog = doc["validation_backlog"]
    assert backlog["record_count"] == 30
    assert backlog["source_records_covered"] == 31
    assert backlog["unpriced_concepts"] == 25
    assert len(backlog["first_evidence_wave"]) == 8
    assert len(set(backlog["first_evidence_wave"])) == 8
    assert "tsc-ttp244plus-budget-fault" in backlog["first_evidence_wave"]
    assert "proofpod-v0" in backlog["first_evidence_wave"]
    assert backlog["verified_profitable_concepts"] == 0
    assert all(v["purchase_authorized"] is False for v in backlog["entries"])
    tsc = next(row for row in backlog["entries"]
               if row["concept_id"] == "tsc-ttp244plus-budget-fault")
    assert tsc["market_sold_median"] is None
    assert tsc["market_sold_evidence_status"] == "NO_VERIFIED_SOLD_COMPS"


def test_paid_acquisition_is_not_an_observed_resale_price():
    item = {
        "evidence_id": "purchase-1", "event_kind": "verified_paid_purchase",
        "unit_price": 600, "currency": "TWD", "market": "Taiwan",
        "exact_model": "Device Q", "variant_verified": True,
        "condition_class": "working_tested", "observed_date": "2026-10-20",
        "source_ref": "my-supplier-invoice-1",
        "settlement_verified": True, "settlement_reference": "my-bank-ref-1",
    }
    data = {"schema_version": "hardware_splicer.market_evidence.v1", "records": [item]}
    out = evaluate_market_evidence(data, candidate_id="Q", market="Taiwan",
                                   currency="TWD", exact_model="Device Q", latest_day="2026-10-25")
    assert len(out["verified_acquisition_records"]) == 1
    assert out["sold_median"] is None
    assert out["transaction_pricing_verified_in_source"] is False
    assert out["purchase_authorized"] is False


def test_tsc_printhead_replacement_can_destroy_modeled_profit():
    root = Path(__file__).resolve().parents[1]
    cases = json.loads((root / "examples" /
        "commercial_tw_salvage_five_screen_snapshot.json").read_text(encoding="utf-8"))
    tsc = next(x["modeled_unit_economics"] for x in cases["evaluations"]
               if x["id"] == "tsc-ttp244plus-budget-fault")
    scenario = json.loads((root / "examples" /
        "commercial_tsc_printhead_cost_stress_2026-10-26.json").read_text(encoding="utf-8"))
    result = repair_cost_stress(tsc, scenario)
    assert result["historical_expected_net"] == 339
    assert result["model_assumed_success_parts"] == 300
    assert result["modeled_profit_if_head_required_on_each_success"] == [-711.0, -466.0]
    assert result["maximum_success_parts_to_meet_original_profit_target"] == 355.71
    assert result["status"] == "HOLD_PRINTHEAD_CONDITION_OR_COST_REJECT"
    assert result["purchase_authorized"] is False


def test_t620_intel_j1900_listing_conflicts_with_oem_amd_config():
    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "examples" /
        "commercial_t620_identity_conflict_2026-10-26.json").read_text(encoding="utf-8"))
    report = reconcile_identity_claims(payload)
    assert report["status"] == "HOLD_IDENTITY_CONFLICT"
    assert report["conflicts"][0]["attribute"] == "cpu_family"
    assert report["conflicts"][0]["seller_claim"] == "Intel J1900"
    assert report["physical_identity_verified"] is False
    assert report["purchase_authorized"] is False


def test_identity_without_technical_discrepancy_is_still_not_physically_verified():
    claim = {
        "schema_version": "hardware_splicer.commercial_identity_claims.v1",
        "candidate_id": "test-only",
        "source_groups": [
            {"source_role": "manufacturer_spec", "source_url": "https://example.org/oem",
             "claims": [{"attribute": "cpu_family", "value": "AMD GX series"}]},
            {"source_role": "seller_listing", "source_url": "https://example.org/seller",
             "claims": [{"attribute": "cpu_family", "value": "AMD GX Series"}]},
        ],
    }
    r = reconcile_identity_claims(claim)
    assert r["status"] == "NO_CONTRADICTION_FOUND"
    assert r["physical_identity_verified"] is False
    assert r["purchase_authorized"] is False


def test_eight_source_specific_packets_require_materials_and_physical_validation(tmp_path):
    root = Path(__file__).resolve().parents[1]
    run = subprocess.run([
        sys.executable, str(root / "scripts" / "replay_hs_commercial_portfolio.py"),
        "--output-dir", str(tmp_path),
    ], cwd=root, capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    doc = json.loads((tmp_path / "commercial_cohort_replay.json").read_text(encoding="utf-8"))
    packets = build_validation_packets(doc)
    assert packets["count"] == 8
    assert len(packets["packets"]) == 8
    assert (tmp_path / "commercial_validation_packets.json").is_file()
    assert all(p["materials_and_supplier_quotes"] and p["hard_stop_conditions"]
               and p["physical_acceptance_plan"] for p in packets["packets"])
    assert all(p["purchase_authorized"] is False for p in packets["packets"])
    assert doc["identity_audits"][0]["status"] == "HOLD_IDENTITY_CONFLICT"
    assert doc["repair_cost_stress_tests"][0]["status"] == "HOLD_PRINTHEAD_CONDITION_OR_COST_REJECT"


def test_public_tw_cn_sourcebook_is_pricebook_not_sold_sales():
    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "examples" /
        "commercial_external_market_observations_2026-10-26.json").read_text(encoding="utf-8"))
    out = evaluate_external_observations(payload)
    assert out["status"] == "RESEARCH_LEADS_ONLY"
    assert out["total_observations"] == 21
    assert out["distinct_candidates_with_observations"] == 8
    assert out["market_counts"] == {"Taiwan": 18, "China": 3}
    assert out["verified_settled_sales"] == 0
    assert out["verified_supplier_quotes"] == 0
    assert out["verified_stock"] == 0
    assert out["procurement_authorized"] is False
    assert len(out["by_candidate"]["TW-PF-ARK-001"]) == 3
    tsc = next(x for x in out["records"] if x["evidence_id"] == "TW-EXT-002")
    assert tsc["price_min"] == 1450
    assert tsc["price_max"] == 1800
    assert tsc["kind"] == "replacement_part_list_price"


def test_market_book_prevents_unearned_transaction_or_supplier_quote_upgrade():
    root = Path(__file__).resolve().parents[1]
    raw = json.loads((root / "examples" /
        "commercial_external_market_observations_2026-10-26.json").read_text(encoding="utf-8"))
    raw["records"][0]["verified_completed_sale"] = True
    x = evaluate_external_observations(raw)
    assert x["status"] == "INVALID"
    assert "illegally_promoted_evidence:TW-EXT-001:verified_completed_sale" in x["errors"]
    raw["records"][0]["verified_completed_sale"] = False
    raw["records"][0]["verified_stock"] = True
    x = evaluate_external_observations(raw)
    assert x["status"] == "INVALID"
    assert "illegally_promoted_evidence:TW-EXT-001:verified_stock" in x["errors"]


def test_external_book_rejects_fake_fx_price_and_duplicate_evidence_id():
    root = Path(__file__).resolve().parents[1]
    raw = json.loads((root / "examples" /
        "commercial_external_market_observations_2026-10-26.json").read_text(encoding="utf-8"))
    raw["records"][0]["currency"] = "CNY"
    out = evaluate_external_observations(raw)
    assert "currency_or_market_mismatch:TW-EXT-001" in out["errors"]
    raw["records"][0]["currency"] = "TWD"
    raw["records"][1]["evidence_id"] = raw["records"][0]["evidence_id"]
    out = evaluate_external_observations(raw)
    assert "duplicate_or_missing_evidence_id:1" in out["errors"]


def test_executed_portfolio_replay_writes_external_source_data_report(tmp_path):
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run([
        sys.executable, str(root / "scripts" / "replay_hs_commercial_portfolio.py"),
        "--output-dir", str(tmp_path),
    ], cwd=root, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    external = json.loads((
        tmp_path / "commercial_external_market_diligence.json"
    ).read_text(encoding="utf-8"))
    assert len(external) == 1
    assert external[0]["total_observations"] == 21
    assert external[0]["verified_supplier_quotes"] == 0
    assert external[0]["procurement_authorized"] is False
    markdown = (tmp_path / "commercial_cohort_replay.md").read_text(encoding="utf-8")
    assert "TW-EXT-007" in markdown
    assert "CN-EXT-019" in markdown
    assert "NT$" in markdown


def test_institutional_auction_research_is_time_bounded_and_license_gated():
    root = Path(__file__).resolve().parents[1]
    sample = json.loads((root / "examples" /
        "commercial_taiwan_institutional_auctions_2026-10-26.json"
    ).read_text(encoding="utf-8"))
    outcome = evaluate_disposal_sources(sample, as_of="2026-10-26")
    assert outcome["count"] == 3
    ttu = next(x for x in outcome["auctions"] if x["source_id"] == "TW-AUCTION-001")
    assert ttu["status"] == "CLOSED_OR_PAST_NOTICE"
    assert ttu["deposit_twd"] == 10000
    assert ttu["eligibility"]["recycling_license_required"] is True
    bli = next(x for x in outcome["auctions"] if x["source_id"] == "TW-AUCTION-002")
    assert bli["reserve_price_twd_bulk_not_units"] == 388620
    feed = next(x for x in outcome["auctions"] if x["source_id"] == "TW-AUCTION-FEED-001")
    assert feed["status"] == "DISCOVERY_FEED_ONLY"
    assert outcome["licensed_waste_handling_authorized"] is False
    assert outcome["bid_authorized"] is False


def test_new_auction_without_license_is_not_a_purchase_opportunity():
    root = Path(__file__).resolve().parents[1]
    raw = json.loads((root / "examples" /
        "commercial_taiwan_institutional_auctions_2026-10-26.json"
    ).read_text(encoding="utf-8"))
    raw["records"][0]["event_date"] = "2026-11-30"
    x = evaluate_disposal_sources(raw, as_of="2026-10-26")
    assert x["auctions"][0]["status"] == "LICENSE_ELIGIBILITY_HOLD"
    assert x["auctions"][0]["bid_authorized"] is False


def test_commercial_replay_exports_auction_diligence(tmp_path):
    root = Path(__file__).resolve().parents[1]
    run = subprocess.run([
        sys.executable, str(root / "scripts" / "replay_hs_commercial_portfolio.py"),
        "--output-dir", str(tmp_path),
    ], cwd=root, capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    x = json.loads((tmp_path / "institutional_disposal_diligence.json"
                   ).read_text(encoding="utf-8"))
    assert len(x) == 1
    assert x[0]["count"] == 3
    assert x[0]["bid_authorized"] is False
    memo = (tmp_path / "commercial_cohort_replay.md").read_text(encoding="utf-8")
    assert "Institutional surplus" in memo
