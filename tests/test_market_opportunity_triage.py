"""Adversarial product-identity and source-integrity tests over real HS gates."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json
import pytest
import tempfile

from hardware_splicer.market_opportunity_triage import (
    OpportunityEvidenceError, qualify, _digest,
)
from scripts.hs_market_evidence_handoff import run as canonical_handoff

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "examples/cyberdeck/dual_touch/market"
PLAN = json.loads((BASE / "discovery_plan.json").read_text(encoding="utf-8"))
RULES = json.loads((BASE / "opportunity_rules.json").read_text(encoding="utf-8"))
CAPTURE = "2026-11-06T14:00:00Z"


def issue(id, repo, n, title, job):
    url = f"https://github.com/{repo}/issues/{n}"
    raw = {"url": url, "title": title, "updated_at": CAPTURE}
    return {"id": f"github-{id}", "kind": "anecdotal_problem", "relation": "general",
            "source_url": url, "observed_at_utc": CAPTURE, "summary": title,
            "source_metadata": {"source": "github_public_issue", "source_record": raw,
                                "source_record_sha256": _digest(raw)},
            "discovery_job_ids": [job]}


def listing(id, title, price, job):
    url = f"https://www.ruten.com.tw/item/{id}/"
    raw = {"id": id, "title": title, "prices": [price],
           "sold_qty": 123, "stock": 4}
    return {"id": f"ruten-{id}", "kind": "marketplace_asking_price", "relation": "adjacent",
            "source_url": url, "observed_at_utc": CAPTURE, "summary": title,
            "source_metadata": {"source": "ruten_public_listing", "source_record": raw,
                                "source_record_sha256": _digest(raw), "asking_price_twd": price,
                                "seller_reported_cumulative_sold": 123},
            "discovery_job_ids": [job]}


def source_pack():
    rows = [
        issue("a", "a/one", 12, "Feature Request: remote coding SSH keyboard broken on phone", "mobile-development-friction"),
        issue("b", "b/two", 25, "Mobile SSH keyboard can't enter Ctrl", "mobile-development-friction"),
        issue("c", "c/three", 2, "Android USB serial fails to reconnect", "embedded-field-terminal"),
        issue("d", "d/four", 4, "Laptop repair: replace battery need clear diagnostics", "repair-and-salvage-workflows"),
        listing("22642901029861", "T-Deck Plus ESP32-S3 device", 2959, "mobile-development-friction"),
        listing("22642901029862", "T-Deck Plus 外殼 case", 150, "mobile-development-friction"),
        listing("22642901029863", "uConsole modular handheld computer", 7700, "embedded-field-terminal"),
        listing("22642901029864", "ThinkPad X240 X250 multiple variants", 3500, "repair-and-salvage-workflows"),
        listing("22642901029865", "ThinkPad X240 i5 laptop", 4100, "repair-and-salvage-workflows"),
    ]
    return {"schema": "hs.market_signals.v1",
            "target_architecture": PLAN["target_architecture"],
            "captured_at_utc": CAPTURE, "plan_sha256": _digest(PLAN),
            "signals": rows,
            "discovery": {"coverage": [{"job": "mobile-development-friction", "truncated": True}],
                          "failures": [], "raw_candidate_count": 11,
                          "acquisition_status": "complete_with_bounded_queries"}}


def make_bridge(pack):
    # This is not an imitated release gate. Call PR #294's real canonical
    # MachineProject recheck, original immutable Pi5 pricing and architecture guard.
    with tempfile.TemporaryDirectory(prefix="hs_triage_", dir=ROOT) as folder:
        f = Path(folder) / "new_signals.json"
        source = json.dumps(pack, ensure_ascii=False).encode()
        f.write_bytes(source)
        handoff = canonical_handoff(signals_override=str(f.relative_to(ROOT)))
        return source, handoff


def test_real_release_plus_separate_product_tracks_and_price_model_identity():
    source, bridge = make_bridge(source_pack())
    report = qualify(source_bytes=source, handoff=bridge, plan=PLAN, rules=RULES)
    a, b, c = report["opportunities"]
    assert report["schema"] == "hs.market_opportunity_triage.v1"
    assert a["candidate_product_id"] == "dual_esp32_touch_4p3_rs485"
    assert a["hs_product_gates"]["release_assessment_applies_to_this_product"]
    assert a["hs_product_gates"]["unresolved_engineering_blockers"] == 6
    assert len(a["problem_reports"]) == 2
    assert a["independent_github_repositories_with_problem_reports"] == 2
    assert a["triage_decision"] == "QUALIFIED_BUYER_RESEARCH_REQUIRED"
    assert a["competing_model_title_matches"][0]["asking_price_min_twd"] == 2959
    assert not a["competing_model_title_matches"][0]["sku_or_variant_verified"]
    assert not b["hs_product_gates"]["release_assessment_applies_to_this_product"]
    assert b["hs_product_gates"]["target_release_state"] is None
    assert c["candidate_product_id"] != a["candidate_product_id"]
    assert c["competing_model_title_matches"][0]["model_title_match"] == "thinkpad-x240"
    assert c["competing_model_title_matches"][0]["asking_price_min_twd"] == 4100
    assert {x["reason"] for x in report["review_queue"]["ambiguous_listings"]} == {
        "likely_accessory_or_parts", "multiple_model_titles"}
    assert report["verified_exact_product_customers"] == 0
    assert not report["safe_to_order_inventory"]
    assert all(not x["manufacturing_or_inventory_authorized"] for x in report["opportunities"])


def test_tampered_pack_rejected_by_canonical_byte_hash():
    pack = source_pack()
    source, bridge = make_bridge(pack)
    edited = deepcopy(pack)
    edited["signals"][0]["summary"] = "Definitely 10000 paying customers"
    with pytest.raises(OpportunityEvidenceError, match="exact source bytes"):
        qualify(source_bytes=json.dumps(edited).encode(), handoff=bridge, plan=PLAN, rules=RULES)


def test_mutated_rule_product_id_cannot_override_target_release_identity():
    pack = source_pack()
    source, bridge = make_bridge(pack)
    rules = deepcopy(RULES)
    rules["lanes"][1]["candidate_product_id"] = "field_terminal_renamed"
    report = qualify(source_bytes=source, handoff=bridge, plan=PLAN, rules=rules)
    assert report["opportunities"][1]["hs_product_gates"]["other_product_release_not_assessed"]


def test_plan_hash_disallows_disguised_research_scope():
    pack = source_pack()
    source, bridge = make_bridge(pack)
    plan = deepcopy(PLAN)
    plan["jobs"][0]["github_queries"].append("demand study")
    with pytest.raises(OpportunityEvidenceError, match="digest"):
        qualify(source_bytes=source, handoff=bridge, plan=plan, rules=RULES)


def test_fake_engineering_or_exact_sales_authority_cannot_be_promoted():
    pack = source_pack()
    source, bridge = make_bridge(pack)
    for edit in [{"safe_to_order_inventory": True},
                 {"verified_exact_customer_orders": 999},
                 {"safe_to_claim_market_demand_for_exact_product": True},
                 {"not_same_product": False}]:
        with pytest.raises(OpportunityEvidenceError):
            qualify(source_bytes=source, handoff={**bridge, **edit}, plan=PLAN, rules=RULES)


def test_source_record_sha_and_handoff_signal_mismatch_cannot_be_hidden():
    pack = source_pack()
    pack["signals"][0]["source_metadata"]["source_record_sha256"] = "f"*64
    source, bridge = make_bridge(pack)
    with pytest.raises(OpportunityEvidenceError, match="provenance"):
        qualify(source_bytes=source, handoff=bridge, plan=PLAN, rules=RULES)


def test_previous_absent_listing_is_not_called_a_lost_market():
    pack = source_pack()
    source, bridge = make_bridge(pack)
    previous = deepcopy(pack)
    previous["captured_at_utc"] = "2026-11-05T14:00:00Z"
    gone = previous["signals"].pop()
    out = qualify(source_bytes=source, handoff=bridge, plan=PLAN, rules=RULES,
                  previous_bytes=json.dumps(previous).encode())
    assert out["changes_since_previous"]["compared_to_prior"]
    assert gone["id"] in out["changes_since_previous"]["new_observations"]
    assert "not market exit" in out["changes_since_previous"]["interpretation"]


def test_changed_marketplace_title_is_only_a_record_change_not_sales_velocity():
    pack = source_pack()
    source, bridge = make_bridge(pack)
    earlier = deepcopy(pack)
    earlier["captured_at_utc"] = "2026-11-05T14:00:00Z"
    row = earlier["signals"][-1]
    row["source_metadata"]["source_record"]["prices"] = [4200]
    row["source_metadata"]["source_record_sha256"] = _digest(row["source_metadata"]["source_record"])
    result = qualify(source_bytes=source, handoff=bridge, plan=PLAN, rules=RULES,
                     previous_bytes=json.dumps(earlier).encode())
    assert row["id"] in result["changes_since_previous"]["changed_source_records"]
    assert all(not model["sold_units_verified"]
               for card in result["opportunities"]
               for model in card["competing_model_title_matches"])


def test_previous_from_future_fails_closed():
    pack = source_pack()
    source, bridge = make_bridge(pack)
    earlier = deepcopy(pack)
    earlier["captured_at_utc"] = "2026-11-07T00:00:00Z"
    with pytest.raises(OpportunityEvidenceError, match="predate"):
        qualify(source_bytes=source, handoff=bridge, plan=PLAN, rules=RULES,
                previous_bytes=json.dumps(earlier).encode())


def test_partial_acquisition_cannot_be_presented_as_complete():
    pack = source_pack()
    pack["discovery"]["failures"] = [{"job": "mobile-development-friction", "source": "github", "query": "mobile ssh", "error": "rate limit"}]
    pack["discovery"]["acquisition_status"] = "partial"
    source, bridge = make_bridge(pack)
    result = qualify(source_bytes=source, handoff=bridge, plan=PLAN, rules=RULES)
    assert all(x["market_evidence_status"] == "BOUNDED_REQUESTS_WITH_FAILURES" for x in result["opportunities"])


def test_wrong_product_rulebook_and_duplicate_model_rejected():
    pack = source_pack()
    source, bridge = make_bridge(pack)
    rules = deepcopy(RULES)
    rules["target_architecture"] = "pi5_7in_touch_keyboard_ups"
    with pytest.raises(OpportunityEvidenceError, match="architecture"):
        qualify(source_bytes=source, handoff=bridge, plan=PLAN, rules=rules)
    rules = deepcopy(RULES)
    rules["lanes"][0]["competitor_models"].append(deepcopy(rules["lanes"][0]["competitor_models"][0]))
    with pytest.raises(OpportunityEvidenceError, match="duplicated model"):
        qualify(source_bytes=source, handoff=bridge, plan=PLAN, rules=rules)
