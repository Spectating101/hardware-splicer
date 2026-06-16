"""Salvage BOM + estimated cost from module catalog (no fab compile required)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .bom_generator import _MODULE_LABELS, _PART_HINTS, SCHEMA_VERSION as BOM_SCHEMA, _jlc_enrich_enabled
from .pcb.module_registry import find_module

SCHEMA_VERSION = "hardware_splicer.salvage_bom_estimate.v1"

# Prototype USD hints when module_library lacks priceUsd (bench/salvage boards).
_PRICE_FALLBACK_USD: Dict[str, float] = {
    "esp32-devkit": 8.0,
    "esp32-cam-module": 10.0,
    "arduino-nano": 6.0,
    "rpi-pico": 5.0,
    "soil_moisture": 2.0,
    "dht22": 4.0,
    "bme280": 5.0,
    "hc-sr04": 3.0,
    "mini-pump-5v": 5.0,
    "water_pump_5v": 5.0,
    "mosfet-irlz44n": 2.0,
    "mosfet-irf520": 2.0,
    "l298n": 6.0,
    "relay-1ch": 2.0,
    "relay-1ch-5v": 2.0,
    "usb-power-5v": 0.0,
    "buck-mp1584": 3.0,
    "buck-lm2596": 4.0,
    "level-shifter-4ch": 2.0,
    "ssd1306-128x64": 4.0,
    "sg90": 3.0,
}


def _unit_price_usd(module_id: str, spec: Mapping[str, Any]) -> tuple[Optional[float], str]:
    price = spec.get("priceUsd")
    try:
        if price is not None:
            return float(price), "catalog_estimate"
    except (TypeError, ValueError):
        pass
    fallback = _PRICE_FALLBACK_USD.get(module_id)
    if fallback is not None:
        return float(fallback), "prototype_fallback"
    return None, "price_unknown"


def _line_for_module(
    module_id: str,
    *,
    qty: int = 1,
    source: str = "salvage",
    salvaged_part: str = "",
    priority: str = "",
) -> Dict[str, Any]:
    spec = find_module(module_id) or {}
    hints = dict(_PART_HINTS.get(module_id) or {})
    unit_usd, price_note = _unit_price_usd(module_id, spec)
    return {
        "module_id": module_id,
        "description": _MODULE_LABELS.get(module_id) or spec.get("label") or module_id,
        "mpn": hints.get("mpn", ""),
        "supplier_sku": hints.get("supplier_sku", ""),
        "qty": qty,
        "unit_price_usd": unit_usd,
        "line_total_usd": round(unit_usd * qty, 2) if unit_usd is not None else None,
        "source": source,
        "salvaged_part": salvaged_part,
        "priority": priority,
        "price_note": price_note,
    }


def build_salvage_bom_estimate(
    *,
    resolved_modules: List[Mapping[str, Any]],
    gap_analysis: Optional[Mapping[str, Any]] = None,
    budget: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """BOM lines for inventory + optional shopping list with USD estimates."""
    gap = dict(gap_analysis or {})
    lines: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for row in resolved_modules:
        module_id = str(row.get("module_id") or "").strip()
        if not module_id or module_id in seen:
            continue
        seen.add(module_id)
        lines.append(
            _line_for_module(
                module_id,
                source="salvage" if str(row.get("source") or "") != "goal_picker" else "goal",
                salvaged_part=str(row.get("part_name") or ""),
            )
        )

    for shop in gap.get("shopping_list") or []:
        module_id = str(shop.get("module_id") or "").strip()
        if not module_id or module_id in seen:
            continue
        seen.add(module_id)
        lines.append(
            _line_for_module(
                module_id,
                source="to_buy",
                priority=str(shop.get("priority") or "recommended"),
            )
        )

    salvage_total = sum(float(row["line_total_usd"]) for row in lines if row.get("line_total_usd") is not None and row.get("source") != "to_buy")
    buy_total = sum(float(row["line_total_usd"]) for row in lines if row.get("line_total_usd") is not None and row.get("source") == "to_buy")
    grand = salvage_total + buy_total

    budget_amount: Optional[float] = None
    budget_currency = "USD"
    if budget:
        budget_currency = str(budget.get("currency") or "USD")
        try:
            budget_amount = float(budget.get("amount"))
        except (TypeError, ValueError):
            budget_amount = None

    within_budget: Optional[bool] = None
    if budget_amount is not None and grand > 0:
        within_budget = grand <= budget_amount

    bom = {
        "schema_version": SCHEMA_VERSION,
        "bom_schema": BOM_SCHEMA,
        "line_count": len(lines),
        "lines": lines,
        "estimated_salvage_usd": round(salvage_total, 2),
        "estimated_purchases_usd": round(buy_total, 2),
        "estimated_total_usd": round(grand, 2) if grand else None,
        "budget": {"currency": budget_currency, "amount": budget_amount},
        "within_budget": within_budget,
        "pricing_note": "USD from catalog priceUsd, prototype fallbacks, and optional JLC in-stock hints.",
    }
    return enrich_salvage_bom_estimate(bom)


def enrich_salvage_bom_estimate(
    bom: Mapping[str, Any],
    *,
    client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Attach JLC/LCSC hints and live price1 when jlcsearch finds an MPN match."""
    if not _jlc_enrich_enabled():
        return dict(bom)

    from .integrations.jlcsearch_client import JlcSearchClient

    client = client or JlcSearchClient()
    enriched_lines: List[Dict[str, Any]] = []
    jlc_hits = 0

    for row in bom.get("lines") or []:
        line = dict(row)
        module_id = str(line.get("module_id") or "")
        mpn = str(line.get("mpn") or "").strip()

        if module_id.startswith("resistor-"):
            try:
                value = module_id.replace("resistor-", "").replace("_", ".")
                hits = client.search_resistors(resistance=value, package="0603", limit=1)
                if hits:
                    _apply_jlc_hit(line, hits[0])
                    jlc_hits += 1
            except Exception:
                pass
        elif module_id.startswith("capacitor-"):
            try:
                value = module_id.replace("capacitor-", "").replace("_", ".")
                hits = client.search_capacitors(capacitance=value, package="0603", limit=1)
                if hits:
                    _apply_jlc_hit(line, hits[0])
                    jlc_hits += 1
            except Exception:
                pass
        elif mpn:
            hit = client.search_by_mpn(mpn)
            if hit:
                _apply_jlc_hit(line, hit)
                jlc_hits += 1

        enriched_lines.append(line)

    out = dict(bom)
    out["lines"] = enriched_lines
    out["jlc_enriched"] = jlc_hits > 0
    out["jlc_hit_count"] = jlc_hits

    salvage_total = sum(
        float(row["line_total_usd"])
        for row in enriched_lines
        if row.get("line_total_usd") is not None and row.get("source") != "to_buy"
    )
    buy_total = sum(
        float(row["line_total_usd"])
        for row in enriched_lines
        if row.get("line_total_usd") is not None and row.get("source") == "to_buy"
    )
    grand = salvage_total + buy_total
    out["estimated_salvage_usd"] = round(salvage_total, 2)
    out["estimated_purchases_usd"] = round(buy_total, 2)
    out["estimated_total_usd"] = round(grand, 2) if grand else None

    budget = dict(bom.get("budget") or {})
    amount = budget.get("amount")
    if amount is not None and grand > 0:
        try:
            out["within_budget"] = grand <= float(amount)
        except (TypeError, ValueError):
            pass
    return out


