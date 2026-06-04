from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass(frozen=True)
class CatalogItem:
    sku: str
    name: str
    unit: str
    pack_size: int = 1
    min_order_qty: int = 1
    price_usd: float = 0.0
    currency: str = "USD"
    url: str = ""
    notes: str = ""


class MechanicalCatalog:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._items: Dict[str, CatalogItem] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            sku = str(obj.get("sku") or "").strip()
            if not sku:
                continue
            self._items[sku] = CatalogItem(
                sku=sku,
                name=str(obj.get("name") or sku),
                unit=str(obj.get("unit") or "ea"),
                pack_size=int(obj.get("pack_size") or 1),
                min_order_qty=int(obj.get("min_order_qty") or 1),
                price_usd=float(obj.get("price_usd") or 0.0),
                currency=str(obj.get("currency") or "USD"),
                url=str(obj.get("url") or ""),
                notes=str(obj.get("notes") or ""),
            )

    def get(self, sku: str) -> Optional[CatalogItem]:
        return self._items.get(sku)
