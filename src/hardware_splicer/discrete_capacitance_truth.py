"""Separate nominal capacitor selection from effective-capacitance closure."""
from __future__ import annotations
from typing import Any, Dict, Mapping

def _nets(p: Mapping[str, Any]) -> Dict[str,set[str]]:
    return {str(r.get('name')):{str(e) for e in list(r.get('endpoints') or [])} for r in list(p.get('nets') or []) if isinstance(r,Mapping) and r.get('name')}
def _net_for(nets: Mapping[str,set[str]], ep: str)->str|None:
    hits=[n for n,e in nets.items() if ep in e]; return hits[0] if len(hits)==1 else None

def audit_ldo_capacitance_evidence(proposal: Mapping[str,Any], evidence: Mapping[str,Any])->Dict[str,Any]:
    selected={str(r.get('ref')):dict(r) for r in list(proposal.get('selected_parts') or []) if isinstance(r,Mapping) and r.get('ref')}
    parts={str(r.get('evidence_id')):dict(r) for r in list(evidence.get('parts') or []) if isinstance(r,Mapping) and r.get('evidence_id')}
    ldo=parts.get(str((selected.get('U1') or {}).get('evidence_id') or ''))
    if not ldo: return {'status':'failed','hard_failures':[{'code':'LDO_EVIDENCE_MISSING'}],'unresolved':[],'authority_effect':'none','power_on_authorized':False}
    c=dict(ldo.get('constraints') or {}); min_in=float(c.get('input_capacitor_min_nominal_uf') or 0); min_out=float(c.get('output_capacitor_min_nominal_uf') or 0); min_eff=float(c.get('effective_capacitance_min_uf') or 0); nets=_nets(proposal)
    rows=[]; hard=[]; unresolved=[]
    for p in list(proposal.get('passives') or []):
        if not isinstance(p,Mapping) or p.get('kind')!='capacitor': continue
        ref=str(p.get('ref') or ''); pair={_net_for(nets,f'{ref}.1'),_net_for(nets,f'{ref}.2')}; role=None; nominal_min=None; bias=None
        if pair=={'+5V','GND'}: role,nominal_min,bias='ldo_input',min_in,5.0
        elif pair=={'+3V3','GND'}: role,nominal_min,bias='ldo_output',min_out,3.3
        if role is None: continue
        nominal=float(p.get('value_uf') or 0); mpn=str(p.get('mpn') or '').strip() or None; ev=p.get('effective_capacitance_uf_at_operating_bias'); eff=float(ev) if ev is not None else None
        row={'ref':ref,'role':role,'nominal_capacitance_uf':nominal,'minimum_nominal_uf':nominal_min,'minimum_effective_uf':min_eff,'operating_bias_v':bias,'mpn':mpn,'effective_capacitance_uf_at_operating_bias':eff}
        if nominal<float(nominal_min or 0): row['status']='fail'; hard.append({'code':'NOMINAL_CAPACITANCE_BELOW_DATASHEET_MINIMUM','ref':ref,'role':role})
        elif mpn is None or eff is None: row['status']='unresolved'; unresolved.append({'code':'EFFECTIVE_CAPACITANCE_UNRESOLVED','ref':ref,'role':role,'minimum_effective_uf':min_eff})
        elif eff<min_eff: row['status']='fail'; hard.append({'code':'EFFECTIVE_CAPACITANCE_BELOW_STABILITY_MINIMUM','ref':ref,'role':role,'effective_uf':eff,'minimum_effective_uf':min_eff})
        else: row['status']='closed'
        rows.append(row)
    roles={r['role'] for r in rows}
    for role in ('ldo_input','ldo_output'):
        if role not in roles: hard.append({'code':'REQUIRED_LDO_CAPACITOR_MISSING','role':role})
    status='failed' if hard else ('blocked' if unresolved else 'closed')
    return {'status':status,'nominal_requirement_pass':not hard,'effective_capacitance_closed':status=='closed','rows':rows,'hard_failures':hard,'unresolved':unresolved,'authority_effect':'none','fabrication_authorized':False,'power_on_authorized':False}
