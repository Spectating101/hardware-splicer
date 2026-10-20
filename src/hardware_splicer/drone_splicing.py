"""Evidence-bound cross-design component splicing for a quadcopter.

Splicing means making and validating substitutions across independently sourced
component families. Unknown physical interfaces never become compatible by
inference or by a model claim.
"""
from __future__ import annotations

from typing import Any, Mapping


def assess_splice(reference:Mapping[str,Any], candidates:list[Mapping[str,Any]])->dict[str,Any]:
    reference_roles={p['id']:p for p in reference['reference_bom']}
    checks=[]
    for candidate in candidates:
        role=candidate['replaces']
        if role not in reference_roles:raise ValueError('unknown role '+role)
        candidate_id=candidate['id']
        origin=candidate.get('origin_repo')
        if not origin:raise ValueError('donor origin required')
        characteristics=candidate.get('characteristics') or {}
        proofs=candidate.get('evidence') or {}
        requirements=candidate.get('requirements') or {}
        failures=[]; gaps=[]; matches=[]
        for field, expected in requirements.items():
            observed=characteristics.get(field)
            if observed is None:
                gaps.append(field+': missing evidence')
            elif isinstance(expected,list):
                if observed not in expected:failures.append(field+': incompatible declared value')
                else:matches.append(field)
            elif observed!=expected:
                failures.append(field+': mismatch')
            else:matches.append(field)
            if field not in proofs or not proofs[field].get('source_locator'):
                gaps.append(field+': missing traceable source')
        for field in candidate.get('mandatory_interfaces',[]):
            if field not in characteristics:gaps.append(field+': interface unresolved')
            elif field not in proofs or not proofs[field].get('source_locator'):
                gaps.append(field+': interface not source verified')
        if failures:state='redesign_required_not_drop_in'
        elif gaps:state='adaptation_or_verification_required'
        else:state='document_review_candidate'
        checks.append({'candidate_id':candidate_id,'replaces':role,
                       'origin_repo':origin,'classification':state,
                       'confirmed_matches':matches,'hard_failures':sorted(set(failures)),
                       'unverified_gaps':sorted(set(gaps)),
                       'adapter_or_redesign':candidate.get('proposed_adaptation',[]),
                       'authority':'proposed_not_physically_validated'})
    return {'schema_version':'hardware_splicer.drone_splicing.v1',
            'original_design':reference['target'],'candidates':checks,
            'approved_for_installation':[], 'physical_testing_performed':False,
            'assembly_authorized':False,'flight_authorized':False}
