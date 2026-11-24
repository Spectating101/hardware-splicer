"""HTTP surface for fabrication missions.

An agent may open a mission, read it, propose events, ask Hardware Splicer to
run its software-only checks, and read the run files. Accepting a mission
needs a person's operator token. No route records an evaluation.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi import status as http_status
from fastapi.concurrency import run_in_threadpool

from .device_api import require_modeled_execution_access
from .intact_reuse import REPORT_SCHEMA as INTACT_REPORT_SCHEMA, discovery as intact_reuse_discovery
from .mission_delivery import (build_mission_package, inspect_mission_delivery, read_mission_package,
                               read_retained_mission_package, stage_mission_design)
from .mission_executor import run_mission_operation
from .mission_store import (
    MissionConflict,
    MissionError,
    MissionNotFound,
    MissionStateError,
    MissionStore,
    MissionValidationError,
)
from .operator_identity import (
    OperatorRegistryError,
    OperatorTokenInvalid,
    resolve_operator,
)
from .project_store import InvalidProjectId, ProjectNotFound


def _mission_error(exc: Exception) -> HTTPException:
    if isinstance(exc, OperatorTokenInvalid):
        return HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"type": "operator_token_invalid", "message": str(exc)},
        )
    if isinstance(exc, OperatorRegistryError):
        return HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"type": "operator_registry_error", "message": str(exc)},
        )
    if isinstance(exc, (ProjectNotFound, MissionNotFound)):
        return HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"type": "not_found", "message": str(exc)},
        )
    if isinstance(exc, MissionValidationError):
        return HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_request", "message": str(exc)},
        )
    if isinstance(exc, InvalidProjectId):
        return HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_identifier", "message": str(exc)},
        )
    if isinstance(exc, MissionStateError):
        return HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"type": "mission_state", "message": str(exc)},
        )
    if isinstance(exc, MissionConflict):
        return HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"type": "mission_conflict", "message": str(exc)},
        )
    if isinstance(exc, ValueError):
        return HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_request", "message": str(exc)},
        )
    if isinstance(exc, MissionError):
        return HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "mission_error", "message": "internal mission error"},
        )
    return HTTPException(
        status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"type": "mission_error", "message": str(exc)},
    )


def _as_request_object(payload: Any, *, label: str) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise MissionValidationError(f"{label} must be an object")
    return dict(payload)


def _operator_token(x_hs_operator_token: str | None) -> str | None:
    if x_hs_operator_token is not None and x_hs_operator_token != "":
        return x_hs_operator_token
    return None


def _human_operator_required() -> HTTPException:
    return HTTPException(
        status_code=http_status.HTTP_403_FORBIDDEN,
        detail={
            "type": "operator_required",
            "message": "a person's operator token is required",
        },
    )


def _route_author(body_author: Any, token: str | None) -> Any:
    """Who a request is from. An operator token decides it; a body-supplied author is never trusted as a person.

    With a valid token the author is the token's identity and any author in the body is ignored. Without one, a body
    author may name an agent, but not a human: a person is identified only by their operator token.
    """
    identity = resolve_operator(_operator_token(token))
    if identity is not None:
        return {"kind": identity.kind, "id": identity.id}
    if isinstance(body_author, Mapping):
        kind = body_author.get("kind")
        if isinstance(kind, str) and kind.strip() == "human":
            raise _human_operator_required()
    return body_author


def _latest_evaluation(mission: Mapping[str, Any], candidate_id: str) -> Dict[str, Any]:
    for candidate in mission.get("candidates") or []:
        if candidate.get("id") != candidate_id:
            continue
        evaluations = candidate.get("evaluations") or []
        if evaluations:
            return dict(evaluations[-1])
    raise MissionError("evaluation missing after run")


def create_mission_router(mission_store: MissionStore) -> APIRouter:
    router = APIRouter(
        prefix="/v1/projects/{project_id}/missions",
        tags=["fabrication-missions"],
    )

    @router.post("", status_code=http_status.HTTP_201_CREATED)
    def open_project_mission(
        project_id: str,
        request: Dict[str, Any],
        x_hs_operator_token: str | None = Header(default=None, alias="X-HS-Operator-Token"),
    ) -> Dict[str, Any]:
        try:
            payload = _as_request_object(request, label="request")
            mission = mission_store.open_mission(
                project_id,
                intake=payload.get("intake"),
                author=_route_author(payload.get("author"), x_hs_operator_token),
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise _mission_error(exc) from exc
        return {"ok": True, "mission": mission}

    @router.get("")
    def list_project_missions(project_id: str) -> Dict[str, Any]:
        try:
            missions = mission_store.list_missions(project_id)
        except Exception as exc:
            raise _mission_error(exc) from exc
        return {"ok": True, "missions": missions}

    @router.get("/{mission_id}")
    def load_project_mission(project_id: str, mission_id: str) -> Dict[str, Any]:
        try:
            mission = mission_store.get_mission(project_id, mission_id)
        except Exception as exc:
            raise _mission_error(exc) from exc
        return {"ok": True, "mission": mission}

    @router.post("/{mission_id}/accept")
    def accept_project_mission(
        project_id: str,
        mission_id: str,
        x_hs_operator_token: str | None = Header(default=None, alias="X-HS-Operator-Token"),
    ) -> Dict[str, Any]:
        try:
            identity = resolve_operator(_operator_token(x_hs_operator_token))
            if identity is None or identity.kind != "human":
                raise _human_operator_required()
            mission = mission_store.accept_mission(
                project_id,
                mission_id,
                author={"kind": identity.kind, "id": identity.id},
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise _mission_error(exc) from exc
        return {"ok": True, "mission": mission}

    @router.get("/{mission_id}/intact-reuse-spec", summary="Discover a bounded intact-input reuse spec and registered source/donor IDs")
    def read_intact_reuse_spec(project_id: str, mission_id: str) -> Dict[str, Any]:
        try:
            view = mission_store.get_mission(project_id, mission_id)
            snapshot = mission_store.project_store.load_latest_with_recovery(project_id)["snapshot"]
            return intact_reuse_discovery(view, snapshot)
        except Exception as exc:
            raise _mission_error(exc) from exc

    @router.post("/{mission_id}/events", status_code=http_status.HTTP_201_CREATED)
    def propose_project_mission_event(
        project_id: str,
        mission_id: str,
        request: Dict[str, Any],
        x_hs_operator_token: str | None = Header(default=None, alias="X-HS-Operator-Token"),
    ) -> Dict[str, Any]:
        try:
            payload = _as_request_object(request, label="request")
            mission = mission_store.propose(
                project_id,
                mission_id,
                payload.get("event"),
                author=_route_author(payload.get("author"), x_hs_operator_token),
                expected_event_seq=payload.get("expected_event_seq"),
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise _mission_error(exc) from exc
        return {"ok": True, "mission": mission}

    @router.post("/{mission_id}/candidates/{candidate_id}/run")
    async def run_project_mission_operation(
        project_id: str,
        mission_id: str,
        candidate_id: str,
        request: Dict[str, Any],
        http_request: Request,
    ) -> Dict[str, Any]:
        try:
            payload = _as_request_object(request, label="request")
            if payload.get("operation") == "device_application_run":
                # Executes generated host code: same gate as /v1/devices/application/run, before anything is run.
                require_modeled_execution_access(http_request)
            mission = await run_in_threadpool(
                run_mission_operation,
                mission_store,
                project_id,
                mission_id,
                candidate_id=candidate_id,
                operation=payload.get("operation"),
            )
            evaluation = _latest_evaluation(mission, candidate_id)
        except HTTPException:
            raise
        except Exception as exc:
            raise _mission_error(exc) from exc
        response = {"ok": True, "mission": mission, "evaluation": evaluation}
        if evaluation["operation"] == "intact_reuse" and evaluation["result"]["errors"] == 0:
            response["bundle_download_path"] = (
                f"/v1/projects/{project_id}/missions/{mission_id}/{evaluation['artifact']}/bundle"
            )
        return response

    @router.get("/{mission_id}/runs/{name}")
    def read_project_mission_run(
        project_id: str,
        mission_id: str,
        name: str,
    ) -> Dict[str, Any]:
        try:
            run = mission_store.read_run(project_id, mission_id, "runs/" + name)
        except Exception as exc:
            if isinstance(exc, (MissionValidationError, MissionError)) and not isinstance(
                exc, (MissionNotFound, MissionStateError, MissionConflict)
            ):
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail={"type": "not_found", "message": str(exc)},
                ) from exc
            raise _mission_error(exc) from exc
        return {"ok": True, "run": run}

    @router.get("/{mission_id}/runs/{name}/bundle", summary="Download a hash-bound intact-reuse SOFTWARE REVIEW bundle, not a READY build package")
    def download_intact_reuse_bundle(project_id: str, mission_id: str, name: str) -> Response:
        try:
            run = read_project_mission_run(project_id, mission_id, name)["run"]
            if run.get("schema_version") != INTACT_REPORT_SCHEMA or run.get("software_checks_passed") is not True:
                raise MissionNotFound("run has no passing intact-reuse software review bundle")
            digest = run.get("package_sha256")
            data = mission_store.read_package(project_id, mission_id, digest)
            if data is None:
                raise MissionNotFound("recorded software review bundle is missing")
        except HTTPException:
            raise
        except Exception as exc:
            raise _mission_error(exc) from exc
        return Response(content=data, media_type="application/zip", headers={
            "Content-Disposition": f'attachment; filename="intact-reuse-{digest[:16]}.zip"',
            "X-Content-SHA256": digest, "X-HS-Artifact-Scope": "software-review-only",
        })

    @router.post("/{mission_id}/needs/{need_seq}/evidence", status_code=http_status.HTTP_201_CREATED)
    def supply_project_mission_evidence(
        project_id: str,
        mission_id: str,
        need_seq: int,
        request: Dict[str, Any],
        x_hs_operator_token: str | None = Header(default=None, alias="X-HS-Operator-Token"),
    ) -> Dict[str, Any]:
        # A person answers a measurement need. The author comes only from the operator token, never from the body.
        try:
            identity = resolve_operator(_operator_token(x_hs_operator_token))
            if identity is None or identity.kind != "human":
                raise _human_operator_required()
            payload = _as_request_object(request, label="request")
            mission = mission_store.supply_evidence(
                project_id,
                mission_id,
                need_seq,
                envelope=payload.get("envelope"),
                values=payload.get("values"),
                author={"kind": identity.kind, "id": identity.id},
                expected_event_seq=payload.get("expected_event_seq"),
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise _mission_error(exc) from exc
        return {"ok": True, "mission": mission}

    @router.get("/{mission_id}/delivery", summary="Inspect already-retained mission output without generating missing files")
    async def inspect_project_mission_delivery(project_id: str, mission_id: str) -> Dict[str, Any]:
        try:
            delivery = await run_in_threadpool(inspect_mission_delivery, mission_store, project_id, mission_id)
        except Exception as exc:
            raise _mission_error(exc) from exc
        return {"ok": True, "delivery": delivery}

    @router.get("/{mission_id}/delivery/packages/{package_sha256}", summary="Download an already-retained prototype review package; never generate it")
    async def download_retained_project_mission_package(project_id: str, mission_id: str, package_sha256: str) -> Response:
        try:
            data = await run_in_threadpool(read_retained_mission_package, mission_store, project_id, mission_id, package_sha256)
        except Exception as exc:
            raise _mission_error(exc) from exc
        return Response(content=data, media_type="application/zip", headers={
            "Content-Disposition": f'attachment; filename="{mission_id}-retained-package.zip"',
            "X-Content-SHA256": package_sha256, "X-HS-Artifact-Scope": "prototype-review-only",
        })

    @router.post("/{mission_id}/package")
    async def build_project_mission_package(project_id: str, mission_id: str) -> Dict[str, Any]:
        try:
            package = await run_in_threadpool(build_mission_package, mission_store, project_id, mission_id)
        except Exception as exc:
            raise _mission_error(exc) from exc
        return {"ok": True, "package": package}

    @router.get("/{mission_id}/package")
    async def download_project_mission_package(project_id: str, mission_id: str) -> Response:
        try:
            data = await run_in_threadpool(read_mission_package, mission_store, project_id, mission_id)
        except Exception as exc:
            raise _mission_error(exc) from exc
        return Response(content=data, media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{mission_id}-package.zip"'})

    @router.post("/{mission_id}/stage", status_code=http_status.HTTP_201_CREATED)
    async def stage_project_mission_design(
        project_id: str,
        mission_id: str,
        request: Dict[str, Any],
        x_hs_operator_token: str | None = Header(default=None, alias="X-HS-Operator-Token"),
    ) -> Dict[str, Any]:
        # Opens a review of the READY design. No route here decides a review: that stays a person's review decision.
        try:
            payload = _as_request_object(request, label="request")
            staged = await run_in_threadpool(
                stage_mission_design, mission_store, project_id, mission_id,
                author=_route_author(payload.get("author"), x_hs_operator_token),
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise _mission_error(exc) from exc
        return {"ok": True, **staged}

    return router
