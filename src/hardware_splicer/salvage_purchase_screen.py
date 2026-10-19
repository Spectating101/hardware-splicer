"""Illustrative per-acquisition resale screen, distinct from derivative DEVELOPMENT economics.

No missing sell-through, actual yield, sourcing evidence, regulatory permission
or market clearing price is inferred. Calculations cannot authorize purchase.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

SCHEMA = "hardware_splicer.salvage_purchase_screen.v1"
NUMBER_KEYS = (
    "ask_twd", "modeled_sale_twd", "success_yield",
    "platform_fee_rate", "successful_parts_twd", "inbound_shipping_twd",
    "outbound_shipping_twd", "packing_twd", "warranty_reserve_twd",
    "intake_labor_hours", "successful_labor_hours", "failed_labor_hours",
    "labor_rate_twd_hour", "failure_salvage_recovery_twd",
    "target_profit_per_purchase_twd",
)


class PurchaseScreenRefused(ValueError):
    pass


def screen(item: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(item, Mapping) or item.get("schema_version") != SCHEMA:
        raise PurchaseScreenRefused("requires exact screen schema")
    if not isinstance(item.get("id"), str) or not item["id"]:
        raise PurchaseScreenRefused("opportunity identifier required")
    values = {}
    for key in NUMBER_KEYS:
        number = item.get(key)
        if isinstance(number, bool) or not isinstance(number, (float, int)) or not math.isfinite(number) or number < 0:
            raise PurchaseScreenRefused(f"{key} must be a finite nonnegative number")
        values[key] = float(number)
    p = values["success_yield"]
    fee = values["platform_fee_rate"]
    if p > 1 or fee > 1:
        raise PurchaseScreenRefused("yield and fee rates must be in [0,1]")
    working_comparable = item.get("working_comparable")
    if working_comparable not in {"verified_same_model", "related_model", "missing"}:
        raise PurchaseScreenRefused("working comparable quality must be explicit")
    evidence_type = item.get("source_ask_status")
    if evidence_type not in {"advertised_asking_price", "verified_paid_transaction"}:
        raise PurchaseScreenRefused("source ask status must be explicitly described")
    sale = values["modeled_sale_twd"]
    success_contribution = (
        sale * (1 - fee)
        - values["successful_parts_twd"] - values["outbound_shipping_twd"]
        - values["packing_twd"] - values["warranty_reserve_twd"]
        - values["successful_labor_hours"] * values["labor_rate_twd_hour"]
    )
    failure_contribution = (
        values["failure_salvage_recovery_twd"]
        - values["failed_labor_hours"] * values["labor_rate_twd_hour"]
    )
    max_bid = (
        p * success_contribution + (1 - p) * failure_contribution
        - values["inbound_shipping_twd"]
        - values["intake_labor_hours"] * values["labor_rate_twd_hour"]
    )
    expected = max_bid - values["ask_twd"]
    min_sale = None
    if p > 0 and fee < 1:
        non_sale_success = success_contribution - sale * (1 - fee)
        min_sale = (
            values["ask_twd"] + values["inbound_shipping_twd"]
            + values["intake_labor_hours"] * values["labor_rate_twd_hour"]
            - p * non_sale_success - (1 - p) * failure_contribution
        ) / (p * (1 - fee))
    # A coherent spread is still NOT permission to buy: actual sale clearing,
    # yield, component faults and ownership provenance require separate proof.
    confidence = "INSUFFICIENT_SAME_MODEL_COMPS" if working_comparable != "verified_same_model" else "ILLUSTRATIVE_PENDING_SOLD_PRICES"
    return {
        "schema_version": SCHEMA,
        "id": item["id"],
        "status": confidence,
        "acquisition_price_basis": evidence_type,
        "source_ask_twd": values["ask_twd"],
        "modeled_sale_twd_not_observed": sale,
        "success_yield_assumed_not_observed": p,
        "success_contribution_before_purchase_twd": round(success_contribution, 2),
        "failure_contribution_before_purchase_twd": round(failure_contribution, 2),
        "expected_net_per_acquired_unit_twd": round(expected, 2),
        "break_even_max_purchase_twd": round(max_bid, 2),
        "max_purchase_for_target_profit_twd": round(max_bid - values["target_profit_per_purchase_twd"], 2),
        "minimum_sale_to_break_even_twd": round(min_sale, 2) if min_sale is not None else None,
        "purchase_authorized": False,
        "required_evidence": [
            "Same-model sold/completed prices, not advertised asking prices",
            "Actual donor condition and fault diagnosis before payment",
            "Measured success yield and repair hours from a precommitted pilot",
            "Ownership and appropriate Taiwanese reuse/resale permissions",
            "Actual shipping, platform fee, warranty and return costs",
        ],
    }


def sensitivity(item: Mapping[str, Any], *, sale_rates: tuple[float, ...] = (0.8, 1.0, 1.2),
                yields: tuple[float, ...] = (0.4, 0.6, 0.8)) -> list[dict[str, Any]]:
    """Explicit downside matrix; does not turn inputs into market forecasts."""
    outputs = []
    for sale_factor in sale_rates:
        for yield_value in yields:
            revised = dict(item)
            revised["modeled_sale_twd"] = item["modeled_sale_twd"] * sale_factor
            revised["success_yield"] = yield_value
            result = screen(revised)
            outputs.append({
                "sale_factor": sale_factor,
                "assumed_success_yield": yield_value,
                "expected_net_twd": result["expected_net_per_acquired_unit_twd"],
            })
    return outputs
