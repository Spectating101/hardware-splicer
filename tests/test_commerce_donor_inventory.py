from __future__ import annotations

import copy
import csv
import io
import json
from pathlib import Path

import pytest

from hardware_splicer.commerce_donor_inventory import CommerceInventoryRefused, normalize_inventory, to_csv


SAMPLE = Path(__file__).resolve().parents[1] / "docs/research/commerce/tw_salvage_donor_listings_2026-10-19.json"


def source():
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def test_snapshot_preserves_actual_product_pages_and_discovery_only_boundary():
    result = normalize_inventory(source())
    assert len(result["records"]) == 17
    assert result["listing_count"] == 17
    assert len(result["family_counts"]) >= 8
    assert all(x["source_url"].startswith("https://www.ruten.com.tw/item/") for x in result["records"])
    assert all(x["status"] == "DISCOVERY_ONLY" and x["donor_contract"] is None for x in result["records"])
    assert all(x["physical_evidence"] is None and not x["authorized_for_fabrication"] for x in result["records"])


def test_source_prices_are_actual_asks_not_values_or_measured_boms():
    out = {x["listing_id"]:x for x in normalize_inventory(source())["records"]}
    assert out["ls2208"]["advertised_ask_twd_min"] == 50
    assert out["thecus-n2200"]["advertised_ask_twd_min"] == 350
    assert out["qnap-ts219pii"]["advertised_ask_twd_max"] == 650
    assert out["xiaomi-lds-spares"]["supply_kind"] == "spare_parts_not_ewaste"
    assert "laser" not in out["ls2208"]["parts_hypotheses_unverified"]  # Listing module hypotheses remain exact source-derived labels
    assert "scanner engine" in out["ls2208"]["parts_hypotheses_unverified"]


def test_export_csv_maintains_identical_ids_and_prices():
    expected = normalize_inventory(source())
    lines = list(csv.DictReader(io.StringIO(to_csv(expected))))
    assert len(lines) == expected["listing_count"]
    assert [r["listing_id"] for r in lines] == [r["listing_id"] for r in expected["records"]]
    assert lines[0]["advertised_ask_twd_min"] == "50"
    assert all(r["status"] == "DISCOVERY_ONLY" for r in lines)


@pytest.mark.parametrize("flag", [
    "condition_verified", "parts_tested", "hardware_interfaces_verified",
    "unit_in_custody", "human_authorized_purchase", "seller_contacted"
])
def test_cannot_promote_seller_claim_into_verified_donor(flag):
    raw = source()
    raw["records"][0][flag] = True
    with pytest.raises(CommerceInventoryRefused,match=flag):
        normalize_inventory(raw)


def test_duplicate_ids_refused():
    raw = source()
    raw["records"][1]["listing_id"] = raw["records"][0]["listing_id"]
    with pytest.raises(CommerceInventoryRefused,match="duplicated"):
        normalize_inventory(raw)


def test_price_variants_and_wrong_sale_claim_refused():
    raw = source()
    raw["records"][0]["asking_price_twd"] = {"min":500,"max":100,"type":"public_advertised_asking_not_final_quote"}
    with pytest.raises(CommerceInventoryRefused):
        normalize_inventory(raw)
    raw = source()
    raw["records"][0]["asking_price_twd"]["type"] = "completed_sale"
    with pytest.raises(CommerceInventoryRefused):
        normalize_inventory(raw)


def test_unrecognized_external_domain_refused():
    raw = source()
    raw["records"][0]["item_url"] = "https://example.com/item/123"
    with pytest.raises(CommerceInventoryRefused):
        normalize_inventory(raw)


def test_no_physical_use_claim_even_when_seller_says_functioned():
    result = normalize_inventory(source())
    qnap = next(r for r in result["records"] if r["listing_id"]=="qnap-ts219pii")
    assert "boot" in qnap["seller_condition_claim"]
    assert qnap["donor_contract"] is None
    assert qnap["authorized_for_fabrication"] is False
