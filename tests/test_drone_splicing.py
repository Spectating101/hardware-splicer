import json
from pathlib import Path
from hardware_splicer.drone_splicing import assess_splice

ROOT=Path(__file__).resolve().parents[1]
REF=json.loads((ROOT/'eval/drone_reference_build/x500_v2.json').read_text())
ALTERNATES=json.loads((ROOT/'eval/drone_splicing/alternates.json').read_text())


def test_real_repo_cross_design_rejections():
    outcome=assess_splice(REF,ALTERNATES)
    states={r['candidate_id']:r['classification'] for r in outcome['candidates']}
    assert states['s500-frame-from-droneskeleton']=='redesign_required_not_drop_in'
    assert states['stm32-custom-flight-controller']=='redesign_required_not_drop_in'
    assert states['salvaged-unknown-esc']=='adaptation_or_verification_required'
    assert states['known-document-only-propeller']=='adaptation_or_verification_required'
    assert not outcome['approved_for_installation']


def test_even_all_evidence_match_cannot_approve_physical_installation():
    donor={'id':'fc-variant','replaces':'fc','origin_repo':'verified-source',
           'requirements':{'protocol':'PWM'}, 'characteristics':{'protocol':'PWM'},
           'evidence':{'protocol':{'source_locator':'manual#p3'}},'mandatory_interfaces':['protocol']}
    result=assess_splice(REF,[donor])
    assert result['candidates'][0]['classification']=='document_review_candidate'
    assert not result['assembly_authorized']
    assert not result['flight_authorized']


def test_unsupported_role_rejected():
    import pytest
    with pytest.raises(ValueError,match='unknown role'):
        assess_splice(REF,[{'id':'a','replaces':'aether','origin_repo':'manual'}])
