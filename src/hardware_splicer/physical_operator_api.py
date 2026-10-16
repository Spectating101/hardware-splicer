"""Canonical HTTP projection of the bounded physical-operator workbench.

The router is always mountable but requires an operator runtime in
``app.state.physical_workbench``.  This keeps machine configuration and private
handles out of OpenAPI while allowing MCP to project the safe canonical routes.
No route registers operators/artifacts, changes endpoints/credentials or mints
a grant directly.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi import status as http_status

from .fabrication_operator import FabricationAuthorityError, FabricationValidationError
from .operator_identity import OperatorRegistryError, OperatorTokenInvalid, resolve_operator
from .physical_workbench import AgentPhysicalWorkbench


def _runtime(request: Request) -> AgentPhysicalWorkbench:
    value = getattr(request.app.state, "physical_workbench", None)
    if not isinstance(value, AgentPhysicalWorkbench):
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"type": "physical_runtime_unavailable", "message": "physical operator runtime is not configured"},
        )
    return value


def _payload(value: Any) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise FabricationValidationError("request must be an object")
    return dict(value)


def _operator_token(value: str | None) -> str | None:
    return value if value else None


def _human(x_hs_operator_token: str | None) -> dict[str, str]:
    try:
        identity = resolve_operator(_operator_token(x_hs_operator_token))
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
    return {"kind": "human", "id": identity.id}


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, FabricationAuthorityError):
        return HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"type": "physical_authority", "message": str(exc)},
        )
    if isinstance(exc, FabricationValidationError):
        return HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_request", "message": str(exc)},
        )
    if isinstance(exc, HTTPException):
        return exc
    return HTTPException(
        status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"type": "physical_operator_error", "message": "internal physical operator error"},
    )


def create_physical_operator_router() -> APIRouter:
    router = APIRouter(prefix="/v1/fabrication", tags=["physical-operators"])

    @router.get("/operators")
    def list_physical_operators(request: Request, kind: str | None = None) -> Dict[str, Any]:
        try:
            kinds = [kind] if kind else None
            values = _runtime(request).list_operators(kinds=kinds)
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "operators": values}

    @router.get("/artifacts")
    def list_physical_artifacts(request: Request, kind: str | None = None) -> Dict[str, Any]:
        try:
            values = _runtime(request).list_artifacts(kind=kind)
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "artifacts": values}

    @router.post("/non-actuating")
    def perform_non_actuating(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        try:
            value = _payload(body)
            receipt = _runtime(request).perform_non_actuating(
                operator_id=value.get("operator_id"),
                project_id=value.get("project_id"),
                mission_id=value.get("mission_id"),
                action=value.get("action"),
                payload=value.get("payload") or {},
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "receipt": receipt}

    @router.post("/approval-requests", status_code=http_status.HTTP_201_CREATED)
    def request_physical_approval(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        try:
            value = _payload(body)
            record = _runtime(request).request_artifact_actuation(
                operator_id=value.get("operator_id"),
                project_id=value.get("project_id"),
                mission_id=value.get("mission_id"),
                action=value.get("action"),
                artifact_id=value.get("artifact_id"),
                bindings=value.get("bindings") or {},
                agent_id=value.get("agent_id"),
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "approval_request": record}

    @router.get("/approval-requests/{request_id}")
    def read_physical_approval(request_id: str, request: Request) -> Dict[str, Any]:
        try:
            record = _runtime(request).approval_status(request_id)
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "approval_request": record}

    @router.post("/approval-requests/{request_id}/approve")
    def approve_physical_request(
        request_id: str,
        request: Request,
        x_hs_operator_token: str | None = Header(default=None, alias="X-HS-Operator-Token"),
    ) -> Dict[str, Any]:
        try:
            author = _human(x_hs_operator_token)
            record = _runtime(request).approvals.approve(request_id, author=author)
        except HTTPException:
            raise
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "approval_request": record}

    @router.post("/approval-requests/{request_id}/reject")
    def reject_physical_request(
        request_id: str,
        request: Request,
        body: Dict[str, Any],
        x_hs_operator_token: str | None = Header(default=None, alias="X-HS-Operator-Token"),
    ) -> Dict[str, Any]:
        try:
            author = _human(x_hs_operator_token)
            value = _payload(body)
            record = _runtime(request).approvals.reject(
                request_id,
                author=author,
                reason=value.get("reason"),
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "approval_request": record}

    @router.post("/approval-requests/{request_id}/execute")
    def execute_approved_physical_request(request_id: str, request: Request) -> Dict[str, Any]:
        try:
            receipt = _runtime(request).execute_approved(request_id)
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "receipt": receipt}

    return router
