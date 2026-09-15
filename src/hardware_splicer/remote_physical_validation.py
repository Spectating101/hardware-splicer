"""Provider-neutral handoff and return audit for remote physical test services.

This module adapts an existing revision-bound project physical-validation packet for a
contract laboratory or PCBA test service.  It deliberately does not create physical
evidence, attest raw files, or authorize any operation.  A structurally accepted return is
only eligible for import through the existing physical-evidence envelope and project APIs.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from copy import deepcopy
from pathlib import PurePosixPath
from typing import Any, Mapping, Sequence

from .project_physical_validation import PROJECT_PHYSICAL_VALIDATION_PACKET_SCHEMA


REMOTE_PHYSICAL_HANDOFF_SCHEMA = "hardware_splicer.remote_physical_handoff.v1"
REMOTE_PHYSICAL_RETURN_SCHEMA = "hardware_splicer.remote_physical_return.v1"
REMOTE_PHYSICAL_RETURN_AUDIT_SCHEMA = "hardware_splicer.remote_physical_return_audit.v1"
REMOTE_PHYSICAL_ARCHIVE_MANIFEST_SCHEMA = (
    "hardware_splicer.remote_physical_handoff_archive.v1"
)

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ENGAGEMENT_MODES = {"pcba_production_and_test", "testing_only", "remote_lab"}
_PRODUCTION_ARTIFACT_ROLES = {
    "schematic",
    "fabrication_archive",
    "bom",
    "pick_and_place",
    "assembly_drawing",
    "test_firmware",
}


class RemotePhysicalValidationError(ValueError):
    """Raised when a remote-lab handoff or return violates the frozen contract."""


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        + "\n"
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _canonical_hash(value: Any) -> str:
    return _sha256(_canonical_json_bytes(value))


def _require_mapping(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RemotePhysicalValidationError(f"{label} must be an object")
    return deepcopy(dict(value))


def _valid_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA256_RE.fullmatch(value))


def _safe_relative_path(value: Any) -> str | None:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    return str(path)


def _media_matches(media_type: str, patterns: Sequence[str]) -> bool:
    candidate = str(media_type or "").casefold()
    for pattern in patterns:
        expected = str(pattern).casefold()
        if expected.endswith("*") and candidate.startswith(expected[:-1]):
            return True
        if candidate == expected:
            return True
    return False


def _normalize_artifacts(
    artifacts: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    roles: set[str] = set()
    for index, value in enumerate(artifacts or ()):
        row = _require_mapping(value, label=f"manufacturing_artifacts[{index}]")
        role = str(row.get("role") or "").strip()
        artifact_id = str(row.get("artifact_id") or "").strip()
        content_hash = row.get("content_hash")
        if not role or not artifact_id or not _valid_hash(content_hash):
            raise RemotePhysicalValidationError(
                "each manufacturing artifact requires role, artifact_id, and sha256 content_hash"
            )
        if role in roles:
            raise RemotePhysicalValidationError(
                f"manufacturing artifact role is duplicated: {role}"
            )
        roles.add(role)
        filename = str(row.get("filename") or "")
        if filename and _safe_relative_path(filename) is None:
            raise RemotePhysicalValidationError(
                f"manufacturing artifact filename is unsafe: {filename}"
            )
        size_bytes = row.get("size_bytes")
        if size_bytes is not None and (
            not isinstance(size_bytes, int)
            or isinstance(size_bytes, bool)
            or size_bytes < 0
        ):
            raise RemotePhysicalValidationError(
                "manufacturing artifact size_bytes must be a non-negative integer"
            )
        normalized_row: dict[str, Any] = {
            "role": role,
            "artifact_id": artifact_id,
            "content_hash": content_hash,
            "filename": filename,
        }
        if size_bytes is not None:
            normalized_row["size_bytes"] = size_bytes
        normalized.append(normalized_row)
    return sorted(normalized, key=lambda row: (row["role"], row["artifact_id"]))


def build_remote_physical_handoff(
    physical_packet: Mapping[str, Any],
    *,
    provider: Mapping[str, Any],
    manufacturing_artifacts: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a deterministic, non-authorizing contract-lab request.

    The bundle is quote-ready even before manufacturing artifacts exist.  Fabrication release
    remains false: only a later human authorization decision can permit that operation.
    """

    packet = _require_mapping(physical_packet, label="physical_packet")
    if packet.get("schema_version") != PROJECT_PHYSICAL_VALIDATION_PACKET_SCHEMA:
        raise RemotePhysicalValidationError("physical packet schema mismatch")
    gates = packet.get("gates")
    if not isinstance(gates, list) or not gates:
        raise RemotePhysicalValidationError("physical packet has no gates")
    packet_hash = _canonical_hash(packet)
    if not all(
        isinstance(packet.get(key), str) and packet.get(key)
        for key in ("packet_id", "project_id", "candidate_revision", "candidate_snapshot_hash")
    ):
        raise RemotePhysicalValidationError("physical packet identity boundary is incomplete")

    resolved_provider = _require_mapping(provider, label="provider")
    provider_id = str(resolved_provider.get("provider_id") or "").strip()
    provider_name = str(resolved_provider.get("provider_name") or "").strip()
    engagement_mode = str(resolved_provider.get("engagement_mode") or "").strip()
    if not provider_id or not provider_name or engagement_mode not in _ENGAGEMENT_MODES:
        raise RemotePhysicalValidationError(
            "provider requires provider_id, provider_name, and a supported engagement_mode"
        )
    provider_projection = {
        "provider_id": provider_id,
        "provider_name": provider_name,
        "engagement_mode": engagement_mode,
        "service_url": str(resolved_provider.get("service_url") or ""),
        "capabilities_requested": sorted(
            {
                str(value).strip()
                for value in resolved_provider.get("capabilities_requested", [])
                if str(value).strip()
            }
        ),
        "selection_status": "proposed_not_engaged",
        "endorsement_asserted": False,
    }

    artifacts = _normalize_artifacts(manufacturing_artifacts)
    supplied_roles = {row["role"] for row in artifacts}
    missing_roles = sorted(_PRODUCTION_ARTIFACT_ROLES - supplied_roles)

    gate_requests: list[dict[str, Any]] = []
    for raw_gate in gates:
        gate = _require_mapping(raw_gate, label="physical_packet.gate")
        gate_requests.append(
            {
                "gate_id": gate.get("gate_id"),
                "phase": gate.get("phase"),
                "title": gate.get("title"),
                "procedure_id": gate.get("procedure_id"),
                "kind": gate.get("kind"),
                "prerequisite_gate_ids": list(gate.get("prerequisite_gate_ids") or []),
                "requires_authorized_operation": gate.get("requires_authorized_operation"),
                "required_measured_fields": list(gate.get("required_measured_fields") or []),
                "required_raw_media": list(gate.get("required_raw_media") or []),
                "required_original_raw_file_count_min": 1,
                "instrument_and_calibration_identity_required": (
                    gate.get("kind") != "inspection"
                ),
                "summary_pass_without_raw_files_accepted": False,
                "safety": gate.get("safety"),
            }
        )

    without_id = {
        "schema_version": REMOTE_PHYSICAL_HANDOFF_SCHEMA,
        "project_id": packet["project_id"],
        "source_physical_packet_id": packet["packet_id"],
        "source_physical_packet_sha256": packet_hash,
        "candidate_revision": packet["candidate_revision"],
        "candidate_snapshot_hash": packet["candidate_snapshot_hash"],
        "project_artifact_hashes": deepcopy(dict(packet.get("artifact_hashes") or {})),
        "provider": provider_projection,
        "manufacturing_artifacts": artifacts,
        "gate_requests": gate_requests,
        "provider_return_requirements": {
            "provider_work_order_identity": True,
            "physical_site_identity": True,
            "test_article_serial_and_revision": True,
            "named_direct_observer_per_executed_gate": True,
            "instrument_identity_per_instrumented_gate": True,
            "calibration_record_per_instrument": True,
            "original_raw_files_with_sha256_and_size": True,
            "measured_values_and_acceptance_criteria": True,
            "provider_attestation": True,
            "editable_summary_only_accepted": False,
            "physical_authorization_from_provider_accepted": False,
        },
        "release_readiness": {
            "ready_for_provider_capability_review": True,
            "ready_for_provider_quote": True,
            "required_production_artifact_roles": sorted(_PRODUCTION_ARTIFACT_ROLES),
            "missing_production_artifact_roles": missing_roles,
            "production_artifact_set_complete": not missing_roles,
            "fabrication_release_ready": False,
            "reason": (
                "Human fabrication authorization is required even after all production artifacts exist."
            ),
        },
        "evidence_import": {
            "next_schema": "hardware_splicer.physical_evidence_envelope.v1",
            "existing_submission_route": (
                f"/v1/projects/{packet['project_id']}/engineering/physical-validation/evidence"
            ),
            "return_audit_is_physical_evidence": False,
            "server_attestation_still_required": True,
        },
        "policy": {
            "personal_contact_data_in_bundle": False,
            "raw_vendor_model_bytes_in_bundle": False,
            "provider_summary_is_not_evidence": True,
            "simulated_evidence_accepted": False,
            "automatic_authorization": False,
            "physical_correctness": "UNPROVEN",
            "physical_authority_granted": False,
            "authority_effect": "none",
        },
    }
    handoff_id = "remote-physical-handoff-" + _canonical_hash(without_id)[7:23]
    return {**without_id, "handoff_id": handoff_id}


