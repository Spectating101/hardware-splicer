"""Project source promotion; no user paths, shell commands or design approval."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict, Field

from .project_api import _project_error
from .project_store import ProjectStore
from .source_project_editing import (
    SCHEMA, SUFFIXES, check_retained_native_design, promote_kicad_source_bundle, native_candidate_bundle,
)


class PromoteSourceBundleRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(strict=True, ge=1)
    source_ids: list[str] | None = Field(default=None, min_length=1, max_length=16)
    primary_source_id: str | None = Field(default=None, min_length=1, max_length=160)


class CheckNativeDesignRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(strict=True, ge=1)
    kind: Literal['pcb', 'schematic'] = 'pcb'


def create_source_project_editing_router(store: ProjectStore | None = None) -> APIRouter:
    store = store or ProjectStore()
    router = APIRouter(tags=['source-project-editing'])

    @router.get('/v1/engineering/sources/editing/schema')
    def editing_schema():
        return {'ok': True, 'schema_version': SCHEMA,
                'request_schema': PromoteSourceBundleRequest.model_json_schema(),
                'check_request_schema': CheckNativeDesignRequest.model_json_schema(),
                'supported_extensions': sorted(SUFFIXES), 'preserves_native_source_bytes': True,
                'requires_registered_project_sources': True, 'physical_authority_granted': False}

    @router.post('/v1/projects/{project_id}/sources/promote-to-editable', status_code=201)
    def promote(project_id: str, request: PromoteSourceBundleRequest):
        try:
            return promote_kicad_source_bundle(store, project_id, **request.model_dump())
        except Exception as exc:
            raise _project_error(exc) from exc

    @router.post('/v1/projects/{project_id}/native/check')
    def check_native(project_id: str, request: CheckNativeDesignRequest):
        try:
            return check_retained_native_design(store, project_id, **request.model_dump())
        except Exception as exc:
            raise _project_error(exc) from exc

    @router.get('/v1/projects/{project_id}/candidates/{candidate_id}/native-bundle',
                response_class=Response, responses={200: {'content': {'application/zip': {}}}})
    def download_native_edit_bundle(project_id: str, candidate_id: str):
        from .project_candidates_api import _candidate_error
        try:
            data = native_candidate_bundle(store, project_id, candidate_id)
        except Exception as exc:
            raise _candidate_error(exc) from exc
        import hashlib
        return Response(data, media_type='application/zip', headers={
            'Content-Disposition': f'attachment; filename="{candidate_id}-native.zip"',
            'ETag': '"sha256:' + hashlib.sha256(data).hexdigest() + '"',
            'X-Content-Type-Options': 'nosniff',
        })

    return router
