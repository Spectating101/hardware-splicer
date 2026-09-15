"""Revision-bound physical validation packets for canonical project snapshots.

This module bridges bounded ``preFabricationPlan`` projects to the existing audited
physical-evidence models.  It does not create a second evidence authority: raw files,
calibration records, evidence envelopes, and authorization ledger entries retain their
canonical schemas and validators.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any, Mapping, Sequence

from .physical_evidence import PhysicalEvidenceKind
from .physical_evidence_ledger import PhysicalEvidenceEnvelope


PROJECT_PHYSICAL_VALIDATION_SCHEMA = "hardware_splicer.project_physical_validation.v1"
PROJECT_PHYSICAL_VALIDATION_PACKET_SCHEMA = (
    "hardware_splicer.project_physical_validation_packet.v1"
)

_NON_CANDIDATE_SURFACES = {
    "physicalValidation",
    # Exporting a package must not stale measurements against unchanged engineering.
    "engineeringPackages",
}


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _candidate_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    candidate = deepcopy(dict(snapshot))
    for key in _NON_CANDIDATE_SURFACES:
        candidate.pop(key, None)
    return candidate


def project_candidate_boundary(
    snapshot: Mapping[str, Any], *, project_id: str
) -> dict[str, str]:
    """Hash the engineering candidate while excluding only audit/export appendages."""

    digest = _canonical_hash(
        {"project_id": project_id, "snapshot": _candidate_snapshot(snapshot)}
    )
    return {
        "candidate_revision": f"{project_id}@{digest[7:23]}",
        "candidate_snapshot_hash": digest,
    }


def _text_corpus(snapshot: Mapping[str, Any]) -> str:
    values = [
        snapshot.get("name"),
        snapshot.get("mission"),
        snapshot.get("engineering_status"),
        snapshot.get("preFabricationPlan"),
    ]
    return json.dumps(values, ensure_ascii=False, default=str).casefold()


def _spi_flash_gates() -> list[dict[str, Any]]:
    return [
        {
            "gate_id": "identify-dut",
            "phase": 0,
            "kind": PhysicalEvidenceKind.INSPECTION.value,
            "procedure_id": "hs.spi.identify-dut.v1",
            "title": "Record the exact physical DUT identity",
            "required_measured_fields": [
                "observed_top_marking",
                "observed_package",
                "observed_pin_count",
                "observed_dimensions_mm",
            ],
            "required_raw_media": ["image/*"],
            "prerequisite_gate_ids": [],
            "requires_authorized_operation": None,
            "safety": "Unpowered inspection only.",
        },
        {
            "gate_id": "identify-programmer",
            "phase": 0,
            "kind": PhysicalEvidenceKind.INSPECTION.value,
            "procedure_id": "hs.spi.identify-programmer.v1",
            "title": "Record the exact programmer and interface identity",
            "required_measured_fields": [
                "manufacturer",
                "model",
                "serial_or_asset_id",
                "interface_connector",
            ],
            "required_raw_media": ["image/*"],
            "prerequisite_gate_ids": [],
            "requires_authorized_operation": None,
            "safety": "Do not connect the DUT or enable target power.",
        },
        {
            "gate_id": "identify-adapter-artifact",
            "phase": 0,
            "kind": PhysicalEvidenceKind.INSPECTION.value,
            "procedure_id": "hs.spi.identify-adapter-artifact.v1",
            "title": "Bind the assembled adapter and translator to immutable identities",
            "required_measured_fields": [
                "assembly_id",
                "assembly_revision",
                "translator_orderable_mpn",
                "translator_package",
                "schematic_hash",
                "pcb_or_wiring_hash",
            ],
            "required_raw_media": ["image/*", "application/*"],
            "prerequisite_gate_ids": [],
            "requires_authorized_operation": None,
            "safety": "Unpowered inspection only; no identity may be inferred from family name.",
        },
        {
            "gate_id": "cold-continuity-and-isolation",
            "phase": 1,
            "kind": PhysicalEvidenceKind.ELECTRICAL.value,
            "procedure_id": "hs.spi.cold-continuity-isolation.v1",
            "title": "Verify pin mapping, ground continuity, shorts, and domain isolation",
            "required_measured_fields": [
                "net_by_net_results",
                "ground_continuity_ohm",
                "vcc_1v8_to_ground_ohm",
                "vcc_3v3_to_ground_ohm",
                "domain_isolation_results",
            ],
            "required_raw_media": ["text/csv", "application/json"],
            "prerequisite_gate_ids": [
                "identify-dut",
                "identify-programmer",
                "identify-adapter-artifact",
            ],
            "requires_authorized_operation": None,
            "safety": "All sources disconnected; discharge rails before resistance measurements.",
        },
        {
            "gate_id": "current-limited-power-up",
            "phase": 2,
            "kind": PhysicalEvidenceKind.ELECTRICAL.value,
            "procedure_id": "hs.spi.current-limited-power-up.v1",
            "title": "Measure startup and steady-state rails under a current limit",
            "required_measured_fields": [
                "supply_current_limit_a",
                "dut_vcc_min_v",
                "dut_vcc_max_v",
                "startup_peak_current_a",
                "steady_state_current_a",
                "power_off_backfeed_current_a",
            ],
            "required_raw_media": ["text/csv", "application/json"],
            "prerequisite_gate_ids": ["cold-continuity-and-isolation"],
            "requires_authorized_operation": "bench_power",
            "safety": "Requires an applicable human BENCH_POWER authorization before energizing.",
        },
        {
            "gate_id": "logic-level-and-timing-capture",
            "phase": 3,
            "kind": PhysicalEvidenceKind.ELECTRICAL.value,
            "procedure_id": "hs.spi.logic-level-timing.v1",
            "title": "Capture both voltage domains and timing at the selected load and clock",
            "required_measured_fields": [
                "spi_clock_hz",
                "host_side_levels_v",
                "dut_side_levels_v",
                "rise_fall_times_s",
                "propagation_delays_s",
                "overshoot_undershoot_v",
            ],
            "required_raw_media": ["text/csv", "application/octet-stream"],
            "prerequisite_gate_ids": ["current-limited-power-up"],
            "requires_authorized_operation": "bench_power",
            "safety": "Begin at the lowest supported clock; stop on rail, current, or thermal excursion.",
        },
        {
            "gate_id": "read-only-jedec-identity",
            "phase": 4,
            "kind": PhysicalEvidenceKind.LOAD.value,
            "procedure_id": "hs.spi.read-only-jedec-id.v1",
            "title": "Repeat a read-only JEDEC identity transaction",
            "required_measured_fields": [
                "command_hex",
                "response_hex_by_trial",
                "trial_count",
                "clock_hz",
            ],
            "required_raw_media": ["text/csv", "application/octet-stream"],
            "prerequisite_gate_ids": ["logic-level-and-timing-capture"],
            "requires_authorized_operation": "bench_power",
            "safety": "Only read-only identity command 0x9F; WREN, program, erase, and status writes are forbidden.",
        },
        {
            "gate_id": "thermal-dwell",
            "phase": 4,
            "kind": PhysicalEvidenceKind.THERMAL.value,
            "procedure_id": "hs.spi.thermal-dwell.v1",
            "title": "Measure translator, regulator, and DUT temperature over a bounded dwell",
            "required_measured_fields": [
                "ambient_c",
                "dwell_s",
                "translator_max_c",
                "regulator_max_c",
                "dut_max_c",
            ],
            "required_raw_media": ["image/*", "text/csv"],
            "prerequisite_gate_ids": ["current-limited-power-up"],
            "requires_authorized_operation": "bench_power",
            "safety": "Stop immediately on unexpected heating or current-limit activation.",
        },
    ]


def _generic_gates() -> list[dict[str, Any]]:
    return [
        {
            "gate_id": "identify-physical-candidate",
            "phase": 0,
            "kind": PhysicalEvidenceKind.INSPECTION.value,
            "procedure_id": "hs.generic.identify-candidate.v1",
            "title": "Bind the physical candidate to immutable engineering artifacts",
            "required_measured_fields": [
                "assembly_id",
                "assembly_revision",
                "artifact_hashes",
            ],
            "required_raw_media": ["image/*", "application/*"],
            "prerequisite_gate_ids": [],
            "requires_authorized_operation": None,
            "safety": "Unpowered inspection only.",
        }
    ]


def build_project_physical_validation_packet(
    snapshot: Mapping[str, Any], *, project_id: str, revision: int
) -> dict[str, Any]:
    """Create a deterministic operator packet bound to canonical engineering state."""

    boundary = project_candidate_boundary(snapshot, project_id=project_id)
    profile = (
        "spi_flash_adapter"
        if re.search(r"\bspi\b", _text_corpus(snapshot))
        else "generic"
    )
    gates = _spi_flash_gates() if profile == "spi_flash_adapter" else _generic_gates()
    packet_id = "physical-validation-" + _canonical_hash(
        {
            "schema": PROJECT_PHYSICAL_VALIDATION_PACKET_SCHEMA,
            "project_id": project_id,
            "profile": profile,
            "candidate_snapshot_hash": boundary["candidate_snapshot_hash"],
            "gates": gates,
        }
    )[7:23]
    return {
        "schema_version": PROJECT_PHYSICAL_VALIDATION_PACKET_SCHEMA,
        "packet_id": packet_id,
        "project_id": project_id,
        "source_revision": revision,
        **boundary,
        "profile": profile,
        "artifact_hashes": {
            "canonical-project-snapshot": boundary["candidate_snapshot_hash"]
        },
        "gates": gates,
        "workflow": {
            "first_executable_gate_ids": [
                row["gate_id"] for row in gates if not row["prerequisite_gate_ids"]
            ],
            "raw_capture_route": "/v1/engineering/physical-evidence/envelopes/build-attested",
            "submission_route": (
                f"/v1/projects/{project_id}/engineering/physical-validation/evidence"
            ),
            "cold_evidence_can_support": ["bench_power"],
            "powered_capture_requires_prior_human_authorization": True,
            "write_erase_program_operations_forbidden_by_packet": True,
        },
        "instrument_requirements": {
            "identity": ["camera_or_document_scanner"],
            "cold_electrical": ["calibrated_dmm"],
            "powered_electrical": [
                "current_limited_supply",
                "calibrated_dmm",
                "logic_analyzer_or_oscilloscope",
            ],
            "thermal": ["calibrated_temperature_instrument"],
        },
        "policy": {
            "physical_correctness": "UNPROVEN",
            "automatic_authorization": False,
            "human_authorization_required": True,
            "server_attested_raw_files_required": True,
            "tamper_evident_envelopes_required": True,
            "append_only_history_required": True,
            "candidate_revision_and_hash_must_match": True,
            "simulated_or_public_web_evidence_accepted": False,
            "required_capture_origin": "physical_test_article",
            "direct_operator_observation_required": True,
            "authority_effect": "none",
        },
    }


def physical_assessment_plan(
    snapshot: Mapping[str, Any], *, project_id: str, packet: Mapping[str, Any]
) -> dict[str, Any]:
    """Project a canonical project into the existing physical assessor contract."""

    prior = snapshot.get("physicalValidation")
    prior = dict(prior) if isinstance(prior, Mapping) else {}
    plan: dict[str, Any] = {
        "project_name": project_id,
        "candidate_revision": packet["candidate_revision"],
        "machine_project": {
            "project_id": project_id,
            "artifacts": [
                {
                    "artifact_id": artifact_id,
                    "metadata": {"content_hash": content_hash},
                }
                for artifact_id, content_hash in packet["artifact_hashes"].items()
            ],
        },
    }
    audit = prior.get("audited_physical_evidence")
    if isinstance(audit, Mapping):
        plan["audited_physical_evidence"] = deepcopy(dict(audit))
    return plan


def validate_packet_evidence(
    packet: Mapping[str, Any],
    envelopes: Sequence[PhysicalEvidenceEnvelope],
    *,
    prior_authorized_operations: Sequence[str] = (),
) -> None:
    """Reject captures that are not structurally attributable to packet gates."""

    gates = {str(row["gate_id"]): row for row in packet.get("gates") or []}
    expected_hashes = dict(packet.get("artifact_hashes") or {})
    authorized_before_capture = {str(value) for value in prior_authorized_operations}
    passed_gate_ids: set[str] = set()
    for envelope in envelopes:
        record = envelope.record
        candidates = [value for value in record.target_ids if value in gates]
        if len(candidates) != 1:
            raise ValueError(
                f"Evidence {record.evidence_id} must target exactly one packet gate."
            )
        gate_id = candidates[0]
        gate = gates[gate_id]
        if record.project_id != packet["project_id"]:
            raise ValueError(f"Evidence {record.evidence_id} has the wrong project_id.")
        if record.candidate_revision != packet["candidate_revision"]:
            raise ValueError(
                f"Evidence {record.evidence_id} targets a stale candidate revision."
            )
        if record.artifact_hashes != expected_hashes:
            raise ValueError(
                f"Evidence {record.evidence_id} does not match the packet artifact boundary."
            )
        if record.metadata.get("simulated") is not False:
            raise ValueError(
                f"Evidence {record.evidence_id} must explicitly declare simulated=false."
            )
        if record.metadata.get("public_web") is not False:
            raise ValueError(
                f"Evidence {record.evidence_id} must explicitly declare public_web=false."
            )
        if record.metadata.get("capture_origin") != "physical_test_article":
            raise ValueError(
                f"Evidence {record.evidence_id} must declare capture_origin=physical_test_article."
            )
        if record.metadata.get("direct_operator_observation") is not True:
            raise ValueError(
                f"Evidence {record.evidence_id} requires direct_operator_observation=true."
            )
        if record.procedure_id != gate["procedure_id"]:
            raise ValueError(
                f"Evidence {record.evidence_id} uses the wrong procedure for {gate_id}."
            )
        if record.kind.value != gate["kind"]:
            raise ValueError(
                f"Evidence {record.evidence_id} uses the wrong evidence kind for {gate_id}."
            )
        if record.authority.value == "authorized":
            raise ValueError(
                f"Evidence {record.evidence_id} may not self-declare authorized authority; "
                "authorization belongs in the human ledger."
            )
        if gate["kind"] != PhysicalEvidenceKind.INSPECTION.value and not record.instrument_ids:
            raise ValueError(
                f"Evidence {record.evidence_id} requires instrument identities."
            )
        if record.passed:
            required_operation = gate.get("requires_authorized_operation")
            if required_operation and required_operation not in authorized_before_capture:
                raise ValueError(
                    f"Passed gate {gate_id} requires a previously persisted "
                    f"{required_operation} authorization."
                )
            missing = [
                field
                for field in gate["required_measured_fields"]
                if record.measured_values.get(field) in (None, "", [], {})
            ]
            if missing:
                raise ValueError(
                    f"Passed evidence {record.evidence_id} omits required measured fields: "
                    + ", ".join(missing)
                    + "."
                )
            if not record.acceptance_criteria:
                raise ValueError(
                    f"Passed evidence {record.evidence_id} requires explicit acceptance criteria."
                )
            media_types = [str(row.media_type).casefold() for row in envelope.raw_files]
            accepted_media = [
                pattern.casefold() for pattern in gate["required_raw_media"]
            ]
            has_required_media = any(
                value.startswith(pattern[:-1])
                if pattern.endswith("*")
                else value == pattern
                for pattern in accepted_media
                for value in media_types
            )
            if not has_required_media:
                raise ValueError(
                    f"Passed evidence {record.evidence_id} lacks an accepted raw media type: "
                    + ", ".join(gate["required_raw_media"])
                    + "."
                )
            passed_gate_ids.add(gate_id)
        if not record.raw_refs:
            raise ValueError(f"Evidence {record.evidence_id} has no raw capture references.")

    for gate_id in passed_gate_ids:
        missing_prerequisites = [
            value
            for value in gates[gate_id]["prerequisite_gate_ids"]
            if value not in passed_gate_ids
        ]
        if missing_prerequisites:
            raise ValueError(
                f"Passed gate {gate_id} lacks passed prerequisites: "
                + ", ".join(missing_prerequisites)
                + "."
            )


def build_gate_assessment(
    packet: Mapping[str, Any], envelopes: Sequence[PhysicalEvidenceEnvelope]
) -> dict[str, Any]:
    latest: dict[str, PhysicalEvidenceEnvelope] = {}
    for envelope in envelopes:
        for target_id in envelope.record.target_ids:
            if target_id in {row["gate_id"] for row in packet["gates"]}:
                latest[target_id] = envelope
    rows: list[dict[str, Any]] = []
    for gate in packet["gates"]:
        envelope = latest.get(gate["gate_id"])
        rows.append(
            {
                "gate_id": gate["gate_id"],
                "phase": gate["phase"],
                "status": (
                    "passed"
                    if envelope is not None and envelope.record.passed
                    else "failed"
                    if envelope is not None
                    else "open"
                ),
                "evidence_id": envelope.record.evidence_id if envelope else None,
                "envelope_id": envelope.envelope_id if envelope else None,
            }
        )
    passed = [row["gate_id"] for row in rows if row["status"] == "passed"]
    return {
        "gates": rows,
        "passed_gate_ids": passed,
        "open_gate_ids": [row["gate_id"] for row in rows if row["status"] == "open"],
        "failed_gate_ids": [row["gate_id"] for row in rows if row["status"] == "failed"],
        "all_gates_passed": len(passed) == len(rows),
        "physical_correctness": "UNPROVEN",
        "automatic_authorization": False,
    }
