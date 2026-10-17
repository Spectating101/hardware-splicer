"""Canonical fail-closed API for fabricator intelligence."""
from __future__ import annotations

from typing import Any, Dict, Mapping

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi import status as http_status

from .fabrication_operator import FabricationValidationError
from .fabricator_intelligence_workbench import FabricatorIntelligenceWorkbench
from .fabricator_lab_workbench import FabricatorLabWorkbench
from .operator_identity import OperatorRegistryError, OperatorTokenInvalid, resolve_operator
from .project_store import ProjectStore


def _runtime(request: Request) -> FabricatorIntelligenceWorkbench:
    value = getattr(request.app.state, "fabricator_intelligence_workbench", None)
    if not isinstance(value, FabricatorIntelligenceWorkbench):
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "type": "fabricator_intelligence_unavailable",
                "message": "fabricator intelligence runtime is not configured",
            },
        )
    return value


def _body(value: Any) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise FabricationValidationError("request must be an object")
    return dict(value)


def _human(token: str | None) -> str:
    try:
        identity = resolve_operator(token if token else None)
    except OperatorTokenInvalid as exc:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"type": "operator_token_invalid", "message": str(exc)},
        ) from exc
    except OperatorRegistryError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"type": "operator_registry_error", "message": str(exc)},
        ) from exc
    if identity is None or identity.kind != "human":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"type": "operator_required", "message": "a person's operator token is required"},
        )
    return identity.id


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
        detail={"type": "fabricator_intelligence_error", "message": "internal fabricator intelligence error"},
    )


def create_fabricator_intelligence_router() -> APIRouter:
    router = APIRouter(prefix="/v1/fabricator/intelligence", tags=["fabricator-intelligence"])

    @router.post("/vision/inspect", status_code=http_status.HTTP_201_CREATED)
    def inspect_retained_image(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        try:
            value = _body(body)
            result = _runtime(request).inspect_image(
                observation_id=value.get("observation_id"),
                task_id=value.get("task_id"),
                output_artifact_id=value.get("output_artifact_id"),
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "inspection": result}

    @router.post("/vision/donor-drafts", status_code=http_status.HTTP_201_CREATED)
    def create_visual_donor_draft(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        try:
            value = _body(body)
            inspection_ids = value.get("inspection_artifact_ids")
            facts = value.get("facts")
            if not isinstance(inspection_ids, list):
                raise FabricationValidationError("inspection_artifact_ids must be a list")
            if not isinstance(facts, list):
                raise FabricationValidationError("facts must be a list")
            result = _runtime(request).draft_donor_from_inspections(
                donor_id=value.get("donor_id"),
                label=value.get("label"),
                inspection_artifact_ids=inspection_ids,
                facts=facts,
                output_artifact_id=value.get("output_artifact_id"),
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, **result}

    @router.post("/vision/donor-drafts/{draft_artifact_id}/confirm", status_code=http_status.HTTP_201_CREATED)
    def confirm_visual_donor_draft(
        draft_artifact_id: str,
        request: Request,
        body: Dict[str, Any],
        x_hs_operator_token: str | None = Header(default=None, alias="X-HS-Operator-Token"),
    ) -> Dict[str, Any]:
        try:
            human_id = _human(x_hs_operator_token)
            value = _body(body)
            capture = value.get("capture")
            decisions = value.get("decisions")
            if not isinstance(capture, Mapping):
                raise FabricationValidationError("capture must be an object")
            if not isinstance(decisions, list):
                raise FabricationValidationError("decisions must be a list")
            result = _runtime(request).confirm_visual_donor_capture(
                draft_artifact_id=draft_artifact_id,
                output_artifact_id=value.get("output_artifact_id"),
                human_id=human_id,
                capture=capture,
                decisions=decisions,
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, **result}

    @router.get("/procurement/quotes")
    def list_procurement_quotes(
        request: Request,
        part_key: str | None = None,
        supplier_id: str | None = None,
    ) -> Dict[str, Any]:
        try:
            values = _runtime(request).list_quotes(part_key=part_key, supplier_id=supplier_id)
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "quotes": values}

    @router.post("/procurement/estimate")
    def estimate_procurement(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        try:
            value = _body(body)
            lines = value.get("lines")
            if not isinstance(lines, list):
                raise FabricationValidationError("lines must be a list")
            estimate = _runtime(request).cost_bom(
                lines=lines,
                currency=value.get("currency"),
                as_of=value.get("as_of"),
                require_known_stock=bool(value.get("require_known_stock", False)),
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "estimate": estimate}

    @router.post("/resources/project")
    def project_salvage_resources(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        try:
            value = _body(body)
            references = value.get("donor_references")
            if not isinstance(references, list):
                raise FabricationValidationError("donor_references must be a list")
            store = getattr(request.app.state, "project_store", None)
            if not isinstance(store, ProjectStore):
                raise FabricationValidationError("canonical project store is unavailable")
            lab = getattr(request.app.state, "fabricator_lab_workbench", None)
            fabrication_resources = lab.list_resources() if isinstance(lab, FabricatorLabWorkbench) else []
            graph = _runtime(request).project_resources(
                project_store=store,
                project_id=value.get("project_id"),
                donor_references=references,
                fabrication_resources=fabrication_resources,
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "resource_graph": graph}

    @router.post("/architecture/tradeoffs")
    def compare_fabrication_options(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        try:
            value = _body(body)
            options = value.get("options")
            if not isinstance(options, list):
                raise FabricationValidationError("options must be a list")
            graph = value.get("resource_graph")
            if graph is not None and not isinstance(graph, Mapping):
                raise FabricationValidationError("resource_graph must be an object")
            comparison = _runtime(request).compare_options(
                options=options,
                currency=value.get("currency"),
                as_of=value.get("as_of"),
                require_known_stock=bool(value.get("require_known_stock", False)),
                resource_graph=graph,
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "comparison": comparison}

    return router
