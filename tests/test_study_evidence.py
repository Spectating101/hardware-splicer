"""Revision-bound study checks: a changed requirement makes earlier checks stale.

The executable fixture below is registered as ``fielddeck-5`` so the replay goes
through the same engine path as the real case (parent sources, archived adapter).
Its two checks mirror the real ones: a runtime target and a source margin.
The last test replays the real Fielddeck 5 study when its native runtime exists.
"""
import functools
from hashlib import sha256
import importlib.util
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from hardware_splicer import digital_cases as cases
from hardware_splicer import digital_project as digital
from hardware_splicer.digital_engine import DigitalStudyEngine
from hardware_splicer.digital_project_api import create_digital_project_router
from hardware_splicer.engineering_assurance_api import create_engineering_assurance_router
from hardware_splicer.jobs import JobBackend, JobStore
from hardware_splicer.project_store import ProjectStore

ROOT = Path(__file__).resolve().parents[1]

BUILD = '''from pathlib import Path
import json
p=Path(__file__).resolve().parent
r=json.loads((p/'requirements.json').read_text())
runtime=round(15/r['load_w'],3)
margin=round(10-r['load_w'],3)
checks=[{'id':'work_runtime','actual':runtime,'limit':r['minimum_work_runtime_h'],'unit':'h',
         'passed':runtime>=r['minimum_work_runtime_h']},
        {'id':'source_margin','actual':margin,'limit':r['minimum_margin_w'],'unit':'W',
         'passed':margin>=r['minimum_margin_w']}]
report={'case_id':'fielddeck-5','requirements':r,'constraints':checks,
        'metrics':{'runtime_h':runtime,'margin_w':margin},'requirements_met':all(c['passed'] for c in checks)}
(p/'parts/body.step').write_text('fixture:'+str(r['load_w']))
(p/'reports/engineering.json').write_text(json.dumps(report))
'''

VERIFY = '''from pathlib import Path
import functools
from hashlib import sha256
import json
p=Path(__file__).resolve().parent
e=json.loads((p/'reports/engineering.json').read_text())
hashes={n:sha256((p/n).read_bytes()).hexdigest() for n in ('parts/body.step','reports/engineering.json')}
(p/'reports/verification.json').write_text(json.dumps({'case_id':'fielddeck-5','artifact_integrity':True,
    'artifact_sha256':hashes,'engineering_acceptance':e['requirements_met']}))
'''


def _declaration(build_sha, **checks):
    return {'evaluator_sha256': {'build.py': build_sha}, 'checks': checks}


@pytest.fixture
def chain(tmp_path, monkeypatch):
    source = tmp_path / 'fixture-source'
    source.mkdir()
    (source / 'build.py').write_text(BUILD)
    (source / 'verify.py').write_text(VERIFY)
    case = cases.RegisteredCase(
        'fielddeck-5', 'Runtime fixture', source, ('build.py', 'verify.py'),
        ('parts/body.step', 'reports/engineering.json', 'reports/verification.json'),
        ('build.py', 'verify.py'), 'verify.py', 'reports/engineering.json', 'reports/verification.json',
        {'minimum_work_runtime_h': (2.5, .1, 24), 'load_w': (5, 1, 9), 'minimum_margin_w': (1, 0, 10)})
    monkeypatch.setitem(cases.CASES, case.case_id, case)
    build_sha = sha256(BUILD.encode()).hexdigest()
    monkeypatch.setitem(cases.CHECK_REQUIREMENTS, 'fielddeck-5', _declaration(
        build_sha, work_runtime=('minimum_work_runtime_h', 'load_w'), source_margin=('load_w', 'minimum_margin_w')))
    monkeypatch.setattr(digital, 'native_python', lambda: sys.executable)
    monkeypatch.setattr(digital, 'runtime_for_case', lambda *_: {'available': True, 'setup_hint': ''})
    store = ProjectStore(tmp_path / 'projects')
    backend = JobBackend(JobStore(tmp_path / 'jobs.db'), worker_count=0)
    engine = DigitalStudyEngine(store, backend)
    app = FastAPI()
    app.include_router(create_digital_project_router(store, backend))
    app.include_router(create_engineering_assurance_router(store))
    yield engine, TestClient(app), build_sha
    backend.stop()


def _delta(client, project, base=1, candidate=2):
    response = client.post(f'/v1/projects/{project}/engineering/assurance/evidence-delta',
                           json={'base_revision': base, 'candidate_revision': candidate})
    assert response.status_code == 200, response.text
    return response.json()


def _change(engine, project, **requirements):
    current = engine.study(project)
    result = engine.run_revision(project, base_revision=current['revision'],
                                 requirements={**current['summary']['requirements'], **requirements})
    assert result['ok'], result
    return result['study']


