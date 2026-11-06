"""Offline contract tests for independent GitHub/Ruten market observations."""
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse
import pytest

from hardware_splicer.market_signal_acquisition import (
    AcquisitionError, acquire, _check_plan, _github, _ruten, fetch_json,
)

PLAN = {
    "schema": "hs.discovery_plan.v1", "target_architecture": "dual_esp32_touch_4p3_rs485",
    "max_pages": 2, "github_per_page": 2, "ruten_limit": 2,
    "jobs": [
        {"id": "mobile-development-friction", "problem_to_investigate": "work", "github_queries": ["mobile ssh"], "github_title_terms": ["keyboard", "ssh"], "ruten_queries": ["T-Deck"]},
        {"id": "another-mobile-job", "problem_to_investigate": "other", "github_queries": ["termux"], "github_title_terms": ["keyboard", "ssh"], "ruten_queries": ["T-Deck"]},
    ],
}
T = datetime(2026, 11, 6, 14, 0, tzinfo=timezone.utc)
ISSUE = {"number": 123, "html_url": "https://github.com/user/repo/issues/123",
         "title": "Virtual keyboard misses Ctrl keys", "updated_at": "2026-11-06T09:00:00Z"}
DETAIL = {"ProdId": "22642901029861", "ProdName": "T-Deck Plus", "PriceRange": [2999],
          "SoldQty": 3, "StockQty": 1}


def fake_get(url, headers):
    u = urlparse(url)
    if "/search/issues" in u.path:
        page = int(parse_qs(u.query)["page"][0])
        if page == 1:
            return {"total_count": 3, "items": [ISSUE, {**ISSUE, "number": 22, "html_url": "https://github.com/o/r/issues/22", "pull_request": {}}]}
        return {"total_count": 3, "items": [{**ISSUE, "number": 124, "html_url": "https://github.com/user/repo/issues/124"}]}
    if "/core/prod" in u.path:
        return {"Rows": [{"Id": DETAIL["ProdId"]}]}
    if "/prod" in u.path:
        return [DETAIL]
    raise AssertionError(url)


def test_producer_emits_bridge_compatible_signals_and_noncommercial_conclusions():
    a = acquire(PLAN, observed=T, getter=fake_get, github_token="test-token")
    assert a["schema"] == "hs.market_signals.v1"
    assert a["target_architecture"] == PLAN["target_architecture"]
    assert len(a["signals"]) == 3
    assert [x["id"] for x in a["signals"]] == sorted(x["id"] for x in a["signals"])
    assert all(set(x["discovery_job_ids"]) == {"mobile-development-friction", "another-mobile-job"} for x in a["signals"])
    assert all(x["kind"] in ("anecdotal_problem", "marketplace_asking_price") for x in a["signals"])
    assert all(x["relation"] != "exact" for x in a["signals"])
    assert all(x.get("count") is None for x in a["signals"])
    r = next(x for x in a["signals"] if x["id"].startswith("ruten"))
    assert r["source_metadata"]["seller_reported_cumulative_sold"] == 3
    assert r["source_metadata"]["asking_price_twd"] == 2999
    assert a["discovery"]["exact_product_customers_verified"] == 0
    assert not a["discovery"]["failures"]
    assert "2026-11-06T14:00:00Z" == r["observed_at_utc"]
    assert a == acquire(PLAN, observed=T, getter=fake_get, github_token="test-token")


def test_github_api_pagination_coverage_not_fabricated():
    a = acquire(PLAN, observed=T, getter=fake_get)
    g = [c for c in a["discovery"]["coverage"] if c["source"] == "github"]
    assert all(c["pages_fetched"] == 2 and c["rows_fetched"] == 3 and c["truncated"] is False for c in g)


def test_partial_provider_failure_is_evident_and_other_source_retained():
    def no_ruten(url, headers):
        if "ruten" in url:
            raise AcquisitionError("Ruten 503")
        return fake_get(url, headers)
    a = acquire(PLAN, observed=T, getter=no_ruten)
    assert len(a["signals"]) == 2
    assert a["discovery"]["acquisition_status"] == "partial"
    assert len(a["discovery"]["failures"]) == 2
    assert all(x["source"] == "ruten" for x in a["discovery"]["failures"])


def test_ruten_masked_or_variant_bad_price_is_discarded():
    assert _ruten({**DETAIL, "PriceRange": [993800]}, "2026-11-06T00:00:00Z") is None
    assert _ruten({**DETAIL, "PriceRange": [2999, 300]}, "2026-11-06T00:00:00Z") is None
    assert _ruten({**DETAIL, "ProdId": "../../etc"}, "2026-11-06T00:00:00Z") is None


def test_github_pr_and_unrelated_url_rejected():
    assert _github({**ISSUE, "pull_request": {}}, "2026-11-06T00:00:00Z") is None
    assert _github({**ISSUE, "html_url": "https://evil.invalid/issues/123"}, "2026-11-06T00:00:00Z") is None


def test_plan_validation_limits_and_unique_jobs():
    for update in ({"max_pages": 999}, {"github_per_page": True}, {"jobs": []},
                   {"target_architecture": "INVALID SPACE"},
                   {"jobs": [PLAN["jobs"][0], PLAN["jobs"][0]]}):
        with pytest.raises(AcquisitionError):
            _check_plan({**PLAN, **update})


def test_naive_timestamp_is_not_accepted():
    with pytest.raises(AcquisitionError, match="timezone"):
        acquire(PLAN, observed=datetime(2026, 11, 6), getter=fake_get)


def test_untrusted_api_origin_rejected_before_network():
    with pytest.raises(AcquisitionError, match="disallowed"):
        fetch_json("https://example.invalid/source", {})


def test_github_source_never_becomes_transaction_claim():
    a = acquire(PLAN, observed=T, getter=fake_get)
    gh = [x for x in a["signals"] if x["id"].startswith("github-")]
    assert gh and all(x["source_metadata"]["not_a_customer_interview"] for x in gh)
    assert all("verified_paid_order" != x["kind"] for x in a["signals"])


def test_irrelevant_public_issue_is_archived_but_not_promoted_to_market_signal():
    def noise(url, headers):
        if "/search/issues" in url:
            return {"total_count": 1, "items": [{**ISSUE, "title": "Auto-generated CI digest report"}]}
        return fake_get(url, headers)
    result = acquire(PLAN, observed=T, getter=noise)
    assert len([x for x in result["signals"] if x["kind"] == "anecdotal_problem"]) == 0
    raw = result["discovery"]["raw_candidates"]
    assert any(x["qualification_events"][0]["reason"] == "rejected_irrelevant_issue_title" for x in raw)


def test_marketplace_accessory_is_retained_in_raw_but_rejected_as_competitor_candidate():
    plan = {**PLAN, "jobs": [{**PLAN["jobs"][0], "ruten_exclude_terms": ["擴展板"]}]}
    def accessory(url, headers):
        if "/prod/" in url:
            return [{**DETAIL, "ProdName": "uConsole 擴展板"}]
        return fake_get(url, headers)
    result = acquire(plan, observed=T, getter=accessory)
    assert all(x["kind"] != "marketplace_asking_price" for x in result["signals"])
    assert any(x["kind"] == "marketplace_asking_price" for x in result["discovery"]["raw_candidates"])


def test_auditable_source_payload_matches_source_record_hash():
    from hardware_splicer.market_signal_acquisition import _digest
    a = acquire(PLAN, observed=T, getter=fake_get)
    for signal in a["signals"]:
        meta = signal["source_metadata"]
        assert _digest(meta["source_record"]) == meta["source_record_sha256"]
