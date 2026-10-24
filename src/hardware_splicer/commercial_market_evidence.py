"""Native-currency transaction evidence for market-level hardware arbitrage.

An advertisement is not a sold comparable; a 'sold' badge is not a verified
settlement. Require exact SKU/variant, evidence of amount actually exchanged,
local market, recorded date, and identifiable cost basis before promotion.
"""
from __future__ import annotations

from datetime import date
from math import isfinite
from statistics import median
from typing import Any, Mapping

SCHEMA = "hardware_splicer.market_evidence.v1"
ALLOWED_CURRENCY = {"TWD", "CNY", "IDR", "USD"}
ASK_KINDS = {"advertised_ask", "supplier_list_price"}
SETTLED_KINDS = {"verified_settled_sale", "verified_paid_purchase"}
EVIDENCE_KINDS = ASK_KINDS | SETTLED_KINDS | {
    "seller_quote", "supplier_quotation", "sold_marker_without_price_proof",
}


def _price(row: Mapping[str, Any], errors: list[str], i: int) -> float | None:
    price = row.get("unit_price")
    if isinstance(price, bool):
        errors.append(f"invalid_price:{i}")
        return None
    try:
        x = float(price)
    except (TypeError, ValueError):
        errors.append(f"invalid_price:{i}")
        return None
    if not isfinite(x) or x < 0:
        errors.append(f"invalid_price:{i}")
        return None
    return x


def _day(raw: Any, errors: list[str], index: int) -> str | None:
    if not isinstance(raw, str):
        errors.append(f"invalid_observed_date:{index}")
        return None
    try:
        value = date.fromisoformat(raw)
    except ValueError:
        errors.append(f"invalid_observed_date:{index}")
        return None
    return value.isoformat()


def evaluate_market_evidence(
    evidence: Mapping[str, Any], *,
    candidate_id: str,
    market: str,
    currency: str,
    exact_model: str,
    latest_day: str,
    lookback_days: int = 120,
) -> dict[str, Any]:
    """Distinguish market asks and receipt-backed comparable prices.

    The returned sold median is descriptive, not a buyer commitment or an
    independently authenticated claim; independent receipt review is required.
    """
    errors: list[str] = []
    if not isinstance(evidence, Mapping) or evidence.get("schema_version") != SCHEMA:
        errors.append("unsupported_evidence_schema")
    if currency not in ALLOWED_CURRENCY:
        errors.append("unsupported_currency")
    try:
        cutoff = date.fromisoformat(latest_day)
    except (TypeError, ValueError):
        errors.append("invalid_latest_day")
        cutoff = None
    if isinstance(lookback_days, bool) or not isinstance(lookback_days, int) or lookback_days < 1:
        errors.append("invalid_lookback_days")
    if not all(isinstance(v, str) and v.strip() for v in (candidate_id, market, exact_model)):
        errors.append("missing_identity")
    if errors:
        return {"status": "INVALID", "errors": errors, "sold_comparables": [],
                "ask_observations": [], "sold_median": None, "purchase_authorized": False}

    from datetime import timedelta
    oldest = cutoff - timedelta(days=lookback_days)
    seen_ids: set[str] = set()
    sold: list[dict[str, Any]] = []
    asks: list[dict[str, Any]] = []
    holds: list[dict[str, Any]] = []
    raw_records = evidence.get("records")
    if not isinstance(raw_records, list) or len(raw_records) > 2000:
        errors.append("missing_or_unbounded_records")
        raw_records = []
    for i, item in enumerate(raw_records):
        if not isinstance(item, Mapping):
            errors.append(f"invalid_record:{i}")
            continue
        eid = item.get("evidence_id")
        if not isinstance(eid, str) or not eid or eid in seen_ids:
            errors.append(f"missing_or_duplicate_id:{i}")
            continue
        seen_ids.add(eid)
        kind = item.get("event_kind")
        if kind not in EVIDENCE_KINDS:
            errors.append(f"invalid_event_kind:{i}")
            continue
        price = _price(item, errors, i)
        observed = _day(item.get("observed_date"), errors, i)
        ref = str(item.get("source_ref") or "").strip()
        if not ref:
            errors.append(f"missing_source_ref:{i}")
            continue
        if price is None or observed is None:
            continue
        if item.get("currency") != currency:
            # Keep other currencies out of this evaluation; never FX silently.
            holds.append({"evidence_id": eid, "reason": "wrong_currency"})
            continue
        if item.get("market") != market:
            holds.append({"evidence_id": eid, "reason": "wrong_market"})
            continue
        if observed > latest_day or observed < oldest.isoformat():
            holds.append({"evidence_id": eid, "reason": "outside_date_window"})
            continue
        if item.get("exact_model") != exact_model or item.get("variant_verified") is not True:
            holds.append({"evidence_id": eid, "reason": "model_or_variant_unverified"})
            continue
        if item.get("condition_class") not in {"working_tested", "broken", "untested"}:
            holds.append({"evidence_id": eid, "reason": "condition_missing"})
            continue
        normalized = {
            "evidence_id": eid, "unit_price": price, "currency": currency,
            "observed_date": observed, "event_kind": kind, "source_ref": ref,
            "condition_class": item["condition_class"],
        }
        if kind == "sold_marker_without_price_proof":
            # Even marketplace "sold" badges are NOT observations of paid
            # transaction amounts. Keep them separate from ordinary price asks.
            holds.append({"evidence_id": eid, "reason": "unverified_sold_marker"})
            continue
        if kind in ASK_KINDS or kind in {"seller_quote", "supplier_quotation"}:
            asks.append(normalized)
            continue
        if item.get("settlement_verified") is not True or not str(item.get("settlement_reference") or "").strip():
            holds.append({"evidence_id": eid, "reason": "settlement_not_verified"})
            continue
        if kind == "verified_settled_sale" and item["condition_class"] != "working_tested":
            holds.append({"evidence_id": eid, "reason": "wrong_condition_for_working_comp"})
            continue
        sold.append(normalized)
    if errors:
        status = "INVALID"
    elif sold:
        status = "SOLD_COMPS_TO_AUDIT"
    else:
        status = "NO_VERIFIED_SOLD_COMPS"
    sold_sales = [row for row in sold if row["event_kind"] == "verified_settled_sale"]
    return {
        "schema_version": "hardware_splicer.market_comparable_screen.v1",
        "candidate_id": candidate_id,
        "market": market,
        "currency": currency,
        "exact_model": exact_model,
        "cutoff_day": latest_day,
        "status": status,
        "errors": sorted(set(errors)),
        "sold_comparables": sold_sales,
        "verified_acquisition_records": [row for row in sold if row["event_kind"] == "verified_paid_purchase"],
        "ask_observations": asks,
        "excluded_evidence": holds,
        "sold_median": round(median([row["unit_price"] for row in sold_sales]), 2) if sold_sales and not errors else None,
        "transaction_pricing_verified_in_source": bool(sold_sales) and not errors,
        "independent_receipt_review_complete": False,
        "buyer_committed": False,
        "purchase_authorized": False,
    }
