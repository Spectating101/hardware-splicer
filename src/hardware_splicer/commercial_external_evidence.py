"""Import live-indexed marketplace/catalog observations WITHOUT manufacturing margins.

Preserves provenance and the difference between a marketplace offer, a stocked
retailer, a manufacturer datasheet, secondary commentary and real transactions.
No observations in this corpus are sold comparables or qualified supplier quotes.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import date
from typing import Any, Mapping

SCHEMA = "hardware_splicer.external_market_observations.v1"
KIND = {
    "used_finished_item_ask",
    "parts_or_unverified_device_ask",
    "replacement_part_list_price",
    "oem_component_catalog_price",
    "commodity_competitor_catalog_price",
    "secondary_market_commentary",
}
CURRENCY = {"Taiwan": "TWD", "China": "CNY", "Indonesia": "IDR"}
NO_PRICE = "NOT_TRANSACTION_READY"


def evaluate_external_observations(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping) or payload.get("schema_version") != SCHEMA:
        return {"status": "INVALID", "errors": ["wrong_external_observations_schema"],
                "records": [], "procurement_authorized": False}
    records = payload.get("records")
    if not isinstance(records, list) or not records or len(records) > 500:
        return {"status": "INVALID", "errors": ["empty_or_unbounded_observations"],
                "records": [], "procurement_authorized": False}
    errors: list[str] = []
    seen: set[str] = set()
    output = []
    for i, row in enumerate(records):
        if not isinstance(row, Mapping):
            errors.append(f"invalid_record:{i}")
            continue
        ident = row.get("evidence_id")
        if not isinstance(ident, str) or not ident or ident in seen:
            errors.append(f"duplicate_or_missing_evidence_id:{i}")
            continue
        seen.add(ident)
        cid = row.get("candidate_id")
        market = row.get("market")
        currency = row.get("currency")
        kind = row.get("kind")
        if not isinstance(cid, str) or not cid:
            errors.append(f"missing_candidate_id:{ident}")
        if market not in CURRENCY or currency != CURRENCY.get(market):
            errors.append(f"currency_or_market_mismatch:{ident}")
        if kind not in KIND:
            errors.append(f"unknown_observation_kind:{ident}")
        source = row.get("source_url")
        if not isinstance(source, str) or not source.startswith("https://"):
            errors.append(f"missing_source_url:{ident}")
        try:
            timestamp = date.fromisoformat(row.get("research_checked_date") or "")
        except (ValueError, TypeError):
            errors.append(f"invalid_check_date:{ident}")
            timestamp = None
        amounts = []
        for key in ("price_min", "price_max"):
            raw = row.get(key)
            if raw is None and key == "price_max" and kind == "secondary_market_commentary":
                amounts.append(None)
                continue
            if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw) or raw < 0:
                errors.append(f"invalid_price:{ident}:{key}")
                amounts.append(None)
            else:
                amounts.append(float(raw))
        if amounts[0] is not None and amounts[1] is not None and amounts[0] > amounts[1]:
            errors.append(f"price_range_reversed:{ident}")
        for forbidden in ("verified_completed_sale", "verified_supplier_quote", "verified_stock", "physical_qualified"):
            if row.get(forbidden) is not False:
                errors.append(f"illegally_promoted_evidence:{ident}:{forbidden}")
        if not isinstance(row.get("source_quality"), str) or not row["source_quality"]:
            errors.append(f"missing_source_quality:{ident}")
        if not isinstance(row.get("qualification"), str) or not row["qualification"]:
            errors.append(f"missing_qualification:{ident}")
        output.append({
            "evidence_id": ident,
            "candidate_id": cid,
            "market": market,
            "currency": currency,
            "kind": kind,
            "price_min": amounts[0],
            "price_max": amounts[1],
            "source_url": source,
            "source_title": row.get("source_title"),
            "source_quality": row.get("source_quality"),
            "qualification": row.get("qualification"),
            "research_checked_date": timestamp.isoformat() if timestamp else None,
            "transaction_status": NO_PRICE,
            "verified_completed_sale": False,
            "verified_stock": False,
            "procurement_authorized": False,
        })
    if errors:
        return {"status": "INVALID", "errors": sorted(set(errors)),
                "records": output, "procurement_authorized": False}

    by_candidate: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for obs in output:
        by_candidate[obs["candidate_id"]].append(obs)
    return {
        "schema_version": "hardware_splicer.external_market_diligence.v1",
        "status": "RESEARCH_LEADS_ONLY",
        "total_observations": len(output),
        "distinct_candidates_with_observations": len(by_candidate),
        "market_counts": dict(Counter(r["market"] for r in output)),
        "type_counts": dict(Counter(r["kind"] for r in output)),
        "by_candidate": dict(by_candidate),
        "records": output,
        "errors": [],
        "verified_settled_sales": 0,
        "verified_supplier_quotes": 0,
        "verified_stock": 0,
        "procurement_authorized": False,
        "caveats": [
            "marketplace asking prices and seller stock claims are not completed transactions",
            "indexed web pages may lag seller updates and listing stock",
            "one seller may cross-list the same device on multiple platforms",
            "components and finished systems cannot be compared as substitutable goods",
            "no landed cost, warranty, repair yield, taxes, freight or approved use is established",
        ],
    }
