"""Open Repair Alliance v0.3 observations, never device diagnosis.

Input is the downloaded EEE CSV, not a webpage or LFS pointer. Results are
aggregate category frequencies from community repair attempts, NOT evidence
that any particular owned donor is repairable or safe.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

REQUIRED = {"id", "product_category", "repair_status", "problem", "repair_barrier_if_end_of_life"}
SOURCE = "https://github.com/openrepair/data"
LICENSE = "CC BY-SA 4.0"

def summarize_repairs(path: str | Path, *, category: str, max_rows: int = 650000) -> dict:
    category = category.strip()
    if len(category) < 2 or len(category) > 120:
        raise ValueError("category must be 2-120 characters")
    if not 1 <= max_rows <= 650000:
        raise ValueError("row limit must be 1-650000")
    p = Path(path)
    if not p.is_file():
        raise ValueError("an existing local ORA EEE CSV is required")
    with p.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames or not REQUIRED.issubset(set(reader.fieldnames)):
            raise ValueError("not an ORDS v0.3 EEE CSV (or file is a Git LFS pointer)")
        count = 0
        matched = 0
        states: Counter[str] = Counter()
        problems: Counter[str] = Counter()
        barriers: Counter[str] = Counter()
        truncated = False
        for row in reader:
            if count >= max_rows:
                truncated = True
                break
            count += 1
            if category.casefold() not in (row.get("product_category") or "").casefold():
                continue
            matched += 1
            states[(row.get("repair_status") or "not recorded")[:80]] += 1
            problems[(row.get("problem") or "not recorded")[:140]] += 1
            barriers[(row.get("repair_barrier_if_end_of_life") or "not recorded")[:140]] += 1
    return {
        "source": "Open Repair Alliance", "schema": "ORDS v0.3 EEE",
        "source_url": SOURCE, "source_license": LICENSE,
        "category_filter": category, "rows_scanned": count, "matching_rows": matched,
        "scan_truncated": truncated, "representative_sample": False,
        "repair_status_counts": dict(states.most_common(15)),
        "problem_counts": dict(problems.most_common(10)),
        "barrier_counts": dict(barriers.most_common(10)),
        "authority": "historical_community_repair_observations_only",
        "device_identity_verified": False, "repair_diagnosis_proven": False,
        "wiring_or_purchase_authorized": False, "mission_success": False,
    }

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hs-open-repair-candidates")
    parser.add_argument("--csv", required=True, help="Downloaded real ORA EEE CSV, not Git LFS pointer")
    parser.add_argument("--category", required=True)
    parser.add_argument("--max-rows", type=int, default=650000)
    args = parser.parse_args(argv)
    print(json.dumps(summarize_repairs(args.csv, category=args.category, max_rows=args.max_rows), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
