"""HTTP surface for candidate proposals.

An edit is never a write to a revision. The only durable writes are the
candidate directory, the candidate record, and a staged review opened through
the existing review store.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping

from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi import status as http_status

from .kicad_edit import KicadEditError
from .operator_identity import OperatorRegistryError, OperatorTokenInvalid, resolve_operator
from .project_api import _project_error
from .project_candidates import (
    MAX_REQUEST_BYTES,
    ArtifactNotRetained,
    ArtifactTooLarge,
    CandidateIntegrityError,
    CandidateNotFound,
    CandidateValidationError,
    InvalidEdit,
    NoEffectiveChange,
    RequestTooLarge,
    TooManyCandidates,
    list_candidates,
    load_candidate,
    propose_candidate,
    read_candidate_file,
)
from .project_review_store import ProjectReviewStore
from .project_store import ProjectStore


def _operator_token(x_hs_operator_token: str | None) -> str | None:
    if x_hs_operator_token is not None and x_hs_operator_token != "":
        return x_hs_operator_token
    return None


def _candidate_error(exc: Exception) -> HTTPException:
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
    if isinstance(exc, RequestTooLarge):
        return HTTPException(
            status_code=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"type": "request_too_large", "message": str(exc)},
        )
    if isinstance(exc, ArtifactNotRetained):
        return HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"type": "artifact_not_retained", "message": str(exc)},
        )
    if isinstance(exc, ArtifactTooLarge):
        return HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "artifact_too_large", "message": str(exc)},
        )
    if isinstance(exc, (InvalidEdit, KicadEditError)):
        return HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_edit", "message": str(exc)},
        )
    if isinstance(exc, NoEffectiveChange):
        return HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "no_effective_change", "message": str(exc)},
        )
    if isinstance(exc, TooManyCandidates):
        return HTTPException(
            status_code=http_status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"type": "too_many_candidates", "message": str(exc)},
        )
    if isinstance(exc, CandidateNotFound):
        return HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"type": "not_found", "message": str(exc)},
        )
    if isinstance(exc, CandidateIntegrityError):
        return HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "integrity_error", "message": str(exc)},
        )
    if isinstance(exc, CandidateValidationError):
        return HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_request", "message": str(exc)},
        )
    return _project_error(exc)


async def _read_capped_json(http_request: Request) -> Dict[str, Any]:
    header = http_request.headers.get("content-length")
    if header is not None:
        try:
            declared = int(header)
        except ValueError as exc:
            raise CandidateValidationError("request must be an object") from exc
        if declared > MAX_REQUEST_BYTES:
            raise RequestTooLarge("request body exceeds 256 KiB")
    chunks = bytearray()
    async for chunk in http_request.stream():
        chunks.extend(chunk)
        if len(chunks) > MAX_REQUEST_BYTES:
            raise RequestTooLarge("request body exceeds 256 KiB")
    if not chunks:
        raise CandidateValidationError("request must be an object")
    try:
        payload = json.loads(bytes(chunks).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CandidateValidationError("request must be an object") from exc
    if not isinstance(payload, Mapping):
        raise CandidateValidationError("request must be an object")
    return dict(payload)


def create_project_candidates_router(
    store: ProjectStore,
    review_store: ProjectReviewStore | None = None,
) -> APIRouter:
    reviews = review_store or ProjectReviewStore(store)
    router = APIRouter(prefix="/v1/projects", tags=["projects", "candidates"])

    @router.post("/{project_id}/candidates", status_code=http_status.HTTP_201_CREATED)
    async def create_project_candidate(
        project_id: str,
        http_request: Request,
        x_hs_operator_token: str | None = Header(default=None, alias="X-HS-Operator-Token"),
    ) -> Dict[str, Any]:
        try:
            payload = await _read_capped_json(http_request)
            identity = resolve_operator(_operator_token(x_hs_operator_token))
            if identity is not None:
                created_by = identity.id
                verified = True
            else:
                created_by = payload.get("author")
                verified = False
            result = propose_candidate(
                store,
                project_id,
                kind=payload.get("kind"),
                ops=payload.get("ops"),
                author=payload.get("author"),
                note=payload.get("note", ""),
                base_revision=payload.get("base_revision"),
                created_by=created_by,
                verified=verified,
                review_store=reviews,
            )
        except Exception as exc:
            raise _candidate_error(exc) from exc
        return {"ok": True, "candidate": result["candidate"], "review": result["review"]}

    @router.get("/{project_id}/candidates")
    def list_project_candidates(project_id: str) -> Dict[str, Any]:
        try:
            candidates = list_candidates(store, project_id)
        except Exception as exc:
            raise _candidate_error(exc) from exc
        return {"ok": True, "project_id": project_id, "candidates": candidates}

    @router.get("/{project_id}/candidates/{candidate_id}")
    def load_project_candidate(project_id: str, candidate_id: str) -> Dict[str, Any]:
        try:
            candidate = load_candidate(store, project_id, candidate_id)
        except Exception as exc:
            raise _candidate_error(exc) from exc
        return {"ok": True, "candidate": candidate}

    @router.get("/{project_id}/candidates/{candidate_id}/files/{kind}")
    def load_project_candidate_file(project_id: str, candidate_id: str, kind: str) -> Response:
        try:
            data, digest = read_candidate_file(store, project_id, candidate_id, kind)
        except Exception as exc:
            raise _candidate_error(exc) from exc
        etag = digest if digest.startswith("sha256:") else f"sha256:{digest}"
        return Response(
            content=data,
            media_type="text/plain",
            headers={"ETag": f'"{etag}"'},
        )

    return router
