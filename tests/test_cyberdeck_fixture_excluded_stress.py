"""Keep support-neighborhood stress separate without hiding global peaks."""
import json
from pathlib import Path

P=Path(__file__).resolve().parents[1]/'projects/cyberdeck_structural_validation_20261021'

def test_fixture_excluded_stress_is_not_global_stress():
    d=json.loads((P/'P2_LID_STRESS_OUTSIDE_FIXTURE_4_3.json').read_text())
    assert d['support_mode']=='normal_only'
    assert not d['fabrication_authorized']
    rows=d['mesh_results']
    for r in rows:
        assert 0 < r['outside_4mm_screw_xy_peak_von_mises_mpa'] < r['peak_von_mises_mpa']
        assert r['outside_4mm_screw_xy_rms_von_mises_mpa'] > 0
        assert r['reaction_z_balance_error_n']<1e-8
    assert abs(rows[0]['outside_4mm_screw_xy_peak_von_mises_mpa']-rows[1]['outside_4mm_screw_xy_peak_von_mises_mpa'])/rows[0]['outside_4mm_screw_xy_peak_von_mises_mpa']<.04
    assert d['local_peak_stress_stable_in_tested_window'] is False
