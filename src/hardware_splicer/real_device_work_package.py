"""Compile bounded real-device repair/build work packages from unverified reviews.

Only source pointers, required deliverables and explicit acceptance gates are
promoted to structured work items. Model prose is never component certification.
"""
from __future__ import annotations

from typing import Any, Mapping


def compile_work_package(case: Mapping[str, Any], review: Mapping[str, Any],
                         *, planner: Mapping[str, Any] | None = None) -> dict[str, Any]:
    model = dict(review.get('operator_casefile') or review)
    plan = dict(planner or {})
    requirements = [
        {'id': f'req-{n+1:02d}', 'requirement': str(item), 'status': 'unverified',
         'evidence_refs': [], 'verification_required': True}
        for n, item in enumerate(case.get('deliverables', []))
    ]
    tasks = [
        {'id': f'step-{n+1:02d}', 'instruction': str(item),
         'status': 'proposed_not_executed', 'evidence_refs': []}
        for n, item in enumerate(model.get('build_or_repair_sequence') or [])
    ]
    unknowns = [
        {'id': f'gap-{n+1:02d}', 'description': str(item),
         'status': 'open', 'resolution_evidence': None}
        for n, item in enumerate(model.get('critical_technical_unknowns') or [])
    ]
    safety_gates = [
        {'id': f'gate-{n+1:02d}', 'criterion': str(item),
         'status': 'not_accepted', 'evidence_refs': []}
        for n, item in enumerate(case.get('acceptance', []))
    ]
    candidate = plan.get('recommended_build_id')
    approved = set(case.get('approved_catalog_build_ids', []))
    return {
        'schema_version': 'hardware_splicer.real_device_work_package.v1',
        'project_id': case['id'], 'device': case['device'],
        'project_kind': case['kind'],
        'catalog_routing': {'candidate': candidate,
                            'status': 'approved' if candidate in approved and candidate else 'blocked_no_compatible_catalog_build'},
        'source_leads': [{'source_id': item['source_id'], 'uri': item['uri'],
                          'verified_full_document': False, 'content_hash': None}
                         for item in case.get('sources', [])],
        'requirements': requirements, 'work_steps': tasks,
        'critical_unknowns': unknowns, 'acceptance_gates': safety_gates,
        'required_parts': [{'requirement': str(item), 'verified_part_number': None,
                            'vendor': None, 'price': None, 'compatibility_verified': False}
                           for item in model.get('compatible_parts_or_requirements') or []],
        'engineering_readiness': 'blocked', 'physical_validation_performed': False,
        'source_documents_verified': False, 'build_or_repair_completed': False,
    }
