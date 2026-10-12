#!/usr/bin/env python3
"""Audit treatment parity between Condition A (advisory) and Condition B (constrained).

Builds both request envelopes for the frozen corpus without calling a provider.
A pass means the comparison is not confounded at request-construction time.
It is not a scored paired result and grants no physical authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from hardware_splicer.cleanroom_unseen_spi_flash_experiment import (  # noqa: E402
    build_unseen_spi_flash_cases,
    validate_unseen_spi_flash_corpus,
)
from hardware_splicer.paired_evaluation import (  # noqa: E402
    CONDITION_ADVISORY,
    CONDITION_CONSTRAINED,
    DEFAULT_MAX_OUTPUT_TOKENS,
    audit_treatment_parity,
    build_request_payload,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-url", default="https://example.invalid/mcp")
    parser.add_argument("--model", default="test-model")
    parser.add_argument("--max-output-tokens", type=int, default=DEFAULT_MAX_OUTPUT_TOKENS)
    parser.add_argument("--out", default="artifacts/paired-evaluation/PARITY_AUDIT.json")
    args = parser.parse_args()

    corpus_validation = validate_unseen_spi_flash_corpus()
    if not corpus_validation.get("pass"):
        raise SystemExit("refusing parity audit because the frozen unseen corpus validation failed")

    rows = []
    failures = []
    for index, case in enumerate(build_unseen_spi_flash_cases(), start=1):
        project_id = f"parity-project-{index:02d}"
        snapshot_text = json.dumps(case.snapshot, ensure_ascii=False)
        hidden = [
            case.case_id,
            case.equivalence_group,
            case.perturbation_kind,
            str(case.project_revision) if case.project_revision is not None else "",
        ]
        if isinstance(case.metadata, dict):
            for value in case.metadata.values():
                token = str(value) if value is not None else ""
                if token and token not in snapshot_text:
                    hidden.append(token)
        hidden = [token for token in hidden if token and token not in snapshot_text]
        constrained = build_request_payload(
            condition=CONDITION_CONSTRAINED,
            case=case,
            project_id=project_id,
            model=args.model,
            max_output_tokens=args.max_output_tokens,
            server_url=args.server_url,
        )
        advisory = build_request_payload(
            condition=CONDITION_ADVISORY,
            case=case,
            project_id=project_id,
            model=args.model,
            max_output_tokens=args.max_output_tokens,
            server_url=args.server_url,
        )
        audit = audit_treatment_parity(constrained, advisory, hidden_markers=hidden)
        rows.append({"case_id": case.case_id, "pass": audit["pass"], "failures": audit["failures"]})
        if not audit["pass"]:
            failures.extend(f"{case.case_id}: {item}" for item in audit["failures"])

    payload = {
        "schema": "hardware_splicer.paired_evaluation_parity_run.v1",
        "pass": not failures,
        "case_count": len(rows),
        "failed_case_count": sum(0 if row["pass"] else 1 for row in rows),
        "failures": failures,
        "cases": rows,
        "physical_authority_granted": False,
        "paired_result_claimed": False,
        "claim_ceiling": (
            "Request-envelope parity across the frozen corpus. Not a transport pilot, "
            "scored paired tranche, or physical result."
        ),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    print(f"parity_audit={out}")
    return 0 if payload["pass"] else 9


if __name__ == "__main__":
    raise SystemExit(main())
