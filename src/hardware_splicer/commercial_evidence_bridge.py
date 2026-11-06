"""Source-conservative evidence bridge from market agents into HS engineering gates.

Inputs are *records produced elsewhere*. The bridge does not browse or verify
customer identity, acquire hardware, or authorize manufacturing. It prevents
pricing, market interest and CAD success from being promoted into paid demand.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
from typing import Any, Mapping
from urllib.parse import urlparse

SCHEMA = "hardware_splicer.commercial_evidence_handoff.v1"
MARKET_SCHEMA = "hs.build_vs_buy.v1"
SIGNAL_KINDS = {
    "crowdfunding_pledge",
    "developer_activity",
    "marketplace_asking_price",
    "marketplace_reported_cumulative_sold",
    "anecdotal_problem",
    "interview_expression",
    "verified_paid_order",
}
SIGNAL_RELATION = {"exact", "adjacent", "general"}
MAX_AGE_DAYS = 30


class CommercialEvidenceError(ValueError):
    """Rejects malformed/unproven data instead of silently repairing it."""


def _read_dict(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise CommercialEvidenceError(f"{path.name}: expected JSON object")
    return raw


def _iso_date(value: Any, label: str) -> date:
    if not isinstance(value, str) or not value:
        raise CommercialEvidenceError(f"{label}: missing date")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CommercialEvidenceError(f"{label}: invalid date") from exc
    if parsed.tzinfo is None:
        raise CommercialEvidenceError(f"{label}: timezone required")
    return parsed.astimezone(timezone.utc).date()


def _https_url(url: Any) -> bool:
    if not isinstance(url, str):
        return False
    u = urlparse(url)
    return u.scheme == "https" and bool(u.hostname) and not u.username and not u.password


def _validate_money(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not (0 <= value < 1e10):
        raise CommercialEvidenceError(f"{label}: invalid nonnegative monetary value")
    return float(value)


def _price_integrity(market: Mapping[str, Any]) -> dict[str, Any]:
    """Recheck priced BOM arithmetic; do not change PR291's original estimates."""
    comp = market.get("comparison")
    if not isinstance(comp, dict):
        raise CommercialEvidenceError("missing pricing comparison")
    lines = market.get("lines")
    if not isinstance(lines, list) or not lines:
        raise CommercialEvidenceError("missing priced BOM lines")
    res: dict[str, Any] = {"matched": False, "listed_input_assumptions": []}
    for mode in ("min", "p25", "median"):
        subtotal = 0.0
        missing: list[str] = []
        for line in lines:
            if line.get("role", "build") != "build":
                continue
            lineid = line.get("id")
            if not isinstance(lineid, str) or not lineid:
                raise CommercialEvidenceError("BOM line has no identity")
            qty = line.get("qty", 1)
            if isinstance(qty, bool) or not isinstance(qty, (int, float)) or not (0 < qty <= 1000):
                raise CommercialEvidenceError("invalid line quantity")
            cost = line.get("fixed_price_twd")
            if cost is not None:
                _validate_money(cost, f"{lineid}.fixed_price")
                if not str(line.get("fixed_price_basis") or "").strip():
                    raise CommercialEvidenceError(f"{lineid}: unlabeled fixed price")
                res["listed_input_assumptions"].append(lineid)
            else:
                amounts = line.get("unit_price_twd")
                if not isinstance(amounts, dict):
                    raise CommercialEvidenceError(f"{lineid}: missing unit price")
                cost = amounts.get(mode)
                if cost is None:
                    missing.append(lineid)
                    continue
                _validate_money(cost, f"{lineid}.{mode}")
            subtotal += float(cost) * qty
        claimed = comp.get(f"build_{mode}_twd")
        if missing:
            if claimed is not None:
                raise CommercialEvidenceError("unpriced lines cannot have completed build total")
        else:
            _validate_money(claimed, f"build_{mode}_twd")
            # Line-level p25/median are already rounded by the separate agent.
            if abs(round(subtotal) - round(float(claimed))) > max(3, len(lines)):
                raise CommercialEvidenceError(f"build_{mode}_twd is inconsistent with source BOM")
        res[mode] = {"recomputed_twd": round(subtotal) if not missing else None,
                     "claimed_twd": claimed, "unpriced": missing}
    res["matched"] = True
    res["listed_input_assumptions"] = sorted(set(res["listed_input_assumptions"]))
    return res


