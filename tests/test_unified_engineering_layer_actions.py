"""Real engines through existing explicitly accepted, revision-pinned AI actions."""
from __future__ import annotations
import json
from pathlib import Path
import pytest

from hardware_splicer.engineering_layer_reviews import (
    prepare_declared_enclosure,screen_declared_chemistry,screen_declared_mechanics,
)
from hardware_splicer.ai_project_tool_executor import execute_ai_project_action_preview
from hardware_splicer.project_store import ProjectStore

ROOT=Path(__file__).resolve().parents[1]

def _action(atype):
    return {'action_id':'review-'+atype,'action_type':atype,
            'project_revision':1,'status':'accepted','source_ids':[],
            'decision':{'decision':'accepted','reviewer':'software-only-reviewer',
                        'decided_at':'2026-10-21T01:00:00+08:00','executed':False}}

def _run(tmp_path, atype, request):
    project='unified-hardware-review'
    store=ProjectStore(tmp_path)
    store.save(project,{'engineeringLayerRequests':request})
    return execute_ai_project_action_preview(store,project,
               {'session_id':'session-unified','project_revision':1},_action(atype))


def test_undetermined_psp_battery_and_contact_produce_chemical_stop(tmp_path):
    req={'chemistry':{'task':'clean_contacts','primary_material':'unknown',
                      'material_identity':'unknown','electrical_state':'unknown',
                      'battery_status':'unknown'}}
    action=_run(tmp_path,'review_practical_chemistry',req)
    assert action['status']=='succeeded'
    assert action['summary']['decision']=='stop_and_escalate'
    artifact=tmp_path/'unified-hardware-review'/action['artifact']['project_relative_path']
    result=json.loads(artifact.read_text())
    assert 'battery_not_confirmed_removed' in str(result['evaluation'])
    assert not result['chemical_clearance_authorized']
    assert not action['release_authorized']


def test_caller_claiming_verified_substrate_cannot_prove_material(tmp_path):
    req={'chemistry':{'task':'bond_joint','primary_material':'PP',
                      'material_identity':'verified','electrical_state':'off',
                      'battery_status':'removed'}}
    action=_run(tmp_path,'review_practical_chemistry',req)
    assert action['status']=='succeeded'
    assert action['summary']['material_identity_downgraded'] is True
    artifact=tmp_path/'unified-hardware-review'/action['artifact']['project_relative_path']
    data=json.loads(artifact.read_text())
    assert not data['independent_material_compatibility_verified']
    assert not data['chemical_clearance_authorized']


def test_drone_compound_geometry_unqualified_for_contact_load_model(tmp_path):
    req={'mechanical':{'design':{'assembly':{'name':'X500-and-donor-arms'}},'mode':'run'}}
    action=_run(tmp_path,'review_mechanical_layer',req)
    assert action['status']=='succeeded'
    assert action['summary']['mechanical_scope']=='unsupported_mechanical_topology'
    assert action['summary']['numerical_status'] is None
    assert not action['release_authorized']


def test_referenced_two_hole_bracket_advisory_never_claims_fem(tmp_path):
    req={'mechanical':{'design':{'bracket':{
        'name':'plate','w_mm':60,'d_mm':20,'t_mm':4,
        'hole_d_mm':3.2,'hole_spacing_mm':40}},'mode':'advisory'}}
    action=_run(tmp_path,'review_mechanical_layer',req)
    assert action['status']=='succeeded'
    assert action['summary']['mechanical_scope']=='available_not_run'
    assert action['summary']['status']=='advisory_only'


def test_native_solidcraft_concept_in_agent_package_not_a_print(tmp_path):
    spec=json.loads((ROOT/'examples/printed_casing/conceptual_salvage_controller.json').read_text())
    action=_run(tmp_path,'prepare_printed_enclosure_concept',{'enclosure':spec})
    assert action['status']=='succeeded'
    assert action['summary']['solidcraft_command_count'] >= 20
    assert not action['summary']['native_cad_executed']
    assert not action['summary']['print_authorized']
    artifact=tmp_path/'unified-hardware-review'/action['artifact']['project_relative_path']
    data=json.loads(artifact.read_text())
    assert data['plan']['real_printer_connected'] is False
    assert data['plan']['slicing_performed'] is False


def test_absent_project_layer_requests_cannot_be_filled_by_model(tmp_path):
    for kind in ('review_mechanical_layer','review_practical_chemistry','prepare_printed_enclosure_concept'):
        result=_run(tmp_path/kind,kind,{})
        assert result['status']=='failed'
        assert not result['release_authorized']
