"""Project-scoped API for bounded parser execution on registered source blobs."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Dict, Mapping

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from .project_store import (
    CorruptProject,
    InvalidProjectId,
    ProjectNotFound,
    ProjectStore,
    ProjectStoreError,
    RevisionConflict,
)
from .stored_source_parser import (
    MAX_PERSISTED_PARSER_OUTPUT_BYTES,
    STORED_SOURCE_PARSER_IMPLEMENTATION,
    STORED_SOURCE_PARSER_SCHEMA,
    execute_stored_source_parser,
)


class StoredSourceParserApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExecuteStoredSourceParserRequest(StoredSourceParserApiModel):
    expected_revision: int = Field(ge=1)


def _parser_error(exc: Exception) -> HTTPException:
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
            detail={
                "type": "stored_source_parser_revision_conflict",
                "message": str(exc),
            },
        )
    if isinstance(exc, CorruptProject):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "corrupt_project", "message": str(exc)},
        )
    if isinstance(exc, (TypeError, ValueError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "type": "invalid_stored_source_parser_request",
                "message": str(exc),
            },
        )
    if isinstance(exc, ProjectStoreError):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "project_store_error", "message": str(exc)},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"type": "stored_source_parser_error", "message": str(exc)},
    )


def _rows(value: Any) -> list[Dict[str, Any]]:
    return [dict(row) for row in value or [] if isinstance(row, Mapping)]


def _run_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("source_id") or ""),
        str(row.get("content_hash") or ""),
        str(row.get("schema_version") or ""),
        str(row.get("parser_identity") or ""),
    )


def _source_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("source_id") or ""),
        str(row.get("content_hash") or row.get("revision") or ""),
    )


def _serialized_size(payload: Mapping[str, Any]) -> int:
    return len(
        json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def create_stored_source_parser_router(
    project_store: ProjectStore | None = None,
) -> APIRouter:
    store = project_store or ProjectStore()
    router = APIRouter(tags=["stored-source-parser"])

    @router.get("/v1/engineering/sources/parser/schema")
    def stored_source_parser_schema() -> Dict[str, Any]:
        return {
            "ok": True,
            "schema_version": STORED_SOURCE_PARSER_SCHEMA,
            "parser_identity": STORED_SOURCE_PARSER_IMPLEMENTATION,
            "maximum_persisted_output_bytes": MAX_PERSISTED_PARSER_OUTPUT_BYTES,
            "supported_routes": [
                "robot_model_import",
                "engineering_source_descriptor",
            ],
            "explicitly_unavailable_routes": ["step_geometry"],
            "raw_bytes_returned": False,
            "automatic_authorization": False,
        }

    @router.post(
        "/v1/projects/{project_id}/sources/{source_id}/parse",
        status_code=status.HTTP_201_CREATED,
    )
    def parse_project_source(
        project_id: str,
        source_id: str,
        request: ExecuteStoredSourceParserRequest,
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
            source = next(
                (
                    row
                    for row in sources
                    if str(row.get("source_id")) == source_id
                ),
                None,
            )
            if source is None:
                raise ProjectNotFound(f"{project_id}:{source_id}")

            result = execute_stored_source_parser(
                project_id,
                source,
                project_root=store.root,
            )
            payload = result.model_dump(mode="json")
            output_size = _serialized_size(payload)
            if output_size > MAX_PERSISTED_PARSER_OUTPUT_BYTES:
                raise ValueError(
                    "stored parser output exceeds the maximum persisted output size"
                )

            runs = _rows(snapshot.get("engineeringSourceParserRuns"))
            key = _run_key(payload)
            existing = next(
                (row for row in runs if _run_key(row) == key),
                None,
            )
            if existing is not None:
                return {
                    "ok": True,
                    "registered": False,
                    "project_id": project_id,
                    "revision": current_revision,
                    "parser_run": existing,
                    "authority_unchanged": True,
                }

            runs.append(payload)
            snapshot["engineeringSourceParserRuns"] = runs

            derived = _rows(snapshot.get("engineeringParsedSources"))
            seen = {_source_key(row) for row in derived}
            for row in result.derived_sources:
                if _source_key(row) not in seen:
                    derived.append(dict(row))
                    seen.add(_source_key(row))
            snapshot["engineeringParsedSources"] = derived

            updated_sources: list[Dict[str, Any]] = []
            for row in sources:
                if str(row.get("source_id")) != source_id:
                    updated_sources.append(row)
                    continue
                metadata = dict(row.get("metadata") or {})
                metadata["latest_parser_run"] = {
                    "schema_version": STORED_SOURCE_PARSER_SCHEMA,
                    "parser_identity": STORED_SOURCE_PARSER_IMPLEMENTATION,
                    "status": result.status.value,
                    "parser_route": result.parser_route,
                    "content_hash": result.content_hash,
                    "persisted_output_size_bytes": output_size,
                    "parsed_output_available": bool(result.parsed_output),
                    "automatic_authorization": False,
                }
                updated_sources.append({**row, "metadata": metadata})
            snapshot["engineeringSources"] = updated_sources

            saved = store.save(
                project_id,
                snapshot,
                expected_revision=current_revision,
                metadata={
                    "source": "stored_source_parser",
                    "stored_source_parser_schema": STORED_SOURCE_PARSER_SCHEMA,
                    "stored_source_parser_identity": (
                        STORED_SOURCE_PARSER_IMPLEMENTATION
                    ),
                    "parsed_source_id": source_id,
                    "parsed_content_hash": result.content_hash,
                    "parser_status": result.status.value,
                    "persisted_output_size_bytes": output_size,
                    "derived_source_count": len(result.derived_sources),
                    "raw_bytes_persisted_in_snapshot": False,
                    "automatic_authorization": False,
                    "physical_authority_unchanged": True,
                },
            )
        except Exception as exc:
            raise _parser_error(exc) from exc

        return {
            "ok": True,
            "registered": True,
            "project_id": project_id,
            "revision": saved["revision"],
            "saved_at": saved["saved_at"],
            "parser_run": payload,
            "persisted_output_size_bytes": output_size,
            "derived_source_count": len(result.derived_sources),
            "authority_unchanged": True,
        }

    return router
