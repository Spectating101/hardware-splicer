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
from hardware_splicer.commercial_investigation import build_investigation_queue
from hardware_splicer.commercial_source_catalog import (
    normalize_historical_purchase_report,
    normalize_historical_regional_scan,
)
from hardware_splicer.commercial_cohort import build_commercial_cohort
from hardware_splicer.commercial_market_evidence import evaluate_market_evidence
from hardware_splicer.commercial_validation_backlog import build_validation_backlog
from hardware_splicer.commercial_validation_packets import build_validation_packets


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
    parser.add_argument("--purchase-report", action="append", type=Path, default=[])
    parser.add_argument("--regional-scan", action="append", type=Path, default=[])
    parser.add_argument("--market-evidence", action="append", type=Path, default=[])
    parser.add_argument("--as-of", default="2026-10-25")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not (args.case or args.pf_run or args.salvage_report
            or args.donor_discovery or args.purchase_screen
            or args.purchase_report or args.regional_scan or args.market_evidence):
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
        purchase_reports = [
            result
            for path in args.purchase_report
            for result in normalize_historical_purchase_report(load(path))
        ]
        regional = [
            result
            for path in args.regional_scan
            for result in normalize_historical_regional_scan(load(path))
        ]
        market_evidence = []
        for path in args.market_evidence:
            payload = load(path)
            market_evidence.append(evaluate_market_evidence(
                payload,
                candidate_id=payload.get("candidate_id"),
                market=payload.get("market"),
                currency=payload.get("currency"),
                exact_model=payload.get("exact_model"),
                latest_day=args.as_of,
            ))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    output = {
        "schema_version": "hardware_splicer.commercial_convergence_dossier.v0",
        "commercial_cases": evaluate_portfolio(cases),
        "product_factory_experiments": pf,
        "salvage_discovery_reports": salvage,
        "donor_discovery_catalogs": donor,
        "salvage_purchase_screens": purchase,
        "historical_salvage_economics": purchase_reports,
        "regional_product_concepts": regional,
        "market_evidence_screens": market_evidence,
        "purchase_authorized": False,
        "physical_authority_granted": False,
        "external_market_demand_proven": False,
        "notes": [
            "Each input retains its originating file path",
            "Target MSRP and salvage values stay hypotheses until qualified evidence",
            "Do not compare economics across TWD/CNY/IDR without explicit FX modeling",
        ],
    }
    output["investigation_queue"] = build_investigation_queue(output)
    output["cohort_review"] = build_commercial_cohort(output)
    output["validation_backlog"] = build_validation_backlog(output)
    if output["validation_backlog"]["record_count"] >= 30:
        output["validation_packets"] = build_validation_packets(output)
    text = json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 2 if (any(c["status"] == "INVALID" for c in output["commercial_cases"]["cases"])
                 or any(c["status"] == "INVALID" for c in market_evidence)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