def test_revision_checks_are_assurance_outputs_bound_to_their_run(chain):
    engine, client, _ = chain
    project = engine.create(case_id='fielddeck-5')['project']['project_id']
    body = client.get(f'/v1/projects/{project}/engineering/assurance?revision=1').json()['assurance']
    checks = {row['local_id']: row for row in body['outputs'] if row['kind'] == 'check'}
    assert set(checks) == {'work_runtime', 'source_margin'}
    run = engine.study(project, 1)
    assert checks['work_runtime']['evidence']['revision'] == 1
    assert checks['work_runtime']['evidence']['run_id'] == run['run_id']
    assert checks['work_runtime']['evidence']['package_sha256'] == run['artifact_manifest']['STUDY.zip']['sha256']
    assert checks['work_runtime']['dependency_declaration'] == 'declared_for_evaluator'
    assert 'requirement:minimum_margin_w' not in checks['work_runtime']['dependency_ids']
    assert body['status'] == 'bounded'
    # Passing checks are digital evidence only; nothing becomes ready.
    assert body['authority_state'] == {'fabrication_ready': False, 'power_on_ready': False, 'evidence_complete': False,
                                       'physical_authority_granted': False, 'authority_effect': 'none'}


def test_changed_target_makes_the_earlier_check_stale_and_keeps_the_failure(chain):
    engine, client, _ = chain
    project = engine.create(case_id='fielddeck-5')['project']['project_id']
    before = client.get(f'/v1/projects/{project}/engineering/assurance?revision=1').json()['assurance']['study']
    _change(engine, project, minimum_work_runtime_h=3.5)
    body = _delta(client, project)
    checks = body['evidence_delta']['study_checks']
    assert checks['changed_dependencies'] == [
        {'dependency_id': 'requirement:minimum_work_runtime_h', 'before': 2.5, 'after': 3.5}]
    [stale] = checks['stale_outputs']
    assert stale['metadata']['node_id'] == 'check:work_runtime'
    assert stale['metadata']['revision'] == 1 and stale['metadata']['passed'] is True
    assert stale['metadata']['counts_for_candidate'] is False
    assert stale['metadata']['rerun'] == {'passed': False, 'actual': 3.0, 'limit': 3.5, 'unit': 'h', 'revision': 2,
                                          'run_id': engine.study(project, 2)['run_id']}
    assert stale['reasons'] == [{'kind': 'changed_dependency', 'ids': ['requirement:minimum_work_runtime_h']}]
    [retained] = checks['retained_outputs']
    assert retained['metadata']['node_id'] == 'check:source_margin'
    [failing] = checks['failing_outputs']
    assert failing['node_id'] == 'check:work_runtime' and failing['transition'] == 'regressed'
    # The earlier check sits in the generic stale list too, never in the retained one.
    assert stale in body['evidence_delta']['affected_outputs']
    assert stale not in body['evidence_delta']['retained_outputs']
    assert checks['packages']['before']['sha256'] != checks['packages']['after']['sha256']
    assert checks['stale_counted_as_passing'] is False
    assert body['physical_authority_granted'] is False and checks['physical_authority_granted'] is False
    # The failing revision stays failing and blocked; the base revision is untouched.
    after = client.get(f'/v1/projects/{project}/engineering/assurance?revision=2').json()['assurance']
    assert after['status'] == 'blocked' and after['summary']['failed_check_count'] == 1
    assert after['authority_state']['physical_authority_granted'] is False
    again = client.get(f'/v1/projects/{project}/engineering/assurance?revision=1').json()['assurance']['study']
    assert again == before


def test_declaration_only_narrows_for_its_exact_evaluator(chain, monkeypatch):
    engine, client, _ = chain
    monkeypatch.setitem(cases.CHECK_REQUIREMENTS, 'fielddeck-5', _declaration(
        '0' * 64, work_runtime=('minimum_work_runtime_h', 'load_w'), source_margin=('load_w', 'minimum_margin_w')))
    project = engine.create(case_id='fielddeck-5')['project']['project_id']
    _change(engine, project, minimum_work_runtime_h=3.5)
    checks = _delta(client, project)['evidence_delta']['study_checks']
    assert {row['metadata']['node_id'] for row in checks['stale_outputs']} == {'check:work_runtime', 'check:source_margin'}
    assert {row['metadata']['dependency_declaration'] for row in checks['stale_outputs']} == {'every_study_input'}
    assert checks['retained_outputs'] == []


def test_a_wrong_declaration_cannot_retain_a_check_whose_rerun_differs(chain, monkeypatch):
    engine, client, build_sha = chain
    # Declared as reading nothing, but source_margin really reads load_w.
    monkeypatch.setitem(cases.CHECK_REQUIREMENTS, 'fielddeck-5', _declaration(
        build_sha, work_runtime=('minimum_work_runtime_h',), source_margin=()))
    project = engine.create(case_id='fielddeck-5')['project']['project_id']
    _change(engine, project, load_w=6)
    checks = _delta(client, project)['evidence_delta']['study_checks']
    stale = {row['metadata']['node_id']: row for row in checks['stale_outputs']}
    assert set(stale) == {'check:work_runtime', 'check:source_margin'}
    assert stale['check:source_margin']['reasons'][-1] == {'kind': 'rerun_result_differs', 'ids': ['check:source_margin']}


