"""Multipart transport for bounded project engineering source ingestion."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Mapping

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from .engineering_source_ingestion import (
    ENGINEERING_SOURCE_INGESTION_SCHEMA,
    MAX_ENGINEERING_SOURCE_BYTES,
    MAX_SOURCE_FILENAME_CHARACTERS,
    EngineeringSourceIngestionResult,
    _write_content_addressed_blob,
    classify_engineering_source,
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


ENGINEERING_SOURCE_MULTIPART_SCHEMA = (
    "hardware_splicer.engineering_source_multipart.v1"
)
UPLOAD_READ_CHUNK_BYTES = 1024 * 1024


def _error(exc: Exception) -> HTTPException:
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
            detail={
                "type": "engineering_source_multipart_revision_conflict",
                "message": str(exc),
            },
        )
    if isinstance(exc, (TypeError, ValueError, json.JSONDecodeError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "type": "invalid_engineering_source_multipart",
                "message": str(exc),
            },
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
        detail={"type": "engineering_source_multipart_error", "message": str(exc)},
    )


def _rows(value: Any) -> list[Dict[str, Any]]:
    return [dict(row) for row in value or [] if isinstance(row, Mapping)]


def _authority(value: str) -> AuthorityState:
    try:
        authority = AuthorityState(value.strip().lower())
    except ValueError as exc:
        raise ValueError(f"unsupported source authority: {value!r}") from exc
    if authority not in {
        AuthorityState.UNKNOWN,
        AuthorityState.PROPOSED,
        AuthorityState.DECLARED,
    }:
        raise ValueError(
            "uploaded project files cannot enter above declared authority"
        )
    return authority


def _filename(value: str | None) -> str:
    resolved = str(value or "upload.bin").strip()
    if not resolved:
        raise ValueError("filename must not be blank")
    if len(resolved) > MAX_SOURCE_FILENAME_CHARACTERS:
        raise ValueError(
            f"filename exceeds {MAX_SOURCE_FILENAME_CHARACTERS} characters"
        )
    if "\x00" in resolved:
        raise ValueError("filename must not contain NUL")
    return resolved


def _metadata(value: str) -> Dict[str, Any]:
    if not value.strip():
        return {}
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("metadata_json must be a JSON object")
    return parsed


async def _read_bounded_upload(upload: UploadFile) -> bytes:
    content = bytearray()
    try:
        while True:
            chunk = await upload.read(UPLOAD_READ_CHUNK_BYTES)
            if not chunk:
                break
            content.extend(chunk)
            if len(content) > MAX_ENGINEERING_SOURCE_BYTES:
                raise ValueError(
                    "multipart engineering source exceeds "
                    f"{MAX_ENGINEERING_SOURCE_BYTES} bytes"
                )
    finally:
        await upload.close()
    return bytes(content)


def ingest_multipart_source_bytes(
    *,
    project_id: str,
    filename: str,
    content: bytes,
    declared_media_type: str | None,
    authority_ceiling: AuthorityState,
    captured_at: str | None,
    metadata: Mapping[str, Any],
    project_root: str | Path,
) -> EngineeringSourceIngestionResult:
    """Hash, classify and store bytes received through multipart transport."""

    if len(content) > MAX_ENGINEERING_SOURCE_BYTES:
        raise ValueError(
            f"engineering source exceeds {MAX_ENGINEERING_SOURCE_BYTES} bytes"
        )
    digest_hex = hashlib.sha256(content).hexdigest()
    content_hash = f"sha256:{digest_hex}"
    classification = classify_engineering_source(
        filename,
        content,
        declared_media_type=declared_media_type,
    )
    blob_ref, duplicate = _write_content_addressed_blob(
        Path(project_root),
        project_id,
        digest_hex,
        content,
    )
    source_id = f"upload-{digest_hex[:20]}"
    source_descriptor: Dict[str, Any] = {
        "source_id": source_id,
        "source_type": classification.source_type,
        "uri": f"hs-project://{project_id}/{blob_ref}",
        "revision": content_hash,
        "content_hash": content_hash,
        "authority_ceiling": authority_ceiling.value,
        "metadata": {
            **dict(metadata),
            "original_filename": filename,
            "captured_at": captured_at,
            "size_bytes": len(content),
            "media_type": classification.media_type,
            "ingestion_schema": ENGINEERING_SOURCE_INGESTION_SCHEMA,
            "multipart_schema": ENGINEERING_SOURCE_MULTIPART_SCHEMA,
            "source_kind": classification.kind.value,
            "parser_disposition": classification.parser_disposition.value,
            "parser_route": classification.parser_route,
            "structured_format": classification.structured_format,
            "blob_ref": blob_ref,
            "server_computed_hash": True,
            "transport_encoding": "multipart/form-data",
            "bytes_retained": True,
            "automatic_authorization": False,
            "limitations": classification.limitations,
        },
    }
    return EngineeringSourceIngestionResult(
        project_id=project_id,
        source_id=source_id,
        original_filename=filename,
        content_hash=content_hash,
        size_bytes=len(content),
        blob_ref=blob_ref,
        duplicate_blob=duplicate,
        bytes_retained=True,
        classification=classification,
        authority_ceiling=authority_ceiling,
        source_descriptor=source_descriptor,
        automatic_authorization=False,
        metadata={
            "server_computed_hash": True,
            "content_addressed_storage": True,
            "transport_encoding": "multipart/form-data",
            "raw_bytes_in_response": False,
            "fabrication_authorized": False,
            "flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        },
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
        "transport_encoding": "multipart/form-data",
        "automatic_authorization": False,
        "metadata": result["metadata"],
    }


def create_engineering_source_multipart_router(
    project_store: ProjectStore | None = None,
) -> APIRouter:
    store = project_store or ProjectStore()
    router = APIRouter(tags=["engineering-source-multipart"])

    @router.get("/v1/engineering/sources/multipart/schema")
    def multipart_schema() -> Dict[str, Any]:
        return {
            "ok": True,
            "schema_version": ENGINEERING_SOURCE_MULTIPART_SCHEMA,
            "maximum_file_bytes": MAX_ENGINEERING_SOURCE_BYTES,
            "read_chunk_bytes": UPLOAD_READ_CHUNK_BYTES,
            "transport": "multipart/form-data",
            "one_file_per_request": True,
            "resumable": False,
            "automatic_authorization": False,
        }

    @router.post(
        "/v1/projects/{project_id}/sources/ingest-file",
        status_code=status.HTTP_201_CREATED,
    )
    async def ingest_project_source_file(
        project_id: str,
        file: UploadFile = File(...),
        expected_revision: int = Form(..., ge=1),
        authority_ceiling: str = Form("declared"),
        captured_at: str = Form(""),
        metadata_json: str = Form("{}"),
    ) -> Dict[str, Any]:
        try:
            envelope = store.load_latest_with_recovery(project_id)
            current_revision = int(envelope["revision"])
            if current_revision != expected_revision:
                raise RevisionConflict(
                    f"project {project_id!r} is at revision {current_revision}, "
                    f"expected {expected_revision}"
                )
            resolved_filename = _filename(file.filename)
            resolved_authority = _authority(authority_ceiling)
            resolved_metadata = _metadata(metadata_json)
            content = await _read_bounded_upload(file)
            result = ingest_multipart_source_bytes(
                project_id=project_id,
                filename=resolved_filename,
                content=content,
                declared_media_type=file.content_type,
                authority_ceiling=resolved_authority,
                captured_at=captured_at.strip() or None,
                metadata=resolved_metadata,
                project_root=store.root,
            )
            payload = result.model_dump(mode="json")
            snapshot = deepcopy(envelope["snapshot"])
            upload_records = _rows(snapshot.get("engineeringSourceUploads"))
            source_descriptors = _rows(snapshot.get("engineeringSources"))

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
                    "transport": "multipart/form-data",
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
                    "source": "engineering_source_multipart",
                    "engineering_source_multipart_schema": (
                        ENGINEERING_SOURCE_MULTIPART_SCHEMA
                    ),
                    "registered_source_id": payload["source_id"],
                    "registered_content_hash": payload["content_hash"],
                    "transport_encoding": "multipart/form-data",
                    "server_computed_hash": True,
                    "bytes_retained": True,
                    "automatic_authorization": False,
                    "physical_authority_unchanged": True,
                },
            )
        except Exception as exc:
            raise _error(exc) from exc

        return {
            "ok": True,
            "registered": True,
            "project_id": project_id,
            "revision": saved["revision"],
            "saved_at": saved["saved_at"],
            "ingestion": payload,
            "transport": "multipart/form-data",
            "authority_unchanged": True,
        }

    return router
