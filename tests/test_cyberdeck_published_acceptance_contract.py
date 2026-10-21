"""A published component-fit audit must match the exact packaged CAD bytes."""
from __future__ import annotations
import hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CASE=ROOT/'projects/cyberdeck_edge_retention_20261021'


def _sha(path:Path)->str:
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def test_published_retainer_reports_actual_source_bound_failed_component_fit():
    audit=json.loads((CASE/'INDEPENDENT_COMPONENT_AUDIT.json').read_text())
    worker=json.loads((CASE/'CAD_REPORT.json').read_text())
    assert audit['schema']=='hs.independent_partial_3d_clearance.v2'
    assert audit['original_kicad_pcb_sha256']==worker['source_board_sha256']
    assert audit['cad_case_step_sha256s']=={
        'base':_sha(CASE/'source_edge_capture_base.step'),
        'lid':_sha(CASE/'source_edge_capture_lid.step'),
    }
    assert audit['status']=='packaged_case_component_collision_found'
    assert audit['prior_reference_audit_matches_exact_packaged_cad_sha256s'] is False
    assert audit['prior_audit_result_reused'] is False
    assert audit['all_seven_original_model_placements_nominally_clear'] is False
    assert audit['source_original_model_hashes_verified'] is True
    assert audit['print_or_fabrication_authorized'] is False
    assert audit['publisher_3d_reference_coverage']=={'modelled':7,'expected_models':11,'no_3d_model':15}
    assert len(audit['independent_model_collisions'])==7
    by_ref={x['reference']:x for x in audit['independent_model_collisions']}
    assert by_ref['SW1']['lid_intersection_mm3']>=1.5
    assert by_ref['SW1']['both_halves_nominally_clear'] is False
    assert all(v['both_halves_nominally_clear'] for k,v in by_ref.items() if k!='SW1')
    assert len(audit['unresolved_model_references'])==4
    assert len(audit['untested_unmodelled_footprints'])==15


def test_checked_in_board_only_geometry_report_not_physical_authority():
    report=json.loads((CASE/'CAD_REPORT.json').read_text())
    checks=report['geometric_clearance_checks']
    assert checks['board_only_zero_interference_pass'] is True
    assert checks['source_pad_projection_no_lip_overlap_pass'] is True
    assert checks['source_tracks_and_vias_projected_keepouts_pass'] is True
    assert report['manufacturing_or_print_authorized'] is False
    assert report['released_for_fabrication'] is False
    assert report['connector_access_verified'] is False
