"""Fail-closed scenario arithmetic for Taiwan dual-touch prototype supplier research.

Asking prices ≠ delivered supplier quotes. SKU25948 touchscreen ≠ SKU30493
non-touch; manufacturer kit cables ≠ separately verified RS485 hinge wiring.
No procurement decisions or engineering authorization are emitted.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from typing import Any, Mapping


SCHEMA = "hs.taiwan_component_sourcing.v1"


class SourcingEvidenceError(ValueError):
    pass


def calculate(snapshot_bytes: bytes) -> dict[str, Any]:
    doc = json.loads(snapshot_bytes)
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise SourcingEvidenceError("wrong supplier snapshot schema")
    if doc.get("architecture") != "dual_esp32_touch_4p3_rs485":
        raise SourcingEvidenceError("incorrect target architecture")
    if doc.get("comparison_ref_architecture") == doc["architecture"]:
        raise SourcingEvidenceError("Pi5 reference BOM must not be merged into ESP32")
    for k, expected in (("orders_placed", 0), ("quotes_obtained", 0),
                        ("parts_received", 0), ("purchase_authorized", False),
                        ("exact_retail_stock_confirmed", False)):
        if doc.get(k) is not expected and doc.get(k) != expected:
            raise SourcingEvidenceError(f"unsupported purchase/supplier authority: {k}")
    dt = datetime.fromisoformat(doc["captured_utc"].replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise SourcingEvidenceError("source timestamp not timezone qualified")
    sources = doc.get("sources", [])
    if not isinstance(sources, list) or len({s.get("id") for s in sources}) != len(sources):
        raise SourcingEvidenceError("invalid/duplicate supplier sources")
    source_lookup = {x["id"]: x for x in sources}
    exact = source_lookup.get("waveshare_25948", {})
    if exact.get("sku") != "25948" or exact.get("touch") is not True:
        raise SourcingEvidenceError("incorrect manufacturer part number")
    local = source_lookup.get("icshop_25948", {})
    if local.get("sku") != exact["sku"] or local.get("availability") != "SOLD_OUT":
        raise SourcingEvidenceError("historical local asking price must not be called orderable")
    mixed = source_lookup.get("ruten_mixed_25948_30493", {})
    if sorted(mixed.get("variants", [])) != ["25948 touchscreen", "30493 no touch"]:
        raise SourcingEvidenceError("marketplace variants not correctly disambiguated")
    if mixed.get("availability") != "VARIANT_STOCK_UNCONFIRMED":
        raise SourcingEvidenceError("Ruten exact touchscreen inventory not verified")
    lo, hi = mixed["range_twd"]
    if type(lo) is not int or type(hi) is not int or not 0 < lo <= hi:
        raise SourcingEvidenceError("bad marketplace asking-price envelope")
    items = doc.get("components", [])
    if not isinstance(items, list) or len({c.get("id") for c in items}) != len(items):
        raise SourcingEvidenceError("missing or duplicate components")
    components = {}
    for item in items:
        if type(item.get("qty")) is not int or item["qty"] <= 0:
            raise SourcingEvidenceError("invalid parts quantity")
        if type(item.get("unit_twd")) is not int or item["unit_twd"] < 0:
            raise SourcingEvidenceError("unpriced component / invalid money")
        if item.get("source_id") is not None and item["source_id"] not in source_lookup:
            raise SourcingEvidenceError("component refers to unknown source")
        components[item["id"]] = item
    if components["display_boards"]["qty"] != 2 or components["display_boards"]["unit_twd"] != hi:
        raise SourcingEvidenceError("touchscreen upper price envelope must be preserved")
    if components["rs485_vendor_cables"]["unit_twd"] != 0:
        raise SourcingEvidenceError("manufacturer included cable allowance changed")
    rate = source_lookup.get("wancai_petg", {})
    if rate.get("weight_known") is not False:
        raise SourcingEvidenceError("cannot claim CAD shell slicing has been quoted")
    if components["printed_shells_petg"]["unit_twd"] != max(
        int(150 * rate["rate_twd_per_g"]), rate["order_minimum_twd"]
    ):
        raise SourcingEvidenceError("PETG estimate must match illustrative 150g weight")
    scenarios = {}
    for scenario in doc["scenarios"]:
        sid = scenario["id"]
        if sid in scenarios:
            raise SourcingEvidenceError("repeated scenario")
        names = scenario.get("included_ids")
        if not isinstance(names, list) or len(names) != len(set(names)) or not set(names) <= set(components):
            raise SourcingEvidenceError("duplicated or unknown scenario components")
        counts = scenario.get("overrides", {})
        prices = scenario.get("unit_overrides_twd", {})
        if not set(counts) <= set(names) or not set(prices) <= set(names):
            raise SourcingEvidenceError("orphaned scenario override")
        cost, rows = 0, []
        for name in names:
            comp = components[name]
            qty = counts.get(name, comp["qty"])
            unit = prices.get(name, comp["unit_twd"])
            if type(qty) is not int or qty <= 0 or type(unit) is not int or unit < 0:
                raise SourcingEvidenceError("bad override")
            if name == "display_boards" and unit not in (hi, local["unit_twd"]):
                raise SourcingEvidenceError("unknown board price")
            cost += qty * unit
            rows.append({"id": name, "qty": qty, "unit_twd": unit, "total_twd": qty * unit,
                         "basis": comp["valuation"]})
        reserve = scenario.get("add_shipping_reserve_twd", 0)
        if type(reserve) is not int or reserve < 0:
            raise SourcingEvidenceError("unquoted freight cannot be negative")
        scenarios[sid] = {
            "description": scenario["description"], "items": rows,
            "shipping_reserve_twd": reserve, "total_twd": cost + reserve,
            "delivered_quote": False, "inventory_orderable": False,
            "caveat": "Scenario only. Exact SKU stock, courier/printing and compatibility not validated."
        }
    if not scenarios or "unavailable_icshop_price_counterfactual" not in scenarios:
        raise SourcingEvidenceError("no historical unavailable benchmark")
    if scenarios["unavailable_icshop_price_counterfactual"]["total_twd"] >= scenarios["full_exterior_concept"]["total_twd"]:
        raise SourcingEvidenceError("unavailable price reference must remain lower than current upper budget")
    return {
        "schema": "hs.taiwan_component_sourcing_receipt.v1",
        "snapshot_sha256": sha256(snapshot_bytes).hexdigest(),
        "captured_utc": doc["captured_utc"], "currency": "TWD",
        "architecture": doc["architecture"],
        "manufacturer_sku": "25948", "non_touch_not_equivalent_sku": "30493",
        "scenarios": scenarios,
        "supplier_sourcing_status": "UNQUOTED_AND_STOCK_UNVERIFIED",
        "source_ids": sorted(source_lookup),
        "no_battery_integrated": True, "exclusions": doc["exclusions"],
        "purchase_authorized": False, "physical_release_authorized": False,
        "next_action": "Request seller variant-specific exact SKU availability and 2-unit checkout total; measure actual shells before printing."
    }
