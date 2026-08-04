"""Project-scoped API for bounded engineering source ingestion."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from .engineering_source_ingestion import (
    ENGINEERING_SOURCE_INGESTION_SCHEMA,
    MAX_ENGINEERING_SOURCE_BASE64_CHARACTERS,
    EngineeringSourceIngestionRequest,
    ingest_engineering_source,
)
from .machine_project import AuthorityState
from .project_store import (
    CorruptProject,
    InvalidProjectId,
    ProjectNotFound,
    ProjectStore,
    ProjectStoreError,
    RevisionConflict,
)


class EngineeringSourceApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EngineeringSourceUploadRequest(EngineeringSourceApiModel):
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(
        min_length=1,
        max_length=MAX_ENGINEERING_SOURCE_BASE64_CHARACTERS,
    )
    declared_media_type: str | None = Field(default=None, max_length=255)
    authority_ceiling: AuthorityState = AuthorityState.DECLARED
    captured_at: str | None = Field(default=None, max_length=128)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    expected_revision: int = Field(ge=1)


def _source_error(exc: Exception) -> HTTPException:
    if isinstance(exc, InvalidProjectId):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_project_id", "message": str(exc)},
        )
    if isinstance(exc, ProjectNotFound):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"type": "project_not_found", "message": str(exc)},
        )
    if isinstance(exc, RevisionConflict):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": "engineering_source_revision_conflict", "message": str(exc)},
        )
    if isinstance(exc, CorruptProject):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "corrupt_project", "message": str(exc)},
        )
    if isinstance(exc, (ValueError, TypeError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_engineering_source", "message": str(exc)},
        )
    if isinstance(exc, ProjectStoreError):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "project_store_error", "message": str(exc)},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"type": "engineering_source_ingestion_error", "message": str(exc)},
    )


def _upload_record(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": result["schema_version"],
        "source_id": result["source_id"],
        "original_filename": result["original_filename"],
        "content_hash": result["content_hash"],
        "size_bytes": result["size_bytes"],
        "blob_ref": result["blob_ref"],
        "duplicate_blob": result["duplicate_blob"],
        "bytes_retained": result["bytes_retained"],
        "classification": result["classification"],
        "authority_ceiling": result["authority_ceiling"],
        "automatic_authorization": False,
        "metadata": result["metadata"],
    }


def create_engineering_source_ingestion_router(
    project_store: ProjectStore | None = None,
) -> APIRouter:
    store = project_store or ProjectStore()
    router = APIRouter(tags=["engineering-source-ingestion"])

    @router.get("/v1/engineering/sources/ingestion/schema")
    def engineering_source_ingestion_schema() -> Dict[str, Any]:
        return {
            "ok": True,
            "schema_version": ENGINEERING_SOURCE_INGESTION_SCHEMA,
            "request_schema": EngineeringSourceUploadRequest.model_json_schema(),
            "bytes_retained": True,
            "automatic_authorization": False,
            "archive_extraction": False,
        }

    @router.post(
        "/v1/projects/{project_id}/sources/ingest",
        status_code=status.HTTP_201_CREATED,
    )
    def ingest_project_source(
        project_id: str,
        request: EngineeringSourceUploadRequest,
    ) -> Dict[str, Any]:
        try:
            envelope = store.load_latest_with_recovery(project_id)
            current_revision = int(envelope["revision"])
            if current_revision != request.expected_revision:
                raise RevisionConflict(
                    f"project {project_id!r} is at revision {current_revision}, "
                    f"expected {request.expected_revision}"
                )

            result = ingest_engineering_source(
                EngineeringSourceIngestionRequest(
                    project_id=project_id,
                    filename=request.filename,
                    content_base64=request.content_base64,
                    declared_media_type=request.declared_media_type,
                    authority_ceiling=request.authority_ceiling,
                    captured_at=request.captured_at,
                    metadata=request.metadata,
                ),
                project_root=store.root,
            )
            payload = result.model_dump(mode="json")
            snapshot = deepcopy(envelope["snapshot"])
            upload_records = [
                dict(row)
                for row in snapshot.get("engineeringSourceUploads") or []
                if isinstance(row, dict)
            ]
            source_descriptors = [
                dict(row)
                for row in snapshot.get("engineeringSources") or []
                if isinstance(row, dict)
            ]

            exact_upload_exists = any(
                row.get("content_hash") == payload["content_hash"]
                and row.get("original_filename") == payload["original_filename"]
                for row in upload_records
            )
            source_exists = any(
                row.get("source_id") == payload["source_id"]
                for row in source_descriptors
            )

            if exact_upload_exists and source_exists:
                return {
                    "ok": True,
                    "registered": False,
                    "project_id": project_id,
                    "revision": current_revision,
                    "ingestion": payload,
                    "authority_unchanged": True,
                }

            if not exact_upload_exists:
                upload_records.append(_upload_record(payload))
            if not source_exists:
                source_descriptors.append(dict(payload["source_descriptor"]))

            snapshot["engineeringSourceUploads"] = upload_records
            snapshot["engineeringSources"] = source_descriptors
            saved = store.save(
                project_id,
                snapshot,
                expected_revision=current_revision,
                metadata={
                    "source": "engineering_source_ingestion",
                    "engineering_source_ingestion_schema": ENGINEERING_SOURCE_INGESTION_SCHEMA,
                    "registered_source_id": payload["source_id"],
                    "registered_content_hash": payload["content_hash"],
                    "server_computed_hash": True,
                    "bytes_retained": True,
                    "automatic_authorization": False,
                    "physical_authority_unchanged": True,
                },
            )
        except Exception as exc:
            raise _source_error(exc) from exc

        return {
            "ok": True,
            "registered": True,
            "project_id": project_id,
            "revision": saved["revision"],
            "saved_at": saved["saved_at"],
            "ingestion": payload,
            "authority_unchanged": True,
        }

    return router
