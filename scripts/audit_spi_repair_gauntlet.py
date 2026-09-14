#!/usr/bin/env python3
"""Independently audit frozen SPI Repair Gauntlet v1 artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "hardware_splicer.spi_repair_gauntlet_artifact_audit.v1"
MAX_PACKET_BYTES = 12_000
MAX_TOTAL_BYTES = 96_000
_FORBIDDEN_ACTOR_KEYS = {
    "profile",
    "expected_post_outcome",
    "required_check",
    "repair_actions",
    "gold_repair",
    "hidden_challenges",
}


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_size(value: Any) -> int:
    return len(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actor-packets", required=True, type=Path)
    parser.add_argument("--private-gold", required=True, type=Path)
    parser.add_argument("--scripted-control", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    actor = _load(args.actor_packets)
    gold = _load(args.private_gold)
    control = _load(args.scripted_control)
    summary = _load(args.summary)

    packets = actor.get("packets") if isinstance(actor, Mapping) else None
    if not isinstance(packets, list):
        raise SystemExit("actor-packets file must contain a packets array")

    challenge_ids: list[str] = []
    size_rows: list[dict[str, Any]] = []
    leakage: dict[str, list[str]] = {}
    authority_errors: list[str] = []
    for packet in packets:
        if not isinstance(packet, Mapping):
            raise SystemExit("actor packet must be an object")
        challenge_id = str(packet.get("challenge_id") or "")
        challenge_ids.append(challenge_id)
        size_rows.append(
            {
                "challenge_id": challenge_id,
                "actual_serialized_bytes": _canonical_size(packet),
                "packager_pre_metadata_bytes": packet.get("packet_size_bytes"),
            }
        )
        leaked = sorted(key for key in _FORBIDDEN_ACTOR_KEYS if key in packet)
        if leaked:
            leakage[challenge_id] = leaked
        boundary = packet.get("authority_boundary")
        if not isinstance(boundary, Mapping) or not (
            boundary.get("vendor_model_campaign_credit_eligible") is False
            and boundary.get("physical_correctness") == "UNPROVEN"
            and boundary.get("physical_authority_granted") is False
        ):
            authority_errors.append(challenge_id)

    actual_max = max((row["actual_serialized_bytes"] for row in size_rows), default=0)
    actual_total = sum(row["actual_serialized_bytes"] for row in size_rows)
    gold_ids = {
        str(row.get("challenge_id"))
        for row in gold.get("hidden_challenges", [])
        if isinstance(row, Mapping)
    } if isinstance(gold, Mapping) else set()
    control_rows = control.get("rows") if isinstance(control, Mapping) else None
    control_ids = {
        str(row.get("challenge_id"))
        for row in control_rows or []
        if isinstance(row, Mapping)
    }

    checks = {
        "exactly_twelve_actor_packets": len(packets) == 12,
        "unique_nonempty_challenge_ids": (
            len(challenge_ids) == len(set(challenge_ids)) and all(challenge_ids)
        ),
        "actual_packet_size_budget": actual_max <= MAX_PACKET_BYTES,
        "actual_total_size_budget": actual_total <= MAX_TOTAL_BYTES,
        "no_gold_keys_in_actor_packets": not leakage,
        "actor_file_declares_gold_absent": actor.get("gold_repairs_present") is False,
        "actor_authority_boundary_closed": not authority_errors,
        "gold_manifest_separate_and_complete": gold_ids == set(challenge_ids),
        "gold_manifest_marked_private": gold.get("actor_must_not_receive_this_manifest") is True,
        "scripted_control_complete": (
            control.get("control_pass") is True
            and control.get("challenge_count") == 12
            and control.get("accepted_count") == 12
            and control_ids == set(challenge_ids)
        ),
        "summary_consistent": (
            summary.get("challenge_count") == 12
            and summary.get("scripted_control_pass") is True
            and summary.get("accepted_scripted_repairs") == 12
            and summary.get("physical_authority_granted") is False
        ),
    }
    audit_pass = all(checks.values())
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "passed_repair_gauntlet_artifact_audit" if audit_pass else "failed_repair_gauntlet_artifact_audit",
        "audit_pass": audit_pass,
        "checks": checks,
        "challenge_ids": challenge_ids,
        "packet_sizes": size_rows,
        "actual_max_packet_bytes": actual_max,
        "actual_total_packet_bytes": actual_total,
        "gold_leakage": leakage,
        "authority_error_challenge_ids": authority_errors,
        "input_hashes": {
            "actor_packets_sha256": _sha256(args.actor_packets),
            "private_gold_sha256": _sha256(args.private_gold),
            "scripted_control_sha256": _sha256(args.scripted_control),
            "summary_sha256": _sha256(args.summary),
        },
        "model_inference_used": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"audit_pass": audit_pass, "actual_max_packet_bytes": actual_max, "actual_total_packet_bytes": actual_total}, sort_keys=True))
    return 0 if audit_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
