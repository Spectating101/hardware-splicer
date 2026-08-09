from __future__ import annotations
import copy
from pathlib import Path
from hardware_splicer.discrete_capacitance_truth import audit_ldo_capacitance_evidence
from hardware_splicer.discrete_electronics_truth import load_json_object
E=Path('experiments/electronics/discrete_uart_3v3_1v8_evidence.json'); P=Path('experiments/electronics/discrete_uart_3v3_1v8_gpt56_sol.json')
def data(): return load_json_object(P),load_json_object(E)
def test_nominal_caps_do_not_close_effective_value():
 p,e=data(); r=audit_ldo_capacitance_evidence(p,e); assert r['status']=='blocked'; assert r['nominal_requirement_pass']; assert not r['effective_capacitance_closed']; assert len(r['unresolved'])==2
def test_nominal_too_small_fails():
 p,e=data(); b=copy.deepcopy(p); next(x for x in b['passives'] if x['ref']=='C2')['value_uf']=0.1; r=audit_ldo_capacitance_evidence(b,e); assert r['status']=='failed'; assert any(x['code']=='NOMINAL_CAPACITANCE_BELOW_DATASHEET_MINIMUM' for x in r['hard_failures'])
def test_effective_value_closes_only_with_identity_and_at_bias_value():
 p,e=data(); b=copy.deepcopy(p)
 for x in b['passives']:
  if x['ref'] in {'C1','C2'}: x['mpn']='evidence-'+x['ref']; x['effective_capacitance_uf_at_operating_bias']=0.7
 r=audit_ldo_capacitance_evidence(b,e); assert r['status']=='closed'; assert r['effective_capacitance_closed']
def test_effective_value_below_minimum_fails():
 p,e=data(); b=copy.deepcopy(p)
 for x in b['passives']:
  if x['ref'] in {'C1','C2'}: x['mpn']='evidence-'+x['ref']; x['effective_capacitance_uf_at_operating_bias']=0.3
 r=audit_ldo_capacitance_evidence(b,e); assert r['status']=='failed'; assert sum(x['code']=='EFFECTIVE_CAPACITANCE_BELOW_STABILITY_MINIMUM' for x in r['hard_failures'])==2