def evaluate(
    *,
    market_bytes: bytes,
    pinned_market_sha256: str,
    source_ref: str,
    signals: Mapping[str, Any],
    hs_release: Mapping[str, Any],
    hs_budget: Mapping[str, Any],
    as_of: date,
    reference_architecture: str,
    target_architecture: str,
) -> dict[str, Any]:
    """Build a deterministic, reviewable research task handoff.

    Note: a source URL is provenance, not an independent verification of its
    content. Even an alleged paid-order signal cannot authorize a launch.
    """
    digest = sha256(market_bytes).hexdigest()
    if not isinstance(pinned_market_sha256, str) or digest != pinned_market_sha256:
        raise CommercialEvidenceError("source snapshot bytes are not pinned to declared sha256")
    if not source_ref or len(source_ref) > 250:
        raise CommercialEvidenceError("missing pinned upstream ref")
    try:
        market = json.loads(market_bytes)
    except (ValueError, UnicodeDecodeError) as exc:
        raise CommercialEvidenceError("invalid source snapshot") from exc
    if not isinstance(market, dict) or market.get("schema") != MARKET_SCHEMA:
        raise CommercialEvidenceError("unsupported market snapshot schema")
    captured = _iso_date(market.get("captured_utc"), "pricing snapshot")
    age = (as_of - captured).days
    if age < 0:
        raise CommercialEvidenceError("pricing source timestamp is in future")
    if not isinstance(signals, Mapping) or signals.get("schema") != "hs.market_signals.v1":
        raise CommercialEvidenceError("unsupported signal schema")
    if signals.get("target_architecture") != target_architecture:
        raise CommercialEvidenceError("signal pack target architecture mismatch")
    if reference_architecture == target_architecture:
        # Explicitly require an exact architecture match. It cannot be inferred
        # just because both market casefiles contain the word "cyberdeck".
        raise CommercialEvidenceError("this cross-product comparison needs distinct architecture IDs")
    if not isinstance(hs_release, Mapping) or not isinstance(hs_budget, Mapping):
        raise CommercialEvidenceError("missing HS engineering evidence")
    if hs_release.get("requested_state") != "operationally_authorized":
        raise CommercialEvidenceError("expected HS operational release assessment")
    release_state = hs_release.get("achieved_state")
    if release_state not in {"concept","design_ready","build_ready","bench_ready","operationally_authorized"}:
        raise CommercialEvidenceError("unrecognized HS release state")
    blockers = hs_release.get("blockers")
    if not isinstance(blockers, list):
        raise CommercialEvidenceError("missing release blockers")
    if release_state == "operationally_authorized" and blockers:
        raise CommercialEvidenceError("contradictory HS release success with blockers")
    if hs_budget.get("quote_obtained") is not False or hs_budget.get("parts_obtained") is not False:
        raise CommercialEvidenceError("current product budget is expected to remain an unquoted study")
    target_budget = _validate_money(hs_budget.get("budget_scenario_twd"), "HS target budget")
    if not isinstance(market.get("buy_alternatives"), list):
        raise CommercialEvidenceError("missing finished alternative price evidence")
    result_signals = []
    signal_ids = set()
    for item in signals.get("signals", []):
        if not isinstance(item, Mapping):
            raise CommercialEvidenceError("invalid market signal")
        sid, kind, relation = item.get("id"), item.get("kind"), item.get("relation")
        if not isinstance(sid, str) or not sid or sid in signal_ids:
            raise CommercialEvidenceError("duplicate or empty signal ID")
        signal_ids.add(sid)
        if kind not in SIGNAL_KINDS or relation not in SIGNAL_RELATION:
            raise CommercialEvidenceError(f"{sid}: unknown signal taxonomy")
        if not _https_url(item.get("source_url")):
            raise CommercialEvidenceError(f"{sid}: public HTTPS source required")
        observed = _iso_date(item.get("observed_at_utc"), f"{sid}.observed_at")
        if observed > as_of:
            raise CommercialEvidenceError(f"{sid}: future-dated signal")
        count = item.get("count")
        if count is not None and (isinstance(count, bool) or not isinstance(count, int) or count < 0):
            raise CommercialEvidenceError(f"{sid}: invalid count")
        # "Crowdfunding pledge" is adjacent paid interest, not verified delivery
        # or a transfer of market demand to our exact product.
        if kind == "verified_paid_order":
            # An online URL and a self-asserted count are not verifiable
            # transaction evidence. Retain source, but forbid readiness.
            strength = "unverified_transaction_claim_requires_independent_review"
        elif kind == "crowdfunding_pledge":
            strength = "adjacent_paid_interest" if relation == "adjacent" else "unverified_exact_product_pledge"
        elif kind in {"marketplace_asking_price", "marketplace_reported_cumulative_sold"}:
            strength = "marketplace_proxy_not_sales_velocity"
        elif kind == "developer_activity":
            strength = "workflow_adoption_not_hardware_demand"
        else:
            strength = "qualitative_interest_not_purchase"
        result_signals.append({
            "id": sid, "kind": kind, "relation": relation,
            "source_url": item["source_url"],
            "observed_at_utc": item["observed_at_utc"],
            "count_if_reported": count, "interpretation": strength,
            "independently_verified": False,
        })
    if not result_signals:
        raise CommercialEvidenceError("no provenance-bearing demand signals")
    price_check = _price_integrity(market)
    alternatives = []
    for a in market["buy_alternatives"]:
        if not isinstance(a, dict):
            raise CommercialEvidenceError("invalid alternative")
        ident = a.get("id")
        if not isinstance(ident, str) or not ident:
            raise CommercialEvidenceError("alternative missing ID")
        kept = a.get("listings_kept")
        if isinstance(kept, bool) or not isinstance(kept, int) or kept < 0:
            raise CommercialEvidenceError("invalid competitor listing count")
        unit = a.get("unit_price_twd")
        if not isinstance(unit, dict):
            raise CommercialEvidenceError("missing competitor price")
        median = unit.get("p25") or unit.get("min")
        if median is not None:
            _validate_money(median, f"{ident}.price")
        with_sales = a.get("with_sales", 0)
        if isinstance(with_sales, bool) or not isinstance(with_sales, int) or with_sales < 0 or with_sales > kept:
            raise CommercialEvidenceError("invalid marketplace reported-sales listing count")
        cheapest = a.get("cheapest") or []
        if cheapest and not all(_https_url(row.get("url")) for row in cheapest):
            raise CommercialEvidenceError("source listing without public URL")
        alternatives.append({
            "id": ident, "source_architecture": reference_architecture,
            "listed_p25_twd": median, "sample_listings_kept": kept,
            "listings_reporting_cumulative_sales": with_sales,
            "sold_units_verified": False, "evidence_type": "seller_asking_prices",
            "not_equivalent_to_target_architecture": True,
            "example_listing_urls": [row["url"] for row in cheapest[:2]],
        })
    pipeline_gates = [
        {"gate":"qualified_buyer_demand","status":"unverified",
         "why":"No independently verified price-specific purchase commitments for the exact target product."},
        {"gate":"sourcing","status":"unverified",
         "why":"HS target BOM contains estimates, no supplier quotes or actual deliveries."},
        {"gate":"physical_product","status":"blocked" if blockers or release_state != "operationally_authorized" else "needs_commercial_review",
         "why":f"HS engineering release is {release_state} with {len(blockers)} blockers."},
        {"gate":"market_snapshot","status":"stale" if age > MAX_AGE_DAYS else "usable_for_price_research",
         "why":f"Competitor/parts data is {age} days old; asking prices are not completed transactions."},
        {"gate":"legal_fulfillment","status":"unverified",
         "why":"No commercial certification, import/export eligibility, warranty or fulfillment approval supplied."},
    ]
    tasks = [
        {"id":"market-live-acquisition","owner":"market_research_agent",
         "evidence_needed":"Independent fresh marketplace sources, exact product/variant identity, durable URL/UTC stamp, sold volume over time; no invented throughput."},
        {"id":"customer-price-interviews","owner":"customer_discovery_agent",
         "evidence_needed":"Qualified target-buyer interviews and independently checked price-specific purchase commitments; keep Taiwan and Indonesia distinct."},
        {"id":"supplier-bom-quote","owner":"sourcing_agent",
         "evidence_needed":"Delivered exact-SKU quote, availability, shipping, tax, warranty and compliant sale route."},
        {"id":"ssh-cyberdeck-bench","owner":"hs_engineering_agent",
         "evidence_needed":"Real authenticated SSH, accessible terminal/agent UI, physical fit, power/hinge, and manufacturer pin evidence."},
    ]
    return {
        "schema": SCHEMA, "as_of_utc": as_of.isoformat(),
        "target_product": target_architecture,
        "reference_product": reference_architecture,
        "not_same_product": True,
        "market_snapshot": {
            "source_ref": source_ref, "sha256": digest, "captured_utc": market["captured_utc"],
            "age_days": age, "product": market.get("product"),
            "notes": market.get("boundary"), "validation": price_check,
            "reference_build_p25_twd": market["comparison"]["build_p25_twd"],
            "reference_only_not_target_cost": True,
        },
        "target_hs_estimated_parts_twd": target_budget,
        "hs_engineering": {
            "achieved_state": release_state, "requested_state": hs_release["requested_state"],
            "blocker_count": len(blockers),
            "blocker_codes": [x.get("code") for x in blockers],
            "operational_authorization_proved": False,
        },
        "alternatives": alternatives,
        "market_signals": result_signals,
        "verified_exact_customer_orders": 0,
        "commercial_readiness": "RESEARCH_AND_PROTOTYPE_ONLY",
        "safe_to_order_inventory": False,
        "safe_to_claim_market_demand_for_exact_product": False,
        "gates": pipeline_gates,
        "next_agent_tasks": tasks,
        "limitations": [
            "Market data ingestion is from other agents' snapshots, not live autonomous web discovery.",
            "A marketplace listing's SoldQty is not independently verified or time-bounded sales velocity.",
            "Adjacent crowdfunding backers cannot be converted to this product's demand.",
            "The Pi5 pricing snapshot and the dual-ESP32 concept are NOT interchangeable BOMs.",
            "No customer interviews, verified orders, product assembly, shipping or certification were performed.",
        ],
    }


