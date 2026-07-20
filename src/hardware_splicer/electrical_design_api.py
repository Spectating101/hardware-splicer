"""HTTP surface for canonical electrical designs."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .electrical_design import ElectricalDesign
from .electrical_design_adapter import electrical_design_from_machine_project
from .machine_project import MachineProject


class ElectricalDesignEnvelope(BaseModel):
    design: ElectricalDesign
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MachineElectricalProjectionRequest(BaseModel):
    project: MachineProject


def _design_response(design: ElectricalDesign) -> Dict[str, Any]:
    issues = design.erc_issues()
    return {
        "ok": True,
        "design": design.model_dump(mode="json"),
        "erc": {
            "issues": [issue.model_dump(mode="json") for issue in issues],
            "error_count": sum(1 for issue in issues if issue.severity == "error"),
            "warning_count": sum(1 for issue in issues if issue.severity != "error"),
            "clean": not any(issue.severity == "error" for issue in issues),
        },
    }


def create_electrical_design_router() -> APIRouter:
    router = APIRouter(prefix="/v1/electrical-designs", tags=["electrical-designs"])

    @router.get("/schema")
    def electrical_design_schema() -> Dict[str, Any]:
        return {"ok": True, "schema": ElectricalDesign.model_json_schema()}

    @router.post("/validate")
    def validate_electrical_design(request: ElectricalDesignEnvelope) -> Dict[str, Any]:
        response = _design_response(request.design)
        response["metadata"] = request.metadata
        return response

    @router.post("/from-machine-project")
    def project_machine_electrical(request: MachineElectricalProjectionRequest) -> Dict[str, Any]:
        return _design_response(electrical_design_from_machine_project(request.project))

    @router.post("/erc")
    def run_electrical_rule_check(request: ElectricalDesignEnvelope) -> Dict[str, Any]:
        return _design_response(request.design)

    return router
