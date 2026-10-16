"""Canonical fail-closed API for the fabricator digital-thread workbench."""
from __future__ import annotations

from typing import Any, Dict, Mapping

from fastapi import APIRouter, HTTPException, Request
from fastapi import status as http_status

from .fabrication_operator import FabricationValidationError
from .fabricator_digital_thread_workbench import FabricatorDigitalThreadWorkbench


def _runtime(request: Request) -> FabricatorDigitalThreadWorkbench:
    value = getattr(request.app.state, "fabricator_digital_thread_workbench", None)
    if not isinstance(value, FabricatorDigitalThreadWorkbench):
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "type": "fabricator_digital_thread_unavailable",
                "message": "fabricator digital-thread runtime is not configured",
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
        detail={"type": "fabricator_digital_thread_error", "message": "internal fabricator digital-thread error"},
    )


def create_fabricator_digital_thread_router() -> APIRouter:
    router = APIRouter(prefix="/v1/fabricator/digital", tags=["fabricator-digital-thread"])

    @router.get("/artifacts")
    def list_engineering_artifacts(request: Request, kind: str | None = None) -> Dict[str, Any]:
        try:
            values = _runtime(request).list_artifacts(kind=kind)
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "artifacts": values}

    @router.get("/mechanics/geometries")
    def list_mechanical_geometries(request: Request) -> Dict[str, Any]:
        try:
            values = _runtime(request).list_mechanical_geometries()
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "geometries": values}

    @router.get("/mechanics/profiles")
    def list_mechanical_profiles(request: Request, printer_id: str | None = None) -> Dict[str, Any]:
        try:
            values = _runtime(request).list_slicer_profiles(printer_id=printer_id)
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "profiles": values}

    @router.post("/mechanics/print-artifacts", status_code=http_status.HTTP_201_CREATED)
    def prepare_mechanical_print_artifact(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        try:
            value = _body(body)
            result = _runtime(request).prepare_print_artifact(
                geometry_id=value.get("geometry_id"),
                profile_id=value.get("profile_id"),
                artifact_id=value.get("artifact_id"),
                output_format=value.get("output_format", "stl"),
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "result": result}

    @router.get("/opcua/{source_id}/measurements")
    def list_opcua_measurements(source_id: str, request: Request) -> Dict[str, Any]:
        try:
            values = _runtime(request).opcua_measurements(source_id)
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "measurements": values}

    @router.post("/opcua/{source_id}/read")
    def read_opcua_measurements(source_id: str, request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        try:
            value = _body(body)
            measurement_ids = value.get("measurement_ids")
            if not isinstance(measurement_ids, list):
                raise FabricationValidationError("measurement_ids must be a list")
            result = _runtime(request).opcua_read(source_id, measurement_ids=measurement_ids)
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "observation": result}

    @router.get("/ros2/{source_id}/graph")
    def capture_ros2_graph(source_id: str, request: Request) -> Dict[str, Any]:
        try:
            result = _runtime(request).ros2_graph(source_id)
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "observation": result}

    @router.post("/motion-plans/{analyzer_id}/dry-run")
    def dry_run_motion_plan(analyzer_id: str, request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        try:
            value = _body(body)
            result = _runtime(request).dry_run_motion_plan(
                analyzer_id,
                artifact_id=value.get("artifact_id"),
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "receipt": result}

    @router.post("/pcb/{project_id}/requests", status_code=http_status.HTTP_201_CREATED)
    def prepare_pcb_fabrication_request(project_id: str, request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        try:
            value = _body(body)
            result = _runtime(request).prepare_pcb_request(
                project_id=project_id,
                revision_id=value.get("revision_id"),
                request_artifact_id=value.get("request_artifact_id"),
                spec=value.get("spec") or {},
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "request": result}

    @router.post("/handoffs", status_code=http_status.HTTP_201_CREATED)
    def build_fabrication_handoff(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        try:
            value = _body(body)
            source_ids = value.get("source_artifact_ids")
            if not isinstance(source_ids, list):
                raise FabricationValidationError("source_artifact_ids must be a list")
            result = _runtime(request).build_handoff(
                project_id=value.get("project_id"),
                mission_id=value.get("mission_id"),
                revision_id=value.get("revision_id"),
                source_artifact_ids=source_ids,
                output_artifact_id=value.get("output_artifact_id"),
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "handoff": result}

    @router.get("/threads/{thread_id}")
    def read_fabrication_thread(thread_id: str, request: Request) -> Dict[str, Any]:
        try:
            result = _runtime(request).thread_manifest(thread_id)
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "thread": result}

    @router.get("/threads/{thread_id}/artifacts/{artifact_id}")
    def trace_fabrication_artifact(thread_id: str, artifact_id: str, request: Request) -> Dict[str, Any]:
        try:
            result = _runtime(request).thread_trace(thread_id, artifact_id=artifact_id)
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "trace": result}

    return router
