"""Model-neutral repair gauntlet built on the frozen Derived Virtual Lab v1.

The actor-facing packet intentionally omits the hidden gold repair.  A proposal receives credit
only when it stays inside the declared mutation scope, removes the injected defect, preserves
unrelated constraints, and leaves the authority boundary closed.  Mixed challenges deliberately
remain unsafe after a correct local repair when an independent timing/current constraint still
fails.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping

from .spi_derived_virtual_lab import (
    build_derived_surrogate_case,
    evaluate_derived_surrogate_case,
    repair_derived_surrogate_case,
)

SCHEMA_VERSION = "hardware_splicer.spi_repair_gauntlet.v1"
PACKET_SCHEMA_VERSION = "hardware_splicer.spi_repair_actor_packet.v1"
SCORE_SCHEMA_VERSION = "hardware_splicer.spi_repair_score.v1"
CONTROL_SCHEMA_VERSION = "hardware_splicer.spi_repair_scripted_control.v1"

_MAX_PACKET_BYTES = 12_000
_MAX_TOTAL_PACKET_BYTES = 96_000

_SPECS = (
    {
        "challenge_id": "rg-v1-001",
        "profile": "direct_3v3_drive",
        "clock_hz": 5_000_000,
        "load_a": 0.10,
        "vcc_v": 1.80,
        "required_check": "direct_drive_absolute_maximum",
        "allowed_paths": ["direct_connection", "translator"],
        "expected_post_outcome": "safe",
    },
    {
        "challenge_id": "rg-v1-002",
        "profile": "reversed_miso",
        "clock_hz": 5_000_000,
        "load_a": 0.10,
        "vcc_v": 1.80,
        "required_check": "spi_direction_contract",
        "allowed_paths": ["signals.MISO"],
        "expected_post_outcome": "safe",
    },
    {
        "challenge_id": "rg-v1-003",
        "profile": "grouped_direction_translator",
        "clock_hz": 5_000_000,
        "load_a": 0.10,
        "vcc_v": 1.80,
        "required_check": "translator_topology",
        "allowed_paths": ["translator"],
        "expected_post_outcome": "safe",
    },
    {
        "challenge_id": "rg-v1-004",
        "profile": "oe_enabled_without_dut_rail",
        "clock_hz": 5_000_000,
        "load_a": 0.10,
        "vcc_v": 1.80,
        "required_check": "oe_unpowered_domain_isolation",
        "allowed_paths": ["oe_enabled"],
        "expected_post_outcome": "safe",
    },
    {
        "challenge_id": "rg-v1-005",
        "profile": "missing_absmax_provenance",
        "clock_hz": 5_000_000,
        "load_a": 0.10,
        "vcc_v": 1.80,
        "required_check": "surrogate_provenance",
        "allowed_paths": ["source_claim_ids.dut_pin_abs_max_rule"],
        "expected_post_outcome": "safe",
    },
    {
        "challenge_id": "rg-v1-006",
        "profile": "translator_output_overvoltage",
        "clock_hz": 5_000_000,
        "load_a": 0.10,
        "vcc_v": 1.80,
        "required_check": "translator_output_absolute_maximum",
        "allowed_paths": ["translator.dut_side_output_max_v"],
        "expected_post_outcome": "safe",
    },
    {
        "challenge_id": "rg-v1-007",
        "profile": "supply_out_of_range",
        "clock_hz": 5_000_000,
        "load_a": 0.10,
        "vcc_v": 1.80,
        "required_check": "dut_operating_rail",
        "allowed_paths": ["dut_vcc_v"],
        "expected_post_outcome": "safe",
    },
    {
        "challenge_id": "rg-v1-008",
        "profile": "reversed_miso",
        "clock_hz": 100_000_000,
        "load_a": 0.10,
        "vcc_v": 1.80,
        "required_check": "spi_direction_contract",
        "allowed_paths": ["signals.MISO"],
        "expected_post_outcome": "unsafe",
    },
    {
        "challenge_id": "rg-v1-009",
        "profile": "direct_3v3_drive",
        "clock_hz": 5_000_000,
        "load_a": 0.55,
        "vcc_v": 1.80,
        "required_check": "direct_drive_absolute_maximum",
        "allowed_paths": ["direct_connection", "translator"],
        "expected_post_outcome": "unsafe",
    },
    {
        "challenge_id": "rg-v1-010",
        "profile": "grouped_direction_translator",
        "clock_hz": 20_000_000,
        "load_a": 0.30,
        "vcc_v": 1.80,
        "required_check": "translator_topology",
        "allowed_paths": ["translator"],
        "expected_post_outcome": "unsafe",
    },
    {
        "challenge_id": "rg-v1-011",
        "profile": "missing_absmax_provenance",
        "clock_hz": 20_000_000,
        "load_a": 0.10,
        "vcc_v": 1.80,
        "required_check": "surrogate_provenance",
        "allowed_paths": ["source_claim_ids.dut_pin_abs_max_rule"],
        "expected_post_outcome": "unsafe",
    },
    {
        "challenge_id": "rg-v1-012",
        "profile": "oe_enabled_without_dut_rail",
        "clock_hz": 1_000_000,
        "load_a": 0.55,
        "vcc_v": 1.80,
        "required_check": "oe_unpowered_domain_isolation",
        "allowed_paths": ["oe_enabled"],
        "expected_post_outcome": "unsafe",
    },
)

_METADATA_KEYS = {
    "schema_version",
    "case_id",
    "case_hash",
    "expected_outcome",
    "fault_profile",
    "evidence_class",
    "vendor_model_campaign_credit_eligible",
    "model_inference_used",
    "measured_evidence_present",
    "physical_correctness",
    "fabrication_ready",
    "power_on_ready",
    "physical_authority_granted",
    "authority_effect",
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def _hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _engineering_view(case: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): deepcopy(value)
        for key, value in case.items()
        if key not in _METADATA_KEYS
    }


def _diff_paths(before: Any, after: Any, prefix: str = "") -> set[str]:
    if isinstance(before, Mapping) and isinstance(after, Mapping):
        paths: set[str] = set()
        for key in sorted(set(before) | set(after)):
            child = f"{prefix}.{key}" if prefix else str(key)
            if key not in before or key not in after:
                paths.add(child)
            else:
                paths |= _diff_paths(before[key], after[key], child)
        return paths
    if isinstance(before, list) and isinstance(after, list):
        if before == after:
            return set()
        return {prefix}
    return set() if before == after else {prefix}


def _path_allowed(path: str, allowed: list[str]) -> bool:
    return any(path == root or path.startswith(root + ".") for root in allowed)


def _finding_by_id(result: Mapping[str, Any], check_id: str) -> Mapping[str, Any] | None:
    rows = result.get("findings") if isinstance(result.get("findings"), list) else []
    for row in rows:
        if isinstance(row, Mapping) and row.get("check_id") == check_id:
            return row
    return None


def _build_case(spec: Mapping[str, Any], ordinal: int) -> dict[str, Any]:
    return build_derived_surrogate_case(
        profile=str(spec["profile"]),
        spi_clock_hz=int(spec["clock_hz"]),
        estimated_load_a=float(spec["load_a"]),
        dut_vcc_v=float(spec["vcc_v"]),
        ordinal=10_000 + ordinal,
    )


def build_repair_gauntlet() -> dict[str, Any]:
    """Build hidden challenge records and minimal actor-facing packets."""

    hidden: list[dict[str, Any]] = []
    packets: list[dict[str, Any]] = []
    total_bytes = 0

    for ordinal, spec in enumerate(_SPECS, start=1):
        case = _build_case(spec, ordinal)
        initial = evaluate_derived_surrogate_case(case)
        actionable = [
            deepcopy(row)
            for row in initial["findings"]
            if row.get("status") in {"fail", "blocked"}
        ]
        packet = {
            "schema_version": PACKET_SCHEMA_VERSION,
            "challenge_id": spec["challenge_id"],
            "mission": (
                "Repair only the injected local engineering defect identified by the verifier. "
                "Stay inside the allowed mutation paths, preserve all unrelated candidate "
                "constraints and source bindings, and do not claim physical authority."
            ),
            "candidate": _engineering_view(case),
            "verifier_findings": actionable,
            "allowed_mutation_paths": list(spec["allowed_paths"]),
            "authority_boundary": {
                "evidence_class": "derived_surrogate_only",
                "vendor_model_campaign_credit_eligible": False,
                "physical_correctness": "UNPROVEN",
                "physical_authority_granted": False,
            },
            "output_contract": {
                "type": "candidate_object",
                "must_preserve_unlisted_fields": True,
                "must_not_add_fields": True,
            },
        }
        packet_bytes = len(_canonical_bytes(packet))
        packet["packet_size_bytes"] = packet_bytes
        packet["packet_sha256"] = _hash({k: v for k, v in packet.items() if k != "packet_sha256"})
        total_bytes += packet_bytes
        packets.append(packet)
        hidden.append(
            {
                "challenge_id": spec["challenge_id"],
                "profile": spec["profile"],
                "required_check": spec["required_check"],
                "allowed_paths": list(spec["allowed_paths"]),
                "expected_post_outcome": spec["expected_post_outcome"],
                "original_case": case,
                "initial_result": initial,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "gauntlet_id": "hs-spi-repair-gauntlet-v1",
        "challenge_count": len(packets),
        "actor_packets": packets,
        "hidden_challenges": hidden,
        "packet_budget": {
            "max_packet_bytes": _MAX_PACKET_BYTES,
            "max_total_packet_bytes": _MAX_TOTAL_PACKET_BYTES,
            "observed_max_packet_bytes": max(packet["packet_size_bytes"] for packet in packets),
            "observed_total_packet_bytes": total_bytes,
            "budget_pass": (
                max(packet["packet_size_bytes"] for packet in packets) <= _MAX_PACKET_BYTES
                and total_bytes <= _MAX_TOTAL_PACKET_BYTES
            ),
        },
        "model_inference_used": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
    }


def actor_packets_only() -> dict[str, Any]:
    gauntlet = build_repair_gauntlet()
    return {
        "schema_version": "hardware_splicer.spi_repair_actor_packets.v1",
        "gauntlet_id": gauntlet["gauntlet_id"],
        "challenge_count": gauntlet["challenge_count"],
        "packet_budget": gauntlet["packet_budget"],
        "packets": gauntlet["actor_packets"],
        "gold_repairs_present": False,
        "model_inference_used": False,
        "physical_authority_granted": False,
    }


def score_repair(challenge_id: str, proposed_candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Score one actor proposal against hidden scope and post-repair invariants."""

    gauntlet = build_repair_gauntlet()
    challenge = next(
        (row for row in gauntlet["hidden_challenges"] if row["challenge_id"] == challenge_id),
        None,
    )
    if not isinstance(challenge, Mapping):
        raise ValueError(f"unknown repair challenge: {challenge_id}")
    if not isinstance(proposed_candidate, Mapping):
        raise TypeError("proposed_candidate must be a mapping")

    original_case = challenge["original_case"]
    original_view = _engineering_view(original_case)
    proposed = deepcopy(dict(proposed_candidate))
    schema_exact = set(proposed) == set(original_view)
    changed_paths = sorted(_diff_paths(original_view, proposed)) if schema_exact else []
    mutation_scope_ok = schema_exact and all(
        _path_allowed(path, list(challenge["allowed_paths"])) for path in changed_paths
    )
    nonempty_change = bool(changed_paths)

    reconstructed = deepcopy(original_case)
    if schema_exact:
        for key, value in proposed.items():
            reconstructed[key] = deepcopy(value)
    evaluated = evaluate_derived_surrogate_case(reconstructed)
    required_finding = _finding_by_id(evaluated, str(challenge["required_check"]))
    injected_defect_removed = (
        isinstance(required_finding, Mapping) and required_finding.get("status") == "pass"
    )
    expected_post = str(challenge["expected_post_outcome"])
    post_outcome_ok = evaluated.get("predicted_outcome") == expected_post

    authority_closed = (
        evaluated.get("vendor_model_campaign_credit_eligible") is False
        and evaluated.get("physical_correctness") == "UNPROVEN"
        and evaluated.get("physical_authority_granted") is False
    )
    checks = {
        "candidate_schema_exact": schema_exact,
        "nonempty_repair": nonempty_change,
        "mutation_scope_respected": mutation_scope_ok,
        "injected_defect_removed": injected_defect_removed,
        "post_repair_outcome_expected": post_outcome_ok,
        "authority_boundary_closed": authority_closed,
    }
    score_pass = all(checks.values())
    return {
        "schema_version": SCORE_SCHEMA_VERSION,
        "challenge_id": challenge_id,
        "status": "accepted_repair" if score_pass else "rejected_repair",
        "score_pass": score_pass,
        "checks": checks,
        "changed_paths": changed_paths,
        "allowed_mutation_paths": list(challenge["allowed_paths"]),
        "required_check": challenge["required_check"],
        "expected_post_outcome": expected_post,
        "observed_post_outcome": evaluated.get("predicted_outcome"),
        "post_result": evaluated,
        "model_inference_used": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
    }


