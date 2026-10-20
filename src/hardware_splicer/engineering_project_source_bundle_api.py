"""Canonical project-scoped software check for a registered KiCad CAD source set."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Mapping

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .engineering_project_source_bundle import analyze_registered_project_bundle
from .project_store import ProjectStore, ProjectNotFound, RevisionConflict


class SourceBundleCheckRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(ge=1)


def _source_fingerprint(rows: list[Mapping[str, Any]]) -> str:
    items = sorted((str(row.get('source_id') or ''), str(row.get('content_hash') or ''))
                   for row in rows)
    return 'sha256:' + hashlib.sha256(json.dumps(items,sort_keys=True).encode()).hexdigest()


def create_project_source_bundle_router(store: ProjectStore | None = None) -> APIRouter:
    store = store or ProjectStore()
    router = APIRouter(tags=['project-source-bundle'])

    @router.post('/v1/projects/{project_id}/engineering/source-bundle/check')
    def check_source_bundle(project_id: str, request: SourceBundleCheckRequest) -> dict[str, Any]:
        try:
            envelope = store.load_latest_with_recovery(project_id)
            revision = envelope['revision']
            if revision != request.expected_revision:
                raise RevisionConflict(f'project currently at {revision}; expected {request.expected_revision}')
            snapshot = deepcopy(envelope['snapshot'])
            sources = [row for row in snapshot.get('engineeringSources') or [] if isinstance(row, Mapping)]
            fingerprint = _source_fingerprint(sources)
            for row in snapshot.get('engineeringSourceBundleRuns') or []:
                if row.get('source_set_sha256') == fingerprint and row.get('schema_version') == 'hardware_splicer.project_source_bundle.v1':
                    return {'ok': True, 'registered': False, 'revision': revision,
                            'project_id': project_id, 'source_bundle_run': row, 'physical_authority_unchanged': True}
            result = analyze_registered_project_bundle(project_id, sources, project_root=store.root)
            result['source_set_sha256'] = fingerprint
            if len(json.dumps(result,ensure_ascii=False).encode()) > 2 * 1024 * 1024:
                raise ValueError('bundle check exceeds bounded artifact output')
            runs = list(snapshot.get('engineeringSourceBundleRuns') or [])
            runs.append(result)
            snapshot['engineeringSourceBundleRuns'] = runs
            saved = store.save(project_id,snapshot,expected_revision=revision,
                               metadata={'source':'project_source_bundle_check',
                                         'source_set_sha256':fingerprint})
            return {'ok': True,'registered': True,'revision':saved['revision'],
                    'project_id':project_id,'source_bundle_run':result,
                    'physical_authority_unchanged':True}
        except ProjectNotFound as exc:
            raise HTTPException(status_code=404,detail=str(exc)) from exc
        except RevisionConflict as exc:
            raise HTTPException(status_code=409,detail=str(exc)) from exc
        except (ValueError,TypeError) as exc:
            raise HTTPException(status_code=422,detail=str(exc)) from exc

    return router
