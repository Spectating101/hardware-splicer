#!/usr/bin/env python3
"""Run source-bound HS RC donor→rover feasibility and work-package audit.

The existing full KiCad splice/compile remains a distinct optional evidence
step. A passed software gate is NOT donor validation or fabrication approval.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from hardware_splicer.donor_to_device_v1 import build_donor_to_device_review  # noqa E402

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--intake", type=Path, default=ROOT/"examples/intakes/splice_robot_drive_brief.json")
    p.add_argument("--fixture", type=Path, default=ROOT/"examples/fixtures/splice_donor_rc_motor_board.json")
    p.add_argument("--splice-result", type=Path)
    p.add_argument("--out", type=Path, required=True)
    a=p.parse_args()
    review=build_donor_to_device_review(
        intake_path=a.intake, donor_fixture_path=a.fixture,
        splice_result_path=a.splice_result, output_dir=a.out)
    print(json.dumps({
        "status":review["status"],"case_id":review["case_id"],
        "source_donor_fixture_is_physical":review["source"]["fixture_is_measured_physical_donor"],
        "reuse_candidates":len(review["reuse_actions"]),
        "interface_checks":len(review["splice_feasibility"]["checks"]),
        "required_bench_gates":len(review["acceptance_gates"]),
        "carrier_compilation":review["carrier_compilation"]["status"],
        "motor_motion_authorized":review["motor_motion_authorized"],
        "output":str(a.out/"DONOR_DEVICE_REVIEW.json"),
    },indent=2))
    return 0  # A blocked physical release is the CORRECT successful audit result.

if __name__ == "__main__":
    raise SystemExit(main())
