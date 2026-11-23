"""HS drone assembly readiness from a declared, never inferred parts inventory."""
from __future__ import annotations
from typing import Any, Mapping

STAGE_REQUIREMENTS={
    'identify': ['frame','fc','power','motors','esc','props','pdb','gps'],
    'frame': ['frame','motors'],
    'power': ['battery','power','pdb','esc','fc'],
    'control': ['fc','esc','gps','telemetry','rc'],
    'px4': ['fc'],
    'bench': ['battery','power','pdb','esc','fc','motors'],
    'release': ['frame','fc','power','motors','esc','props','pdb','gps','battery','rc'],
}


def assess_inventory(reference:Mapping[str,Any], available:Mapping[str,Any]) -> dict[str,Any]:
    parts={p['id']:p for p in reference['reference_bom']}
    unknown=set(available)-set(parts)
    if unknown:raise ValueError('unknown inventory ids: '+','.join(sorted(unknown)))
    rows=[]
    for key, part in parts.items():
        supplied=available.get(key) or {}
        if not isinstance(supplied,Mapping):raise ValueError('inventory entries must be objects')
        count=supplied.get('quantity',0)
        if type(count) is not int or count<0:raise ValueError('invalid quantity '+key)
        confirmed=supplied.get('identity_verified') is True
        compatible=supplied.get('compatibility_verified') is True
        if compatible and not confirmed:raise ValueError('compatibility without part identity verification')
        rows.append({'id':key,'required_quantity':part['quantity'],'on_hand_quantity':count,
                     'shortfall':max(0,part['quantity']-count),
                     'identity_verified':confirmed,'compatibility_verified':compatible,
                     'ready':count>=part['quantity'] and confirmed and compatible})
    status={row['id']:row for row in rows}
    stage_rows=[]
    for stage in reference['assembly_stages']:
        deps=STAGE_REQUIREMENTS[stage['id']]
        missing=[i for i in deps if not status[i]['ready']]
        # All stages demand signed evidence; inventory alone never authorizes assembly.
        stage_rows.append({'stage_id':stage['id'],'required_parts':deps,
                           'unverified_or_missing_parts':missing,
                           'required_evidence':stage['required_evidence'],
                           'review_status':'hold',
                           'eligible_for_document_review':not missing})
    return {'schema_version':'hardware_splicer.drone_inventory_readiness.v1',
            'inventory':rows,'stages':stage_rows,
            'unfilled_line_items':sum(row['shortfall']>0 for row in rows),
            'unverified_line_items':sum(not row['ready'] for row in rows),
            'physical_assembly_authorized':False,'flight_authorized':False}
