"""Read-only normalization of public commerce donor observations.

A listing is a proposed *source*, never an owned, identified, tested,
safety-cleared donor. No scraping, internet access or project writes here.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from urllib.parse import urlparse
import csv
import io
import json
from typing import Any

SCHEMA = "hardware_splicer.commerce_donor_listings.v1"
EVIDENCE_TIER = "marketplace_seller_claim_only"


class CommerceInventoryRefused(ValueError):
    pass


def normalize_inventory(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or raw.get("schema_version") != SCHEMA:
        raise CommerceInventoryRefused("unsupported commerce inventory")
    records = raw.get("records")
    if not isinstance(records, list) or not records or len(records) > 500:
        raise CommerceInventoryRefused("bounded nonempty records required")
    known_ids = set()
    normalized = []
    for idx, item in enumerate(records):
        if not isinstance(item, Mapping):
            raise CommerceInventoryRefused(f"record {idx} not an object")
        key = item.get("listing_id")
        if not isinstance(key, str) or not key or key in known_ids:
            raise CommerceInventoryRefused(f"invalid or duplicated listing_id at {idx}")
        known_ids.add(key)
        url = item.get("item_url")
        if not isinstance(url, str):
            raise CommerceInventoryRefused("item_url missing")
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.netloc != "www.ruten.com.tw" or not parsed.path.startswith("/item/"):
            raise CommerceInventoryRefused(f"not a canonical Ruten item page: {key}")
        price = item.get("asking_price_twd")
        if not isinstance(price, Mapping):
            raise CommerceInventoryRefused(f"missing ask range: {key}")
        low, high = price.get("min"), price.get("max")
        if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in (low, high)) or low > high:
            raise CommerceInventoryRefused(f"invalid ask range: {key}")
        if price.get("type") != "public_advertised_asking_not_final_quote":
            raise CommerceInventoryRefused(f"unverified price described as transaction: {key}")
        if item.get("evidence_tier") != EVIDENCE_TIER or item.get("engineering_authority") != "DISCOVERY_ONLY":
            raise CommerceInventoryRefused(f"unauthorized evidence promotion: {key}")
        for truth in ("condition_verified", "parts_tested", "hardware_interfaces_verified",
                      "unit_in_custody", "human_authorized_purchase", "seller_contacted"):
            if item.get(truth) is not False:
                raise CommerceInventoryRefused(f"unproven flag {truth}: {key}")
        ideas = item.get("potential_hardware_modules_NOT_VERIFIED")
        if not isinstance(ideas, list) or not ideas or any(not isinstance(x, str) or not x for x in ideas):
            raise CommerceInventoryRefused(f"invalid potential hardware modules: {key}")
        for field in ("device_family", "title_translated", "seller_condition_and_inclusion_claim",
                      "unknowns_and_seller_questions", "supply_kind"):
            if not isinstance(item.get(field), str) or not item[field]:
                raise CommerceInventoryRefused(f"missing required seller/context field {field}: {key}")
        # Keep the source text in exactly its low-authority role. Do not
        # produce donor contract, wiring or confirmed component inventory.
        normalized.append({
            "listing_id":key,
            "source_url":url,
            "family":item["device_family"],
            "supply_kind":item["supply_kind"],
            "advertised_ask_twd_min":low,
            "advertised_ask_twd_max":high,
            "seller_condition_claim":item["seller_condition_and_inclusion_claim"],
            "parts_hypotheses_unverified":list(ideas),
            "inspection_questions":item["unknowns_and_seller_questions"],
            "status":"DISCOVERY_ONLY",
            "donor_contract":None,
            "physical_evidence":None,
            "authorized_for_fabrication":False,
        })
    count = Counter(row["family"] for row in normalized)
    return {
        "schema_version":"hardware_splicer.commerce_donor_discovery.v1",
        "observed_date":raw.get("as_of"),
        "listing_count":len(normalized),
        "family_counts":dict(sorted(count.items())),
        "scope":"seller-claimed marketplace listing, NOT an HS verified/owned donor",
        "records":normalized,
    }


def to_csv(discovery: Mapping[str, Any]) -> str:
    rows = discovery["records"]
    fields = ["listing_id", "family", "supply_kind", "advertised_ask_twd_min",
              "advertised_ask_twd_max", "seller_condition_claim",
              "parts_hypotheses_unverified", "inspection_questions", "source_url", "status"]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        row = dict(row)
        row["parts_hypotheses_unverified"] = " | ".join(row["parts_hypotheses_unverified"])
        writer.writerow(row)
    return out.getvalue()
