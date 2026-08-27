"""Apply one bounded execution manifest to a guided engineering plan."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping

from .engineering_execution import ExecutionResult
from .engineering_execution_evidence import attach_execution_evidence
from .engineering_status import build_engineering_status
from .machine_project import MachineProject


EXECUTION_PLAN_UPDATE_SCHEMA = "hardware_splicer.engineering_execution_plan_update.v1"


def apply_execution_evidence_to_plan(
    plan: Mapping[str, Any],
    result: ExecutionResult | Mapping[str, Any],
    *,
    target_ids: Iterable[str] = (),
    requirement_ids: Iterable[str] = (),
) -> Dict[str, Any]:
    """Update MachineProject, unified status, compile payload, and readiness."""

    updated = dict(plan)
    project = MachineProject.model_validate(updated.get("machine_project") or {})
    project = attach_execution_evidence(
        project,
        result,
        target_ids=target_ids,
        requirement_ids=requirement_ids,
    )
    updated["machine_project"] = project.model_dump(mode="json")

    status = build_engineering_status(updated)
    status_payload = status.model_dump(mode="json")
    payloads = dict(project.discipline_payloads)
    payloads["engineering_status"] = status_payload
    metadata = dict(project.metadata)
    metadata.update(
        {
            "engineering_execution_plan_update_schema": EXECUTION_PLAN_UPDATE_SCHEMA,
            "engineering_status_schema": status.schema_version,
            "engineering_status": status.overall_status,
            "engineering_current_phase": status.current_phase,
            "engineering_blocker_count": len(status.blockers),
            "engineering_next_action_id": status.next_action_id,
            "physical_authority_unchanged": True,
            "operational_authority_unchanged": True,
        }
    )
    project = project.model_copy(
        update={"discipline_payloads": payloads, "metadata": metadata},
        deep=True,
    )
    updated["machine_project"] = project.model_dump(mode="json")
    updated["engineering_status"] = status_payload

    readiness = dict(updated.get("engineering_readiness") or {})
    execution_payload = project.discipline_payloads.get("engineering_execution_evidence")
    manifests = (
        list(execution_payload.get("manifests") or [])
        if isinstance(execution_payload, Mapping)
        else []
    )
    readiness.update(
        {
            "status": status.overall_status,
            "current_phase": status.current_phase,
            "unified_blocker_count": len(status.blockers),
            "unified_advisory_count": len(status.advisories),
            "next_action_id": status.next_action_id,
            "software_execution_evidence_count": len(manifests),
            "physical_authority_unchanged": True,
            "automatic_execution": False,
            "fabrication_authorized": False,
            "flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        }
    )
    updated["engineering_readiness"] = readiness

    scenario = dict(updated.get("scenario") or {})
    compile_spec = dict(scenario.get("compile_spec") or {})
    compile_spec["machine_project"] = project.model_dump(mode="json")
    compile_spec["engineering_status"] = status_payload
    compile_spec["engineering_execution_evidence"] = execution_payload
    scenario["compile_spec"] = compile_spec
    scenario["next_action"] = (
        status.next_actions[0].model_dump(mode="json")
        if status.next_actions
        else None
    )
    scenario["execution_evidence_acceptance"] = {
        "manifest_count": len(manifests),
        "software_only": True,
        "physical_authority_unchanged": True,
        "flash_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "release_authorized": False,
    }
    updated["scenario"] = scenario
    return updated
