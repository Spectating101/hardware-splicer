"""Recorded Policy Lab changes are rebound to saved revisions and served read-only.

Reuses the executable Fielddeck 5 fixture chain from test_change_dossier.py.
"""
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from hardware_splicer.change_dossier import build_change_evidence, write_change_evidence
from hardware_splicer.change_history import (ChangeHistoryError, change_dossier, record_change_evidence,
                                             record_cite_edition, record_proposal)
from hardware_splicer.change_history_api import create_change_history_router
from hardware_splicer.project_store import ProjectStore

from test_change_dossier import candidate_chain, chain, engine  # noqa: F401  (pytest fixtures)


def _json(path):
    return json.loads(path.read_bytes())


@pytest.fixture
def recorded(chain, candidate_chain, tmp_path):
    engine, project, root, files = candidate_chain
    first = chain[3]
    store = engine.projects
    record_proposal(store, _json(first['proposal']), _json(first['base_review']))
    record_proposal(store, _json(files['proposal']), _json(files['base_review']))
    packet = build_change_evidence(store, project, base_revision=2, candidate_revision=3, root=root, files=files)
    receipt = write_change_evidence(tmp_path / 'packet.json', packet)
    record_change_evidence(store, packet, receipt['sha256'])
    record_cite_edition(store, project, edition_id='a' * 64, bound_revision=3, packet_sha256=receipt['sha256'],
                        event='issued', status='current', head_revision=3)
    return engine, project, receipt['sha256']


def test_changes_are_rebound_to_their_applying_revisions(recorded):
    engine, project, packet_sha = recorded
    view = change_dossier(engine.projects, project)
    assert view['head_revision'] == 3 and view['physical_authority_granted'] is False
    first, second = view['changes']
    assert first['policy_decision'] == 'BLOCKED' and first['base_revision'] == 1
    assert first['requirement_changes'] == {'minimum_work_runtime_h': {'before': 2.5, 'after': 3.5}}
    # The target-only revision stays visibly failed.
    assert first['applied_revision']['revision'] == 2 and first['applied_revision']['requirements_met'] is False
    assert [c['id'] for c in first['applied_revision']['checks'] if not c['passed']] == ['work_runtime']
    # The base revision's checks come along so a reader can tell a raised requirement from a regression.
    base_runtime = next(c for c in first['base_checks'] if c['id'] == 'work_runtime')
    assert base_runtime['passed'] is True and base_runtime['limit'] == 2.5
    assert first['candidates'] == [] and first['change_evidence'] is None
    assert second['applied_revision']['revision'] == 3
    [candidate] = second['candidates']
    assert candidate['input'] == 'load_w' and candidate['physical_means'] == 'unknown / not tested'
    assert candidate['native_outcome']['native_value'] == 3.75 and candidate['native_outcome']['met'] is True
    assert second['change_evidence']['packet_sha256'] == packet_sha
    [edition] = view['cite_editions']
    assert edition['bound_revision'] == 3 and edition['stale_by_hs_head'] is False and view['cite_linked'] is True
    text = json.dumps(view).lower()
    assert '"ready"' not in text and 'approved' not in text


def test_a_newer_head_makes_a_recorded_edition_stale(recorded):
    engine, project, packet_sha = recorded
    current = engine.study(project)
    assert engine.run_revision(project, base_revision=3, requirements={**current['summary']['requirements'],
                                                                       'minimum_work_runtime_h': 3.0})['ok']
    record_cite_edition(engine.projects, project, edition_id='a' * 64, bound_revision=3, packet_sha256=packet_sha,
                        event='currency_check', status='stale', head_revision=4, reasons=['HS project is at revision 4'])
    [edition] = change_dossier(engine.projects, project)['cite_editions']
    assert edition['stale_by_hs_head'] is True
    assert edition['latest_check']['status'] == 'stale' and edition['latest_check']['head_revision'] == 4


def test_records_that_do_not_bind_saved_revisions_are_refused(recorded, tmp_path):
    engine, project, packet_sha = recorded
    store = engine.projects
    with pytest.raises(ChangeHistoryError, match='canonical bytes'):
        record_change_evidence(store, {'physical_authority_granted': False, 'project_id': project}, packet_sha)
    with pytest.raises(ChangeHistoryError):
        record_cite_edition(store, project, edition_id='a' * 64, bound_revision=3, packet_sha256=packet_sha,
                            event='issued', status='approved')
    proposal = {'schema': 'hardware_splicer.policy_feedback_proposal.v1', 'status': 'validated_proposal',
                'physical_authority_granted': False, 'automatic_execution': False, 'project_id': project,
                'base_revision': 1, 'run_id': 'f' * 32, 'policy_decision': 'BLOCKED', 'source_binding': {}}
    with pytest.raises(ChangeHistoryError, match='base revision'):
        record_proposal(store, proposal, {'decision': 'BLOCKED', 'source_binding': {}, 'policy': {'id': 'x', 'version': '1'}})
    with pytest.raises(ChangeHistoryError, match='non-executing'):
        record_proposal(store, {**proposal, 'automatic_execution': True}, {})
    records = sorted((store.root / project / 'change-history').glob('*.json'))
    assert len(records) == 4  # nothing was added by the refusals


def test_api_serves_the_view_read_only(recorded, tmp_path):
    engine, project, _ = recorded
    app = FastAPI()
    app.include_router(create_change_history_router(engine.projects))
    client = TestClient(app)
    before = sorted(p.name for p in (engine.projects.root / project / 'change-history').glob('*'))
    body = client.get(f'/v1/projects/{project}/change-dossier').json()
    assert body['ok'] is True and len(body['change_dossier']['changes']) == 2
    assert sorted(p.name for p in (engine.projects.root / project / 'change-history').glob('*')) == before
    assert client.get('/v1/projects/digital-' + '0' * 32 + '/change-dossier').status_code == 404
    plain = ProjectStore(tmp_path / 'plain')
    plain.save('plain', {'projectId': 'plain', 'mode': 'greenfield'}, expected_revision=0)
    other = FastAPI()
    other.include_router(create_change_history_router(plain))
    response = TestClient(other).get('/v1/projects/plain/change-dossier')
    assert response.status_code == 422


def test_project_without_records_reports_no_changes_and_no_cite_link(engine):
    project = engine.create(case_id='fielddeck-5')['project']['project_id']
    view = change_dossier(engine.projects, project)
    assert view['changes'] == [] and view['cite_editions'] == [] and view['cite_linked'] is False