def build_remote_physical_return_template(handoff: Mapping[str, Any]) -> dict[str, Any]:
    resolved = _require_mapping(handoff, label="handoff")
    if resolved.get("schema_version") != REMOTE_PHYSICAL_HANDOFF_SCHEMA:
        raise RemotePhysicalValidationError("remote handoff schema mismatch")
    return {
        "schema_version": REMOTE_PHYSICAL_RETURN_SCHEMA,
        "handoff_id": resolved.get("handoff_id"),
        "source_physical_packet_id": resolved.get("source_physical_packet_id"),
        "candidate_revision": resolved.get("candidate_revision"),
        "candidate_snapshot_hash": resolved.get("candidate_snapshot_hash"),
        "provider": {
            "provider_id": resolved.get("provider", {}).get("provider_id"),
            "provider_name": resolved.get("provider", {}).get("provider_name"),
            "work_order_id": None,
            "physical_site_id": None,
        },
        "test_article": {
            "assembly_id": None,
            "assembly_revision": None,
            "serial_numbers": [],
            "manufacturing_artifacts": deepcopy(
                list(resolved.get("manufacturing_artifacts") or [])
            ),
        },
        "calibrations": [],
        "gate_results": [
            {
                "gate_id": gate.get("gate_id"),
                "procedure_id": gate.get("procedure_id"),
                "status": "not_run",
                "captured_at": None,
                "operator_id": None,
                "direct_operator_observation": False,
                "measured_values": {
                    field: None for field in gate.get("required_measured_fields", [])
                },
                "acceptance_criteria": {},
                "instrument_ids": [],
                "calibration_ids": [],
                "failure_reason": None,
                "raw_files": [],
            }
            for gate in resolved.get("gate_requests", [])
        ],
        "provider_attestation": {
            "signed_by": None,
            "role": None,
            "signed_at": None,
            "statement": (
                "The identified operators directly observed the reported tests on the identified physical test article."
            ),
        },
        "automatic_authorization": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
    }


