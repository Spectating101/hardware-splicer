"""Canonical project-scoped software check for a registered KiCad CAD source set."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import shutil
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

    @router.get('/v1/engineering/source-bundle/capabilities')
    def capabilities() -> dict[str, Any]:
        """Report actual available software engineering backends, not promises."""
        from .engineering_multidomain_sources import _SUPPORTED_CAD_PYTHON
        return {
            'source_types': ['kicad_project','stl_mesh','step_brep','scad_polyhedron',
                             'repair_guide_html','markdown_reference_bom'],
            'project_scoped_hash_bound': True,
            'kicad_cli_available': bool(shutil.which('kicad-cli')),
            'occt_cad_kernel_available': _SUPPORTED_CAD_PYTHON.is_file(),
            'physical_build_capability_proven': False,
            'cross_device_compatibility_proven': False,
        }

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
            constraints = snapshot.get('constraints') or {}
            cap = constraints.get('max_cost_usd') if isinstance(constraints, Mapping) else None
            if cap is not None:
                try:
                    cap = float(cap)
                except (ValueError, TypeError) as exc:
                    raise ValueError('project budget cap must be numeric') from exc
                if cap < 0 or cap > 10000000:
                    raise ValueError('project budget cap outside supported range')
            parameters_hash = 'sha256:' + hashlib.sha256(json.dumps(
                {'max_cost_usd': cap},sort_keys=True).encode()).hexdigest()
            for row in snapshot.get('engineeringSourceBundleRuns') or []:
                if row.get('source_set_sha256') == fingerprint and row.get('analysis_parameters_sha256') == parameters_hash and row.get('schema_version') == 'hardware_splicer.project_source_bundle.v1':
                    return {'ok': True, 'registered': False, 'revision': revision,
                            'project_id': project_id, 'source_bundle_run': row, 'physical_authority_unchanged': True}
            result = analyze_registered_project_bundle(project_id, sources, project_root=store.root, budget_cap_usd=cap)
            result['analysis_parameters_sha256'] = parameters_hash
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
