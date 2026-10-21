"""Normal-only support is a sensitivity bound, not nonlinear contact."""
import json
from pathlib import Path

P=Path(__file__).resolve().parents[1]/'projects/cyberdeck_structural_validation_20261021'

def test_normal_support_increases_compliance_and_does_not_release():
    for name,baseline in [('LID_NORMAL_ONLY_4_3','P2_LID_FINE_EXACT_LOAD'),('BASE_NORMAL_ONLY_10_8','P2_BASE_CORRECT_PCB_SEAT')]:
        trial=json.loads((P/('P2_'+name+'.json')).read_text())
        original=json.loads((P/(baseline+'.json')).read_text())['results']
        assert trial['support_mode']=='normal_only'
        assert trial['nonlinear_contact_modelled'] is False
        assert trial['real_fastener_preload_modelled'] is False
        assert trial['fabrication_authorized'] is False
        for a,b in zip(original,trial['mesh_results']):
            assert a['mesh_size_mm']==b['mesh_size_mm']
            assert b['displacement_mm']>a['displacement_mm']
            assert b['peak_von_mises_mpa']>a['peak_von_mises_mpa']
            assert b['reaction_z_balance_error_n']<1e-8

def test_short_base_window_does_not_override_global_release_block():
    trial=json.loads((P/'P2_BASE_NORMAL_ONLY_10_8.json').read_text())
    assert trial['local_peak_stress_stable_in_tested_window'] is True
    assert trial['single_favorable_refinement_window_is_not_release_evidence'] is True
    assert trial['fabrication_authorized'] is False
