#!/usr/bin/env python3
"""Freeze the zero-inference SPI Repair Gauntlet v1 packets and scripted control."""

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

from hardware_splicer.spi_repair_gauntlet import (  # noqa: E402
    actor_packets_only,
    build_repair_gauntlet,
    run_scripted_repair_control,
)


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()

    gauntlet = build_repair_gauntlet()
    actor = actor_packets_only()
    control = run_scripted_repair_control()

    private_manifest = {
        "schema_version": "hardware_splicer.spi_repair_gauntlet_private_manifest.v1",
        "gauntlet_id": gauntlet["gauntlet_id"],
        "challenge_count": gauntlet["challenge_count"],
        "packet_budget": gauntlet["packet_budget"],
        "hidden_challenges": [
            {
                "challenge_id": row["challenge_id"],
                "profile": row["profile"],
                "required_check": row["required_check"],
                "allowed_paths": row["allowed_paths"],
                "expected_post_outcome": row["expected_post_outcome"],
                "initial_predicted_outcome": row["initial_result"]["predicted_outcome"],
            }
            for row in gauntlet["hidden_challenges"]
        ],
        "actor_must_not_receive_this_manifest": True,
        "model_inference_used": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
    }

    _write(args.out_dir / "actor_packets.json", actor)
    _write(args.out_dir / "private_gold_manifest.json", private_manifest)
    _write(args.out_dir / "scripted_control_report.json", control)

    summary = {
        "gauntlet_id": gauntlet["gauntlet_id"],
        "challenge_count": gauntlet["challenge_count"],
        "packet_budget": gauntlet["packet_budget"],
        "scripted_control_pass": control["control_pass"],
        "accepted_scripted_repairs": control["accepted_count"],
        "model_inference_used": False,
        "physical_authority_granted": False,
    }
    _write(args.out_dir / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0 if control["control_pass"] and gauntlet["packet_budget"]["budget_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