def _required_identity_blockers(
    handoff: Mapping[str, Any], returned: Mapping[str, Any]
) -> list[str]:
    blockers: list[str] = []
    expected = {
        "handoff_id": handoff.get("handoff_id"),
        "source_physical_packet_id": handoff.get("source_physical_packet_id"),
        "candidate_revision": handoff.get("candidate_revision"),
        "candidate_snapshot_hash": handoff.get("candidate_snapshot_hash"),
    }
    for key, value in expected.items():
        if returned.get(key) != value:
            blockers.append(f"return {key} does not match the handoff")
    provider = returned.get("provider") if isinstance(returned.get("provider"), Mapping) else {}
    expected_provider = handoff.get("provider") if isinstance(handoff.get("provider"), Mapping) else {}
    for key in ("provider_id", "provider_name"):
        if provider.get(key) != expected_provider.get(key):
            blockers.append(f"return provider {key} does not match the handoff")
    for key in ("work_order_id", "physical_site_id"):
        if not str(provider.get(key) or "").strip():
            blockers.append(f"return provider {key} is required")
    article = returned.get("test_article") if isinstance(returned.get("test_article"), Mapping) else {}
    for key in ("assembly_id", "assembly_revision"):
        if not str(article.get(key) or "").strip():
            blockers.append(f"test_article {key} is required")
    if not isinstance(article.get("serial_numbers"), list) or not article.get("serial_numbers"):
        blockers.append("test_article serial_numbers are required")
    if article.get("manufacturing_artifacts") != handoff.get("manufacturing_artifacts"):
        blockers.append("test_article manufacturing artifacts do not match the handoff")
    attestation = (
        returned.get("provider_attestation")
        if isinstance(returned.get("provider_attestation"), Mapping)
        else {}
    )
    for key in ("signed_by", "role", "signed_at", "statement"):
        if not str(attestation.get(key) or "").strip():
            blockers.append(f"provider_attestation {key} is required")
    if (
        returned.get("automatic_authorization") is not False
        or returned.get("physical_authority_granted") is not False
        or returned.get("physical_correctness") != "UNPROVEN"
        or returned.get("authority_effect") != "none"
    ):
        blockers.append("remote return attempts to cross the physical-authority boundary")
    return blockers


