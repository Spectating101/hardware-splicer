"""HTTP surface for source-agnostic engineering planning."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .change_impact import ChangeImpactGraph, build_change_impact_graph
from .engineering_analysis import EngineeringAnalysisReport, analyze_engineering_candidate
from .engineering_planner import normalize_engineering_intake, plan_engineering_project
from .engineering_source_graph import EngineeringSourceGraph, build_engineering_source_graph
from .machine_project import MachineProject
from .machine_project_seed import machine_project_from_intake
from .robot_topology import RobotTopology, build_robot_topology


class EngineeringPlanRequest(BaseModel):
    intake: Dict[str, Any]
    engineering_sources: list[Any] = Field(default_factory=list)
    declared_conflicts: list[Dict[str, Any]] = Field(default_factory=list)
    baseline_project: Dict[str, Any] | None = None
    skip_vision: bool = True


class SourceGraphRequest(BaseModel):
    engineering_sources: list[Any] = Field(default_factory=list)
    declared_conflicts: list[Dict[str, Any]] = Field(default_factory=list)
    unresolved_source_ids: list[str] = Field(default_factory=list)


class RobotTopologyRequest(BaseModel):
    intake: Dict[str, Any]
    hinted_genre: str | None = None
    machine_project: MachineProject | None = None


class EngineeringAnalysisRequest(BaseModel):
    intake: Dict[str, Any]
    robot_topology: RobotTopology | None = None


class ChangeImpactRequest(BaseModel):
    intake: Dict[str, Any]
    machine_project: MachineProject | None = None
    robot_topology: RobotTopology | None = None
    engineering_source_graph: EngineeringSourceGraph | None = None
    baseline_project: Dict[str, Any] | None = None


def _unprocessable(error_type: str, exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"type": error_type, "message": str(exc)},
    )


def create_engineering_router() -> APIRouter:
    router = APIRouter(prefix="/v1/engineering", tags=["engineering"])

    @router.get("/schemas")
    def engineering_schemas() -> Dict[str, Any]:
        return {
            "ok": True,
            "schemas": {
                "engineering_source_graph": EngineeringSourceGraph.model_json_schema(),
                "robot_topology": RobotTopology.model_json_schema(),
                "engineering_analysis": EngineeringAnalysisReport.model_json_schema(),
                "change_impact": ChangeImpactGraph.model_json_schema(),
            },
        }

    @router.post("/sources/reconcile")
    def reconcile_sources(request: SourceGraphRequest) -> Dict[str, Any]:
        try:
            graph = build_engineering_source_graph(
                request.engineering_sources,
                declared_conflicts=request.declared_conflicts,
                unresolved_source_ids=request.unresolved_source_ids,
            )
        except ValueError as exc:
            raise _unprocessable("invalid_engineering_source_graph", exc) from exc
        return {
            "ok": True,
            "graph": graph.model_dump(mode="json"),
            "source_provenance_complete": graph.source_provenance_complete,
            "blocking_conflict_count": len(graph.blocking_conflicts),
        }

    @router.post("/topology")
    def create_topology(request: RobotTopologyRequest) -> Dict[str, Any]:
        try:
            intake = normalize_engineering_intake(request.intake)
            project = request.machine_project or machine_project_from_intake(intake)
            topology = build_robot_topology(
                intake,
                hinted_genre=request.hinted_genre,
                machine_project=project,
            )
        except ValueError as exc:
            raise _unprocessable("invalid_robot_topology", exc) from exc
        return {
            "ok": True,
            "topology": topology.model_dump(mode="json"),
            "degree_of_freedom_count": topology.degree_of_freedom_count,
            "unresolved_count": len(topology.unresolved),
            "motion_authorized": False,
        }

    @router.post("/analysis")
    def analyze_candidate(request: EngineeringAnalysisRequest) -> Dict[str, Any]:
        try:
            intake = normalize_engineering_intake(request.intake)
            topology = request.robot_topology or build_robot_topology(intake)
            report = analyze_engineering_candidate(intake, topology=topology)
        except ValueError as exc:
            raise _unprocessable("invalid_engineering_analysis", exc) from exc
        return {
            "ok": True,
            "engineering_analysis": report.model_dump(mode="json"),
            "blocking_finding_count": len(report.blocking_findings),
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        }

    @router.post("/change-impact")
    def assess_change_impact(request: ChangeImpactRequest) -> Dict[str, Any]:
        try:
            intake = normalize_engineering_intake(request.intake)
            project = request.machine_project or machine_project_from_intake(intake)
            topology = request.robot_topology or build_robot_topology(
                intake,
                machine_project=project,
            )
            impact = build_change_impact_graph(
                intake,
                machine_project=project,
                topology=topology,
                source_graph=request.engineering_source_graph,
                baseline_project=request.baseline_project,
            )
        except ValueError as exc:
            raise _unprocessable("invalid_change_impact_graph", exc) from exc
        return {
            "ok": True,
            "change_impact": impact.model_dump(mode="json"),
            "affected_domains": impact.affected_domains,
            "affected_target_ids": impact.affected_target_ids,
            "blocking_impact_count": len(impact.blocking_impacts),
            "release_authority_preserved": not bool(impact.blocking_impacts),
        }

    @router.post("/plan")
    def create_engineering_plan(request: EngineeringPlanRequest) -> Dict[str, Any]:
        try:
            plan = plan_engineering_project(
                request.intake,
                engineering_sources=request.engineering_sources,
                declared_conflicts=request.declared_conflicts,
                baseline_project=request.baseline_project,
                skip_vision=request.skip_vision,
            )
        except (TypeError, ValueError) as exc:
            raise _unprocessable("invalid_engineering_plan", exc) from exc
        return {
            "ok": True,
            "plan": plan,
            "engineering_readiness": plan.get("engineering_readiness"),
            "machine_project": plan.get("machine_project"),
        }

    return router
