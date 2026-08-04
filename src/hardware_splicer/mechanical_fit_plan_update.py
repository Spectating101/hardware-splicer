"""Integrate bounded mechanical-fit findings into canonical guided plans.

Fit checks are projected into manufacturing closure before unified status is rebuilt.
This keeps blocker groups, ranked next actions, readiness, persistence, and the compile
payload coherent. The report remains bounded to declared normals, same-frame AABBs,
and declared fastener stacks; it grants no fabrication or physical authority.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from .engineering_status import build_engineering_status
from .machine_project import MachineProject
from .mechanical_fit import FitStatus, MechanicalFitReport


MECHANICAL_FIT_PLAN_SCHEMA = "hardware_splicer.mechanical_fit_plan_update.v1"
_SYNTHETIC_SOURCE = "mechanical_fit"


def _closure_check(report: MechanicalFitReport, check) -> Dict[str, Any]:
    return {
        "check_id": f"mechanical-fit-{check.check_id}",
        "status": "pass" if check.status == FitStatus.PASS else check.status.value,
        "severity": "error" if check.blocking else "warning",
        "message": check.message,
        "target_ids": list(check.target_ids),
        "source_ids": [],
        "unresolved_fields": list(check.unresolved_fields),
        "metadata": {
            **dict(check.metadata),
            "source_schema": report.schema_version,
            "source_kind": _SYNTHETIC_SOURCE,
            "fit_check_id": check.check_id,
            "fit_category": check.category,
            "aabb_only": True,
            "full_brep_collision": False,
            "structural_analysis": False,
            "thread_strength_verified": False,
            "fabrication_authorized": False,
        },
    }


def _project_fit(project: MachineProject, report: MechanicalFitReport) -> MachineProject:
    payloads = dict(project.discipline_payloads)
    payloads["mechanical_fit"] = report.model_dump(mode="json")
    metadata = dict(project.metadata)
    metadata.update(
        {
            "mechanical_fit_schema": report.schema_version,
            "mechanical_fit_plan_schema": MECHANICAL_FIT_PLAN_SCHEMA,
            "mechanical_fit_status": report.status,
            "mechanical_fit_check_count": len(report.checks),
            "mechanical_fit_blocker_count": len(report.blocking_checks),
            "mechanical_fit_aabb_only": True,
            "full_brep_collision": False,
            "structural_analysis": False,
            "thread_strength_verified": False,
            "manufacturing_authorized": False,
            "fabrication_authorized": False,
            "release_authorized": False,
        }
    )
    return MachineProject.model_validate(
        project.model_copy(
            update={"discipline_payloads": payloads, "metadata": metadata},
            deep=True,
        ).model_dump(mode="json")
    )


def apply_mechanical_fit_to_plan(
    plan: Mapping[str, Any],
    report: MechanicalFitReport | Mapping[str, Any],
) -> Dict[str, Any]:
    """Attach one fit report and rebuild manufacturing status and next actions."""

    updated = dict(plan)
    resolved = (
        report
        if isinstance(report, MechanicalFitReport)
        else MechanicalFitReport.model_validate(report)
    )
    project = MachineProject.model_validate(updated.get("machine_project") or {})
    if resolved.project_id != project.project_id:
        raise ValueError("mechanical fit project_id does not match MachineProject")

    project = _project_fit(project, resolved)
    updated["machine_project"] = project.model_dump(mode="json")
    updated["mechanical_fit"] = resolved.model_dump(mode="json")

    closure = dict(updated.get("manufacturing_closure") or {})
    existing_checks = [
        dict(row)
        for row in closure.get("checks") or []
        if isinstance(row, Mapping)
        and (row.get("metadata") or {}).get("source_kind") != _SYNTHETIC_SOURCE
    ]
    fit_checks = [_closure_check(resolved, row) for row in resolved.checks]
    closure["checks"] = [*existing_checks, *fit_checks]
    closure["mechanical_fit_schema"] = resolved.schema_version
    closure["mechanical_fit_status"] = resolved.status
    closure["mechanical_fit_blocker_count"] = len(resolved.blocking_checks)
    closure["fabrication_authorized"] = False
    updated["manufacturing_closure"] = closure

    missing = [
        str(value)
        for value in updated.get("missing_info") or []
        if not str(value).startswith("Mechanical fit ")
    ]
    missing.extend(
        f"Mechanical fit {row.check_id}: {row.message}"
        for row in resolved.blocking_checks
    )
    updated["missing_info"] = list(dict.fromkeys(missing))

    status = build_engineering_status(updated)
    status_payload = status.model_dump(mode="json")
    payloads = dict(project.discipline_payloads)
    payloads["engineering_status"] = status_payload
    project = MachineProject.model_validate(
        project.model_copy(
            update={"discipline_payloads": payloads},
            deep=True,
        ).model_dump(mode="json")
    )
    updated["machine_project"] = project.model_dump(mode="json")
    updated["engineering_status"] = status_payload

    readiness = dict(updated.get("engineering_readiness") or {})
    readiness.update(
        {
            "status": status.overall_status,
            "current_phase": status.current_phase,
            "mechanical_fit_status": resolved.status,
            "mechanical_fit_check_count": len(resolved.checks),
            "mechanical_fit_blocker_count": len(resolved.blocking_checks),
            "clearance_box_count": len(resolved.clearance_boxes),
            "clearance_requirement_count": len(resolved.clearance_requirements),
            "fastener_stack_count": len(resolved.fastener_stacks),
            "mechanical_fit_aabb_only": True,
            "full_brep_collision": False,
            "structural_analysis": False,
            "thread_strength_verified": False,
            "manufacturing_authorized": False,
            "fabrication_authorized": False,
            "release_authorized": False,
        }
    )
    updated["engineering_readiness"] = readiness

    scenario = dict(updated.get("scenario") or {})
    compile_spec = dict(scenario.get("compile_spec") or {})
    compile_spec["machine_project"] = project.model_dump(mode="json")
    compile_spec["mechanical_fit"] = resolved.model_dump(mode="json")
    compile_spec["manufacturing_closure"] = closure
    compile_spec["engineering_status"] = status_payload
    scenario["compile_spec"] = compile_spec
    scenario["mechanical_fit_acceptance"] = {
        "status": resolved.status,
        "blocking_check_count": len(resolved.blocking_checks),
        "aabb_only": True,
        "full_brep_collision": False,
        "structural_analysis": False,
        "thread_strength_verified": False,
        "fabrication_authorized": False,
        "release_authorized": False,
    }
    updated["scenario"] = scenario
    return updated
