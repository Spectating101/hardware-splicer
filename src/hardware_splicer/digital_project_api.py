"""Digital requirement revisions on the canonical product API."""
from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from . import digital_project as digital
from .project_api import _project_error
from .project_review_store import ProjectReviewStore
from .project_store import RevisionConflict


class CreateDigitalProject(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(default='HS-3G-B digital study', min_length=1, max_length=100)


class DigitalRunRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    base_revision: int = Field(ge=1)
    change_request: str = Field(default='', max_length=200)
    requirements: dict[str, Any] = Field(default_factory=dict)
    request_id: UUID = Field(default_factory=uuid4)


def create_digital_project_router(store, backend):
    router = APIRouter(tags=['digital studies'])
    reviews = ProjectReviewStore(store)

    @router.post('/v1/digital/projects', status_code=201)
    def create(request: CreateDigitalProject):
        try:
            envelope = digital.create_project(store, name=request.name.strip() or 'Digital study')
            return {'ok': True, 'project': envelope}
        except Exception as exc:
            raise _project_error(exc) from exc

    @router.get('/v1/projects/{project_id}/digital')
    def get_study(project_id: str, revision: int | None = Query(default=None, ge=1)):
        try:
            current = digital.describe(store, project_id, revision)
            history = [digital.describe(store, project_id, row['revision']) for row in reviews.list_revisions(project_id)]
            jobs = backend.store.list_digital_jobs(project_id)
            return {'ok': True, 'study': current, 'history': history, 'runtime': digital.runtime(),
                    'jobs': [job.to_dict() for job in jobs]}
        except Exception as exc:
            raise _project_error(exc) from exc

    @router.post('/v1/projects/{project_id}/digital/runs', status_code=202)
    def submit_run(project_id: str, request: DigitalRunRequest):
        try:
            envelope, _, seal = digital.load_run(store, project_id, request.base_revision)
            requirements = digital.requirement_tools().resolve(seal['summary']['requirements'],
                                                               request.change_request, request.requirements)
            payload = {'project_id': project_id, 'base_revision': request.base_revision,
                       'change_request': request.change_request.strip(), 'requirements': requirements}
            job_id = uuid5(NAMESPACE_URL, f'hardware-splicer:digital:{project_id}:{request.request_id}').hex
            existing = backend.store.get_job(job_id)
            if existing:
                if existing.options.get('payload') != payload:
                    raise RevisionConflict('This request ID already belongs to a different change.')
                return {'ok': True, 'job': existing.to_dict()}
            if store.load(project_id)['revision'] != request.base_revision:
                raise RevisionConflict('A newer project revision exists. Reload before changing requirements.')
            availability = digital.runtime()
            if not availability['available']:
                raise HTTPException(status_code=503, detail={'type': 'digital_runtime_unavailable',
                                                            'message': availability['setup_hint']})
            job = backend.submit_task(job_id=job_id, request_id='digital:' + project_id + ':' + str(request.request_id),
                                      project_name=envelope['snapshot'].get('projectName', 'Digital study'),
                                      output_dir=store.root / '.digital-jobs' / job_id,
                                      job_type='digital_study', payload=payload)
            return {'ok': True, 'job': job.to_dict(), 'resolved_requirements': requirements}
        except HTTPException:
            raise
        except Exception as exc:
            raise _project_error(exc) from exc

    @router.get('/v1/projects/{project_id}/digital/revisions/{revision}/artifacts/{name}')
    def artifact(project_id: str, revision: int, name: str):
        try:
            _, directory, seal = digital.load_run(store, project_id, revision)
            path = digital.checked_file(directory, name, seal['artifact_sha256'])
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
        return FileResponse(path, media_type=types.get(path.suffix, 'text/plain'), filename=name,
                            headers={'X-Content-Type-Options': 'nosniff'})

    return router
