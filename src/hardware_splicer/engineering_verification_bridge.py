"""Project engineering analyses and regression scope into MachineProject evidence gates."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from .change_impact import ChangeImpactGraph
from .engineering_analysis import AnalysisStatus, EngineeringAnalysisReport
from .machine_project import (
    AuthorityState,
    EvidenceRef,
    MachineProject,
    VerificationMethod,
    VerificationStatus,
    VerificationType,
)


VERIFICATION_BRIDGE_SCHEMA = "hardware_splicer.engineering_verification_bridge.v1"


def _mapped_target(target_id: str, identity_map: Mapping[str, Any], project: MachineProject) -> str:
    topology_map = identity_map.get("topology_to_machine_component")
    if isinstance(topology_map, Mapping) and target_id in topology_map:
        return str(topology_map[target_id])
    valid_ids = {
        project.project_id,
        *(row.subsystem_id for row in project.subsystems),
        *(row.component_id for row in project.components),
        *(row.interface_id for row in project.interfaces),
        *(row.constraint_id for row in project.constraints),
    }
    return target_id if target_id in valid_ids else project.project_id


def _verification_type(method: str) -> VerificationType:
    lowered = method.lower()
    if "inspection" in lowered:
        return VerificationType.INSPECTION
    if "demonstration" in lowered or "motion" in lowered or "safety" in lowered:
        return VerificationType.DEMONSTRATION
    if "analysis" in lowered or "simulation" in lowered or "review" in lowered:
        return VerificationType.ANALYSIS
    return VerificationType.TEST


def bridge_engineering_verification(
    project: MachineProject,
    *,
    analysis: EngineeringAnalysisReport,
    change_impact: ChangeImpactGraph,
    identity_map: Mapping[str, Any],
) -> MachineProject:
    """Add idempotent analysis evidence and planned physical regression checks."""

    evidence = {row.evidence_id: row.model_copy(deep=True) for row in project.evidence}
    verifications = {row.verification_id: row.model_copy(deep=True) for row in project.verifications}

    for finding in analysis.findings:
        verification_id = f"verification-{finding.finding_id}"
        evidence_id = f"evidence-{finding.finding_id}"
        target_ids = [
            _mapped_target(target_id, identity_map, project)
            for target_id in finding.target_ids
        ] or [project.project_id]
        if finding.status in {AnalysisStatus.PASS, AnalysisStatus.FAIL}:
            evidence[evidence_id] = EvidenceRef(
                evidence_id=evidence_id,
                kind="bounded_engineering_calculation",
                basis=finding.message,
                ref=f"analysis://{finding.finding_id}",
                supports=target_ids,
                authority=AuthorityState.PROPOSED,
                simulated=True,
                metadata={
                    "bridge": VERIFICATION_BRIDGE_SCHEMA,
                    "category": finding.category,
                    "inputs": finding.inputs,
                    "outputs": finding.outputs,
                    "assumptions": finding.assumptions,
                    "physical_validation_required": True,
                },
            )
        status = {
            AnalysisStatus.PASS: VerificationStatus.PASSED,
            AnalysisStatus.FAIL: VerificationStatus.FAILED,
            AnalysisStatus.REVIEW: VerificationStatus.BLOCKED,
            AnalysisStatus.UNKNOWN: VerificationStatus.BLOCKED if finding.blocking else VerificationStatus.PLANNED,
        }[finding.status]
        verifications[verification_id] = VerificationMethod(
            verification_id=verification_id,
            name=f"Engineering analysis: {finding.category}",
            method_type=VerificationType.ANALYSIS,
            status=status,
            target_ids=target_ids,
            evidence_ids=[evidence_id] if evidence_id in evidence else [],
            procedure=(
                finding.message
                + (f" Missing inputs: {', '.join(finding.missing_inputs)}." if finding.missing_inputs else "")
                + " Reconfirm with physical measurements and bounded testing before operation."
            ),
            acceptance_criteria={
                "calculation_status": "pass",
                "physical_confirmation_required": True,
                "blocking": finding.blocking,
            },
            authority=AuthorityState.PROPOSED,
            metadata={
                "bridge": VERIFICATION_BRIDGE_SCHEMA,
                "analysis_finding_id": finding.finding_id,
                "analysis_status": finding.status.value,
            },
        )

    for check in change_impact.regression_checks:
        verification_id = f"verification-{check.check_id}"
        target_ids = [
            _mapped_target(target_id, identity_map, project)
            for target_id in check.target_ids
        ] or [project.project_id]
        verifications[verification_id] = VerificationMethod(
            verification_id=verification_id,
            name=check.name,
            method_type=_verification_type(check.method),
            status=VerificationStatus.PLANNED,
            target_ids=target_ids,
            procedure=(
                f"Run {check.method} for {', '.join(target_ids)}. "
                "Capture instrument identity, configuration, raw result, revision hashes, and operator disposition."
            ),
            acceptance_criteria=dict(check.acceptance_criteria),
            authority=AuthorityState.PROPOSED,
            metadata={
                "bridge": VERIFICATION_BRIDGE_SCHEMA,
                "regression_check_id": check.check_id,
                "blocking": check.blocking,
                "change_id": change_impact.change_id,
            },
        )

    payloads = dict(project.discipline_payloads)
    payloads["engineering_verification_bridge"] = {
        "schema_version": VERIFICATION_BRIDGE_SCHEMA,
        "analysis_verification_ids": sorted(
            verification_id
            for verification_id in verifications
            if verification_id.startswith("verification-analysis-")
        ),
        "regression_verification_ids": sorted(
            f"verification-{row.check_id}" for row in change_impact.regression_checks
        ),
        "physical_authority_unchanged": True,
    }
    metadata = dict(project.metadata)
    metadata.update(
        {
            "engineering_verification_bridge": VERIFICATION_BRIDGE_SCHEMA,
            "physical_verification_required": True,
            "operational_authority_unchanged": True,
        }
    )
    return MachineProject(
        **{
            **project.model_dump(mode="python"),
            "verifications": list(verifications.values()),
            "evidence": list(evidence.values()),
            "discipline_payloads": payloads,
            "metadata": metadata,
        }
    )
