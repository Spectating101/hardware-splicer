import pytest
from hardware_splicer.real_device_work_package import compile_work_package

CASE={'id':'donor-controller','device':'owned control board','kind':'repair','deliverables':['interface inventory'],'acceptance':['bench validation']}
REVIEW={'operator_casefile':{'build_or_repair_sequence':['Inspect connector pinout'],'critical_technical_unknowns':['Protocol unspecified'],'compatible_parts_or_requirements':['Harness']}}

def test_rea_static_evidence_generates_actionable_cross_domain_step_without_release():
    result=compile_work_package(CASE,REVIEW,reverse_engineering={
        'schema':'hardware_splicer.rea_javascript_intake.v1',
        'status':'static_analysis_available_unverified','rea_evidence_id':'ev_test',
        'input_tree_sha256':'sha256:'+'a'*64,'source_executed':False,'release_authorized':False})
    assert result['reverse_engineering']['evidence_id']=='ev_test'
    assert any('PCB observations' in t['instruction'] for t in result['work_steps'])
    assert result['engineering_readiness']=='blocked'
    assert not result['physical_validation_performed']

def test_missing_provider_adds_real_investigation_gap():
    result=compile_work_package(CASE,REVIEW,reverse_engineering={
        'schema':'hardware_splicer.rea_investigation.v1','status':'blocked','provider_code':'target_unavailable'})
    assert any('Reverse-engineering investigation' in u['description'] for u in result['critical_unknowns'])

@pytest.mark.parametrize('bad',[{'schema':'fake','status':'blocked'},
                                {'schema':'hardware_splicer.rea_javascript_intake.v1','status':'static_analysis_available_unverified'},
                                {'schema':'hardware_splicer.rea_investigation.v1','status':'blocked','release_authorized':True}])
def test_cannot_launder_bad_rea_evidence_into_work_package(bad):
    with pytest.raises(ValueError): compile_work_package(CASE,REVIEW,reverse_engineering=bad)
