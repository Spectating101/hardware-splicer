"""Source-contour CAD validation and fail-closed project tool behavior."""
from __future__ import annotations
import base64
from pathlib import Path
import shutil
import pytest

from hardware_splicer.engineering_source_ingestion import (
    EngineeringSourceIngestionRequest,ingest_engineering_source,
)
from hardware_splicer.engineering_cad_edge_retention import generate_registered_pcb_edge_retention_candidate
from hardware_splicer.engineering_kicad_interface import inspect_board_interface_bytes
from hardware_splicer.project_store import ProjectStore

SOURCE_ROOT=(Path(__file__).resolve().parents[1]/
  '.cache/source-proofs/RPI_DEV_extracted/RPI Dev/RPI_Dev_1')


def _input_project(tmp_path):
    if not all((SOURCE_ROOT/name).exists() for name in ('RPI_Dev_1.kicad_pcb','RPI_Dev_1.kicad_pro')):
        pytest.skip('original third-party KiCad sample not restored in this environment')
    if not shutil.which('kicad-cli'):
        pytest.skip('KiCad command line tool unavailable')
    store=ProjectStore(tmp_path/'store')
    sources=[]
    for name in ('RPI_Dev_1.kicad_pcb','RPI_Dev_1.kicad_pro'):
        r=ingest_engineering_source(EngineeringSourceIngestionRequest(
          project_id='real-kicad-design',filename=name,
          content_base64=base64.b64encode((SOURCE_ROOT/name).read_bytes()).decode()),
          project_root=store.root)
        sources.append(r.source_descriptor)
    return store,sources


def test_incomplete_project_denies_edge_retention_design(tmp_path):
    with pytest.raises(ValueError,match='one registered KiCad board'):
        generate_registered_pcb_edge_retention_candidate('x',[],tmp_path/'out')
    with pytest.raises(ValueError,match='corresponding registered'):
        generate_registered_pcb_edge_retention_candidate('x',[
          {'content_hash':'sha256:'+'1'*64,'metadata':{'original_filename':'no_pro.kicad_pcb'}}],tmp_path/'out')


def test_actual_source_board_edge_capture_step_parts_no_interference(tmp_path):
    store,sources=_input_project(tmp_path)
    result=generate_registered_pcb_edge_retention_candidate(
        'real-kicad-design',sources,tmp_path/'generated',project_root=store.root)
    assert result['status']=='generated_collision_screened_edge_retention_candidate'
    assert result['source_outline_vertex_count']==33
    assert result['source_hole_misclassification_avoided']
    assert result['source_geometry_trace']['source_npht_feature_references']==['Q1']
    assert result['source_geometry_trace']['verified_board_mounting_footprints']==[]
    g=result['geometric_clearance_checks']
    assert g['board_only_zero_interference_pass']
    assert max(g['original_board_to_base_overlap_mm3'],g['original_board_to_lid_overlap_mm3'],
               g['base_to_lid_overlap_mm3'])<=0.02
    assert g['all_four_screw_centres_outside_board_AABB']
    assert g['source_pad_keepout_count']==23
    assert g['uncorrected_pad_keepout_overlap_mm3'] > 30
    assert g['corrected_pad_keepout_overlap_mm3'] <= 0.02
    assert g['source_pad_projection_no_lip_overlap_pass']
    assert len(result['external_lid_screw_centres_mm'])==4
    assert not result['board_corner_M3_holes_assumed']
    assert result['enclosure_outer_mm']=={'x':106.9,'y':77.3,'z':6.46}
    assert len(result['generated_artifacts'])==4
    assert all((tmp_path/'generated'/a['filename']).stat().st_size>1000
               for a in result['generated_artifacts'])
    assert result['pad_bounding_regions_excluded_from_candidate_lip']
    assert not result['connector_access_verified']
    assert not result['copper_edge_keepout_verified']
    assert not result['component_height_or_pad_clearance_verified']
    assert not result['manufacturing_or_print_authorized']


def test_nominal_outline_contains_curved_notch_and_no_false_board_mounts():
    if not (SOURCE_ROOT/'RPI_Dev_1.kicad_pcb').exists():
        pytest.skip('public source sample absent')
    audited=inspect_board_interface_bytes((SOURCE_ROOT/'RPI_Dev_1.kicad_pcb').read_bytes())
    if audited['status']=='pcbnew_not_available':pytest.skip('system pcbnew unavailable')
    assert audited['edge_cuts_profile_closed']
    assert audited['edge_cuts_profile_is_arc_tessellated']
    assert audited['edge_cuts_source_outline_count']==1
    assert len(audited['edge_cuts_profile_mm'])==33
    assert audited['explicit_mounting_footprint_refs']==[]
    assert audited['pad_count_all_layers']==145
    assert audited['nominal_edge_lip_pad_risk_candidate_count']==23
    assert any(34.90<p['x']<39.90 and p['y']>30 for p in audited['edge_cuts_profile_mm'])
    assert not audited['physical_fit_authorized']


def test_source_only_cad_prototype_is_not_blocked_by_missing_layer_request():
    from hardware_splicer.ai_project_orchestrator import build_ai_project_context,build_ai_project_prompt
    context=build_ai_project_context('test',1,{'engineeringLayerRequests':{}},mission='Source only CAD prototype')
    prompt=build_ai_project_prompt(context,max_actions=5)
    assert 'generate_board_edge_retention_candidate' in prompt
    assert 'They do NOT require engineeringLayerRequests' in prompt
    assert 'Those remain blocked' in prompt
