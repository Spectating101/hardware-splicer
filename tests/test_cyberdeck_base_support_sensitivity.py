"""Retain real base support sensitivity and protect non-release assertions."""
import json
from pathlib import Path

P=Path(__file__).resolve().parents[1]/'projects/cyberdeck_structural_validation_20261021'

def test_base_support_sensitivity_is_not_physical_bolt_validation():
    alternate=json.loads((P/'P2_BASE_COLLAR_SUPPORT_SENSITIVITY_10_8.json').read_text())
    initial=json.loads((P/'P2_BASE_CORRECT_PCB_SEAT.json').read_text())
    assert alternate['part']=='base'
    assert alternate['collar_outer_radius_mm']==2.45
    assert alternate['real_fastener_preload_modelled'] is False
    assert alternate['nonlinear_contact_modelled'] is False
    assert alternate['local_peak_stress_stable_in_tested_window'] is False
    assert alternate['fabrication_authorized'] is False
    for standard, enlarged in zip(initial['results'][:2],alternate['mesh_results']):
        assert standard['mesh_size_mm']==enlarged['mesh_size_mm']
        assert enlarged['peak_von_mises_mpa']<standard['peak_von_mises_mpa']
        assert enlarged['displacement_mm']<standard['displacement_mm']
        assert enlarged['reaction_z_balance_error_n']<1e-8
