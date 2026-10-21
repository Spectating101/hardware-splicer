"""Retain verified support-condition sensitivity; never equate it to bolt contact."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/'projects/cyberdeck_structural_validation_20261021'


def test_support_width_changes_peak_stress_without_authorizing_release():
    alternative=json.loads((ROOT/'P2_LID_COLLAR_SUPPORT_SENSITIVITY_4_3.json').read_text())
    original=json.loads((ROOT/'P2_LID_FINE_EXACT_LOAD.json').read_text())
    assert alternative['collar_outer_radius_mm']==2.65
    assert alternative['real_fastener_preload_modelled'] is False
    assert alternative['nonlinear_contact_modelled'] is False
    assert alternative['local_peak_stress_stable_in_tested_window'] is False
    assert alternative['fabrication_authorized'] is False
    for before, after in zip(original['results'],alternative['mesh_results']):
        assert before['mesh_size_mm']==after['mesh_size_mm']
        assert after['peak_von_mises_mpa'] < 0.8*before['peak_von_mises_mpa']
        assert after['displacement_mm'] < before['displacement_mm']
        assert after['reaction_z_balance_error_n'] < 1e-8
