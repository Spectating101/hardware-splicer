#!/usr/bin/env python3
"""Recompute Taiwan dual-touch component budgets from dated source observations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hardware_splicer.taiwan_sourcing_budget import calculate

DEFAULT_SOURCE = "examples/cyberdeck/dual_touch/sourcing/taiwan_snapshot_20261106.json"
DEFAULT_OUT = "examples/cyberdeck/dual_touch/sourcing/taiwan_budget_receipt.json"


def within_repo(relative: str) -> Path:
    path = Path(relative)
    resolved = (ROOT / path).resolve()
    if path.is_absolute() or not resolved.is_relative_to(ROOT):
        raise ValueError("sourcing input/output must be within repository")
    return resolved


def run(source: str = DEFAULT_SOURCE) -> dict:
    return calculate(within_repo(source).read_bytes())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=DEFAULT_SOURCE)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--check-only", action="store_true")
    opts = ap.parse_args()
    receipt = run(opts.source)
    if not opts.check_only:
        path = within_repo(opts.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for key, val in receipt["scenarios"].items():
        print(f"{key}: NT$ {val['total_twd']:,} (estimate ONLY, stock unverified)")
    print("Purchase authorization:", receipt["purchase_authorized"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