def from_files(
    *, market_path: Path, pinned_market_sha256: str, source_ref: str,
    signals_path: Path, hs_release_path: Path, hs_budget_path: Path,
    hs_machine_project_path: Path,
    as_of: date, reference_architecture: str, target_architecture: str,
) -> dict[str, Any]:
    from .machine_project import MachineProject, ReleaseState

    # Recalculate the actual canonical HS authority gate; a market agent must
    # not be able to promote itself by editing an assessment JSON file.
    project = MachineProject.model_validate(_read_dict(hs_machine_project_path))
    if project.metadata.get("physical_items_count") != 0:
        raise CommercialEvidenceError("pilot assumptions changed; requalify physical evidence")
    fresh_assessment = project.assess_release(ReleaseState.OPERATIONALLY_AUTHORIZED).model_dump(mode="json")
    if fresh_assessment != _read_dict(hs_release_path):
        raise CommercialEvidenceError("stored HS release evidence differs from canonical recomputation")
    return evaluate(
        market_bytes=market_path.read_bytes(),
        pinned_market_sha256=pinned_market_sha256,
        source_ref=source_ref,
        signals=_read_dict(signals_path),
        hs_release=fresh_assessment,
        hs_budget=_read_dict(hs_budget_path),
        as_of=as_of,
        reference_architecture=reference_architecture,
        target_architecture=target_architecture,
    )
