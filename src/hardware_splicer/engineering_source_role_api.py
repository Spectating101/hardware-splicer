"""Revisioned correction of registered source roles without authority elevation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .engineering_source_graph import SourceType
from .machine_project import AuthorityState
from .project_store import (
    CorruptProject,
    InvalidProjectId,
    ProjectNotFound,
    ProjectStore,
    ProjectStoreError,
    RevisionConflict,
)


class SourceRoleModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceRoleCorrectionRequest(SourceRoleModel):
    expected_revision: int = Field(ge=1)
    source_type: SourceType | None = None
    authority_ceiling: AuthorityState | None = None
    note: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def require_change(self) -> "SourceRoleCorrectionRequest":
        if self.source_type is None and self.authority_ceiling is None:
            raise ValueError("source_type or authority_ceiling is required")
        return self


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, InvalidProjectId):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_project_id", "message": str(exc)},
        )
    if isinstance(exc, ProjectNotFound):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"type": "project_or_source_not_found", "message": str(exc)},
        )
    if isinstance(exc, RevisionConflict):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": "source_role_revision_conflict", "message": str(exc)},
        )
    if isinstance(exc, CorruptProject):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "corrupt_project", "message": str(exc)},
        )
    if isinstance(exc, (TypeError, ValueError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_source_role_correction", "message": str(exc)},
        )
    if isinstance(exc, ProjectStoreError):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "project_store_error", "message": str(exc)},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"type": "source_role_correction_error", "message": str(exc)},
    )


def _rows(value: Any) -> list[Dict[str, Any]]:
    return [dict(row) for row in value or [] if isinstance(row, Mapping)]


def _authority(value: Any) -> AuthorityState:
    try:
        return AuthorityState(str(value or AuthorityState.DECLARED.value).lower())
    except ValueError as exc:
        raise ValueError(f"unsupported source authority: {value!r}") from exc


def _authority_rank(value: AuthorityState) -> int:
    return {
        AuthorityState.UNKNOWN: 0,
        AuthorityState.PROPOSED: 1,
        AuthorityState.DECLARED: 2,
        AuthorityState.OBSERVED: 3,
        AuthorityState.MEASURED: 4,
        AuthorityState.VERIFIED: 5,
        AuthorityState.AUTHORIZED: 6,
    }[value]


def create_engineering_source_role_router(
    project_store: ProjectStore | None = None,
) -> APIRouter:
    store = project_store or ProjectStore()
    router = APIRouter(tags=["engineering-source-role"])

    @router.patch("/v1/projects/{project_id}/sources/{source_id}/role")
    def correct_source_role(
        project_id: str,
        source_id: str,
        request: SourceRoleCorrectionRequest,
    ) -> Dict[str, Any]:
        try:
            envelope = store.load_latest_with_recovery(project_id)
            current_revision = int(envelope["revision"])
            if current_revision != request.expected_revision:
                raise RevisionConflict(
                    f"project {project_id!r} is at revision {current_revision}, "
                    f"expected {request.expected_revision}"
                )
            snapshot = deepcopy(envelope["snapshot"])
            sources = _rows(snapshot.get("engineeringSources"))
            index = next(
                (
                    row_index
                    for row_index, row in enumerate(sources)
                    if str(row.get("source_id")) == source_id
                ),
                None,
            )
            if index is None:
                raise ProjectNotFound(f"{project_id}:{source_id}")
            current = dict(sources[index])
            current_authority = _authority(current.get("authority_ceiling"))
            next_authority = request.authority_ceiling or current_authority
            if _authority_rank(next_authority) > _authority_rank(current_authority):
                raise ValueError(
                    "source role correction may preserve or reduce authority, never elevate it"
                )
            if _authority_rank(next_authority) > _authority_rank(AuthorityState.DECLARED):
                raise ValueError("uploaded project sources cannot exceed declared authority")

            immutable_before = {
                key: current.get(key)
                for key in ("source_id", "uri", "revision", "content_hash")
            }
            previous_source_type = str(current.get("source_type") or "other")
            metadata = dict(current.get("metadata") or {})
            history = _rows(metadata.get("source_role_history"))
            history.append(
                {
                    "previous_source_type": previous_source_type,
                    "next_source_type": (
                        request.source_type.value
                        if request.source_type is not None
                        else previous_source_type
                    ),
                    "previous_authority_ceiling": current_authority.value,
                    "next_authority_ceiling": next_authority.value,
                    "note": request.note,
                    "automatic_authorization": False,
                }
            )
            metadata["source_role_history"] = history
            metadata["source_role_user_corrected"] = True
            metadata["automatic_authorization"] = False
            updated = {
                **current,
                "source_type": (
                    request.source_type.value
                    if request.source_type is not None
                    else previous_source_type
                ),
                "authority_ceiling": next_authority.value,
                "metadata": metadata,
            }
            immutable_after = {
                key: updated.get(key)
                for key in ("source_id", "uri", "revision", "content_hash")
            }
            if immutable_after != immutable_before:
                raise ValueError("source role correction changed immutable source identity")
            sources[index] = updated
            snapshot["engineeringSources"] = sources

            uploads = _rows(snapshot.get("engineeringSourceUploads"))
            for row in uploads:
                if str(row.get("source_id")) != source_id:
                    continue
                row["authority_ceiling"] = next_authority.value
                classification = row.get("classification")
                if isinstance(classification, dict) and request.source_type is not None:
                    classification["source_type"] = request.source_type.value
            snapshot["engineeringSourceUploads"] = uploads

            saved = store.save(
                project_id,
                snapshot,
                expected_revision=current_revision,
                metadata={
                    "source": "engineering_source_role_correction",
                    "corrected_source_id": source_id,
                    "previous_source_type": previous_source_type,
                    "next_source_type": updated["source_type"],
                    "previous_authority_ceiling": current_authority.value,
                    "next_authority_ceiling": next_authority.value,
                    "immutable_identity_preserved": True,
                    "automatic_authorization": False,
                    "physical_authority_unchanged": True,
                },
            )
        except Exception as exc:
            raise _error(exc) from exc

        return {
            "ok": True,
            "project_id": project_id,
            "revision": saved["revision"],
            "saved_at": saved["saved_at"],
            "source": updated,
            "authority_elevated": False,
            "immutable_identity_preserved": True,
        }

    return router
