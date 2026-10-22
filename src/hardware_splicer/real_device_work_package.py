"""Compile bounded real-device repair/build work packages from unverified reviews.

Only source pointers, required deliverables and explicit acceptance gates are
promoted to structured work items. Model prose is never component certification.
"""
from __future__ import annotations

from typing import Any, Mapping


def compile_work_package(case: Mapping[str, Any], review: Mapping[str, Any],
                         *, planner: Mapping[str, Any] | None = None,
                         reverse_engineering: Mapping[str, Any] | None = None,
                         splice_candidate: Mapping[str, Any] | None = None,
                         external_engine_execution: Mapping[str, Any] | None = None) -> dict[str, Any]:
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
    investigation = dict(reverse_engineering or {})
    rea_status = investigation.get('status')
    if investigation:
        allowed = {'static_analysis_available_unverified','analysis_available_unverified','blocked','unavailable'}
        if investigation.get('schema') not in {'hardware_splicer.rea_javascript_intake.v1',
                                               'hardware_splicer.rea_investigation.v1'} or rea_status not in allowed:
            raise ValueError('unsupported reverse-engineering evidence')
        if any(investigation.get(flag) is True for flag in
               ('release_authorized','fabrication_authorized','firmware_flash_authorized','source_executed')):
            raise ValueError('reverse-engineering evidence cannot confer authority')
        if rea_status.endswith('_unverified') and not (
                investigation.get('rea_evidence_id') or investigation.get('artifact_sha256')):
            raise ValueError('successful REA investigation requires source evidence reference')
        if rea_status in {'blocked','unavailable'}:
            unknowns.append({'id':f'gap-{len(unknowns)+1:02d}',
                             'description':'Reverse-engineering investigation unavailable or unsupported; identify compatible format/provider.',
                             'status':'open','resolution_evidence':None})
        else:
            tasks.append({'id':f'step-{len(tasks)+1:02d}',
                          'instruction':'Review REA static findings against PCB observations and physical interfaces; validate candidate behavior on an isolated bench.',
                          'status':'proposed_not_executed',
                          'evidence_refs':[str(investigation.get('rea_evidence_id') or investigation.get('artifact_sha256'))]})
    splice_report = None
    if splice_candidate is not None:
        from .device_splice_feasibility import assess_device_splice
        splice_report = assess_device_splice(splice_candidate)
        for work in splice_report["required_actions"]:
            tasks.append({
                "id": f"step-{len(tasks)+1:02d}",
                "instruction": work["action"],
                "status": "proposed_not_executed",
                "evidence_refs": [],
                "interface_id": work["interface_id"],
            })
            unknowns.append({
                "id": f"gap-{len(unknowns)+1:02d}",
                "description": work["reason"] or work["action"],
                "status": "open",
                "resolution_evidence": None,
                "interface_id": work["interface_id"],
            })
        safety_gates.append({
            "id": f"gate-{len(safety_gates)+1:02d}",
            "criterion": "Independently verify all donor specifications, electrical wiring, actual 3D fit, and isolated bench operation before build authorization.",
            "status": "not_accepted",
            "evidence_refs": [],
        })
    # External CAD/EDA engines are optional subordinate sources of *candidate*
    # evidence. An external tool report cannot grant build or release authority.
    external_engines = None
    if external_engine_execution is not None:
        from .external_engine_orchestration import REPORT_SCHEMA
        data = external_engine_execution
        if not isinstance(data, Mapping) or data.get('schema') != REPORT_SCHEMA:
            raise ValueError('unsupported external-engine execution report')
        if any(data.get(key) is True for key in (
            'fabrication_authorized', 'power_on_authorized', 'release_authorized',
            'electrical_operation_verified', 'exact_mechanical_assembly_verified',
        )):
            raise ValueError('external report attempts to confer physical authority')
        rows = data.get('tasks')
        if not isinstance(rows, list) or not 1 <= len(rows) <= 12:
            raise ValueError('bounded external task results required')
        statuses = {'tool_passed_artifact_observed', 'blocked_dependency',
                    'blocked_missing_external_engine', 'blocked_tool_error',
                    'blocked_execution_failure', 'blocked_missing_or_invalid_output',
                    'blocked_not_step_export', 'blocked_no_output_evidence',
                    'blocked_stale_project_artifact',
                    'blocked_missing_circuit_json', 'blocked_circuit_json_interchange',
                    'blocked_invalid_geometry'}
        if any(not isinstance(row, Mapping) or row.get('status') not in statuses
               or not isinstance(row.get('id'), str) for row in rows):
            raise ValueError('invalid external-engine task results')
        external_engines = {
            'status': 'external_outputs_unverified_for_physical_readiness',
            'plan_sha256': data.get('plan_sha256'),
            'tasks': [{'id': row['id'], 'engine': row.get('engine'),
                       'status': row['status'],
                       'canonical_electrical_interchange': (
                           dict(row.get('canonical_electrical_interchange'))
                           if isinstance(row.get('canonical_electrical_interchange'), Mapping)
                           else None
                       ),
                       'native_geometry_validation': (
                           dict(row.get('native_geometry_validation'))
                           if isinstance(row.get('native_geometry_validation'), Mapping)
                           else None
                       ),
                       'artifact_sha256': [artifact.get('sha256')
                                            for artifact in (row.get('artifacts') or [])
                                            if isinstance(artifact, Mapping)]}
                      for row in rows],
            'archive_bytes_independently_verified': False,
            'provider_outputs_physically_verified': False,
            'power_on_authorized': False,
            'release_authorized': False,
        }
        for task in external_engines['tasks']:
            tasks.append({
                'id': f'step-{len(tasks)+1:02d}',
                'instruction': ('Resolve external provider failure and rerun: '
                                if task['status'] != 'tool_passed_artifact_observed'
                                else 'Independently validate external engineering output: ')
                               + str(task['engine']) + '/' + str(task['id']),
                'status': 'proposed_not_executed', 'evidence_refs': [],
                'external_task_id': task['id'],
            })
        safety_gates.append({
            'id': f'gate-{len(safety_gates)+1:02d}',
            'criterion': 'Validate all specialist CAD/EDA outputs against source files, assembly interfaces, and physical bench evidence before release.',
            'status': 'not_accepted', 'evidence_refs': [],
        })
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
        'reverse_engineering': {'status':rea_status or 'not_provided',
                                'evidence_id':investigation.get('rea_evidence_id'),
                                'source_sha256':investigation.get('artifact_sha256') or investigation.get('input_tree_sha256'),
                                'behavior_physically_verified':False},
        'device_splice_feasibility': splice_report,
        'external_engine_execution': external_engines,
        'requirements': requirements, 'work_steps': tasks,
        'critical_unknowns': unknowns, 'acceptance_gates': safety_gates,
        'required_parts': [{'requirement': str(item), 'verified_part_number': None,
                            'vendor': None, 'price': None, 'compatibility_verified': False}
                           for item in model.get('compatible_parts_or_requirements') or []],
        'engineering_readiness': 'blocked', 'physical_validation_performed': False,
        'source_documents_verified': False, 'build_or_repair_completed': False,
    }
