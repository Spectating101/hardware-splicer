"""Evaluate a local HS commercial case without contacting sellers or making purchases.

Usage:
    PYTHONPATH=src python scripts/evaluate_commercial_value.py examples/commercial_value_case_twd.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hardware_splicer.commercial_value_routing import evaluate_commercial_case


def main() -> int:
    parser = argparse.ArgumentParser(description="HS internal commercial screening, advisory only")
    parser.add_argument("case", type=Path, help="JSON scenario with native currency")
    parser.add_argument("--output", type=Path, help="Write report to specified location")
    args = parser.parse_args()
    try:
        payload = json.loads(args.case.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        parser.error(f"cannot load scenario: {exc}")
    result = evaluate_commercial_case(payload)
    serialized = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    return 2 if result["status"] == "INVALID" else 0


if __name__ == "__main__":
    raise SystemExit(main())
