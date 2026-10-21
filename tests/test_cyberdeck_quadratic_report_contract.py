"""Always-on CI checks for hash-bound structural results and non-authority.

No optional scientific dependencies are needed to validate that test claims
remain attached to the source CAD and that an FEM result does not grant release.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PROOF=ROOT/'projects/cyberdeck_structural_validation_20261021'


def _read(name:str)->dict:
    return json.loads((PROOF/name).read_text(encoding='utf-8'))


def test_quadratic_virtual_mechanics_evidence_stays_bound_to_source_revision():
    study=_read('P2_CORRECT_LOAD_VALIDATION.json')
    source=_read('source_edge_retention_report.json')
    manifest={x['filename']:x['sha256'] for x in source['generated_artifacts']}
    assert study['schema']=='hardware_splicer.corrected_cyberdeck_quadratic_FEM.v1'
    assert study['source_original_kicad_sha256']==source['source_board_sha256']
    assert study['CAD_SHA256s']=={
      'source_edge_capture_base.step':manifest['source_edge_capture_base.step'],
      'source_edge_capture_lid.step':manifest['source_edge_capture_lid.step']}
    assert study['new_physics_solver_implemented'] is False
    assert study['source_derived_load_area_constant_with_refinement'] is True
    assert 297.<study['contact_area_lid_mm2']<298.
    assert 299.<study['contact_area_base_mm2']<301.


def test_base_load_targets_original_board_seat_not_case_outside_face():
    study=_read('P2_CORRECT_LOAD_VALIDATION.json')
    source=_read('source_edge_retention_report.json')
    assert study['corrected_base_load_on_original_pcb_bottom_z_mm']==0.0
    assert study['base_load_faces_to_negative_z_n']==-1.0
    assert study['lid_load_faces_to_positive_z_n']==1.0
    assert study['base_corrected_top_face_results']['source_step_sha256']==study['CAD_SHA256s']['source_edge_capture_base.step']
    assert study['base_corrected_top_face_results']['relative_max_displacement_spread_in_tested_window']<0.035
    assert source['manufacturing_or_print_authorized'] is False


def test_simulated_material_is_not_misrepresented_as_physical_qualification():
    study=_read('P2_CORRECT_LOAD_VALIDATION.json')
    assert study['force_assumption_total_abs_N']==1
    assert study['load_and_material_measured'] is False
    assert study['number_of_actual_physical_specimens_tested']==0
    assert study['base_corrected_top_face_results']['peak_local_stress_convergence_accepted'] is False
    assert study['fabrication_authorized'] is False
    assert study['operational_safety_verified'] is False
    assert study['product_functional_confirmed'] is False
    assert study['original_published_cad_known_SW1_collision_mm3']>1


def test_original_or_derivative_unlicensed_cad_is_not_redistributed():
    assert not (PROOF/'source_edge_capture_base.step').exists()
    assert not (PROOF/'source_edge_capture_lid.step').exists()
