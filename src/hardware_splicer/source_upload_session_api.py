"""HTTP surface for bounded resumable engineering source uploads."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from .engineering_source_multipart_api import ingest_multipart_source_bytes
from .machine_project import AuthorityState
from .project_store import (
    CorruptProject,
    InvalidProjectId,
    ProjectNotFound,
    ProjectStore,
    ProjectStoreError,
    RevisionConflict,
)
from .source_upload_session import (
    MAX_SOURCE_UPLOAD_CHUNKS,
    SOURCE_UPLOAD_CHUNK_BYTES,
    SOURCE_UPLOAD_SESSION_SCHEMA,
    SourceUploadSessionConflict,
    SourceUploadSessionCreate,
    SourceUploadSessionError,
    SourceUploadSessionNotFound,
    UploadSessionStatus,
    abandon_source_upload_session,
    assemble_source_upload_session,
    create_source_upload_session,
    expected_chunk_size,
    finalize_source_upload_session_manifest,
    load_source_upload_session,
    store_source_upload_chunk,
)


class SourceUploadSessionApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateSourceUploadSessionRequest(SourceUploadSessionApiModel):
    filename: str = Field(min_length=1, max_length=255)
    total_size_bytes: int = Field(ge=1)
    expected_revision: int = Field(ge=1)
    declared_media_type: str | None = Field(default=None, max_length=255)
    authority_ceiling: AuthorityState = AuthorityState.DECLARED
    expected_content_hash: str | None = Field(default=None, max_length=71)
    captured_at: str | None = Field(default=None, max_length=128)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FinalizeSourceUploadSessionRequest(SourceUploadSessionApiModel):
    expected_revision: int = Field(ge=1)


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, InvalidProjectId):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_project_id", "message": str(exc)},
        )
    if isinstance(exc, (ProjectNotFound, SourceUploadSessionNotFound)):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"type": "project_or_upload_session_not_found", "message": str(exc)},
        )
    if isinstance(exc, (RevisionConflict, SourceUploadSessionConflict)):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": "source_upload_session_conflict", "message": str(exc)},
        )
    if isinstance(exc, (TypeError, ValueError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_source_upload_session", "message": str(exc)},
        )
    if isinstance(exc, CorruptProject):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "corrupt_project", "message": str(exc)},
        )
    if isinstance(exc, (ProjectStoreError, SourceUploadSessionError)):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "source_upload_session_store_error", "message": str(exc)},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"type": "source_upload_session_error", "message": str(exc)},
    )


def _rows(value: Any) -> list[Dict[str, Any]]:
    return [dict(row) for row in value or [] if isinstance(row, Mapping)]


def _upload_record(result: Dict[str, Any], session_id: str) -> Dict[str, Any]:
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
        "transport_encoding": "resumable-raw-chunks",
        "upload_session_id": session_id,
        "automatic_authorization": False,
        "metadata": result["metadata"],
    }


async def _read_exact_chunk(request: Request, expected_size: int) -> bytes:
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > expected_size:
            raise ValueError(
                f"chunk body exceeds expected size of {expected_size} bytes"
            )
    if len(content) != expected_size:
        raise ValueError(
            f"chunk body must contain exactly {expected_size} bytes"
        )
    return bytes(content)


def _registered_result(
    snapshot: Mapping[str, Any],
    *,
    filename: str,
    content_hash: str,
) -> Dict[str, Any] | None:
    uploads = _rows(snapshot.get("engineeringSourceUploads"))
    sources = _rows(snapshot.get("engineeringSources"))
    upload = next(
        (
            row
            for row in uploads
            if row.get("original_filename") == filename
            and row.get("content_hash") == content_hash
        ),
        None,
    )
    if upload is None:
        return None
    source_id = str(upload.get("source_id") or "")
    source = next(
        (row for row in sources if str(row.get("source_id")) == source_id),
        None,
    )
    if source is None:
        return None
    return {
        "schema_version": upload.get("schema_version"),
        "project_id": source.get("metadata", {}).get("project_id"),
        "source_id": source_id,
        "original_filename": filename,
        "content_hash": content_hash,
        "size_bytes": upload.get("size_bytes"),
        "blob_ref": upload.get("blob_ref"),
        "duplicate_blob": True,
        "bytes_retained": True,
        "classification": upload.get("classification") or {},
        "authority_ceiling": source.get("authority_ceiling"),
        "source_descriptor": source,
        "automatic_authorization": False,
        "metadata": upload.get("metadata") or {},
    }


def create_source_upload_session_router(
    project_store: ProjectStore | None = None,
) -> APIRouter:
    store = project_store or ProjectStore()
    router = APIRouter(tags=["source-upload-sessions"])

    @router.get("/v1/engineering/sources/upload-sessions/schema")
    def source_upload_session_schema() -> Dict[str, Any]:
        return {
            "ok": True,
            "schema_version": SOURCE_UPLOAD_SESSION_SCHEMA,
            "chunk_size_bytes": SOURCE_UPLOAD_CHUNK_BYTES,
            "maximum_chunk_count": MAX_SOURCE_UPLOAD_CHUNKS,
            "project_revision_pinned": True,
            "project_mutated_before_finalize": False,
            "resumable": True,
            "automatic_authorization": False,
        }

    @router.post(
        "/v1/projects/{project_id}/source-upload-sessions",
        status_code=status.HTTP_201_CREATED,
    )
    def create_session(
        project_id: str,
        request: CreateSourceUploadSessionRequest,
    ) -> Dict[str, Any]:
        try:
            envelope = store.load_latest_with_recovery(project_id)
            current_revision = int(envelope["revision"])
            if current_revision != request.expected_revision:
                raise RevisionConflict(
                    f"project {project_id!r} is at revision {current_revision}, "
                    f"expected {request.expected_revision}"
                )
            session = create_source_upload_session(
                SourceUploadSessionCreate(
                    project_id=project_id,
                    filename=request.filename,
                    total_size_bytes=request.total_size_bytes,
                    expected_revision=request.expected_revision,
                    declared_media_type=request.declared_media_type,
                    authority_ceiling=request.authority_ceiling,
                    expected_content_hash=request.expected_content_hash,
                    captured_at=request.captured_at,
                    metadata=request.metadata,
                ),
                project_root=store.root,
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {
            "ok": True,
            "project_id": project_id,
            "revision": current_revision,
            "session": session.model_dump(mode="json"),
            "project_mutated": False,
            "authority_unchanged": True,
        }

    @router.get(
        "/v1/projects/{project_id}/source-upload-sessions/{session_id}"
    )
    def load_session(project_id: str, session_id: str) -> Dict[str, Any]:
        try:
            session = load_source_upload_session(
                project_id,
                session_id,
                project_root=store.root,
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {
            "ok": True,
            "session": session.model_dump(mode="json"),
            "complete": session.complete,
            "received_chunk_count": len(session.received_chunks),
        }

    @router.put(
        "/v1/projects/{project_id}/source-upload-sessions/{session_id}/chunks/{chunk_index}"
    )
    async def upload_chunk(
        project_id: str,
        session_id: str,
        chunk_index: int,
        request: Request,
        x_chunk_sha256: str | None = Header(default=None),
    ) -> Dict[str, Any]:
        try:
            session = load_source_upload_session(
                project_id,
                session_id,
                project_root=store.root,
            )
            required_size = expected_chunk_size(session, chunk_index)
            content = await _read_exact_chunk(request, required_size)
            updated, chunk, registered = store_source_upload_chunk(
                project_id,
                session_id,
                chunk_index,
                content,
                expected_content_hash=x_chunk_sha256,
                project_root=store.root,
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {
            "ok": True,
            "registered": registered,
            "session_id": session_id,
            "chunk": chunk.model_dump(mode="json"),
            "received_chunk_count": len(updated.received_chunks),
            "chunk_count": updated.chunk_count,
            "complete": updated.complete,
            "project_mutated": False,
        }

    @router.post(
        "/v1/projects/{project_id}/source-upload-sessions/{session_id}/finalize"
    )
    def finalize_session(
        project_id: str,
        session_id: str,
        request: FinalizeSourceUploadSessionRequest,
    ) -> Dict[str, Any]:
        try:
            existing_session = load_source_upload_session(
                project_id,
                session_id,
                project_root=store.root,
            )
            if existing_session.status == UploadSessionStatus.FINALIZED:
                return {
                    "ok": True,
                    "registered": False,
                    "project_id": project_id,
                    "revision": existing_session.finalized_revision,
                    "session": existing_session.model_dump(mode="json"),
                    "ingestion": existing_session.ingestion,
                    "authority_unchanged": True,
                }
            if request.expected_revision != existing_session.expected_revision:
                raise RevisionConflict(
                    "finalize expected_revision differs from the session's pinned revision"
                )

            session, content, content_hash = assemble_source_upload_session(
                project_id,
                session_id,
                project_root=store.root,
            )
            envelope = store.load_latest_with_recovery(project_id)
            current_revision = int(envelope["revision"])
            snapshot = deepcopy(envelope["snapshot"])

            if current_revision != session.expected_revision:
                recovered = _registered_result(
                    snapshot,
                    filename=session.filename,
                    content_hash=content_hash,
                )
                if recovered is None:
                    raise RevisionConflict(
                        f"project {project_id!r} is at revision {current_revision}, "
                        f"session pinned {session.expected_revision}"
                    )
                finalized = finalize_source_upload_session_manifest(
                    project_id,
                    session_id,
                    revision=current_revision,
                    ingestion=recovered,
                    project_root=store.root,
                )
                return {
                    "ok": True,
                    "registered": False,
                    "recovered_after_commit": True,
                    "project_id": project_id,
                    "revision": current_revision,
                    "session": finalized.model_dump(mode="json"),
                    "ingestion": recovered,
                    "authority_unchanged": True,
                }

            result = ingest_multipart_source_bytes(
                project_id=project_id,
                filename=session.filename,
                content=content,
                declared_media_type=session.declared_media_type,
                authority_ceiling=session.authority_ceiling,
                captured_at=session.captured_at,
                metadata={
                    **session.metadata,
                    "upload_session_id": session_id,
                    "upload_transport": "resumable-raw-chunks",
                },
                project_root=store.root,
            )
            payload = result.model_dump(mode="json")
            uploads = _rows(snapshot.get("engineeringSourceUploads"))
            sources = _rows(snapshot.get("engineeringSources"))
            exact_upload_exists = any(
                row.get("content_hash") == payload["content_hash"]
                and row.get("original_filename") == payload["original_filename"]
                for row in uploads
            )
            source_exists = any(
                row.get("source_id") == payload["source_id"] for row in sources
            )
            if not exact_upload_exists:
                uploads.append(_upload_record(payload, session_id))
            if not source_exists:
                sources.append(dict(payload["source_descriptor"]))
            snapshot["engineeringSourceUploads"] = uploads
            snapshot["engineeringSources"] = sources

            if exact_upload_exists and source_exists:
                saved_revision = current_revision
                registered = False
            else:
                saved = store.save(
                    project_id,
                    snapshot,
                    expected_revision=current_revision,
                    metadata={
                        "source": "source_upload_session_finalize",
                        "source_upload_session_schema": SOURCE_UPLOAD_SESSION_SCHEMA,
                        "upload_session_id": session_id,
                        "registered_source_id": payload["source_id"],
                        "registered_content_hash": payload["content_hash"],
                        "transport_encoding": "resumable-raw-chunks",
                        "server_computed_hash": True,
                        "automatic_authorization": False,
                        "physical_authority_unchanged": True,
                    },
                )
                saved_revision = int(saved["revision"])
                registered = True

            finalized = finalize_source_upload_session_manifest(
                project_id,
                session_id,
                revision=saved_revision,
                ingestion=payload,
                project_root=store.root,
            )
        except Exception as exc:
            raise _error(exc) from exc

        return {
            "ok": True,
            "registered": registered,
            "project_id": project_id,
            "revision": saved_revision,
            "session": finalized.model_dump(mode="json"),
            "ingestion": payload,
            "authority_unchanged": True,
        }

    @router.delete(
        "/v1/projects/{project_id}/source-upload-sessions/{session_id}"
    )
    def abandon_session(project_id: str, session_id: str) -> Dict[str, Any]:
        try:
            session = abandon_source_upload_session(
                project_id,
                session_id,
                project_root=store.root,
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {
            "ok": True,
            "abandoned": True,
            "session": session.model_dump(mode="json"),
            "project_mutated": False,
        }

    return router
