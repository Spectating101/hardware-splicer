"""Research-only Taiwan institutional surplus auction eligibility screening.

Unlike ordinary secondhand goods, auctioned 'approved scrap' may require a
licensed recycling company and deposit. This layer NEVER authorizes bidding.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping

SCHEMA = "hardware_splicer.institutional_disposal_sources.v1"


def evaluate_disposal_sources(payload: Mapping[str, Any], *, as_of: str) -> dict[str, Any]:
    if payload.get("schema_version") != SCHEMA:
        raise ValueError("unsupported disposal feed schema")
    today = date.fromisoformat(as_of)
    rows = payload.get("records")
    if not isinstance(rows, list) or not rows:
        raise ValueError("no auction records")
    out = []
    seen = set()
    for r in rows:
        if not isinstance(r, Mapping):
            raise ValueError("malformed auction")
        uid = r.get("source_id")
        if not isinstance(uid, str) or not uid or uid in seen:
            raise ValueError("duplicate/empty auction ID")
        seen.add(uid)
        if r.get("market") != "Taiwan" or not str(r.get("source_url") or "").startswith("https://"):
            raise ValueError("auction requires native market and source URL")
        when = date.fromisoformat(r["event_date"]) if r.get("event_date") else None
        if when and when <= today:
            reason = "AUCTION_EVENT_NOT_FUTURE"
            status = "CLOSED_OR_PAST_NOTICE"
        elif r.get("eligibility", {}).get("recycling_license_required") is True:
            reason = "LICENSED_WASTE_RECYCLER_AND_REGISTRATION_REQUIRED"
            status = "LICENSE_ELIGIBILITY_HOLD"
        elif r.get("event_status") == "DISCOVERY_FEED":
            reason = "NOT_A_SPECIFIC_AUCTION_LOT"
            status = "DISCOVERY_FEED_ONLY"
        else:
            reason = "ELIGIBILITY_AND_OFFER_REQUIRE_DIRECT_VERIFICATION"
            status = "NOT_YET_QUALIFIED"
        out.append({
            "source_id": uid, "agency": r.get("agency"), "source_url": r["source_url"],
            "event_date": r.get("event_date"), "event_status": r.get("event_status"),
            "eligibility": r.get("eligibility"),
            "reserve_price_twd_bulk_not_units": r.get("reserve_price_twd"),
            "deposit_twd": r.get("bid_deposit_twd"),
            "asset_class": r.get("asset_class"),
            "status": status, "reason": reason,
            "purchase_authorized": False, "bid_authorized": False,
        })
    return {
        "schema_version": "hardware_splicer.institutional_disposal_diligence.v1",
        "status": "SOURCE_RESEARCH_ONLY",
        "count": len(out),
        "auctions": out,
        "licensed_waste_handling_authorized": False,
        "bid_authorized": False,
        "warnings": [
            "expired auction notices are not purchasable inventory",
            "one bulk reserve price is not a finished-item, component or scrap-unit price",
            "some waste/scrap bids require a qualified recycling business",
            "any lots require legal eligibility, handling and transport review",
        ],
    }