def _apply_jlc_hit(line: Dict[str, Any], hit: Mapping[str, Any]) -> None:
    lcsc = hit.get("lcsc") or hit.get("lcsc_id")
    mfr = str(hit.get("mfr") or hit.get("mpn") or hit.get("manufacturer_part_number") or "")
    price1 = hit.get("price1")
    stock = hit.get("stock")
    if lcsc:
        line["jlc_lcsc"] = str(lcsc)
    if mfr:
        line["jlc_mpn"] = mfr
    if stock is not None:
        line["jlc_stock"] = stock
    if price1 is not None:
        try:
            unit = float(price1)
            qty = int(line.get("qty") or 1)
            line["jlc_unit_price_usd"] = round(unit, 4)
            if line.get("source") == "to_buy" or line.get("price_note") == "price_unknown":
                line["unit_price_usd"] = round(unit, 4)
                line["line_total_usd"] = round(unit * qty, 2)
                line["price_note"] = "jlc_in_stock"
        except (TypeError, ValueError):
            pass


def write_salvage_bom_artifacts(bom: Mapping[str, Any], out_dir: str | Path) -> Dict[str, str]:
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / "SALVAGE_BOM.json"
    csv_path = target / "SALVAGE_BOM.csv"
    json_path.write_text(json.dumps(dict(bom), indent=2), encoding="utf-8")
    fieldnames = [
        "module_id",
        "description",
        "mpn",
        "supplier_sku",
        "jlc_lcsc",
        "jlc_mpn",
        "jlc_unit_price_usd",
        "qty",
        "unit_price_usd",
        "line_total_usd",
        "source",
        "salvaged_part",
        "priority",
        "price_note",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in bom.get("lines") or []:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    return {"salvage_bom_json": str(json_path), "salvage_bom_csv": str(csv_path)}
