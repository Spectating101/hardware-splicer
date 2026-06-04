#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, Any


def _load_buy_list(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate editable SKU_OVERRIDES template from bundle buy list.")
    ap.add_argument("--bundle-dir", required=True, help="Path to mecha bundle output directory")
    ap.add_argument("--out", default="SKU_OVERRIDES.template.json", help="Output filename (inside bundle dir if relative)")
    args = ap.parse_args()

    bundle_dir = Path(args.bundle_dir)
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = bundle_dir / out_path

    buy_locked = _load_buy_list(bundle_dir / "BUY_LIST.locked.csv")
    buy_unlocked = _load_buy_list(bundle_dir / "BUY_LIST.csv")
    rows = buy_locked if buy_locked else buy_unlocked

    rules: Dict[str, Any] = {}
    for r in rows:
        item = (r.get("item") or "").strip()
        if not item:
            continue
        if item in rules:
            continue
        rules[item] = {
            "sku": (r.get("sku") or ""),
            "price_usd": float(r.get("price_usd") or 0.0),
            "url": (r.get("url") or ""),
        }

    payload = {
        "by_item_contains": rules,
        "_notes": {
            "how_to_use": "Copy this file to SKU_OVERRIDES.json, edit sku/price/url, then rerun mecha_splicer_spec.py with --include-pricing.",
            "match_rule": "substring match on item name",
        },
    }

    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
