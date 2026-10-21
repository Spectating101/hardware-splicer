"""Prevent displacement-only convergence from authorizing structural claims.

These thresholds are screening diagnostics for one hypothetical load case,
not physical safety or a general-purpose mesh-convergence certificate.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'projects/cyberdeck_structural_validation_20261021'


def _pairs(filename):
    samples = json.loads((ROOT / filename).read_text())['results']
    assert len(samples) >= 2
    return samples[-2], samples[-1]


def _relative_change(before, after, key):
    assert before[key] > 0 and after[key] > 0
    return abs(after[key] - before[key]) / before[key]


def test_lid_near_mesh_displacement_and_rms_screen_only():
    coarse, fine = _pairs('P2_LID_FINE_EXACT_LOAD.json')
    assert coarse['mesh_size_mm'] > fine['mesh_size_mm']
    assert _relative_change(coarse, fine, 'displacement_mm') < .01
    assert _relative_change(coarse, fine, 'volume_integrated_von_mises_rms_mpa') < .01
    assert _relative_change(coarse, fine, 'peak_von_mises_mpa') < .03
    assert abs(coarse['integration_patch_area_mm2'] - fine['integration_patch_area_mm2']) < 1e-7
    assert max(coarse['reaction_z_balance_error_n'], fine['reaction_z_balance_error_n']) < 1e-8
    assert coarse['release_authorized'] is False and fine['release_authorized'] is False


def test_base_peak_stress_not_converged_even_if_displacement_is_stable():
    coarse, fine = _pairs('P2_BASE_CORRECT_PCB_SEAT.json')
    assert _relative_change(coarse, fine, 'displacement_mm') < .02
    assert _relative_change(coarse, fine, 'peak_von_mises_mpa') > .05
    assert fine['release_authorized'] is False


def test_earlier_first_order_false_convergence_is_preserved_as_counterexample():
    verdict = json.loads((ROOT / 'VALIDATION_VERDICT.json').read_text())
    assert verdict['extended_lid_result']['finer_mesh_overturns_apparent_3mesh_convergence'] is True
    assert verdict['overall_numerical_mesh_convergence_accepted'] is False
    assert verdict['structural_release_authorized'] is False


def test_actual_finer_quadratic_lid_overturns_local_peak_stress_screen():
    study = json.loads((ROOT / 'P2_LID_REFINEMENT_3_2P5_2.json').read_text())
    assert study['schema'] == 'hardware_splicer.quadratic_structural_screen.v1'
    assert study['part'] == 'lid'
    assert [r['mesh_size_mm'] for r in study['mesh_results']] == [3.0, 2.5, 2.0]
    assert study['global_elastic_response_stable_in_tested_window'] is False
    assert study['local_peak_stress_stable_in_tested_window'] is False
    assert all(c['local_peak_stress_change'] > .1 for c in study['mesh_comparisons'])
    assert max(r['reaction_z_balance_error_n'] for r in study['mesh_results']) < 1e-8
    areas = [r['integration_patch_area_mm2'] for r in study['mesh_results']]
    assert max(areas) - min(areas) < 1e-7
    assert study['fabrication_authorized'] is False
