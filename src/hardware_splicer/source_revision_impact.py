"""Invalidate inherited outputs when a native design source changes."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .evidence_impact import evaluate_evidence_impact


DERIVED_FAMILIES = (
    'native_rule_checks', 'mechanical_fit', 'wiring', 'materials',
    'firmware', 'model3d', 'manufacturing_package',
)


def invalidate_source_derived_outputs(
    snapshot: Mapping[str, Any], *, changed_source_ids: Sequence[str] = (),
    changed_artifact_kinds: Sequence[str] = (), basis: str,
) -> dict[str, Any]:
    """Keep historical data while visibly requiring checks for the new source.

    Dependency coverage across electronics, mechanics and firmware is not yet
    complete. Inherited outputs therefore cannot silently survive a native
    source change. This records required work; it does not regenerate a part or
    alter any physical authorization ledger.
    """
    result = deepcopy(dict(snapshot))
    changed = ['native_source_bundle', *('source:' + value for value in changed_source_ids),
               *('artifact:' + value for value in changed_artifact_kinds)]
    impact = evaluate_evidence_impact({
        'changed_dependency_ids': list(dict.fromkeys(changed)),
        'evidence_items': [
            {'evidence_id': name, 'depends_on': ['native_source_bundle'],
             'dependencies_complete': False,
             'metadata': {'scope': 'conservative_recheck_after_source_change'}}
            for name in DERIVED_FAMILIES
        ],
    })
    previous = result.get('sourceRevisionImpact')
    result['sourceRevisionImpact'] = {
        'schema_version': 'hardware_splicer.source_revision_impact.v1',
        'status': 'requires_recheck', 'basis': basis,
        'changed_source_ids': list(dict.fromkeys(changed_source_ids)),
        'changed_artifact_kinds': list(dict.fromkeys(changed_artifact_kinds)),
        'families': {name: {'status': 'requires_recheck'} for name in DERIVED_FAMILIES},
        'previous_impact_schema': previous.get('schema_version') if isinstance(previous, dict) else None,
        'evidence_impact': impact,
        'automatic_regeneration': False,
        'physical_authority_granted': False,
    }
    invalidated = []
    for key in ('machineProject', 'machine_project'):
        project = result.get(key)
        if not isinstance(project, dict):
            continue
        for verification in project.get('verifications') or []:
            if not isinstance(verification, dict) or verification.get('status') not in {'passed', 'running'}:
                continue
            old_status = verification['status']
            verification['status'] = 'blocked'
            verification['metadata'] = {
                **(verification.get('metadata') or {}),
                'native_source_change': {'basis': basis, 'previous_status': old_status,
                                         'requires_new_evidence': True},
            }
            if verification.get('verification_id') not in invalidated:
                invalidated.append(verification.get('verification_id'))
    result['sourceRevisionImpact']['invalidated_verification_ids'] = invalidated
    return result
