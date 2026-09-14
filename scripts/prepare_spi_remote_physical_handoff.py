#!/usr/bin/env python3
"""Build a deterministic provider-neutral remote physical-validation handoff."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.remote_physical_validation import (  # noqa: E402
    build_remote_physical_handoff,
    build_remote_physical_handoff_archive,
    build_remote_physical_return_template,
    render_remote_physical_test_plan,
)


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-packet", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--provider-id", default="contract-pcba-test-service")
    parser.add_argument("--provider-name", default="Contract PCBA Test Service")
    parser.add_argument(
        "--engagement-mode",
        choices=("pcba_production_and_test", "testing_only", "remote_lab"),
        default="pcba_production_and_test",
    )
    parser.add_argument("--service-url", default="")
    parser.add_argument(
        "--manufacturing-artifacts",
        type=Path,
        help="optional JSON array of role/artifact_id/content_hash/filename rows",
    )
    args = parser.parse_args()

    packet = _load_json(args.physical_packet)
    artifacts = (
        _load_json(args.manufacturing_artifacts)
        if args.manufacturing_artifacts is not None
        else []
    )
    if not isinstance(packet, dict):
        raise SystemExit("physical packet JSON must be an object")
    if not isinstance(artifacts, list):
        raise SystemExit("manufacturing artifacts JSON must be an array")

    handoff = build_remote_physical_handoff(
        packet,
        provider={
            "provider_id": args.provider_id,
            "provider_name": args.provider_name,
            "engagement_mode": args.engagement_mode,
            "service_url": args.service_url,
            "capabilities_requested": [
                "pcba_functional_test",
                "electrical_performance_test",
                "custom_test_fixture_review",
                "original_raw_measurement_export",
            ],
        },
        manufacturing_artifacts=artifacts,
    )
    template = build_remote_physical_return_template(handoff)
    archive = build_remote_physical_handoff_archive(handoff)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.out_dir / "REMOTE_TEST_REQUEST.json", handoff)
    _write_json(args.out_dir / "EVIDENCE_RETURN_MANIFEST.template.json", template)
    (args.out_dir / "REMOTE_TEST_PLAN.md").write_text(
        render_remote_physical_test_plan(handoff), encoding="utf-8"
    )
    archive_path = args.out_dir / "REMOTE_PHYSICAL_HANDOFF.zip"
    archive_path.write_bytes(archive)
    summary = {
        "schema_version": "hardware_splicer.remote_physical_handoff_preparation.v1",
        "handoff_id": handoff["handoff_id"],
        "archive": str(archive_path),
        "archive_sha256": "sha256:" + hashlib.sha256(archive).hexdigest(),
        "archive_size_bytes": len(archive),
        "ready_for_provider_quote": handoff["release_readiness"]["ready_for_provider_quote"],
        "production_artifact_set_complete": handoff["release_readiness"][
            "production_artifact_set_complete"
        ],
        "fabrication_release_ready": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
    }
    _write_json(args.out_dir / "PREPARATION_SUMMARY.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
