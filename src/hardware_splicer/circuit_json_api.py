"""Product routes for Circuit JSON interoperability and import diagnostics."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .integrations.circuit_json_import import circuit_json_to_netlist


class CircuitJsonInspectRequest(BaseModel):
    documents: list[Dict[str, Any]] = Field(default_factory=list)
    source_label: str = "circuit_json_inline"


def create_circuit_json_router() -> APIRouter:
    router = APIRouter(prefix="/v1/interchange/circuit-json", tags=["circuit-json"])

    @router.post("/inspect")
    def inspect(request: CircuitJsonInspectRequest) -> Dict[str, Any]:
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
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "circuit_json_import_error",
                        "message": str(exc),
                    }
                },
            ) from exc

        diagnostics = dict(netlist.metadata.get("circuit_json") or {})
        unresolved_count = (
            len(diagnostics.get("unresolved_ports") or [])
            + len(diagnostics.get("unresolved_trace_ports") or [])
            + len(diagnostics.get("ambiguous_traces") or [])
        )
        single_pin_count = len(diagnostics.get("single_pin_nets") or [])
        upstream_diagnostic_count = len(diagnostics.get("upstream_diagnostics") or [])
        compilable = bool(netlist.components and netlist.nets)

        if not netlist.components:
            status = "blocked"
            headline = "No source components could be imported."
        elif not netlist.nets:
            status = "blocked"
            headline = "Components imported, but no multi-pin electrical nets were resolved."
        elif unresolved_count or single_pin_count:
            status = "review_required"
            headline = "Circuit imported with unresolved or incomplete connectivity."
        else:
            status = "ready"
            headline = "Circuit source graph is ready for Hardware Splicer compile."

        return {
            "ok": True,
            "schema_version": "hardware_splicer.circuit_json_inspection.v1",
            "status": status,
            "headline": headline,
            "compilable": compilable,
            "authority": "proposed",
            "summary": {
                "document_count": len(request.documents),
                "component_count": len(netlist.components),
                "net_count": len(netlist.nets),
                "unresolved_count": unresolved_count,
                "single_pin_net_count": single_pin_count,
                "upstream_diagnostic_count": upstream_diagnostic_count,
            },
            "components": [component.to_dict() for component in netlist.components],
            "nets": [net.to_dict() for net in netlist.nets],
            "diagnostics": diagnostics,
            "netlist": netlist.to_dict(),
        }

    return router
