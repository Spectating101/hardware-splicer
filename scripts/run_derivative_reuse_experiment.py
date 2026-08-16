#!/usr/bin/env python3
"""Run a manifest-derived reuse prediction and optional outer adjudication."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from hardware_splicer.derivative_reuse import (
    adjudicate_derivative_reuse,
    predict_derivative_reuse,
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("case JSON must contain an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    case = _load(args.case)
    prediction = predict_derivative_reuse(
        case.get("baseline_manifest") or {},
        case.get("candidate_manifest") or {},
        case.get("inherited_evidence_items") or [],
    )

    adjudication_result = None
    adjudication = case.get("adjudication")
    if prediction.get("status") == "predicted" and isinstance(adjudication, dict):
        adjudication_result = adjudicate_derivative_reuse(
            prediction,
            expected_invalidated_evidence_ids=adjudication.get(
                "expected_invalidated_evidence_ids", []
            ),
            adjudicated_evidence_ids=adjudication.get("adjudicated_evidence_ids"),
            adjudicator=str(adjudication.get("adjudicator") or ""),
            adjudication_basis=str(adjudication.get("adjudication_basis") or ""),
        )

    payload = {
        "mode": "capability_derivative_reuse_experiment",
        "case_id": case.get("case_id"),
        "claim_ceiling": case.get("claim_ceiling", "prediction_only"),
        "physical_evidence": False,
        "commercial_economics_proven": False,
        "prediction": prediction,
        "adjudication": adjudication_result,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"case_id={payload['case_id']}")
    print(f"prediction_status={prediction.get('status')}")
    print(f"prediction_hash={prediction.get('prediction_hash')}")
    if prediction.get("impact_report"):
        print(
            "impact_summary="
            + json.dumps(prediction["impact_report"].get("summary") or {}, sort_keys=True)
        )
    if adjudication_result is not None:
        print(f"adjudication_status={adjudication_result.get('status')}")

    if prediction.get("status") != "predicted":
        return 2
    if adjudication_result is not None and adjudication_result.get("status") != "adjudicated":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
