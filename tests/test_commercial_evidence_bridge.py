"""Regression and adversarial tests for cross-agent commercial research handoff.

These tests intentionally do NOT treat listing sales counters, backers, or
green CAD meshes as proof of commercial readiness.
"""
from __future__ import annotations

import copy
from datetime import date, timedelta
import json
from hashlib import sha256
from pathlib import Path
import sys

import pytest

from hardware_splicer.commercial_evidence_bridge import (
    CommercialEvidenceError,
    evaluate,
    from_files,
)
from hardware_splicer.machine_project import MachineProject, ReleaseState

ROOT=Path(__file__).resolve().parents[1]
MARKET=ROOT/"examples/cyberdeck/dual_touch/market"
INPUT=MARKET/"inputs"
HS=ROOT/"examples/cyberdeck/dual_touch/evidence/native_mecha"
MANIFEST=json.loads((INPUT/"handoff_manifest_20261106.json").read_text())
SNAPSHOT=(INPUT/"pr291_pi5_market_snapshot_20261106.json").read_bytes()
SIGNALS=json.loads((INPUT/"adjacent_market_signals_20261106.json").read_text())
RELEASE=json.loads((HS/"hs_release_assessment.json").read_text())
BUDGET=json.loads((HS/"budget.json").read_text())

def scenario(*, market_bytes=SNAPSHOT, signals=None, release=None, budget=None, as_of=date(2026,11,6),
             target="dual_esp32_touch_4p3_rs485", reference="pi5_7in_touch_keyboard_ups"):
    return evaluate(
        market_bytes=market_bytes,
        pinned_market_sha256=sha256(market_bytes).hexdigest(),
        source_ref="Spectating101/hardware-splicer@afa56cafacc1d72c1459c58392738b86081589c0:examples/arbitrage_lab/build_vs_buy/evidence/cyberdeck_pi5_20261106.json",
        signals=SIGNALS if signals is None else signals,
        hs_release=RELEASE if release is None else release,
        hs_budget=BUDGET if budget is None else budget,
        as_of=as_of, target_architecture=target, reference_architecture=reference,
    )

def market_with_change(transform):
    obj=json.loads(SNAPSHOT)
    transform(obj)
    return json.dumps(obj).encode()

def test_pinned_real_agent_inputs_and_canonical_hs_release():
    got=from_files(
        market_path=INPUT/"pr291_pi5_market_snapshot_20261106.json",
        pinned_market_sha256=MANIFEST["reference_evidence"]["sha256"],
        source_ref="Spectating101/hardware-splicer@afa56caf:cyberdeck_pi5_20261106.json",
        signals_path=INPUT/"adjacent_market_signals_20261106.json",
        hs_release_path=HS/"hs_release_assessment.json",
        hs_machine_project_path=HS/"machine_project.json",
        hs_budget_path=HS/"budget.json",
        as_of=date(2026,11,6),
        reference_architecture=MANIFEST["reference_architecture"],
        target_architecture=MANIFEST["target_architecture"],
    )
    assert got["schema"]=="hardware_splicer.commercial_evidence_handoff.v1"
    assert got["not_same_product"]
    assert got["target_hs_estimated_parts_twd"]==2965
    assert got["market_snapshot"]["reference_build_p25_twd"]==8057
    assert got["market_snapshot"]["validation"]["p25"]["recomputed_twd"]==8057
    assert got["market_snapshot"]["validation"]["min"]["recomputed_twd"]==6505
    assert got["market_snapshot"]["validation"]["median"]["recomputed_twd"]==9374
    assert got["market_snapshot"]["validation"]["listed_input_assumptions"]==["cables_misc","shell_print"]
    assert got["hs_engineering"]["blocker_count"]==6
    assert got["commercial_readiness"]=="RESEARCH_AND_PROTOTYPE_ONLY"
    assert got["verified_exact_customer_orders"]==0
    assert not got["safe_to_order_inventory"]
    assert not got["safe_to_claim_market_demand_for_exact_product"]
    assert len(got["next_agent_tasks"])>=3
    assert all(not x["independently_verified"] for x in got["market_signals"])

def test_hs_model_actual_release_matches_captured_result():
    p=MachineProject.model_validate(json.loads((HS/"machine_project.json").read_text()))
    assert p.assess_release(ReleaseState.OPERATIONALLY_AUTHORIZED).model_dump(mode="json")==RELEASE

def test_pr291_competitor_listings_are_not_verified_sales():
    got=scenario()
    found={x["id"]:x for x in got["alternatives"]}
    assert found["ClockworkPi uConsole"]["listed_p25_twd"]==7700
    assert found["ClockworkPi uConsole"]["listings_reporting_cumulative_sales"]==1
    assert found["used business laptop"]["listed_p25_twd"]==5668
    assert all(not x["sold_units_verified"] for x in got["alternatives"])
    assert all(x["not_equivalent_to_target_architecture"] for x in got["alternatives"])

def test_crowdfunders_not_combined_into_exact_product_customers():
    got=scenario()
    paid=[x for x in got["market_signals"] if x["kind"]=="crowdfunding_pledge"]
    assert len(paid)==2
    assert all(x["relation"]=="adjacent" and x["interpretation"]=="adjacent_paid_interest" for x in paid)
    assert got["verified_exact_customer_orders"]==0

