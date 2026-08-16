#!/usr/bin/env python3
"""Evaluate a persisted selective-evidence-impact case.

This runner records deterministic impact plumbing only. A passing dry-run case is
not physical evidence, independent-user evidence, or proof of platform economics.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Running a file from scripts/ puts that directory first on sys.path. This repo
# also has scripts/hardware_splicer.py, which would otherwise shadow the installed
# hardware_splicer package. Pin src/ before importing the package.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from hardware_splicer.evidence_impact import (  # noqa: E402
    evaluate_evidence_impact,
    score_evidence_invalidation,
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
    report = evaluate_evidence_impact(case)
    adjudication = case.get("adjudication")
    score = None
    if report.get("status") == "evaluated" and isinstance(adjudication, dict):
        score = score_evidence_invalidation(
            report,
            expected_invalidated_evidence_ids=adjudication.get(
                "expected_invalidated_evidence_ids", []
            ),
            adjudicated_evidence_ids=adjudication.get("adjudicated_evidence_ids"),
        )

    payload = {
        "mode": "deterministic_evidence_impact_dry_run",
        "physical_evidence": False,
        "commercial_economics_proven": False,
        "independent_adjudication": False,
        "case_id": case.get("case_id"),
        "report": report,
        "score": score,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"case_id={payload['case_id']}")
    print(f"status={report.get('status')}")
    print(f"summary={json.dumps(report.get('summary') or {}, sort_keys=True)}")
    if score is not None:
        print(f"score_status={score.get('status')}")
        print(
            "invalidation_counts="
            + json.dumps(
                {
                    "tp": score.get("correctly_invalidated_count"),
                    "fp": score.get("unnecessarily_invalidated_count"),
                    "fn": score.get("missed_invalidation_count"),
                },
                sort_keys=True,
            )
        )

    if report.get("status") != "evaluated":
        return 2
    if score is not None and score.get("status") != "scored":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
