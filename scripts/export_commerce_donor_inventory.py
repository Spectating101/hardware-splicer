"""Convert a manually reviewed commerce research snapshot to portable discovery JSON/CSV.

Does not contact sellers, scrape shops, or import unverified goods as project donors.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hardware_splicer.commerce_donor_inventory import normalize_inventory, to_csv

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "docs/research/commerce/tw_salvage_donor_listings_2026-10-19.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT.parent)
    args = parser.parse_args()
    raw = json.loads(args.input.read_text(encoding="utf-8"))
    result = normalize_inventory(raw)
    args.out_dir.mkdir(parents=True,exist_ok=True)
    (args.out_dir / "tw_donor_discovery_2026-10-19.json").write_text(
        json.dumps(result,indent=2,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf-8")
    (args.out_dir / "tw_donor_discovery_2026-10-19.csv").write_text(
        to_csv(result),encoding="utf-8")
    print(f"Exported {result['listing_count']} source listings across {len(result['family_counts'])} families")
    for family,count in result["family_counts"].items():
        print(f"  {family}: {count}")


if __name__ == "__main__":
    main()