def test_unchanged_requirements_retain_every_check(chain):
    engine, client, _ = chain
    project = engine.create(case_id='fielddeck-5')['project']['project_id']
    _change(engine, project)
    checks = _delta(client, project)['evidence_delta']['study_checks']
    assert checks['changed_dependencies'] == [] and checks['stale_outputs'] == []
    assert {row['metadata']['node_id'] for row in checks['retained_outputs']} == {'check:work_runtime', 'check:source_margin'}


def test_non_digital_projects_have_no_study_projection(tmp_path):
    store = ProjectStore(tmp_path / 'projects')
    store.save('plain', {'projectId': 'plain', 'mode': 'greenfield'}, expected_revision=0)
    app = FastAPI()
    app.include_router(create_engineering_assurance_router(store))
    body = TestClient(app).get('/v1/projects/plain/engineering/assurance').json()['assurance']
    assert body['study'] is None and body['summary']['check_count'] == 0


def test_fielddeck5_declaration_names_the_current_evaluator_files():
    declared = cases.CHECK_REQUIREMENTS['fielddeck-5']
    for name, digest in declared['evaluator_sha256'].items():
        assert sha256((ROOT / name).read_bytes()).hexdigest() == digest, (
            f'{name} changed: re-read which requirements each check uses, then update the declaration')
    assert set(declared['checks']) == {'work_runtime', 'ordinary_source_margin', 'high_keyboard_supply_limit'}
    assert set().union(*map(set, declared['checks'].values())) <= set(cases.FIELDDECK_5.requirements)


@functools.cache
def _demo():
    spec = importlib.util.spec_from_file_location('demo_revision_staleness', ROOT / 'scripts/demo_revision_staleness.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _replay(engine, client, **kwargs):
    demo = _demo()

    def call(method, path, body=None):
        response = client.request(method, path, json=body)
        return response.status_code, response.json()

    def wait(job_id):
        project = engine.backend.store.get_job(job_id).options['payload']['project_id']
        return engine.run_job(project, job_id)['job']

    return demo, demo.run_chain(call, wait, **kwargs)


def test_demo_script_replays_the_chain_with_its_negative_case(chain):
    engine, client, _ = chain
    project = engine.create(case_id='fielddeck-5')['project']['project_id']
    demo, report = _replay(engine, client, project_id=project)
    assert report['problems'] == []
    assert report['input']['revision'] == 1 and report['revision']['revision'] == 2
    assert report['revision']['parent_revision'] == 1 and report['base_revision_unchanged'] is True
    assert [row['check'] for row in report['assessment']['stale']] == ['check:work_runtime']
    assert report['assessment']['stale'][0]['from_revision'] == 1
    assert [row['node_id'] for row in report['assessment']['failing']] == ['check:work_runtime']
    assert report['revision']['requirements_met'] is False
    assert report['physical_authority_granted'] is False and report['ready'] is False
    text = demo.render(report)
    assert 'STALE    check:work_runtime from revision 1' in text and 'FAILING  check:work_runtime in revision 2' in text
    # A second replay refuses to re-apply the same target to the changed revision.
    with pytest.raises(demo.ChainError, match='already has'):
        _replay(engine, client, project_id=project)


def test_real_fielddeck5_study_replays_the_runtime_target_change(tmp_path):
    if not digital.runtime_for_case('fielddeck-5')['available']:
        pytest.skip('Fielddeck 5 native runtime (CadQuery, Pydantic v2) is not available; '
                    'set HARDWARE_SPLICER_DIGITAL_PYTHON')
    store = ProjectStore(tmp_path / 'projects')
    backend = JobBackend(JobStore(tmp_path / 'jobs.db'), worker_count=0)
    try:
        engine = DigitalStudyEngine(store, backend)
        app = FastAPI()
        app.include_router(create_digital_project_router(store, backend))
        app.include_router(create_engineering_assurance_router(store))
        client = TestClient(app)
        project = engine.create(case_id='fielddeck-5')['project']['project_id']
        _, report = _replay(engine, client, project_id=project)
    finally:
        backend.stop()
    assert report['problems'] == []
    assessment = report['assessment']
    assert assessment['changed_dependencies'] == [
        {'dependency_id': 'requirement:minimum_work_runtime_h', 'before': 2.5, 'after': 3.5}]
    assert [row['check'] for row in assessment['stale']] == ['check:work_runtime']
    assert {row['check'] for row in assessment['retained']} == {'check:ordinary_source_margin',
                                                                 'check:high_keyboard_supply_limit'}
    assert all(row['declaration'] == 'declared_for_evaluator' for row in assessment['stale'] + assessment['retained'])
    [failing] = assessment['failing']
    assert failing['node_id'] == 'check:work_runtime' and failing['passed'] is False
    assert failing['actual'] < failing['limit'] == 3.5
