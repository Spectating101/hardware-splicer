"""Project-scoped API for source storage audit and explicit cleanup."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, status

from .project_store import (
    CorruptProject,
    InvalidProjectId,
    ProjectNotFound,
    ProjectStore,
    ProjectStoreError,
)
from .source_storage_operations import (
    SOURCE_STORAGE_OPERATIONS_SCHEMA,
    SourceStorageCleanupRequest,
    audit_project_source_storage,
    cleanup_project_source_storage,
)


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, InvalidProjectId):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_project_id", "message": str(exc)},
        )
    if isinstance(exc, (ProjectNotFound, FileNotFoundError)):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"type": "project_not_found", "message": str(exc)},
        )
    if isinstance(exc, (TypeError, ValueError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_source_storage_operation", "message": str(exc)},
        )
    if isinstance(exc, CorruptProject):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "corrupt_project", "message": str(exc)},
        )
    if isinstance(exc, ProjectStoreError):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "project_store_error", "message": str(exc)},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"type": "source_storage_operation_error", "message": str(exc)},
    )


def create_source_storage_operations_router(
    project_store: ProjectStore | None = None,
) -> APIRouter:
    store = project_store or ProjectStore()
    router = APIRouter(tags=["source-storage-operations"])

    @router.get("/v1/engineering/sources/storage/schema")
    def storage_operations_schema() -> Dict[str, Any]:
        return {
            "ok": True,
            "schema_version": SOURCE_STORAGE_OPERATIONS_SCHEMA,
            "dry_run_default": True,
            "typed_project_confirmation_required": True,
            "referenced_blob_deletion": False,
            "project_revision_mutated": False,
            "automatic_deletion": False,
        }

    @router.get("/v1/projects/{project_id}/source-storage/audit")
    def audit_storage(
        project_id: str,
        revision: int | None = Query(default=None, ge=1),
    ) -> Dict[str, Any]:
        try:
            envelope = (
                store.load(project_id, revision=revision)
                if revision is not None
                else store.load_latest_with_recovery(project_id)
            )
            report = audit_project_source_storage(
                project_id,
                envelope["snapshot"],
                project_root=store.root,
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {
            "ok": True,
            "project_id": project_id,
            "project_revision": envelope["revision"],
            "audit": report.model_dump(mode="json"),
        }

    @router.post("/v1/projects/{project_id}/source-storage/cleanup")
    def cleanup_storage(
        project_id: str,
        request: SourceStorageCleanupRequest,
    ) -> Dict[str, Any]:
        try:
            envelope = store.load_latest_with_recovery(project_id)
            result = cleanup_project_source_storage(
                project_id,
                envelope["snapshot"],
                request,
                project_root=store.root,
            )
            refreshed = audit_project_source_storage(
                project_id,
                envelope["snapshot"],
                project_root=store.root,
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {
            "ok": True,
            "project_id": project_id,
            "project_revision": envelope["revision"],
            "cleanup": result.model_dump(mode="json"),
            "audit": refreshed.model_dump(mode="json"),
            "project_revision_mutated": False,
        }

    return router
