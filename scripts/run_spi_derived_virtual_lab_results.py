#!/usr/bin/env python3
"""Export per-case results for the frozen Derived Virtual Lab v1 corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
src_root = str(SRC_ROOT)
while src_root in sys.path:
    sys.path.remove(src_root)
sys.path.insert(0, src_root)

from hardware_splicer.spi_derived_virtual_lab import (  # noqa: E402
    evaluate_derived_surrogate_case,
    generate_derived_surrogate_corpus,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    rows = []
    for case in generate_derived_surrogate_corpus():
        result = evaluate_derived_surrogate_case(case)
        rows.append(
            {
                "case_id": case["case_id"],
                "case_hash": case["case_hash"],
                "fault_profile": case["fault_profile"],
                "expected_outcome": case["expected_outcome"],
                "predicted_outcome": result["predicted_outcome"],
                "status": result["status"],
                "counts": result["counts"],
                "findings": result["findings"],
                "evidence_class": result["evidence_class"],
                "vendor_model_campaign_credit_eligible": result[
                    "vendor_model_campaign_credit_eligible"
                ],
                "physical_correctness": result["physical_correctness"],
                "physical_authority_granted": result["physical_authority_granted"],
            }
        )

    payload = {
        "schema_version": "hardware_splicer.spi_derived_virtual_lab_results.v1",
        "benchmark_id": "hs-spi-derived-virtual-lab-v1",
        "case_count": len(rows),
        "rows": rows,
        "evidence_class": "derived_surrogate_only",
        "vendor_model_campaign_credit_eligible": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"case_count": len(rows), "out": str(args.out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
