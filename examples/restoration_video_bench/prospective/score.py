"""Score an externally reviewed repair only AFTER the prediction digest is frozen.

Not used by prediction CI. Outcomes are NEVER committed to the prediction
branch; a separate reviewer supplies their creator-observed/instrumented label.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from predict import validate_receipt


def adjudicate(receipt: dict, outcome: dict, expected_digest: str) -> dict:
    validate_receipt(receipt, expected_digest)
    if outcome.get("case_id") != receipt.get("case_id"):
        raise ValueError("case ID mismatch")
    if outcome.get("source_url") != receipt.get("source_url"):
        raise ValueError("video source mismatch")
    status = outcome.get("adjudication_status")
    if status not in {"resolved", "unresolved", "ambiguous"}:
        raise ValueError("reviewer must explicitly adjudicate or defer")
    if not outcome.get("reviewer") or not outcome.get("evidence_description"):
        raise ValueError("reviewer identity and evidence description required")
    label = outcome.get("root_cause") if status == "resolved" else None
    if status == "resolved" and not isinstance(label, str):
        raise ValueError("resolved outcome requires root cause label")
    was_abstained = receipt["decision"] == "ABSTAIN_DEVICE_INCOMPATIBLE"
    return {
        "schema": "hs.restoration.prospective_adjudication.v1",
        "case_id": receipt["case_id"],
        "sealed_prediction_sha256": expected_digest,
        "adjudication_status": status,
        "outcome_quality": outcome.get("quality", "creator_report_unverified"),
        "qualified_candidate_hit": (
            label in receipt["qualified_hypothesis_ids"] if label else None
        ),
        "raw_baseline_top1_hit": (
            label == receipt["baseline_first_choice"] if label else None
        ),
        "HS_abstained": was_abstained,
        "HS_diagnosed_repair": False,
        "HS_performed_repair": False,
        "note": "An abstention is not scored as a successful fault diagnosis.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="POST-review scoring; not a pre-outcome command")
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--external-outcome", type=Path, required=True)
    parser.add_argument("--expected-receipt-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    gold = json.loads(args.external_outcome.read_text(encoding="utf-8"))
    result = adjudicate(receipt, gold, args.expected_receipt_sha256)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