def audit_remote_physical_return(
    handoff: Mapping[str, Any],
    returned_manifest: Mapping[str, Any],
    *,
    raw_payloads: Mapping[str, bytes],
) -> dict[str, Any]:
    """Audit raw contract-lab return bytes without promoting them to evidence."""

    resolved_handoff = _require_mapping(handoff, label="handoff")
    returned = _require_mapping(returned_manifest, label="returned_manifest")
    blockers: list[str] = []
    warnings: list[str] = []
    if resolved_handoff.get("schema_version") != REMOTE_PHYSICAL_HANDOFF_SCHEMA:
        raise RemotePhysicalValidationError("remote handoff schema mismatch")
    if returned.get("schema_version") != REMOTE_PHYSICAL_RETURN_SCHEMA:
        blockers.append("remote return schema mismatch")
    blockers.extend(_required_identity_blockers(resolved_handoff, returned))

    gate_contracts = {
        str(row.get("gate_id")): row
        for row in resolved_handoff.get("gate_requests", [])
        if isinstance(row, Mapping) and row.get("gate_id")
    }
    calibration_rows = returned.get("calibrations")
    calibrations: dict[str, Mapping[str, Any]] = {}
    if isinstance(calibration_rows, list):
        for index, row in enumerate(calibration_rows):
            if not isinstance(row, Mapping):
                blockers.append(f"calibrations[{index}] must be an object")
                continue
            calibration_id = str(row.get("calibration_id") or "")
            instrument_id = str(row.get("instrument_id") or "")
            if not calibration_id or not instrument_id:
                blockers.append(f"calibrations[{index}] lacks calibration or instrument identity")
            elif calibration_id in calibrations:
                blockers.append(f"calibration_id is duplicated: {calibration_id}")
            else:
                calibrations[calibration_id] = row

    gate_rows = returned.get("gate_results")
    if not isinstance(gate_rows, list):
        blockers.append("gate_results must be a list")
        gate_rows = []
    accepted_gate_ids: list[str] = []
    accepted_gate_statuses: dict[str, str] = {}
    rejected_gate_ids: list[str] = []
    open_gate_ids: list[str] = []
    seen_gate_ids: set[str] = set()
    referenced_paths: set[str] = set()

    for index, raw_row in enumerate(gate_rows):
        if not isinstance(raw_row, Mapping):
            blockers.append(f"gate_results[{index}] must be an object")
            continue
        row = dict(raw_row)
        gate_id = str(row.get("gate_id") or "")
        contract = gate_contracts.get(gate_id)
        row_blockers: list[str] = []
        if not gate_id or contract is None:
            blockers.append(f"gate_results[{index}] references an unknown gate")
            continue
        if gate_id in seen_gate_ids:
            blockers.append(f"gate result is duplicated: {gate_id}")
            continue
        seen_gate_ids.add(gate_id)
        status = row.get("status")
        if status == "not_run":
            open_gate_ids.append(gate_id)
            continue
        if status not in {"pass", "fail"}:
            row_blockers.append("status must be pass, fail, or not_run")
        if row.get("procedure_id") != contract.get("procedure_id"):
            row_blockers.append("procedure_id does not match the frozen gate")
        for key in ("captured_at", "operator_id"):
            if not str(row.get(key) or "").strip():
                row_blockers.append(f"{key} is required")
        if row.get("direct_operator_observation") is not True:
            row_blockers.append("direct_operator_observation=true is required")
        if status == "fail" and not str(row.get("failure_reason") or "").strip():
            row_blockers.append("failed gate requires failure_reason")

        measured = row.get("measured_values") if isinstance(row.get("measured_values"), Mapping) else {}
        criteria = (
            row.get("acceptance_criteria")
            if isinstance(row.get("acceptance_criteria"), Mapping)
            else {}
        )
        if status == "pass":
            missing = [
                field
                for field in contract.get("required_measured_fields", [])
                if measured.get(field) in (None, "", [], {})
            ]
            if missing:
                row_blockers.append("missing measured fields: " + ", ".join(missing))
            if not criteria:
                row_blockers.append("passing gate requires acceptance_criteria")

        instrument_ids = [str(value) for value in row.get("instrument_ids", [])]
        calibration_ids = [str(value) for value in row.get("calibration_ids", [])]
        if contract.get("instrument_and_calibration_identity_required"):
            if not instrument_ids:
                row_blockers.append("instrument identities are required")
            if not calibration_ids:
                row_blockers.append("calibration identities are required")
        for calibration_id in calibration_ids:
            calibration = calibrations.get(calibration_id)
            if calibration is None:
                row_blockers.append(f"unknown calibration: {calibration_id}")
            elif str(calibration.get("instrument_id")) not in instrument_ids:
                row_blockers.append(
                    f"calibration {calibration_id} does not match a gate instrument"
                )

        raw_files = row.get("raw_files") if isinstance(row.get("raw_files"), list) else []
        if not raw_files:
            row_blockers.append("executed gate requires original raw files")
        media_ok = False
        for file_index, file_row in enumerate(raw_files):
            if not isinstance(file_row, Mapping):
                row_blockers.append(f"raw_files[{file_index}] must be an object")
                continue
            path = _safe_relative_path(file_row.get("path"))
            if path is None:
                row_blockers.append(f"raw_files[{file_index}] path is unsafe")
                continue
            if path in referenced_paths:
                row_blockers.append(f"raw file is referenced more than once: {path}")
            referenced_paths.add(path)
            expected_hash = file_row.get("sha256")
            expected_size = file_row.get("size_bytes")
            payload = raw_payloads.get(path)
            if not _valid_hash(expected_hash):
                row_blockers.append(f"raw file {path} has invalid sha256")
            if not isinstance(expected_size, int) or isinstance(expected_size, bool) or expected_size < 0:
                row_blockers.append(f"raw file {path} has invalid size_bytes")
            if not isinstance(payload, bytes):
                row_blockers.append(f"raw file bytes are missing: {path}")
            else:
                if _sha256(payload) != expected_hash:
                    row_blockers.append(f"raw file hash mismatch: {path}")
                if len(payload) != expected_size:
                    row_blockers.append(f"raw file size mismatch: {path}")
            if _media_matches(
                str(file_row.get("media_type") or ""),
                list(contract.get("required_raw_media") or []),
            ):
                media_ok = True
        if raw_files and not media_ok:
            row_blockers.append("raw files do not include a required media type")

        if row_blockers:
            rejected_gate_ids.append(gate_id)
            blockers.extend(f"{gate_id}: {message}" for message in row_blockers)
        else:
            accepted_gate_ids.append(gate_id)
            accepted_gate_statuses[gate_id] = str(status)

    for gate_id in tuple(accepted_gate_ids):
        if accepted_gate_statuses.get(gate_id) != "pass":
            continue
        contract = gate_contracts[gate_id]
        missing_prerequisites = [
            prerequisite
            for prerequisite in contract.get("prerequisite_gate_ids", [])
            if accepted_gate_statuses.get(str(prerequisite)) != "pass"
        ]
        if missing_prerequisites:
            accepted_gate_ids.remove(gate_id)
            accepted_gate_statuses.pop(gate_id, None)
            rejected_gate_ids.append(gate_id)
            blockers.append(
                f"{gate_id}: passing result lacks accepted passing prerequisites: "
                + ", ".join(str(value) for value in missing_prerequisites)
            )

    for gate_id in gate_contracts:
        if gate_id not in seen_gate_ids:
            open_gate_ids.append(gate_id)
    unreferenced = sorted(set(raw_payloads) - referenced_paths)
    if unreferenced:
        warnings.append("unreferenced raw payloads: " + ", ".join(unreferenced))

    blockers = list(dict.fromkeys(blockers))
    warnings = list(dict.fromkeys(warnings))
    eligible = not blockers and bool(accepted_gate_ids)
    complete = eligible and set(accepted_gate_ids) == set(gate_contracts)
    return {
        "schema_version": REMOTE_PHYSICAL_RETURN_AUDIT_SCHEMA,
        "status": (
            "eligible_for_physical_evidence_import"
            if eligible
            else "rejected_remote_return"
        ),
        "audit_pass": eligible,
        "handoff_id": resolved_handoff.get("handoff_id"),
        "accepted_gate_ids": accepted_gate_ids,
        "rejected_gate_ids": rejected_gate_ids,
        "open_gate_ids": sorted(set(open_gate_ids)),
        "complete_return": complete,
        "blockers": blockers,
        "warnings": warnings,
        "next_step": (
            "Build server-attested physical evidence envelopes from each accepted gate and submit through the existing project physical-validation API."
            if eligible
            else "Correct the return manifest or raw files; no physical evidence may be imported."
        ),
        "return_audit_is_physical_evidence": False,
        "automatic_authorization": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
    }


