#!/usr/bin/env python3
"""Export a derived assurance view or blind claim-review packet from a project."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path[:] = [
    str(_REPO_ROOT / "src"),
    *[entry for entry in sys.path if Path(entry or os.curdir).resolve() != _SCRIPT_DIR],
]

from hardware_splicer.engineering_assurance import (
    build_engineering_assurance,
    build_independent_review_packet,
    evaluate_assurance_delta,
)
from hardware_splicer.project_store import ProjectStore


def _values(items: list[str]) -> list[str]:
    return sorted({item.strip() for item in items if item.strip()})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--revision", type=int)
    parser.add_argument(
        "--kind", choices=("assurance", "review-packet", "delta"), default="assurance"
    )
    parser.add_argument("--changed-source-id", action="append", default=[])
    parser.add_argument("--changed-claim-id", action="append", default=[])
    parser.add_argument("--unresolved-source-id", action="append", default=[])
    parser.add_argument("--unresolved-claim-id", action="append", default=[])
    args = parser.parse_args()

    store = ProjectStore(args.project_root)
    envelope = store.load(args.project_id, args.revision)
    assurance = build_engineering_assurance(
        envelope["snapshot"],
        project_id=args.project_id,
        revision=int(envelope["revision"]),
    )
    if args.kind == "review-packet":
        result = build_independent_review_packet(assurance)
    elif args.kind == "delta":
        result = evaluate_assurance_delta(
            assurance,
            changed_source_ids=_values(args.changed_source_id),
            changed_claim_ids=_values(args.changed_claim_id),
            unresolved_source_ids=_values(args.unresolved_source_id),
            unresolved_claim_ids=_values(args.unresolved_claim_id),
        )
    else:
        result = assurance
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