def test_pinned_snapshot_tamper_rejected():
    corrupted=SNAPSHOT+b"\n "
    with pytest.raises(CommercialEvidenceError,match="pinned"):
        evaluate(
            market_bytes=corrupted, pinned_market_sha256=MANIFEST["reference_evidence"]["sha256"],
            source_ref="trusted-pr291-agent",signals=SIGNALS,
            hs_release=RELEASE,hs_budget=BUDGET,as_of=date(2026,11,6),
            reference_architecture="pi5",target_architecture=SIGNALS["target_architecture"],
        )

def test_price_total_falsification_is_rejected_even_with_matching_sha():
    b=market_with_change(lambda x:x["comparison"].update(build_p25_twd=200))
    with pytest.raises(CommercialEvidenceError,match="inconsistent"):
        scenario(market_bytes=b)

def test_unlabeled_fixed_bom_cost_rejected():
    def mutate(x):
        for row in x["lines"]:
            if row.get("fixed_price_twd") is not None:
                row.pop("fixed_price_basis")
                return
    with pytest.raises(CommercialEvidenceError,match="unlabeled"):
        scenario(market_bytes=market_with_change(mutate))

@pytest.mark.parametrize("bad",[-1,float("inf"),True])
def test_negative_nanlike_or_boolean_money_rejected(bad):
    with pytest.raises(CommercialEvidenceError):
        scenario(budget={**BUDGET,"budget_scenario_twd":bad})

def test_claiming_same_hardware_without_source_match_is_rejected():
    with pytest.raises(CommercialEvidenceError,match="distinct architecture"):
        scenario(reference="dual_esp32_touch_4p3_rs485")

def test_signal_pack_cannot_be_reused_on_different_product():
    with pytest.raises(CommercialEvidenceError,match="architecture mismatch"):
        scenario(target="smartphone_cellular")

def test_self_asserted_paid_orders_do_not_create_verified_orders():
    signals=copy.deepcopy(SIGNALS)
    signals["signals"].append({
        "id":"fabricated_claim","kind":"verified_paid_order","relation":"exact",
        "source_url":"https://example.com/claim","observed_at_utc":"2026-11-06T00:00:00Z",
        "count":1000,
    })
    got=scenario(signals=signals)
    assert got["verified_exact_customer_orders"]==0
    assert not got["safe_to_order_inventory"]
    assert got["market_signals"][-1]["interpretation"]=="unverified_transaction_claim_requires_independent_review"

def test_cumulative_marketplace_counter_is_never_sales_velocity():
    signals=copy.deepcopy(SIGNALS)
    signals["signals"].append({
        "id":"sales-counter", "kind":"marketplace_reported_cumulative_sold",
        "relation":"adjacent", "source_url":"https://www.ruten.com.tw/item/12345678901234/",
        "observed_at_utc":"2026-11-06T00:00:00Z", "count":999999,
    })
    got=scenario(signals=signals)
    assert got["verified_exact_customer_orders"]==0
    assert "not_sales_velocity" in got["market_signals"][-1]["interpretation"]

@pytest.mark.parametrize("bad",[
    "http://example.com","https://user:password@example.com/foo","file:///etc/passwd","",
])
def test_sources_must_be_public_https_urls(bad):
    signals=copy.deepcopy(SIGNALS)
    signals["signals"][0]["source_url"]=bad
    with pytest.raises(CommercialEvidenceError,match="HTTPS"):
        scenario(signals=signals)

def test_duplicate_signal_identifiers_fail_closed():
    signals=copy.deepcopy(SIGNALS)
    signals["signals"].append(copy.deepcopy(signals["signals"][0]))
    with pytest.raises(CommercialEvidenceError,match="duplicate"):
        scenario(signals=signals)

def test_empty_signal_pack_rejected():
    with pytest.raises(CommercialEvidenceError,match="no provenance"):
        scenario(signals={**SIGNALS,"signals":[]})

def test_older_market_snapshot_is_explicitly_stale():
    got=scenario(as_of=date(2027,1,6))
    states={x["gate"]:x["status"] for x in got["gates"]}
    assert states["market_snapshot"]=="stale"
    assert got["commercial_readiness"]=="RESEARCH_AND_PROTOTYPE_ONLY"

def test_market_snapshot_future_date_not_accepted():
    with pytest.raises(CommercialEvidenceError,match="future"):
        scenario(as_of=date(2026,11,1))

def test_fake_verified_release_with_original_blockers_rejected():
    forged={**RELEASE,"achieved_state":"operationally_authorized"}
    with pytest.raises(CommercialEvidenceError,match="contradictory"):
        scenario(release=forged)

def test_edited_stored_release_cannot_override_machine_project(tmp_path):
    edited={**RELEASE,"blockers":[]}
    fake=tmp_path/"release.json";fake.write_text(json.dumps(edited))
    with pytest.raises(CommercialEvidenceError,match="canonical recomputation"):
        from_files(
            market_path=INPUT/"pr291_pi5_market_snapshot_20261106.json",
            pinned_market_sha256=MANIFEST["reference_evidence"]["sha256"],
            source_ref="pinned",signals_path=INPUT/"adjacent_market_signals_20261106.json",
            hs_release_path=fake,hs_machine_project_path=HS/"machine_project.json",
            hs_budget_path=HS/"budget.json",
            as_of=date(2026,11,6),
            reference_architecture="pi5",target_architecture=SIGNALS["target_architecture"],
        )

def test_seller_sales_count_above_listings_kept_rejected():
    def mutate(x):
        x["buy_alternatives"][0]["with_sales"]=100
    with pytest.raises(CommercialEvidenceError,match="reported-sales"):
        scenario(market_bytes=market_with_change(mutate))
