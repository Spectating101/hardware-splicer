"""Integrate bounded STEP and mount reconciliation into guided engineering plans."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from .engineering_status import (
    EngineeringStatus,
    StatusBlocker,
    StatusSeverity,
    build_engineering_status,
)
from .machine_project import ArtifactRef, AuthorityState, MachineProject
from .step_geometry import MechanicalGeometryReport, MechanicalCheckStatus


MECHANICAL_GEOMETRY_PLAN_SCHEMA = "hardware_splicer.mechanical_geometry_plan_update.v1"


def _artifact_id(model_id: str) -> str:
    return f"step-model-{model_id}"


def _attach_step_artifacts(
    project: MachineProject,
    report: MechanicalGeometryReport,
) -> MachineProject:
    replacement_ids = {_artifact_id(model.model_id) for model in report.models}
    artifacts = [
        row for row in project.artifacts if row.artifact_id not in replacement_ids
    ]
    for model in report.models:
        artifacts.append(
            ArtifactRef(
                artifact_id=_artifact_id(model.model_id),
                kind="step_model",
                ref=model.source_id,
                authority=AuthorityState.DECLARED,
                metadata={
                    "schema_version": model.schema_version,
                    "model_id": model.model_id,
                    "content_hash": model.content_hash,
                    "byte_count": model.byte_count,
                    "file_schema": model.file_schema,
                    "products": model.products,
                    "units": model.units,
                    "entity_count": model.entity_count,
                    "cartesian_point_count": model.cartesian_point_count,
                    "bounding_box": (
                        model.bounding_box.model_dump(mode="json")
                        if model.bounding_box is not None
                        else None
                    ),
                    "unresolved": model.unresolved,
                    "full_brep_validation": False,
                    "collision_analysis": False,
                    "fabrication_authorized": False,
                },
            )
        )
    payloads = dict(project.discipline_payloads)
    payloads["mechanical_geometry"] = report.model_dump(mode="json")
    metadata = dict(project.metadata)
    metadata.update(
        {
            "mechanical_geometry_schema": report.schema_version,
            "step_model_count": len(report.models),
            "declared_mount_count": len(report.mounts),
            "mechanical_geometry_blocker_count": len(report.blocking_checks),
            "step_point_envelope_only": True,
            "full_brep_validation": False,
            "collision_analysis": False,
            "fabrication_authorized": False,
        }
    )
    return MachineProject.model_validate(
        project.model_copy(
            update={
                "artifacts": artifacts,
                "discipline_payloads": payloads,
                "metadata": metadata,
            },
            deep=True,
        ).model_dump(mode="json")
    )


def _status_with_mechanical_geometry(
    status: EngineeringStatus,
    report: MechanicalGeometryReport,
) -> EngineeringStatus:
    additions: list[StatusBlocker] = []
    for check in report.checks:
        if check.status == MechanicalCheckStatus.PASS:
            continue
        additions.append(
            StatusBlocker(
                blocker_id=f"mechanical-{check.check_id}",
                category="manufacturing",
                severity=(
                    StatusSeverity.ERROR if check.blocking else StatusSeverity.WARNING
                ),
                message=check.message,
                target_ids=check.target_ids,
                required_inputs=check.unresolved_fields,
                required_evidence=[
                    f"Mechanical evidence closing {check.check_id}."
                ],
                source_ids=check.source_ids,
                metadata={
                    "mechanical_check_id": check.check_id,
                    "mechanical_category": check.category,
                    "step_point_envelope_only": True,
                    "full_brep_validation": False,
                },
            )
        )
    if not additions:
        summary = dict(status.summary)
        summary.update(
            {
                "mechanical_geometry_check_count": len(report.checks),
                "mechanical_geometry_blocker_count": 0,
            }
        )
        return status.model_copy(update={"summary": summary}, deep=True)

    blockers = {row.blocker_id: row for row in status.blockers}
    advisories = {row.blocker_id: row for row in status.advisories}
    for row in additions:
        if row.severity == StatusSeverity.ERROR:
            blockers[row.blocker_id] = row
            advisories.pop(row.blocker_id, None)
        else:
            advisories[row.blocker_id] = row
    groups = {key: list(values) for key, values in status.blocker_groups.items()}
    manufacturing_ids = list(groups.get("manufacturing") or [])
    for row in additions:
        if row.blocker_id not in manufacturing_ids:
            manufacturing_ids.append(row.blocker_id)
    groups["manufacturing"] = manufacturing_ids
    summary = dict(status.summary)
    summary.update(
        {
            "blocking_count": len(blockers),
            "advisory_count": len(advisories),
            "mechanical_geometry_check_count": len(report.checks),
            "mechanical_geometry_blocker_count": len(report.blocking_checks),
        }
    )
    return status.model_copy(
        update={
            "overall_status": "blocked" if blockers else status.overall_status,
            "current_phase": (
                status.current_phase
                if status.current_phase in {"source", "topology", "requirements", "analysis"}
                else "manufacturing"
            ),
            "blockers": list(blockers.values()),
            "advisories": list(advisories.values()),
            "blocker_groups": groups,
            "summary": summary,
        },
        deep=True,
    )


def apply_mechanical_geometry_to_plan(
    plan: Mapping[str, Any],
    report: MechanicalGeometryReport | Mapping[str, Any],
) -> Dict[str, Any]:
    """Attach STEP identity and route unresolved mechanical checks into status."""

    updated = dict(plan)
    resolved = (
        report
        if isinstance(report, MechanicalGeometryReport)
        else MechanicalGeometryReport.model_validate(report)
    )
    project = MachineProject.model_validate(updated.get("machine_project") or {})
    if resolved.project_id != project.project_id:
        raise ValueError("mechanical geometry project_id does not match MachineProject")
    project = _attach_step_artifacts(project, resolved)
    updated["machine_project"] = project.model_dump(mode="json")
    updated["mechanical_geometry"] = resolved.model_dump(mode="json")
    status = _status_with_mechanical_geometry(build_engineering_status(updated), resolved)
    status_payload = status.model_dump(mode="json")

    payloads = dict(project.discipline_payloads)
    payloads["engineering_status"] = status_payload
    metadata = dict(project.metadata)
    metadata.update(
        {
            "mechanical_geometry_plan_schema": MECHANICAL_GEOMETRY_PLAN_SCHEMA,
            "mechanical_geometry_status": resolved.status,
            "mechanical_geometry_blocker_count": len(resolved.blocking_checks),
            "manufacturing_authorized": False,
            "fabrication_authorized": False,
            "release_authorized": False,
        }
    )
    project = project.model_copy(
        update={"discipline_payloads": payloads, "metadata": metadata},
        deep=True,
    )
    updated["machine_project"] = project.model_dump(mode="json")
    updated["engineering_status"] = status_payload

    readiness = dict(updated.get("engineering_readiness") or {})
    readiness.update(
        {
            "status": status.overall_status,
            "current_phase": status.current_phase,
            "mechanical_geometry_status": resolved.status,
            "mechanical_geometry_check_count": len(resolved.checks),
            "mechanical_geometry_blocker_count": len(resolved.blocking_checks),
            "step_model_count": len(resolved.models),
            "declared_mount_count": len(resolved.mounts),
            "step_point_envelope_only": True,
            "full_brep_validation": False,
            "collision_analysis": False,
            "manufacturing_authorized": False,
            "fabrication_authorized": False,
            "release_authorized": False,
        }
    )
    updated["engineering_readiness"] = readiness

    scenario = dict(updated.get("scenario") or {})
    compile_spec = dict(scenario.get("compile_spec") or {})
    compile_spec["machine_project"] = project.model_dump(mode="json")
    compile_spec["mechanical_geometry"] = resolved.model_dump(mode="json")
    compile_spec["engineering_status"] = status_payload
    scenario["compile_spec"] = compile_spec
    scenario["mechanical_geometry_acceptance"] = {
        "status": resolved.status,
        "blocking_check_count": len(resolved.blocking_checks),
        "step_point_envelope_only": True,
        "full_brep_validation": False,
        "collision_analysis": False,
        "fabrication_authorized": False,
    }
    updated["scenario"] = scenario
    return updated
