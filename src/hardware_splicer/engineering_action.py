"""Prepare one ranked engineering action without performing physical operations."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from pydantic import BaseModel, ConfigDict, Field

from .engineering_execution import ExecutionRequest, preview_engineering_execution
from .engineering_status import EngineeringStatus, NextAction, build_engineering_status
from .machine_project import MachineProject
from .manufacturing_closure import ManufacturingClosureReport, build_manufacturing_closure


ENGINEERING_ACTION_SCHEMA = "hardware_splicer.engineering_action.v1"


class ActionBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class PreparedEngineeringAction(ActionBase):
    schema_version: str = ENGINEERING_ACTION_SCHEMA
    project_id: str
    action: NextAction
    status: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in value if isinstance(row, Mapping)] if isinstance(value, list) else []


def _select_action(status: EngineeringStatus, action_id: str | None) -> NextAction:
    if action_id:
        selected = next((row for row in status.next_actions if row.action_id == action_id), None)
        if selected is None:
            raise ValueError(f"unknown engineering action {action_id!r}")
        return selected
    if not status.next_actions:
        raise ValueError("engineering status has no next action")
    return status.next_actions[0]


def _source_payload(plan: Mapping[str, Any]) -> Dict[str, Any]:
    graph = _mapping(plan.get("engineering_source_graph"))
    return {
        "unresolved_source_ids": list(graph.get("unresolved_source_ids") or []),
        "blocking_conflicts": [row for row in _rows(graph.get("conflicts")) if row.get("blocking")],
        "decision_route": "/v1/engineering/sources/resolve-conflicts",
        "boundary_route": "/v1/engineering/sources/select-boundary",
    }


def _topology_payload(plan: Mapping[str, Any]) -> Dict[str, Any]:
    topology = _mapping(plan.get("robot_topology"))
    return {
        "topology_id": topology.get("topology_id"),
        "robot_genre": topology.get("robot_genre"),
        "unresolved": _rows(topology.get("unresolved")),
        "link_count": len(_rows(topology.get("links"))),
        "joint_count": len(_rows(topology.get("joints"))),
        "actuator_count": len(_rows(topology.get("actuators"))),
        "sensor_count": len(_rows(topology.get("sensors"))),
        "topology_route": "/v1/engineering/topology",
    }


def _analysis_payload(plan: Mapping[str, Any]) -> Dict[str, Any]:
    report = _mapping(plan.get("engineering_analysis"))
    findings = _rows(report.get("findings"))
    return {
        "blocking_findings": [row for row in findings if row.get("blocking")],
        "other_findings": [row for row in findings if not row.get("blocking")],
        "analysis_route": "/v1/engineering/analysis",
    }


def _manufacturing_payload(plan: Mapping[str, Any]) -> tuple[Dict[str, Any], list[str]]:
    existing = plan.get("manufacturing_closure")
    if isinstance(existing, Mapping):
        try:
            report = ManufacturingClosureReport.model_validate(existing)
        except ValueError:
            report = build_manufacturing_closure(plan)
    else:
        report = build_manufacturing_closure(plan)
    blockers = [row.message for row in report.blocking_checks]
    return {
        "manufacturing_closure": report.model_dump(mode="json"),
        "mechanical_geometry": _mapping(plan.get("mechanical_geometry")),
        "mechanical_fit": _mapping(plan.get("mechanical_fit")),
        "closure_route": "/v1/engineering/manufacturing-closure",
        "mechanical_schema_route": "/v1/engineering/mechanical/schema",
        "geometry_apply_route": "/v1/engineering/mechanical/geometry/apply",
        "fit_check_route": "/v1/engineering/mechanical/fit/check",
        "fit_apply_route": "/v1/engineering/mechanical/fit/apply",
        "required_evidence": report.required_evidence,
        "full_brep_collision": False,
        "structural_analysis": False,
        "fabrication_authorized": False,
    }, blockers


def _execution_payload(plan: Mapping[str, Any]) -> tuple[Dict[str, Any], list[str], list[str]]:
    execution_plan = _mapping(plan.get("engineering_execution_plan"))
    previews: list[Dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    for row in _rows(execution_plan.get("checks")):
        try:
            request = ExecutionRequest.model_validate({**row, "execute": False})
            preview = preview_engineering_execution(request)
            previews.append(preview.model_dump(mode="json"))
            blockers.extend(preview.blockers)
        except (TypeError, ValueError) as exc:
            blockers.append(str(exc))
    for row in _rows(execution_plan.get("unresolved")):
        warnings.append(str(row.get("reason") or "bounded execution input is unresolved"))
    return {
        "checks": _rows(execution_plan.get("checks")),
        "previews": previews,
        "unresolved": _rows(execution_plan.get("unresolved")),
        "capability_route": "/v1/engineering/execution/capabilities",
        "preview_route": "/v1/engineering/execution/preview",
        "run_route": "/v1/engineering/execution/run",
        "evidence_route": "/v1/engineering/execution/evidence/save",
    }, list(dict.fromkeys(blockers)), list(dict.fromkeys(warnings))


def _change_payload(plan: Mapping[str, Any]) -> Dict[str, Any]:
    impact = _mapping(plan.get("change_impact"))
    return {
        "baseline_revision": impact.get("baseline_revision"),
        "candidate_revision": impact.get("candidate_revision"),
        "blocking_impacts": [row for row in _rows(impact.get("impacts")) if row.get("blocking")],
        "regression_checks": _rows(impact.get("regression_checks")),
        "unresolved": _rows(impact.get("unresolved")),
        "change_impact_route": "/v1/engineering/change-impact",
    }


def _verification_payload(plan: Mapping[str, Any]) -> Dict[str, Any]:
    machine = _mapping(plan.get("machine_project"))
    verifications = _rows(machine.get("verifications"))
    return {
        "failed": [row for row in verifications if row.get("status") == "failed"],
        "blocked": [row for row in verifications if row.get("status") == "blocked"],
        "planned": [row for row in verifications if row.get("status") in {None, "planned", "running"}],
        "execution_evidence_route": "/v1/engineering/execution/evidence/save",
    }


def _release_payload(plan: Mapping[str, Any]) -> tuple[Dict[str, Any], list[str]]:
    blockers: list[str] = []
    assessment: Dict[str, Any] | None = None
    try:
        project = MachineProject.model_validate(plan.get("machine_project") or {})
        release = project.assess_release()
        assessment = release.model_dump(mode="json")
        blockers.extend(row.message for row in release.blockers)
    except (TypeError, ValueError) as exc:
        blockers.append(f"MachineProject release assessment is unavailable: {exc}")

    scoped = _mapping(plan.get("scoped_release_assessment"))
    if scoped and not scoped.get("authorized"):
        for row in scoped.get("blockers") or []:
            if isinstance(row, Mapping):
                blockers.append(str(row.get("message") or row.get("reason") or "Scoped release blocker"))
            else:
                blockers.append(str(row))
    return {
        "operator_guide": _mapping(plan.get("operator_guide")),
        "release_assessment": assessment,
        "physical_evidence_package": _mapping(plan.get("physical_evidence_package")),
        "scoped_release_assessment": scoped,
        "review_route": "/v1/engineering/guide",
        "physical_schema_route": "/v1/engineering/physical-evidence/schema",
        "physical_assess_route": "/v1/engineering/physical-evidence/assess",
        "physical_release_assess_route": "/v1/engineering/physical-evidence/release-assess",
        "physical_apply_save_route": "/v1/engineering/physical-evidence/apply-save",
        "physical_evidence_required": True,
        "human_authorization_required": True,
        "automatic_authorization": False,
    }, list(dict.fromkeys(blockers))


def prepare_engineering_action(
    plan: Mapping[str, Any],
    *,
    action_id: str | None = None,
) -> PreparedEngineeringAction:
    """Prepare the selected ranked action without automatic physical execution."""

    # Engineering status performs fresh candidate-bound physical revalidation. Prepared
    # actions must consume that status rather than trusting cached plan flags; otherwise a
    # stale scoped_release_assessment can say "ready" after the candidate revision has
    # invalidated authorization.
    status = build_engineering_status(plan)
    action = _select_action(status, action_id)
    payload: Dict[str, Any]
    blockers: list[str] = []
    warnings: list[str] = []
    category = action.category
    if category == "source":
        payload = _source_payload(plan)
    elif category == "topology":
        payload = _topology_payload(plan)
    elif category == "requirements":
        payload = {
            "normalized_intake": _mapping(plan.get("normalized_intake")),
            "missing_info": list(plan.get("missing_info") or []),
            "plan_route": "/v1/engineering/plan",
        }
    elif category == "analysis":
        payload = _analysis_payload(plan)
    elif category == "manufacturing":
        payload, blockers = _manufacturing_payload(plan)
    elif category == "execution":
        payload, blockers, warnings = _execution_payload(plan)
    elif category == "change":
        payload = _change_payload(plan)
    elif category == "verification":
        payload = _verification_payload(plan)
    elif category == "release":
        payload, blockers = _release_payload(plan)
        blockers.extend(
            row.message
            for row in status.blockers
            if str(row.category or "") == "release"
        )
    else:
        payload = {
            "missing_info": list(plan.get("missing_info") or []),
            "plan_route": "/v1/engineering/plan",
        }
    prepared_status = "blocked" if blockers else "ready"
    return PreparedEngineeringAction(
        project_id=status.project_id,
        action=action,
        status=prepared_status,
        payload=payload,
        blockers=list(dict.fromkeys(blockers)),
        warnings=list(dict.fromkeys(warnings)),
        metadata={
            "automatic_execution": False,
            "physical_action": False,
            "network_authorized": False,
            "device_access_authorized": False,
            "fabrication_authorized": False,
            "flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
            "physical_authorization_revalidated": bool(
                status.metadata.get("physical_authorization_revalidated")
            ),
        },
    )


# Compatibility marker retained for callers/tests that previously installed an external
# action-layer wrapper. Revalidation is now native to prepare_engineering_action itself.
_physical_action_revalidation_installed = True
