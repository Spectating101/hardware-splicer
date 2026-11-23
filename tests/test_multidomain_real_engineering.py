"""Engineering controls exercised against real third-party artifacts when available."""
from __future__ import annotations
import base64
import json
from pathlib import Path
import shutil
import pytest

from hardware_splicer.ai_project_orchestrator import run_ai_project_orchestrator
from hardware_splicer.ai_project_tool_executor import (
    AIActionNotExecutable, execute_ai_project_action_preview,
)
from hardware_splicer.engineering_multidomain_sources import (
    inspect_repair_guide_html, inspect_scad_polyhedron,
)
from hardware_splicer.engineering_project_source_bundle import analyze_project_bundle
from hardware_splicer.engineering_cad_carrier import generate_registered_pcb_carrier
from hardware_splicer.engineering_source_ingestion import (
    EngineeringSourceIngestionRequest, MAX_ENGINEERING_SOURCE_BYTES, ingest_engineering_source,
)
from hardware_splicer.project_store import ProjectStore


def test_large_cad_sources_fit_bounded_32mb_limit():
    assert MAX_ENGINEERING_SOURCE_BYTES == 32*1024*1024
    assert 24624144 < MAX_ENGINEERING_SOURCE_BYTES


def test_missing_project_context_does_not_promote_pcb_drc():
    out=analyze_project_bundle({'other.kicad_pcb':b'(kicad_pcb (version 2024))'})
    assert out['project_context']=='missing'
    assert not out['software_checks']
    assert not out['release_authorized']


def test_read_repair_steps_from_real_psp_manual_not_double_count():
    ref=Path('/tmp/hs-real-repair-psp/umd-replacement.html')
    if not ref.exists():pytest.skip('live third-party guide not available')
    doc=inspect_repair_guide_html(ref.read_bytes())
    assert doc['status']=='indexed_real_repair_guide'
    assert doc['source_steps_extracted']==42
    assert doc['step_references'][0]['source_anchor']=='s8065'
    assert doc['step_references'][-1]['source_anchor']=='s8384'
    assert doc['procedural_category_counts']['battery_isolation']>0
    assert not doc['actual_device_inspected']
    assert not doc['physical_disassembly_authorized']


def test_real_scad_donor_frame_arm_has_measurements_without_assembly_claim():
    ref=Path('/tmp/hs_drone_reference_scan/DroneSkeleton/arm.scad')
    if not ref.exists():pytest.skip('donor geometry not available')
    doc=inspect_scad_polyhedron(ref.read_bytes())
    assert doc['status']=='parsed_polyhedron_vertices'
    assert doc['point_count']==56896
    assert doc['axis_span'][0]==374.515
    assert not doc['full_assembly_validated']


def test_model_source_aliases_are_exact_and_unknown_source_is_not_silently_repaired():
    snapshot={'engineeringSources':[
      {'source_id':'upload-real-abc','content_hash':'sha256:'+'1'*64,'metadata':{'original_filename':'frame.step'}},
    ]}
    def model(_prompt,**_kwargs):
      reply={'summary':'CAD analysis requested','requirements':[{'id':'r','statement':'Review frame','source_ids':['S1','S99']}],
        'open_questions':[],'architecture_candidates':[],
        'actions':[{'action_type':'inspect_registered_sources','title':'Inspect donor source',
                    'rationale':'Source CAD needed','inputs':{},'source_ids':['S1','S99']}]}
      return {'ok':True,'provider':'fake-only-in-test','model':'fake', 'content':json.dumps(reply)}
    sess=run_ai_project_orchestrator('frame-project',1,snapshot,mission='Review frame geometry',llm_callable=model)
    assert sess['actions'][0]['source_ids']==['upload-real-abc']
    assert sess['actions'][0]['unrecognized_source_ids']==['S99']
    assert sess['unrecognized_source_references']==['S99']
    assert sess['requirements'][0]['source_ids']==['upload-real-abc']
    assert not sess['power_on_authorized']


def test_bogus_source_attribution_blocks_execution(tmp_path):
    store=ProjectStore(tmp_path)
    store.save('invalid-refs',{'engineeringSources':[]})
    action={'action_id':'inspect-bad','action_type':'inspect_registered_sources',
            'status':'accepted','project_revision':1,'unrecognized_source_ids':['ghost'],
            'decision':{'decision':'accepted','reviewer':'assistant','decided_at':'now','executed':False}}
    with pytest.raises(AIActionNotExecutable,match='unrecognized'):
        execute_ai_project_action_preview(store,'invalid-refs',
            {'session_id':'audit-unknown','project_revision':1},action)


def test_actual_cyberdeck_board_cad_generation_creates_step_and_stl(tmp_path):
    ref=Path('/tmp/hs-capability-trial-20261020/reference/extracted')
    python=Path.home() / '.local/share/hardware-splicer/cad-venv/bin/python'
    names=['RPI_Dev_1.kicad_pcb','RPI_Dev_1.kicad_pro']
    if not python.exists() or not shutil.which('kicad-cli') or not all((ref/n).exists() for n in names):
        pytest.skip('real CAD and PCB source unavailable')
    store=ProjectStore(tmp_path/'store')
    desc=[]
    for name in names:
        req=EngineeringSourceIngestionRequest(project_id='cyberdeck',filename=name,
              content_base64=base64.b64encode((ref/name).read_bytes()).decode())
        resp=ingest_engineering_source(req,project_root=store.root)
        desc.append(resp.source_descriptor)
    created=generate_registered_pcb_carrier('cyberdeck',desc,tmp_path/'cad',project_root=store.root)
    assert created['status']=='generated_valid_solid_candidate'
    assert created['carrier_outer_mm']['x']>created['board_bbox_mm']['x']
    assert created['validated_single_solid']
    assert len(created['generated_artifacts'])==2
    assert all((tmp_path/'cad'/art['name']).stat().st_size>1000 for art in created['generated_artifacts'])
    assert not created['functional_part_fit_verified']
    assert not created['build_authorized']
