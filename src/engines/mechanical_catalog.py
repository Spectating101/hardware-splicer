from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class CatalogItem:
    id: str
    name: str
    category: str
    specs: Dict[str, Any]
    price_twd: int
    currency: str
    url: str
    seller: str
    notes: str


def load_catalog_jsonl(path: Path) -> List[CatalogItem]:
    items: List[CatalogItem] = []
    if not path.exists():
        return items
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        items.append(
            CatalogItem(
                id=str(obj.get("id") or ""),
                name=str(obj.get("name") or ""),
                category=str(obj.get("category") or ""),
                specs=obj.get("specs") or {},
                price_twd=int(obj.get("price_twd") or 0),
                currency=str(obj.get("currency") or "TWD"),
                url=str(obj.get("url") or ""),
                seller=str(obj.get("seller") or ""),
                notes=str(obj.get("notes") or ""),
            )
        )
    return [i for i in items if i.id]


def catalog_default_path(repo_root: Path) -> Path:
    return repo_root / "data" / "mechanical" / "catalog.jsonl"


def index_by_id(items: List[CatalogItem]) -> Dict[str, CatalogItem]:
    return {i.id: i for i in items if i.id}


def sum_cost_twd(line_items: List[Dict[str, Any]]) -> int:
    total = 0
    for li in line_items:
        qty = int(li.get("qty") or 1)
        unit = int(li.get("unit_price_twd") or 0)
        total += qty * unit
    return total


def build_candidate_boms(
    *,
    catalog: List[CatalogItem],
    work_area_mm: Tuple[int, int] = (100, 100),
    accuracy_mm: float = 0.25,
    prefer: str = "cheapest",
) -> Dict[str, Any]:
    """
    Build 2–3 candidate mechanical BOMs using a minimal catalog.

    This intentionally does not browse. It chooses from:
      - kits (preferred) OR
      - a generic rails/belts/stuff list when kits are absent
    """
    by_id = index_by_id(catalog)

    def pick(item_id: str, qty: int, role: str) -> Dict[str, Any]:
        it = by_id.get(item_id)
        if not it:
            return {"id": item_id, "name": item_id, "qty": qty, "unit_price_twd": 0, "role": role, "missing": True}
        return {
            "id": it.id,
            "name": it.name,
            "qty": qty,
            "unit_price_twd": it.price_twd,
            "currency": it.currency,
            "url": it.url,
            "seller": it.seller,
            "role": role,
            "notes": it.notes,
        }

    w, h = work_area_mm
    candidates: List[Dict[str, Any]] = []

    # Candidate A: Cheapest base kit.
    kit_a = "kit_3018_cnc" if prefer == "cheapest" else "kit_xy_plotter"
    cand_a_items = [
        pick(kit_a, 1, "motion_platform"),
        pick("estop_button", 1, "safety"),
        pick("endstop_switch", 3, "endstops"),
        pick("probe_holder_spring", 1, "tooling"),
    ]
    candidates.append(
        {
            "name": "A: Base kit (fastest/cheapest)",
            "intent": "Get moving XY+Z with minimal sourcing. Swap spindle for probe mount.",
            "line_items": cand_a_items,
            "total_twd": sum_cost_twd(cand_a_items),
        }
    )

    # Candidate B: CoreXY frame kit (better motion quality).
    cand_b_items = [
        pick("kit_corexy_2020", 1, "motion_platform"),
        pick("nema17_42", 3, "steppers"),
        pick("gt2_belt_5m", 1, "belts"),
        pick("gt2_pulley_20t", 4, "pulleys"),
        pick("t8_leadscrew_300", 1, "z_axis"),
        pick("coupler_5x8", 1, "z_axis"),
        pick("endstop_switch", 3, "endstops"),
        pick("estop_button", 1, "safety"),
        pick("probe_holder_spring", 1, "tooling"),
    ]
    candidates.append(
        {
            "name": "B: CoreXY kit + common parts (balanced)",
            "intent": "Better speed/quality; more assembly/tuning.",
            "line_items": cand_b_items,
            "total_twd": sum_cost_twd(cand_b_items),
        }
    )

    # Candidate C: Stiffer Z upgrade path (add linear rail).
    cand_c_items = [
        pick("kit_3018_cnc", 1, "motion_platform"),
        pick("mgn12_rail_300", 1, "z_upgrade"),
        pick("t8_leadscrew_300", 1, "z_axis"),
        pick("coupler_5x8", 1, "z_axis"),
        pick("endstop_switch", 3, "endstops"),
        pick("estop_button", 1, "safety"),
        pick("probe_holder_spring", 1, "tooling"),
    ]
    candidates.append(
        {
            "name": "C: Base kit + stiffer Z (probe-friendly)",
            "intent": "Improve repeatability for probing by stiffening Z mechanics.",
            "line_items": cand_c_items,
            "total_twd": sum_cost_twd(cand_c_items),
        }
    )

    # Missing items summary
    missing_ids: List[str] = []
    for cand in candidates:
        for li in cand["line_items"]:
            if li.get("missing"):
                missing_ids.append(li["id"])

    return {
        "inputs": {"work_area_mm": [w, h], "accuracy_mm": accuracy_mm, "prefer": prefer},
        "candidates": candidates,
        "missing_catalog_items": sorted(set(missing_ids)),
        "notes": [
            "Prices default to 0 until you fill Shopee URL + price_twd in data/mechanical/catalog.jsonl.",
            "This is a mechanical BOM helper; electronics/control BOM is handled separately.",
        ],
    }

