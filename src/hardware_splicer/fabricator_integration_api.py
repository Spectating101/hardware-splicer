"""Canonical fail-closed API for the fabricator integration workbench."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from fastapi import APIRouter, HTTPException, Request
from fastapi import status as http_status

from .fabrication_operator import FabricationValidationError
from .fabricator_integration_workbench import FabricatorIntegrationWorkbench


def _runtime(request: Request) -> FabricatorIntegrationWorkbench:
    value = getattr(request.app.state, "fabricator_workbench", None)
    if not isinstance(value, FabricatorIntegrationWorkbench):
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "type": "fabricator_runtime_unavailable",
                "message": "fabricator integration runtime is not configured",
            },
        )
    return value


def _body(value: Any) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise FabricationValidationError("request must be an object")
    return dict(value)


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, FabricationValidationError):
        return HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_request", "message": str(exc)},
        )
    if isinstance(exc, HTTPException):
        return exc
    return HTTPException(
        status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"type": "fabricator_integration_error", "message": "internal fabricator integration error"},
    )


def create_fabricator_integration_router() -> APIRouter:
    router = APIRouter(prefix="/v1/fabricator", tags=["fabricator-integrations"])

    @router.get("/capabilities")
    def list_fabrication_capabilities(request: Request, kind: str | None = None) -> Dict[str, Any]:
        try:
            values = _runtime(request).list_capabilities(kind=kind)
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "capabilities": values}

    @router.post("/capabilities/match")
    def match_fabrication_capabilities(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        try:
            value = _body(body)
            matches = _runtime(request).match_capabilities(
                required_capabilities=value.get("required_capabilities") or [],
                kind=value.get("kind"),
                numeric_minimums=value.get("numeric_minimums") or {},
                allow_simulated=bool(value.get("allow_simulated", True)),
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "matches": matches}

    @router.post("/kicad/{project_id}/verify")
    def verify_kicad_project(project_id: str, request: Request) -> Dict[str, Any]:
        try:
            receipt = _runtime(request).kicad_verify(project_id)
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "receipt": receipt}

    @router.post("/kicad/{project_id}/manufacturing")
    def export_kicad_manufacturing(project_id: str, request: Request) -> Dict[str, Any]:
        try:
            receipt = _runtime(request).kicad_manufacturing(project_id)
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "receipt": receipt}

    @router.post("/ngspice/{circuit_id}")
    def run_ngspice(circuit_id: str, request: Request, body: Dict[str, Any] | None = None) -> Dict[str, Any]:
        try:
            value = _body(body or {})
            receipt = _runtime(request).simulate_circuit(circuit_id, mode=value.get("mode", "report"))
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "receipt": receipt}

    @router.get("/mtconnect/{source_id}/probe")
    def probe_mtconnect(source_id: str, request: Request) -> Dict[str, Any]:
        try:
            observation = _runtime(request).mtconnect(source_id, operation="probe")
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "observation": observation}

    @router.get("/mtconnect/{source_id}/current")
    def current_mtconnect(source_id: str, request: Request) -> Dict[str, Any]:
        try:
            observation = _runtime(request).mtconnect(source_id, operation="current")
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "observation": observation}

    @router.post("/mtconnect/{source_id}/sample")
    def sample_mtconnect(source_id: str, request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        try:
            value = _body(body)
            observation = _runtime(request).mtconnect(
                source_id,
                operation="sample",
                from_sequence=value.get("from_sequence"),
                count=value.get("count", 1000),
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "observation": observation}

    @router.post("/machine-jobs/{analyzer_id}/dry-run")
    def dry_run_machine_job(analyzer_id: str, request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        try:
            value = _body(body)
            receipt = _runtime(request).dry_run_machine_job(
                analyzer_id,
                artifact_id=value.get("artifact_id"),
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "receipt": receipt}

    @router.get("/openpnp/{job_id}/simulation-package")
    def openpnp_simulation_package(job_id: str, request: Request) -> Dict[str, Any]:
        try:
            package = _runtime(request).openpnp_simulation_package(job_id)
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "simulation_package": package}

    @router.get("/benchmarks")
    def list_fabricator_benchmarks(request: Request) -> Dict[str, Any]:
        try:
            values = _runtime(request).benchmarks()
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "benchmarks": values}

    @router.post("/benchmarks/{benchmark_id}/assess")
    def assess_fabricator_benchmark(benchmark_id: str, request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        try:
            value = _body(body)
            records = value.get("records") or []
            if not isinstance(records, list):
                raise FabricationValidationError("records must be a list")
            assessment = _runtime(request).assess_benchmark(benchmark_id, records)
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "assessment": assessment}

    @router.post("/projects/{project_id}/missions/{mission_id}/revision-proposal")
    def build_physical_revision_proposal(
        project_id: str,
        mission_id: str,
        request: Request,
        body: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        try:
            value = _body(body or {})
            proposal = _runtime(request).revision_proposal(
                project_id,
                mission_id,
                candidate_id=value.get("candidate_id"),
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "proposal": proposal}

    return router
