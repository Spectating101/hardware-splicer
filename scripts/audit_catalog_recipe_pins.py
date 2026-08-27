#!/usr/bin/env python3
"""Audit catalog recipe wire endpoints against module truth and engine pads."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hardware_splicer.catalog_recipe_pin_audit import audit_catalog_recipe_pins


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default="artifacts/catalog-recipe-pin-audit/CATALOG_RECIPE_PIN_AUDIT.json",
        help="Output report path",
    )
    args = parser.parse_args()

    report = audit_catalog_recipe_pins()
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "recipe_count": report["recipe_count"],
        "checked_endpoint_count": report["checked_endpoint_count"],
        "blocking_finding_count": report["blocking_finding_count"],
        "affected_builds": sorted(report["findings_by_build"]),
        "report_path": str(out),
    }, indent=2))
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
