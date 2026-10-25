"""Test how actual *listed* replacement-part prices affect a prior salvage model.

Preserves the historical repair model's expected contribution. Treats a new
part-cost input as a sensitivity scenario, not a purchase quote.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

SCHEMA = "hardware_splicer.commercial_repair_stress.v1"


def repair_cost_stress(model: Mapping[str, Any], proposal: Mapping[str, Any]) -> dict[str, Any]:
    required = ("candidate_id", "currency", "old_expected_net", "old_success_parts",
                "success_yield", "target_profit", "replacement_cost_low",
                "replacement_cost_high", "source_url", "source_date")
    for k in required:
        if k not in proposal:
            raise ValueError(f"missing stress input:{k}")
    if proposal["currency"] != "TWD" or proposal["candidate_id"] != model.get("id"):
        raise ValueError("wrong model or native currency")
    if not str(proposal["source_url"]).startswith("https://"):
        raise ValueError("not a traceable listing source")
    values: dict[str, float] = {}
    for name in ("old_expected_net", "old_success_parts", "success_yield",
                 "target_profit", "replacement_cost_low", "replacement_cost_high"):
        raw = proposal[name]
        if isinstance(raw, bool):
            raise ValueError(f"invalid money/probability:{name}")
        try:
            val = float(raw)
        except (TypeError, ValueError):
            raise ValueError(f"invalid money/probability:{name}")
        if not math.isfinite(val):
            raise ValueError(f"nonfinite:{name}")
        values[name] = val
    if not 0 < values["success_yield"] <= 1:
        raise ValueError("invalid success fraction")
    if not 0 <= values["old_success_parts"]:
        raise ValueError("negative baseline parts")
    if not 0 <= values["replacement_cost_low"] <= values["replacement_cost_high"]:
        raise ValueError("invalid replacement quote range")
    if values["target_profit"] < 0:
        raise ValueError("invalid target")
    if abs(float(model.get("expected_net_per_acquired_unit_twd", float("inf"))) - values["old_expected_net"]) > 0.01:
        raise ValueError("historical model net mismatch")
    # Only when the replacement head is needed by every otherwise-successful
    # repair, and REPLACES the old success-parts allowance rather than being
    # additive. Not a probability model for undiagnosed printhead failure.
    def adjusted_cost(part: float) -> float:
        increment = max(0.0, part - values["old_success_parts"])
        return values["old_expected_net"] - values["success_yield"] * increment
    max_parts = values["old_success_parts"] + (
        values["old_expected_net"] - values["target_profit"]
    ) / values["success_yield"]
    return {
        "schema_version": SCHEMA,
        "candidate_id": model["id"],
        "currency": "TWD",
        "historical_expected_net": round(values["old_expected_net"], 2),
        "model_assumed_success_parts": round(values["old_success_parts"], 2),
        "listing_replacement_range": [
            round(values["replacement_cost_low"], 2),
            round(values["replacement_cost_high"], 2),
        ],
        "modeled_profit_if_head_required_on_each_success": [
            round(adjusted_cost(values["replacement_cost_high"]), 2),
            round(adjusted_cost(values["replacement_cost_low"]), 2),
        ],
        "maximum_success_parts_to_meet_original_profit_target": round(max_parts, 2),
        "original_target_profit": round(values["target_profit"], 2),
        "status": "HOLD_PRINTHEAD_CONDITION_OR_COST_REJECT"
        if adjusted_cost(values["replacement_cost_low"]) < values["target_profit"]
        else "UNVERIFIED_SCREEN_ONLY",
        "source_url": proposal["source_url"],
        "source_date": proposal["source_date"],
        "purchase_authorized": False,
        "assumptions": [
            "replacement needed for every otherwise-successful repair",
            "replacement head substitutes for baseline success-parts allowance",
            "original modeled yield and resale price unchanged",
            "seller-listed parts not actual quoted/paid replacement price",
        ],
    }