def render_remote_physical_test_plan(handoff: Mapping[str, Any]) -> str:
    resolved = _require_mapping(handoff, label="handoff")
    if resolved.get("schema_version") != REMOTE_PHYSICAL_HANDOFF_SCHEMA:
        raise RemotePhysicalValidationError("remote handoff schema mismatch")
    lines = [
        "# Remote physical validation test request",
        "",
        f"- Handoff: `{resolved['handoff_id']}`",
        f"- Project: `{resolved['project_id']}`",
        f"- Candidate: `{resolved['candidate_revision']}`",
        f"- Provider target: {resolved['provider']['provider_name']}",
        "- Authority: none; this request does not authorize fabrication or power-on.",
        "",
        "## Required execution order",
        "",
        "| Phase | Gate | Procedure | Required return |",
        "|---:|---|---|---|",
    ]
    for gate in resolved.get("gate_requests", []):
        fields = ", ".join(f"`{value}`" for value in gate["required_measured_fields"])
        lines.append(
            f"| {gate['phase']} | `{gate['gate_id']}` — {gate['title']} | "
            f"`{gate['procedure_id']}` | Original raw file(s); {fields} |"
        )
    lines.extend(
        [
            "",
            "## Return rules",
            "",
            "- Identify the provider work order, physical site, test article revision, and serial number.",
            "- Name the direct operator for every executed gate.",
            "- Return original instrument exports or captures with SHA-256 and byte size.",
            "- Include instrument identities and calibration records for instrumented gates.",
            "- Report failures with their raw captures; do not replace them with a summary PASS/FAIL sheet.",
            "- Do not claim that the provider report grants fabrication, power-on, or physical authority.",
            "",
            "## Safety boundary",
            "",
        ]
    )
    for gate in resolved.get("gate_requests", []):
        lines.append(f"- `{gate['gate_id']}`: {gate['safety']}")
    lines.extend(
        [
            "",
            "## Current release status",
            "",
            f"Missing production artifact roles: {', '.join(resolved['release_readiness']['missing_production_artifact_roles']) or 'none'}.",
            "Fabrication release remains false until a separate human authorization is persisted.",
            "",
        ]
    )
    return "\n".join(lines)


