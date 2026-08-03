"""Product route for importing Circuit JSON into canonical electrical identity."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .electrical_interchange import electrical_design_from_interchange
from .integrations.circuit_json_import import circuit_json_to_netlist


class CircuitJsonElectricalDesignRequest(BaseModel):
    project_id: str = Field(min_length=1)
    documents: list[Dict[str, Any]] = Field(default_factory=list)
    source_label: str = "circuit_json_inline"


def create_electrical_interchange_router() -> APIRouter:
    router = APIRouter(prefix="/v1/interchange/circuit-json", tags=["circuit-json"])

    @router.post("/electrical-design")
    def project_electrical_design(
        request: CircuitJsonElectricalDesignRequest,
    ) -> Dict[str, Any]:
        if not request.documents:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "circuit_json_empty",
                        "message": "Circuit JSON documents array is required.",
                    }
                },
            )
        try:
            netlist = circuit_json_to_netlist(
                request.documents,
                source=request.source_label or "circuit_json_inline",
            )
            design = electrical_design_from_interchange(
                netlist,
                request.documents,
                project_id=request.project_id,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "circuit_json_electrical_projection_error",
                        "message": str(exc),
                    }
                },
            ) from exc

        erc = [issue.model_dump(mode="json") for issue in design.erc_issues()]
        identity = dict(design.metadata.get("identity_map") or {})
        unresolved = list(design.metadata.get("unresolved_identity") or [])
        return {
            "ok": True,
            "schema_version": "hardware_splicer.electrical_interchange.v1",
            "authority": "proposed",
            "summary": {
                "component_count": len(design.components),
                "pin_count": len(design.pins),
                "net_count": len(design.nets),
                "erc_issue_count": len(erc),
                "unresolved_identity_count": len(unresolved),
            },
            "identity_map": identity,
            "unresolved_identity": unresolved,
            "erc": erc,
            "electrical_design": design.model_dump(mode="json"),
        }

    return router
