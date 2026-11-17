"""HTTP adapter for bounded digital part substitution studies."""
from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict, Field

from .part_substitution import SubstitutionSpecification
from .project_api import _project_error
from .project_part_substitutions import (
    assess_project_substitution, export_substitution_bundle, load_substitution_assessment,
    propose_project_substitution,
)
from .project_store import ProjectStore


class AssessSubstitutionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(strict=True, ge=1)
    specification: SubstitutionSpecification
    generate_geometry: bool = Field(default=False, strict=True)


class ProposeSubstitutionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(strict=True, ge=1)
    author: str = Field(default='api', min_length=1, max_length=128)
    note: str = Field(default='', max_length=2000)


def create_project_part_substitutions_router(store: ProjectStore):
    router = APIRouter(tags=['projects', 'part-substitution'])

    def call(function, *args, **kwargs):
        try:
            return function(store, *args, **kwargs)
        except Exception as exc:
            raise _project_error(exc) from exc

    @router.get('/v1/engineering/parts/substitution/schema')
    def schema():
        return {'request_schema': AssessSubstitutionRequest.model_json_schema(),
                'scope': 'Declared digital profiles, connected steady-state loads and nominal geometry.',
                'physical_authority_granted': False}

    @router.post('/v1/projects/{project_id}/parts/substitutions', status_code=201)
    def assess(project_id: str, request: AssessSubstitutionRequest):
        return call(assess_project_substitution, project_id, **request.model_dump(mode='json', by_alias=True))

    @router.get('/v1/projects/{project_id}/parts/substitutions/{assessment_id}')
    def show(project_id: str, assessment_id: str):
        return call(load_substitution_assessment, project_id, assessment_id)

    @router.post('/v1/projects/{project_id}/parts/substitutions/{assessment_id}/propose', status_code=201)
    def propose(project_id: str, assessment_id: str, request: ProposeSubstitutionRequest):
        return call(propose_project_substitution, project_id, assessment_id, **request.model_dump())

    @router.get('/v1/projects/{project_id}/parts/substitutions/{assessment_id}/bundle', response_class=Response,
                responses={200: {'content': {'application/zip': {}}}})
    def bundle(project_id: str, assessment_id: str):
        import hashlib
        data = call(export_substitution_bundle, project_id, assessment_id)
        return Response(data, media_type='application/zip', headers={
            'Content-Disposition': f'attachment; filename="{assessment_id}.zip"',
            'ETag': '"sha256:' + hashlib.sha256(data).hexdigest() + '"',
            'X-Content-Type-Options': 'nosniff',
        })

    return router
