#!/usr/bin/env python3
"""Independent control: run actual FEM from the unified software action.

Dimensions/load are declared controls, never measurements of drone hardware.
"""
from pathlib import Path
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from hardware_splicer.project_store import ProjectStore
from hardware_splicer.ai_project_tool_executor import execute_ai_project_action_preview

root=Path('/tmp/hs-unified-cross-domain-20261021')
project='hs-unified-structural-calibration'
store=ProjectStore(root/'store')
if (store.root/project/'project.json').exists():
    raise ValueError('refusing to overwrite existing FEM trial')
input_spec=json.loads((ROOT/'examples/mechanical/mecha_simple_plate_bracket.json').read_text())
request={'design':{'bracket':input_spec['bracket']},'mode':'run',
         'analysis_purpose':'Controlled two-hole bracket numerical model, not real donor interfaces'}
store.save(project,{'projectId':project,'engineeringLayerRequests':{'mechanical':request},
                   'fabrication_authorized':False,'release_authorized':False},
           metadata={'source':'calibration_user-authorized-software-only'})
action={'action_id':'calibrate-two-pin-contact', 'action_type':'review_mechanical_layer',
        'status':'accepted','project_revision':1,'source_ids':[],
        'decision':{'decision':'accepted','reviewer':'operator-software-calibration',
                    'decided_at':'2026-10-21T01:00:00+08:00','executed':False}}
result=execute_ai_project_action_preview(store,project,
         {'session_id':'session-software-calibration','project_revision':1},action)
(root/'structural_calibration_result.json').write_text(json.dumps(result,indent=2)+'\n')
print('CALIBRATION',result['status'],result['summary'],'PHYSICAL_AUTH',result['physical_authority_unchanged'],flush=True)