def build_remote_physical_handoff_archive(handoff: Mapping[str, Any]) -> bytes:
    """Create a byte-deterministic ZIP suitable for a provider quote attachment."""

    resolved = _require_mapping(handoff, label="handoff")
    template = build_remote_physical_return_template(resolved)
    payloads: dict[str, bytes] = {
        "REMOTE_TEST_REQUEST.json": _canonical_json_bytes(resolved),
        "REMOTE_TEST_PLAN.md": render_remote_physical_test_plan(resolved).encode("utf-8"),
        "EVIDENCE_RETURN_MANIFEST.template.json": _canonical_json_bytes(template),
    }
    manifest = {
        "schema_version": REMOTE_PHYSICAL_ARCHIVE_MANIFEST_SCHEMA,
        "handoff_id": resolved.get("handoff_id"),
        "manifest_self_hash_excluded": True,
        "files": [
            {"path": name, "sha256": _sha256(payload), "size_bytes": len(payload)}
            for name, payload in sorted(payloads.items())
        ],
        "physical_authority_granted": False,
        "authority_effect": "none",
    }
    payloads["MANIFEST.json"] = _canonical_json_bytes(manifest)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, payload in sorted(payloads.items()):
            info = zipfile.ZipInfo(
                filename=f"REMOTE_PHYSICAL_HANDOFF/{name}",
                date_time=(1980, 1, 1, 0, 0, 0),
            )
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, payload)
    return output.getvalue()
