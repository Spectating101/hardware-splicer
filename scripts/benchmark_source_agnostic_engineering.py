#!/usr/bin/env python3
"""Run reconstruction, synthesis, repair, and field-evolution benchmarks."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from hardware_splicer.source_agnostic_benchmark import (  # noqa: E402
    evaluate_source_agnostic_suite,
    load_source_agnostic_scenario,
)

CASE_DIR = ROOT / "examples" / "source_agnostic"
DEFAULT_CASES = [
    CASE_DIR / "conflicting_quadruped_reconstruction.json",
    CASE_DIR / "requirement_only_inspection_rover.json",
    CASE_DIR / "donor_repair_rover.json",
    CASE_DIR / "field_failure_payload_revision.json",
]


def main(argv: list[str] | None = None) -> int:
    args = list(argv or sys.argv[1:])
    paths = [Path(value) for value in args] if args else DEFAULT_CASES
    suite = evaluate_source_agnostic_suite(
        load_source_agnostic_scenario(path) for path in paths
    )
    print(json.dumps(suite, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
