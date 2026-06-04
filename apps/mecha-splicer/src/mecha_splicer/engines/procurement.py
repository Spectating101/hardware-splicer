from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .catalog import MechanicalCatalog


@dataclass(frozen=True)
class LockedLine:
    category: str
    item: str
    spec: str
    required_qty: int
    purchase_qty: int
    notes: str
    sku: str
    unit: str
    pack_size: int
    min_order_qty: int
    price_usd: float
    url: str
    subtotal_usd: float
    locked: bool


def load_overrides(path: Optional[str | Path]) -> Dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def apply_overrides(bom: List[Dict[str, Any]], overrides: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Overrides format:
      {
        "by_item_contains": {
          "M3 screws": {"sku": "...", "price_usd": 1.23, "url": "..." }
        }
      }
    """
    rules = (overrides or {}).get("by_item_contains") or {}
    if not isinstance(rules, dict):
        rules = {}

    out: List[Dict[str, Any]] = []
    for line in bom:
        item = str(line.get("item") or "")
        updated = dict(line)
        for needle, patch in rules.items():
            if not needle:
                continue
            if needle.lower() in item.lower():
                if isinstance(patch, dict):
                    for k in ("sku", "price_usd", "url"):
                        if k in patch:
                            updated[k] = patch[k]
        out.append(updated)
    return out


def lock_bom(
    bom: List[Dict[str, Any]],
    *,
    catalog: MechanicalCatalog,
) -> List[LockedLine]:
    locked: List[LockedLine] = []
    for line in bom:
        sku = str(line.get("sku") or "").strip()
        cat = str(line.get("category") or "")
        item = str(line.get("item") or "")
        spec = str(line.get("spec") or "")
        required_qty = int(line.get("qty") or 0)
        notes = str(line.get("notes") or "")

        if not sku:
            locked.append(
                LockedLine(
                    category=cat,
                    item=item,
                    spec=spec,
                    required_qty=required_qty,
                    purchase_qty=0,
                    notes=notes,
                    sku="",
                    unit="",
                    pack_size=0,
                    min_order_qty=0,
                    price_usd=0.0,
                    url=str(line.get("url") or ""),
                    subtotal_usd=0.0,
                    locked=False,
                )
            )
            continue

        ci = catalog.get(sku)
        price = float(line.get("price_usd") or (ci.price_usd if ci else 0.0))
        unit = ci.unit if ci else str(line.get("unit") or "")
        pack_size = int(line.get("pack_size") or (ci.pack_size if ci else 1))
        moq = int(line.get("min_order_qty") or (ci.min_order_qty if ci else 1))
        url = str(line.get("url") or (ci.url if ci else ""))
        pack_size = max(1, pack_size)
        moq = max(1, moq)

        # Procurement quantity planning (v2):
        # - purchase_qty counts *packs* if pack_size>1, otherwise units
        # - apply MOQ in purchase units
        purchase_qty = 0
        if required_qty > 0:
            purchase_qty = int((required_qty + pack_size - 1) // pack_size)
            purchase_qty = max(purchase_qty, moq)
        subtotal = price * float(purchase_qty)
        if required_qty:
            notes = (notes + "; " if notes else "") + f"pack_size={pack_size}, buy_qty={purchase_qty}"
        locked.append(
            LockedLine(
                category=cat,
                item=item,
                spec=spec,
                required_qty=required_qty,
                purchase_qty=purchase_qty,
                notes=notes,
                sku=sku,
                unit=unit,
                pack_size=pack_size,
                min_order_qty=moq,
                price_usd=price,
                url=url,
                subtotal_usd=subtotal,
                locked=bool(ci) or bool(price) or bool(url),
            )
        )
    return locked


def write_buy_list_csv(path: str | Path, lines: Iterable[LockedLine]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "category",
                "item",
                "spec",
                "required_qty",
                "purchase_qty",
                "sku",
                "unit",
                "pack_size",
                "min_order_qty",
                "price_usd",
                "subtotal_usd",
                "url",
                "notes",
            ]
        )
        for l in lines:
            w.writerow(
                [
                    l.category,
                    l.item,
                    l.spec,
                    l.required_qty,
                    l.purchase_qty,
                    l.sku,
                    l.unit,
                    l.pack_size,
                    l.min_order_qty,
                    f"{l.price_usd:.2f}",
                    f"{l.subtotal_usd:.2f}",
                    l.url,
                    l.notes,
                ]
            )


def write_lock_report_md(path: str | Path, lines: List[LockedLine]) -> None:
    total = len(lines)
    locked_n = sum(1 for l in lines if l.locked and l.sku)
    missing_sku = sum(1 for l in lines if not l.sku)
    cost = sum(l.subtotal_usd for l in lines)

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    md = []
    md.append("# Procurement Lock Report\n")
    md.append(f"- Lines: {total}")
    md.append(f"- Locked: {locked_n}")
    md.append(f"- Missing SKU: {missing_sku}")
    md.append(f"- Est. COGS (USD, catalog/overrides): ${cost:.2f}\n")
    md.append("## Missing\n")
    for l in lines:
        if not l.sku:
            md.append(f"- {l.item} ({l.spec}) — no SKU mapped")
    md.append("")
    p.write_text("\n".join(md), encoding="utf-8")
