"""Material and outsourcing cost reconciliation for HS commercial build routes.

An itemized material plan is not a verified engineering BOM or proof of
safe electrical compatibility. All planning costs stay labeled by evidence.
"""
from __future__ import annotations

import math
from typing import Any, Mapping


def _money(raw: Any, field: str, problems: list[str]) -> tuple[float | None, bool]:
    if not isinstance(raw, Mapping):
        problems.append(f"missing_material_money:{field}")
        return None, False
    if raw.get("evidence_class") not in {"HYPOTHESIS", "ESTIMATED", "QUOTED", "MEASURED"}:
        problems.append(f"invalid_material_evidence:{field}")
    reference = str(raw.get("reference") or "").strip()
    verified = raw.get("evidence_class") in {"QUOTED", "MEASURED"} and bool(reference)
    if raw.get("evidence_class") in {"QUOTED", "MEASURED"} and not reference:
        problems.append(f"missing_material_reference:{field}")
    val = raw.get("amount")
    if isinstance(val, bool):
        problems.append(f"invalid_material_money:{field}")
        return None, False
    try:
        num = float(val)
    except (TypeError, ValueError):
        problems.append(f"invalid_material_money:{field}")
        return None, False
    if not math.isfinite(num) or num < 0:
        problems.append(f"invalid_material_money:{field}")
        return None, False
    return num, verified


def evaluate_material_plan(plan: Any, *, currency: str, expected_cost: float) -> dict[str, Any]:
    problems: list[str] = []
    blockers: list[str] = []
    if not isinstance(plan, Mapping):
        return {
            "status": "INVALID",
            "errors": ["missing_material_plan"],
            "blockers": ["materials_not_itemized"],
            "total": None,
            "physically_verified": False,
        }
    if plan.get("currency") != currency:
        problems.append("material_currency_mismatch")
    items = plan.get("line_items")
    if not isinstance(items, list) or not items or len(items) > 200:
        problems.append("missing_or_unbounded_material_lines")
        items = []
    total = 0.0
    part_ids: set[str] = set()
    all_quoted = True
    any_reclaimed = False
    for ix, item in enumerate(items):
        if not isinstance(item, Mapping):
            problems.append(f"invalid_material_line:{ix}")
            continue
        ident = str(item.get("part_id") or "").strip()
        if not ident or ident in part_ids:
            problems.append(f"missing_or_duplicate_part:{ix}")
        part_ids.add(ident)
        qty = item.get("quantity")
        if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
            problems.append(f"invalid_material_quantity:{ix}")
            continue
        value, strong = _money(item.get("unit_cost"), f"line_items.{ix}", problems)
        all_quoted = all_quoted and strong
        if value is not None:
            total += qty * value
        condition = item.get("material_state")
        if condition not in {"new", "salvaged_unverified", "salvaged_bench_verified"}:
            problems.append(f"missing_material_state:{ix}")
        if condition in {"salvaged_unverified", "salvaged_bench_verified"}:
            any_reclaimed = True
            if not str(item.get("donor_asset_ref") or "").strip():
                problems.append(f"missing_donor_provenance:{ix}")
            if condition == "salvaged_unverified":
                blockers.append(f"salvaged_component_unverified:{ix}")
            if condition == "salvaged_bench_verified" and not str(item.get("test_reference") or "").strip():
                blockers.append(f"salvage_test_receipt_missing:{ix}")
    fabrication, fab_strong = _money(plan.get("fabrication_service"), "fabrication_service", problems)
    all_quoted = all_quoted and fab_strong
    if fabrication is not None:
        total += fabrication
    if not math.isfinite(total):
        problems.append("nonfinite_material_total")
    if math.isfinite(total) and math.isfinite(expected_cost):
        if abs(total - expected_cost) > 0.02:
            problems.append("material_total_does_not_reconcile")
    if not all_quoted:
        blockers.append("unverified_material_quotes")
    if any_reclaimed and not str(plan.get("recovery_labor_cost_location") or "").strip():
        blockers.append("unallocated_salvage_labor")
    return {
        "status": "INVALID" if problems else "SCREENING_ONLY" if blockers else "QUOTE_READY",
        "errors": sorted(set(problems)),
        "blockers": sorted(set(blockers)),
        "total": round(total, 2) if math.isfinite(total) else None,
        "parts_count": len(items),
        "physically_verified": False,
        "purchase_authorized": False,
        "limitations": [
            "itemized prices are not functional validation",
            "QUOTE_READY does not imply physical compatibility or authority to fabricate",
            "donor/test references must be inspected independently",
        ],
    }
