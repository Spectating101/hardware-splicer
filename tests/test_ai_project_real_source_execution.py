"""Exercise accepted, software-only ERC/DRC actions against actual archived sources."""
from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
from hardware_splicer.ai_project_tool_executor import execute_ai_project_action_preview
from hardware_splicer.project_store import ProjectStore
from hardware_splicer.engineering_source_ingestion import (
    EngineeringSourceIngestionRequest, ingest_engineering_source,
)
import base64


def _action(kind):
    return {'action_id':'action-'+kind, 'action_type':kind,
            'project_revision':1, 'status':'accepted',
            'decision':{'decision':'accepted','reviewer':'delegated-software-review',
                        'decided_at':'2026-10-20T23:00:00Z','executed':False}}


def test_missing_registered_complete_project_fails_and_records_no_fake_check(tmp_path):
    store=ProjectStore(tmp_path)
    store.save('example',{'engineeringSources':[]})
    session={'session_id':'session-real','project_revision':1}
    result=execute_ai_project_action_preview(store,'example',session,_action('run_drc'))
    assert result['status']=='failed'
    assert not result['release_authorized']
    assert 'rule_finding_count' not in result['summary']


def test_real_registered_project_model_action_runs_erc(tmp_path):
    source=Path('/tmp/hs-capability-trial-20261020/reference/extracted')
    names=['RPI_Dev_1.kicad_pro','RPI_Dev_1.kicad_sch','RPI_Dev_1.kicad_pcb']
    import shutil
    if not all((source/n).is_file() for n in names) or not shutil.which('kicad-cli'):
        pytest.skip('archived real project unavailable')
    store=ProjectStore(tmp_path)
    refs=[]
    for n in names:
        response=ingest_engineering_source(EngineeringSourceIngestionRequest(
            project_id='real-source',filename=n,content_base64=base64.b64encode((source/n).read_bytes()).decode()),
            project_root=store.root)
        refs.append(response.source_descriptor)
    store.save('real-source',{'engineeringSources':refs})
    session={'session_id':'session-real','project_revision':1}
    result=execute_ai_project_action_preview(store,'real-source',session,_action('run_erc'))
    assert result['status']=='succeeded'
    assert result['summary']['rule_finding_count']==43
    assert result['summary']['source_set_sha256'].startswith('sha256:')
    assert result['summary']['check']=='erc'
    assert result['summary']['manufacturing_approved'] is False
    assert not result['release_authorized']
