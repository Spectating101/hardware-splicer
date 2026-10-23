"""Read existing HS source reports into one advisory-only commercial dossier.

Examples:
  PYTHONPATH=src python scripts/converge_commercial_sources.py \
      --case examples/commercial_value_case_twd.json \
      --salvage-report apps/circuit-ai/eval/salvage_workflow_report.json

For open PF PRs, export each run JSON from its source branch before passing
--pf-run; this command never rebases or claims evidence from another branch.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hardware_splicer.commercial_value_routing import (
    evaluate_portfolio, normalize_product_factory_run,
    normalize_salvage_opportunities, normalize_donor_discovery,
    normalize_salvage_purchase_screen,
)


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="HS source convergence (read-only advisory)")
    parser.add_argument("--case", action="append", type=Path, default=[])
    parser.add_argument("--pf-run", action="append", type=Path, default=[])
    parser.add_argument("--salvage-report", action="append", type=Path, default=[])
    parser.add_argument("--donor-discovery", action="append", type=Path, default=[])
    parser.add_argument("--purchase-screen", action="append", type=Path, default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not (args.case or args.pf_run or args.salvage_report
            or args.donor_discovery or args.purchase_screen):
        parser.error("at least one supported source required")

    try:
        cases = [load(path) for path in args.case]
        pf = [
            normalize_product_factory_run(load(path), source_ref=str(path))
            for path in args.pf_run
        ]
        salvage = [
            {
                "source_ref": str(path),
                "opportunities": normalize_salvage_opportunities(
                    load(path), source_ref=str(path),
                ),
            }
            for path in args.salvage_report
        ]
        donor = [
            {
                "source_ref": str(path),
                "listings": normalize_donor_discovery(load(path), source_ref=str(path)),
            }
            for path in args.donor_discovery
        ]
        purchase = [
            normalize_salvage_purchase_screen(load(path), source_ref=str(path))
            for path in args.purchase_screen
        ]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    output = {
        "schema_version": "hardware_splicer.commercial_convergence_dossier.v0",
        "commercial_cases": evaluate_portfolio(cases),
        "product_factory_experiments": pf,
        "salvage_discovery_reports": salvage,
        "donor_discovery_catalogs": donor,
        "salvage_purchase_screens": purchase,
        "purchase_authorized": False,
        "physical_authority_granted": False,
        "external_market_demand_proven": False,
        "notes": [
            "Each input retains its originating file path",
            "Target MSRP and salvage values stay hypotheses until qualified evidence",
            "Do not compare economics across TWD/CNY/IDR without explicit FX modeling",
        ],
    }
    text = json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 2 if any(c["status"] == "INVALID" for c in output["commercial_cases"]["cases"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