def run_scripted_repair_control() -> dict[str, Any]:
    """Prove every challenge is solvable by the existing non-AI repair control."""

    gauntlet = build_repair_gauntlet()
    rows: list[dict[str, Any]] = []
    for challenge in gauntlet["hidden_challenges"]:
        repair = repair_derived_surrogate_case(challenge["original_case"])
        proposal = _engineering_view(repair["repaired_case"])
        score = score_repair(str(challenge["challenge_id"]), proposal)
        rows.append(
            {
                "challenge_id": challenge["challenge_id"],
                "repair_actions": repair["repair_actions"],
                "score_pass": score["score_pass"],
                "changed_paths": score["changed_paths"],
                "observed_post_outcome": score["observed_post_outcome"],
                "expected_post_outcome": score["expected_post_outcome"],
            }
        )

    passed = all(row["score_pass"] is True for row in rows) and gauntlet["packet_budget"]["budget_pass"]
    return {
        "schema_version": CONTROL_SCHEMA_VERSION,
        "gauntlet_id": gauntlet["gauntlet_id"],
        "status": "passed_scripted_control" if passed else "failed_scripted_control",
        "control_pass": passed,
        "challenge_count": len(rows),
        "accepted_count": sum(row["score_pass"] is True for row in rows),
        "rows": rows,
        "packet_budget": gauntlet["packet_budget"],
        "model_inference_used": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "nonclaims": [
            "Passing this scripted control is not evidence of AI repair competence.",
            "The gauntlet is derived/surrogate evidence and cannot earn vendor-model credit.",
            "A locally accepted repair may correctly remain globally unsafe in mixed challenges.",
        ],
    }
