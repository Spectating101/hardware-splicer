"""Digital requirement revisions on the canonical product API."""
from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from . import digital_project as digital
from .digital_cases import DEFAULT_CASE
from .project_api import _project_error
from .digital_engine import DigitalStudyEngine, DigitalRuntimeUnavailable
from .digital_brief import BriefProviderError


class CreateDigitalProject(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str | None = Field(default=None, min_length=1, max_length=100)
    case_id: str = Field(default=DEFAULT_CASE, min_length=1, max_length=64)


class DigitalRunRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    base_revision: int = Field(ge=1, strict=True)
    change_request: str = Field(default='', max_length=200)
    requirements: dict[str, Any] = Field(default_factory=dict)
    request_id: UUID = Field(default_factory=uuid4)


class DigitalBriefRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    brief: str = Field(min_length=1, max_length=4000)
    project_id: str | None = Field(default=None, min_length=1, max_length=128)
    base_revision: int | None = Field(default=None, ge=1, strict=True)


def create_digital_project_router(store, backend):
    router = APIRouter(tags=['digital studies'])
    engine = DigitalStudyEngine(store, backend)

    def artifact_links(project_id, study):
        study = dict(study)
        manifest = study.pop('artifact_manifest')
        study['artifacts'] = {name: f'/v1/projects/{project_id}/digital/revisions/{study["revision"]}/artifacts/{name}'
                              for name in sorted(manifest)}
        return study

    @router.post('/v1/digital/projects', status_code=201)
    def create(request: CreateDigitalProject):
        try:
            return engine.create(name=(request.name.strip() or 'Digital study') if request.name is not None else None,
                                 case_id=request.case_id)
        except DigitalRuntimeUnavailable as exc:
            raise HTTPException(status_code=503, detail={'type': 'digital_runtime_unavailable', 'message': str(exc)}) from exc
        except Exception as exc:
            raise _project_error(exc) from exc

    @router.get('/v1/digital/cases')
    def registered_cases():
        return engine.cases()

    @router.post('/v1/digital/prompt')
    def build_from_prompt(request: DigitalBriefRequest):
        try:
            return engine.from_prompt(**request.model_dump())
        except (BriefProviderError, DigitalRuntimeUnavailable) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise _project_error(exc) from exc

    @router.get('/v1/projects/{project_id}/digital')
    def get_study(project_id: str, revision: int | None = Query(default=None, ge=1)):
        try:
            result = engine.project_state(project_id, revision)
            result['study'] = artifact_links(project_id, result['study'])
            result['history'] = [artifact_links(project_id, row) for row in result['history']]
            return result
        except Exception as exc:
            raise _project_error(exc) from exc

    @router.post('/v1/projects/{project_id}/digital/runs', status_code=202)
    def submit_run(project_id: str, request: DigitalRunRequest):
        try:
            return engine.enqueue_revision(project_id, **request.model_dump())
        except DigitalRuntimeUnavailable as exc:
            raise HTTPException(status_code=503, detail={'type': 'digital_runtime_unavailable', 'message': str(exc)}) from exc
        except Exception as exc:
            raise _project_error(exc) from exc

    @router.get('/v1/projects/{project_id}/digital/compare')
    def compare(project_id: str, before_revision: int = Query(ge=1), after_revision: int = Query(ge=1)):
        try:
            return engine.compare(project_id, before_revision=before_revision, after_revision=after_revision)
        except Exception as exc:
            raise _project_error(exc) from exc

    @router.get('/v1/projects/{project_id}/digital/revisions/{revision}/audit')
    def audit(project_id: str, revision: int):
        return engine.audit(project_id, revision)

    @router.post('/v1/projects/{project_id}/digital/revisions/{revision}/verify')
    def verify(project_id: str, revision: int):
        try:
            return engine.audit(project_id, revision, native=True)
        except Exception as exc:
            raise _project_error(exc) from exc

    @router.get('/v1/projects/{project_id}/digital/revisions/{revision}/artifacts/{name:path}')
    def artifact(project_id: str, revision: int, name: str):
        try:
            _, directory, seal = digital.load_run(store, project_id, revision)
            path = digital.checked_file(directory, name, seal['artifact_sha256'], case_id=digital.case_id_for(seal),
                                        case=digital.case_for_run(seal))
        except Exception as exc:
            raise _project_error(exc) from exc
        if name == 'VIEWER.html':
            # The viewer needs WebGL scripts, but no origin access or network.
            return FileResponse(path, media_type='text/html', headers={
                'Content-Security-Policy': "sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; connect-src 'none'",
                'X-Content-Type-Options': 'nosniff',
            })
        types = {'.zip': 'application/zip', '.glb': 'model/gltf-binary', '.step': 'model/step',
                 '.csv': 'text/csv', '.json': 'application/json', '.png': 'image/png', '.gif': 'image/gif'}
        return FileResponse(path, media_type=types.get(path.suffix, 'text/plain'), filename=path.name,
                            headers={'X-Content-Type-Options': 'nosniff'})

    return router
