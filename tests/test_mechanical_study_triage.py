import json
from pathlib import Path
import pytest
from hardware_splicer.mechanical_study_triage import assess_structural_study
P=Path(__file__).resolve().parents[1]/'projects/cyberdeck_structural_validation_20261021'

@pytest.mark.parametrize('name',['P2_LID_REFINEMENT_3_2P5_2.json','P2_BASE_NORMAL_ONLY_REFINEMENT_8_6_4.json','P2_LID_STRESS_OUTSIDE_FIXTURE_4_3.json'])
def test_source_bound_studies_remain_unreleased(name):
    r=assess_structural_study(json.loads((P/name).read_text()))
    assert 'peak_stress_unstable' in r['blockers']
    assert not r['fabrication_authorized']

def test_bad_equilibrium_and_false_release_rejected():
    d=json.loads((P/'P2_LID_REFINEMENT_3_2P5_2.json').read_text())
    d['fabrication_authorized']=True
    with pytest.raises(ValueError):assess_structural_study(d)
    d['fabrication_authorized']=False
    d['mesh_results'][0]['reaction_z_balance_error_n']=1
    with pytest.raises(ValueError):assess_structural_study(d)
