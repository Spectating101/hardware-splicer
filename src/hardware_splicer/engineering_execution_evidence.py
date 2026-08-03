"""Bridge bounded execution manifests into MachineProject verification evidence.

A passing software/design check can verify that specific check. It is always marked as
software-only evidence so it cannot satisfy physical bench or operational release
requirements. Failed, blocked, unavailable, timed-out, and errored runs remain visible
and block their verification method.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Mapping

from .engineering_execution import (
    ExecutionOperation,
    ExecutionResult,
    ExecutionStatus,
    execution_manifest,
)
from .machine_project import (
    AuthorityState,
    EvidenceRef,
    MachineProject,
    VerificationMethod,
    VerificationStatus,
    VerificationType,
)


EXECUTION_EVIDENCE_SCHEMA = "hardware_splicer.engineering_execution_evidence.v1"


def _slug(value: Any, fallback: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "").strip()).strip("-._").lower()
    return token[:120] or fallback


def _known_object_ids(project: MachineProject) -> set[str]:
    values = {project.project_id}
    values.update(row.requirement_id for row in project.requirements)
    values.update(row.function_id for row in project.functions)
    values.update(row.subsystem_id for row in project.subsystems)
    values.update(row.component_id for row in project.components)
    values.update(row.interface_id for row in project.interfaces)
    values.update(row.constraint_id for row in project.constraints)
    values.update(row.verification_id for row in project.verifications)
    values.update(row.evidence_id for row in project.evidence)
    values.update(row.artifact_id for row in project.artifacts)
    return values


def _verification_type(operation: ExecutionOperation) -> VerificationType:
    if operation in {
        ExecutionOperation.KICAD_ERC,
        ExecutionOperation.KICAD_DRC,
        ExecutionOperation.URDF_CHECK,
        ExecutionOperation.ROS2_DOCTOR,
    }:
        return VerificationType.INSPECTION
    if operation in {
        ExecutionOperation.NGSPICE,
        ExecutionOperation.ARTIFACT_HASH,
    }:
        return VerificationType.ANALYSIS
    return VerificationType.TEST


def _verification_status(status: ExecutionStatus) -> VerificationStatus:
    if status == ExecutionStatus.PASSED:
        return VerificationStatus.PASSED
    if status == ExecutionStatus.FAILED:
        return VerificationStatus.FAILED
    if status == ExecutionStatus.PLANNED:
        return VerificationStatus.PLANNED
    return VerificationStatus.BLOCKED


def _result_and_manifest(
    value: ExecutionResult | Mapping[str, Any],
) -> tuple[ExecutionResult, Dict[str, Any]]:
    if isinstance(value, ExecutionResult):
        result = value
        return result, execution_manifest(result)
    payload = dict(value)
    result = ExecutionResult.model_validate(payload)
    manifest = dict(payload)
    if not manifest.get("manifest_hash"):
        manifest = execution_manifest(result)
    return result, manifest


def attach_execution_evidence(
    project: MachineProject,
    result_value: ExecutionResult | Mapping[str, Any],
    *,
    target_ids: Iterable[str] = (),
    requirement_ids: Iterable[str] = (),
) -> MachineProject:
    """Attach or update one execution result and its verification record."""

    result, manifest = _result_and_manifest(result_value)
    known_ids = _known_object_ids(project)
    requested_targets = [str(value) for value in target_ids if value]
    resolved_targets = [value for value in requested_targets if value in known_ids]
    unknown_targets = [value for value in requested_targets if value not in known_ids]
    if not resolved_targets:
        resolved_targets = [project.project_id]

    known_requirements = {row.requirement_id for row in project.requirements}
    resolved_requirements = [
        str(value) for value in requirement_ids if str(value) in known_requirements
    ]
    token = _slug(result.execution_id, "execution")
    evidence_id = f"execution-evidence-{token}"
    verification_id = f"execution-verification-{token}"
    passed = result.status == ExecutionStatus.PASSED
    evidence_authority = AuthorityState.VERIFIED if passed else AuthorityState.OBSERVED
    manifest_hash = str(manifest.get("manifest_hash") or "")

    evidence = EvidenceRef(
        evidence_id=evidence_id,
        kind="software_execution_result",
        basis=(
            f"Bounded {result.operation.value} execution passed."
            if passed
            else f"Bounded {result.operation.value} execution ended as {result.status.value}."
        ),
        ref=manifest_hash or None,
        supports=resolved_targets,
        authority=evidence_authority,
        simulated=True,
        metadata={
            "schema_version": EXECUTION_EVIDENCE_SCHEMA,
            "execution_id": result.execution_id,
            "operation": result.operation.value,
            "status": result.status.value,
            "returncode": result.returncode,
            "duration_s": result.duration_s,
            "tool": result.tool,
            "tool_available": result.tool_available,
            "workspace": result.workspace,
            "target": result.target,
            "output_hashes": result.output_hashes,
            "manifest_hash": manifest_hash,
            "software_only": True,
            "physical_evidence": False,
            "network_authorized": False,
            "device_access_authorized": False,
            "flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "unknown_requested_target_ids": unknown_targets,
            "blockers": result.blockers,
        },
    )
    verification = VerificationMethod(
        verification_id=verification_id,
        name=f"Bounded {result.operation.value} execution",
        method_type=_verification_type(result.operation),
        status=_verification_status(result.status),
        requirement_ids=resolved_requirements,
        target_ids=resolved_targets,
        evidence_ids=[evidence_id],
        procedure=(
            "Run the named, allowlisted operation in the bounded execution service; "
            "retain the manifest hash, tool identity, return code, output hashes, and logs."
        ),
        acceptance_criteria={
            "required_status": ExecutionStatus.PASSED.value,
            "actual_status": result.status.value,
            "returncode": result.returncode,
            "manifest_hash_present": bool(manifest_hash),
            "software_only": True,
            "physical_authority_unchanged": True,
        },
        authority=AuthorityState.VERIFIED if passed else AuthorityState.OBSERVED,
        metadata={
            "schema_version": EXECUTION_EVIDENCE_SCHEMA,
            "execution_id": result.execution_id,
            "operation": result.operation.value,
            "manifest": manifest,
        },
    )

    evidence_rows = [row for row in project.evidence if row.evidence_id != evidence_id]
    evidence_rows.append(evidence)
    verification_rows = [
        row for row in project.verifications if row.verification_id != verification_id
    ]
    verification_rows.append(verification)

    payloads = dict(project.discipline_payloads)
    execution_payload = payloads.get("engineering_execution_evidence")
    execution_rows = (
        list(execution_payload.get("manifests") or [])
        if isinstance(execution_payload, Mapping)
        else []
    )
    execution_rows = [
        row
        for row in execution_rows
        if not isinstance(row, Mapping) or row.get("execution_id") != result.execution_id
    ]
    execution_rows.append(manifest)
    payloads["engineering_execution_evidence"] = {
        "schema_version": EXECUTION_EVIDENCE_SCHEMA,
        "manifests": execution_rows,
        "software_only": True,
        "physical_authority_unchanged": True,
        "release_authorized": False,
    }
    metadata = dict(project.metadata)
    metadata.update(
        {
            "engineering_execution_evidence_schema": EXECUTION_EVIDENCE_SCHEMA,
            "engineering_execution_evidence_count": len(execution_rows),
            "physical_authority_unchanged": True,
            "operational_authority_unchanged": True,
        }
    )
    return MachineProject.model_validate(
        project.model_copy(
            update={
                "evidence": evidence_rows,
                "verifications": verification_rows,
                "discipline_payloads": payloads,
                "metadata": metadata,
            },
            deep=True,
        ).model_dump(mode="json")
    )
