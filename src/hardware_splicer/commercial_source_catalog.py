"""Typed imports for pinned, unverified local/regional commercial source records.

Source data is not a current marketplace listing, supplier quote or confirmed sale.
Do not multiply branch snapshots into fabricated transaction counts.
"""
from __future__ import annotations

from typing import Any, Mapping


def _source_ref(data: Mapping[str, Any]) -> str:
    return str(data.get("source_pr_url") or data.get("source_original_path") or "unattributed")


def normalize_historical_regional_scan(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Import PR #109's *six* product-route hypotheses in TWD/CNY."""
    if report.get("schema") != "hardware_splicer.regional_product_factory_scan.v1":
        raise ValueError("unsupported historical regional scan")
    results: list[dict[str, Any]] = []
    for key, currency in (("taiwan", "TWD"), ("mainland_china", "CNY")):
        region = report.get(key)
        if not isinstance(region, Mapping):
            raise ValueError(f"missing_regional_section:{key}")
        options = region.get("candidate_routes")
        if not isinstance(options, list):
            raise ValueError(f"missing_candidate_routes:{key}")
        for record in options:
            if not isinstance(record, Mapping):
                raise ValueError("invalid regional route")
            identifier = str(record.get("id") or "").strip()
            if not identifier:
                raise ValueError("missing regional candidate id")
            name = str(record.get("working_name") or "").strip()
            if not name:
                raise ValueError("missing regional working name")
            price = record.get("illustrative_target_price_twd")
            if price is None:
                price = record.get("illustrative_target_price_twd_range")
            if price is None:
                price = record.get("illustrative_target_price_rmb")
            if price is None:
                price = record.get("illustrative_target_price_rmb_range")
            cogs = record.get("illustrative_effective_cogs_twd")
            if cogs is None:
                cogs = record.get("illustrative_effective_cogs_twd_range")
            if cogs is None:
                cogs = record.get("illustrative_effective_cogs_rmb")
            if cogs is None:
                cogs = record.get("illustrative_effective_cogs_rmb_range")
            if price is None or cogs is None:
                raise ValueError(f"missing regional price or cost hypothesis:{identifier}")
            def verify_hypothesis_number(v: Any) -> float | list[float]:
                if isinstance(v, list):
                    if len(v) != 2 or any(isinstance(x, bool) or not isinstance(x, (int, float)) or x < 0 for x in v) or v[0] > v[1]:
                        raise ValueError("invalid regional range")
                    return list(v)
                if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
                    raise ValueError("invalid regional amount")
                return v
            results.append({
                "candidate_id": identifier,
                "working_name": name,
                "market": key,
                "currency": currency,
                "origin": "product_factory_regional_hypothesis",
                "donor_thesis": record.get("donor"),
                "transformation_thesis": record.get("transformation"),
                "indicative_ask_not_sold_price": {
                    "amount_or_range": verify_hypothesis_number(price),
                    "evidence_class": "HYPOTHESIS",
                    "reference": _source_ref(report),
                },
                "indicative_cogs_not_supplier_quote": {
                    "amount_or_range": verify_hypothesis_number(cogs),
                    "evidence_class": "HYPOTHESIS",
                    "reference": _source_ref(report),
                },
                "source_ref": _source_ref(report),
                "source_date": report.get("observed_at"),
                "business_status": "UNPRICED_REQUIRES_MATCHED_BOM_AND_BUYER",
                "purchase_authorized": False,
            })
    if len({r["candidate_id"] for r in results}) != len(results):
        raise ValueError("duplicate regional candidate id")
    return results


def normalize_historical_purchase_report(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Preserve five PR #147 executed economic screens and downside matrices.

    The original specialized purchase-screen calculator remains authoritative;
    importing its frozen output avoids duplicating its asymmetric success/
    failure-cost formula in this portfolio engine.
    """
    if report.get("schema_version") != "hardware_splicer.salvage_purchase_screen_report.v1":
        raise ValueError("unsupported historical purchase report")
    outputs = report.get("evaluations")
    if not isinstance(outputs, list) or not outputs:
        raise ValueError("purchase evaluations absent")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in outputs:
        if not isinstance(item, Mapping):
            raise ValueError("invalid purchase evaluation")
        model = item.get("modeled_unit_economics")
        if not isinstance(model, Mapping) or model.get("schema_version") != "hardware_splicer.salvage_purchase_screen.v1":
            raise ValueError("missing original purchase screen")
        identifier = str(model.get("id") or "")
        if not identifier or identifier in seen:
            raise ValueError("duplicate purchase screen")
        if model.get("purchase_authorized") is not False:
            raise ValueError("purchase screen cannot grant authority")
        seen.add(identifier)
        net = model.get("expected_net_per_acquired_unit_twd")
        bid = model.get("max_purchase_for_target_profit_twd")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in (net, bid)):
            raise ValueError("malformed purchase screen values")
        if model.get("acquisition_price_basis") == "advertised_asking_price":
            demand_status = "UNVERIFIED_SOLD_COMPS"
        else:
            demand_status = "CHECK_TRANSACTION_PROVENANCE"
        sensitivity = item.get("downside_sensitivity")
        if not isinstance(sensitivity, list) or len(sensitivity) != 9:
            raise ValueError("missing downside matrix")
        rows.append({
            "candidate_id": identifier,
            "origin": "taiwan_salvage_screen",
            "currency": "TWD",
            "modeled_expected_net_twd": net,
            "modeled_target_profit_max_bid_twd": bid,
            "modeled_sale_twd_not_observed": model.get("modeled_sale_twd_not_observed"),
            "source_ask_twd": model.get("source_ask_twd"),
            "source_market_links": list(item.get("source_urls") or []),
            "comparable_market_links": list(item.get("comparable_urls") or []),
            "source_date": "2026-10-19",
            "source_ref": _source_ref(report),
            "price_quality": demand_status,
            "nine_point_sensitivity": sensitivity,
            "failure_mode_gate": item.get("failure_mode_gate"),
            "source_confidence": item.get("source_confidence"),
            "current_decision": "SCREEN_POSITIVE_UNVALIDATED" if net > 0 and bid > 0
                                else "SCREEN_REJECTED_OR_ZERO",
            "purchase_authorized": False,
        })
    return rows
