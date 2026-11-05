from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hs_salvage_pilot", ROOT / "salvage_pilot.py")
pilot = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(pilot)


def source():
    return json.loads((ROOT / "salvage_sources.json").read_text())


def by_id(i):
    return next(x for x in source()["donor_leads"] if x["id"] == i)


def test_actual_donated_desktop_inventory_not_working():
    s = by_id("hsinchu_free_desktop")
    assert "motherboard" in s["reported_included"]
    assert "power_supply" in s["reported_included"]
    assert "CPU" in s["unverified"]
    assert s["physical_acquired"] is False
    assert s["platform"] == "PTT Give"


def test_ptt_give_no_resale_cannot_be_overridden():
    s = by_id("sanchong_scrap_20261030")
    assert pilot.valid_transfer(s) is False
    s.update(physical_acquired=True, donor_owner_permission=True,
             commercial_disposition_rights="verified_unrestricted_transfer",
             source_availability="received_and_documented")
    assert pilot.valid_transfer(s) is False


def test_hypothetical_donor_cannot_be_commercial_stock_even_with_fake_record():
    s = by_id("direct_owner_cleanout_hypothetical")
    s.update(physical_acquired=True, donor_owner_permission=True,
             commercial_disposition_rights="verified_unrestricted_transfer",
             source_availability="received_and_documented")
    assert pilot.valid_transfer(s) is False


def test_paid_offer_current_state_without_purchase_is_blocked():
    s = by_id("taoyuan_damaged_cpu_board_20261026")
    assert s["asking_price_twd"] == 600
    assert not pilot.valid_transfer(s)
    assert s["source_availability"] == "listing_unverified"


def test_margin_destroys_paid_salvage_cpu_flip():
    s = by_id("taoyuan_damaged_cpu_board_20261026")
    product = pilot.candidate_valuation(s)[0]
    report = pilot.economics(s,product,0.5)
    assert report["profit_if_functionally_verified_and_sold_twd"] == -720
    assert report["loss_if_failed_twd"] == -1100
    assert report["hypothetical_expected_contribution_twd"] == -910
    assert report["sellable_and_bench_verified"] is False


def test_complete_desktop_scenarios_are_not_physical_product():
    s = by_id("direct_owner_cleanout_hypothetical")
    routes = {x["product_id"]:x for x in pilot.candidate_valuation(s)}
    assert len(routes) == 3
    whole = pilot.economics(s,routes["refurbished_complete_desktop"],0.5)
    assert whole["profit_if_functionally_verified_and_sold_twd"] == 630
    assert whole["loss_if_failed_twd"] == -600
    assert whole["hypothetical_expected_contribution_twd"] == 15
    assert whole["acquisition_or_transfer_authorized"] is False


def test_nas_path_not_proven_profitable_despite_high_ask():
    s = by_id("direct_owner_cleanout_hypothetical")
    nas = next(x for x in pilot.candidate_valuation(s) if x["product_id"]=="nas_from_scrap_unverified_market")
    report = pilot.economics(s,nas,0.5)
    assert report["profit_if_functionally_verified_and_sold_twd"] < 0
    assert report["hypothetical_expected_contribution_twd"] < 0


@pytest.mark.parametrize("p",[-0.1,1.1])
def test_invalid_probabilities_rejected(p):
    s = by_id("taoyuan_damaged_cpu_board_20261026")
    with pytest.raises(ValueError):
        pilot.economics(s,pilot.candidate_valuation(s)[0],p)


def test_all_public_commercial_trades_blocked_and_source_explicit(monkeypatch):
    monkeypatch.setattr(pilot,"existing_hs_salvage_engine",lambda:{"backend_verdict":"collect_more_evidence"})
    report=pilot.decision_run(source())
    assert report["source_count"]==4
    assert report["confirmed_resale_authorized_lots"]==0
    assert report["verified_usable_assets"]==0
    assert report["functional_products_produced"]==0
    assert report["sales_recorded"]==0
    assert report["overall_decision"]=="NO_COMMERCIAL_SALVAGE_AVAILABLE_YET"
    assert all(not r["acquisition_or_transfer_authorized"] for r in report["scenarios"])
    assert all(not r["sellable_and_bench_verified"] for r in report["scenarios"])


def test_preserved_execution_proof_is_honest():
    p = ROOT/"evidence/salvage_decision.json"
    report=json.loads(p.read_text())
    assert report["confirmed_resale_authorized_lots"] == 0
    assert report["physical_validation_status"] == "NONE"
    assert report["hs_salvage_core"]["backend_verdict"] == "collect_more_evidence"
    assert report["hs_salvage_core"]["real_verified_salvage_asset_count"] == 0
