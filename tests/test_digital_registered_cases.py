"""Case dispatch, persistence and rejection tests, separate from native CAD proofs.

The tiny executable case below deliberately has no CAD claim. It isolates the
engine lifecycle so the real device tests can concentrate on native geometry.
"""
from dataclasses import replace
from pathlib import Path
import importlib.util
import json
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from hardware_splicer import digital_cases as cases
from hardware_splicer import digital_project as digital
from hardware_splicer.digital_engine import DigitalStudyEngine
from hardware_splicer.digital_engine_cli import parser, dispatch
from hardware_splicer.digital_project_api import create_digital_project_router
from hardware_splicer.jobs import JobBackend, JobStore
from hardware_splicer.project_store import CorruptProject, ProjectStore


BUILD = '''from pathlib import Path
import json
p=Path(__file__).resolve().parent
r=json.loads((p/'requirements.json').read_text())
metric=r['load_a']*5
report={'case_id':'test-device','requirements':r,'metrics':{'power_w':metric},
        'constraints':[{'id':'power','passed':metric<=r['maximum_power_w'],
                        'actual':metric,'limit':r['maximum_power_w'],'unit':'W'}],
        'requirements_met':metric<=r['maximum_power_w']}
(p/'parts/body.step').write_text('pipeline-fixture:'+str(metric))
(p/'reports/engineering.json').write_text(json.dumps(report))
'''

VERIFY = '''from pathlib import Path
import json
p=Path(__file__).resolve().parent
r=json.loads((p/'requirements.json').read_text())
e=json.loads((p/'reports/engineering.json').read_text())
assert e['metrics']['power_w']==r['load_a']*5
assert (p/'parts/body.step').read_text()=='pipeline-fixture:'+str(r['load_a']*5)
(p/'reports/verification.json').write_text(json.dumps({'artifact_integrity':True}))
'''


@pytest.fixture
def registered_engine(tmp_path, monkeypatch):
    source = tmp_path / 'registered-source'
    source.mkdir()
    (source / 'build.py').write_text(BUILD)
    (source / 'verify.py').write_text(VERIFY)
    case = cases.RegisteredCase(
        'test-device', 'Executable pipeline fixture', source, ('build.py', 'verify.py'),
        ('parts/body.step', 'reports/engineering.json', 'reports/verification.json'),
        ('build.py', 'verify.py'), 'verify.py', 'reports/engineering.json', 'reports/verification.json',
        {'load_a': (1, .1, 3), 'maximum_power_w': (8, .1, 20)})
    monkeypatch.setitem(cases.CASES, case.case_id, case)
    monkeypatch.setattr(digital, 'native_python', lambda: sys.executable)
    monkeypatch.setattr(digital, 'runtime_for_case', lambda *_: {'available': True, 'setup_hint': ''})
    backend = JobBackend(JobStore(tmp_path / 'jobs.db'), worker_count=0)
    engine = DigitalStudyEngine(ProjectStore(tmp_path / 'projects'), backend)
    yield engine, case
    backend.stop()


def create(engine):
    return engine.create(case_id='test-device')['project']['project_id']


def client(engine):
    app = FastAPI()
    app.include_router(create_digital_project_router(engine.projects, engine.backend))
    return TestClient(app)


def test_registered_case_runs_isolated_stages_and_serves_nested_artifacts(registered_engine):
    engine, case = registered_engine
    before = {p.name: p.read_bytes() for p in case.root.iterdir()}
    project = create(engine)
    study = engine.study(project)
    assert study['summary']['case_id'] == 'test-device'
    assert study['summary']['metrics'] == {'power_w': 5}
    assert study['summary']['requirements_met'] is True
    assert engine.audit(project, native=True)['native_verification']['passed'] is True
    assert before == {p.name: p.read_bytes() for p in case.root.iterdir()}
    response = client(engine).get(f'/v1/projects/{project}/digital/revisions/1/artifacts/parts/body.step')
    assert response.status_code == 200
    assert response.text == 'pipeline-fixture:5.0'
    assert response.headers['content-disposition'].endswith('filename="body.step"')


def test_registered_revision_changes_real_computation_and_retains_failed_target(registered_engine, tmp_path):
    engine, _ = registered_engine
    project = create(engine)
    original = engine.study(project)
    result = engine.run_revision(project, base_revision=1, requirements={'load_a': 2},
                                 change_request='Increase the declared load')
    assert result['ok']
    assert result['study']['summary']['metrics']['power_w'] == 10
    assert result['study']['summary']['requirements_met'] is False
    assert engine.study(project, 1) == original
    comparison = engine.compare(project, before_revision=1, after_revision=2)
    assert comparison['metrics']['power_w']['delta'] == 5
    assert comparison['constraints'][0]['transition'] == 'regressed'
    assert engine.audit(project, native=True)['ok'] is True
    assert engine.export(project, tmp_path / 'failed-target.zip')['requirements_met'] is False
    copied = digital.duplicate_project(engine.projects, project, 'registered-copy')
    assert copied['snapshot']['digitalStudy']['case_id'] == 'test-device'
    assert engine.study('registered-copy')['summary'] == result['study']['summary']


@pytest.mark.parametrize('requirements', [
    {'load_a': True}, {'load_a': float('nan')}, {'load_a': 10**400},
    {'payload_mass_g': 3}, {'path': '/tmp/arbitrary.py'}, {'load_a': 4},
])
def test_case_requirements_cannot_escape_the_registered_contract(registered_engine, requirements):
    engine, _ = registered_engine
    project = create(engine)
    with pytest.raises(ValueError):
        engine.enqueue_revision(project, base_revision=1, requirements=requirements)
    assert engine.backend.store.list_digital_jobs(project) == []


def test_case_selection_is_server_owned_and_change_labels_do_not_claim_language_understanding(registered_engine):
    engine, _ = registered_engine
    with pytest.raises(ValueError, match='Unknown registered'):
        engine.create(case_id='../arbitrary.py')
    project = create(engine)
    with pytest.raises(ValueError, match='explicit numeric'):
        engine.enqueue_revision(project, base_revision=1, change_request='Make it more powerful')
    response = client(engine).post('/v1/digital/projects', json={'case_id': 'unknown'})
    assert response.status_code == 422
    listed = client(engine).get('/v1/digital/cases').json()
    assert listed['default_case_id'] == 'hs3g-b'
    assert 'fielddeck-7' in {row['case_id'] for row in listed['cases']}


def test_nested_directory_symlinks_are_rejected_even_with_identical_bytes(registered_engine, tmp_path):
    engine, _ = registered_engine
    project = create(engine)
    _, directory, _ = digital.load_run(engine.projects, project)
    (directory / 'parts').rename(tmp_path / 'parts-outside')
    (directory / 'parts').symlink_to(tmp_path / 'parts-outside', target_is_directory=True)
    assert not engine.audit(project)['ok']
    assert client(engine).get(f'/v1/projects/{project}/digital/revisions/1/artifacts/parts/body.step').status_code == 500


def test_native_audit_rejects_resealed_false_calculation_and_preserves_published_bytes(registered_engine, monkeypatch):
    engine, case = registered_engine
    project = create(engine)
    _, directory, seal = digital.load_run(engine.projects, project)
    report = cases.read(directory / case.calculation)
    report['metrics']['power_w'] = 6
    cases.write(directory / case.calculation, report)
    # Deliberately defeat byte integrity to exercise independent native recomputation.
    cases.seal_package(case, directory)
    seal['summary'] = cases.summarize(case, directory)
    for name in case.artifacts:
        seal['artifact_sha256'][name] = cases.sha(directory / name)
    import zipfile
    with zipfile.ZipFile(directory / 'STUDY.zip', 'w') as archive:
        for name in sorted(case.artifacts):
            archive.write(directory / name, name)
    seal['artifact_sha256']['STUDY.zip'] = cases.sha(directory / 'STUDY.zip')
    digital.write_json(directory / 'sealed-run.json', seal)
    before = {name: (directory / name).read_bytes() for name in case.artifacts}
    monkeypatch.setenv('PYTHONOPTIMIZE', '1')
    audit = engine.audit(project, native=True)
    assert audit['artifact_integrity'] is True
    assert audit['native_verification']['passed'] is False
    assert before == {name: (directory / name).read_bytes() for name in case.artifacts}


def test_job_cannot_switch_case_after_submission(registered_engine):
    engine, _ = registered_engine
    project = create(engine)
    submitted = engine.enqueue_revision(project, base_revision=1)
    job = engine.backend.store.claim_next(job_id=submitted['job']['job_id'])
    job.options['payload']['case_id'] = 'fielddeck-7'
    with pytest.raises(CorruptProject, match='different registered case'):
        digital.execute_study(engine.backend, job)
    assert engine.projects.load(project)['revision'] == 1


def test_fresh_generation_cannot_reuse_missing_output_from_a_prior_run(registered_engine):
    engine, case = registered_engine
    project = create(engine)
    (case.root / 'build.py').write_text('print("no output")\n')
    result = engine.run_revision(project, base_revision=1)
    assert not result['ok']
    assert engine.projects.load(project)['revision'] == 1
    assert engine.audit(project)['ok']


def test_cli_can_select_case_and_revise_explicit_json(registered_engine, tmp_path):
    engine, _ = registered_engine
    project = dispatch(engine, parser().parse_args(['init', '--case', 'test-device']))['project']['project_id']
    requirements = tmp_path / 'changes.json'
    requirements.write_text('{"load_a": 2}')
    result = dispatch(engine, parser().parse_args(['revise', project, '--base-revision', '1',
                                                   '--requirements', str(requirements)]))
    assert result['study']['summary']['metrics']['power_w'] == 10


def test_fielddeck_requirement_contract_matches_its_native_calculator():
    path = cases.FIELDDECK.root / 'study_contract.py'
    spec = importlib.util.spec_from_file_location('fielddeck_registry_contract_test', path)
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    assert {key: value[1:] for key, value in cases.FIELDDECK.requirements.items()} == native.BOUNDS
    design = json.loads((cases.FIELDDECK.root / 'design.json').read_text())
    assert cases.FIELDDECK.defaults() == native.validate_requirements(design=design)


def test_archived_adapter_survives_new_artifacts_bounds_and_entrypoints(registered_engine, monkeypatch, tmp_path):
    engine, case = registered_engine
    project = create(engine)
    before = engine.study(project)
    future = replace(case, inputs=(*case.inputs, 'future.py'), outputs=(*case.outputs, 'future.json'),
                     stages=('build.py', 'future.py'), verifier='future.py',
                     requirements={'load_a': (2, 2, 3), 'maximum_power_w': (8, .1, 20)})
    monkeypatch.setitem(cases.CASES, case.case_id, future)
    assert engine.study(project) == before
    assert engine.audit(project, native=True)['ok']
    assert engine.export(project, tmp_path / 'historical.zip')['ok']
    digital.duplicate_project(engine.projects, project, 'historical-copy')
    assert engine.study('historical-copy')['summary'] == before['summary']
    assert client(engine).get(f'/v1/projects/{project}/digital/revisions/1/artifacts/parts/body.step').status_code == 200


def test_archived_entrypoint_cannot_escape_its_sealed_inputs(registered_engine):
    engine, _ = registered_engine
    project = create(engine)
    _, directory, seal = digital.load_run(engine.projects, project)
    seal['case_contract']['stages'][-1] = '../../outside.py'
    seal['case_contract']['verifier'] = '../../outside.py'
    digital.write_json(directory / 'sealed-run.json', seal)
    assert not engine.audit(project, native=True)['ok']


def test_native_reports_cannot_promote_physical_authority(registered_engine):
    engine, case = registered_engine
    project = create(engine)
    _, directory, _ = digital.load_run(engine.projects, project)
    report = cases.read(directory / case.calculation)
    report['physical_authority_granted'] = True
    cases.write(directory / case.calculation, report)
    with pytest.raises(CorruptProject, match='physical authority'):
        cases.seal_package(case, directory)


@pytest.mark.parametrize('phase', ['baseline', 'revision'])
def test_optimized_host_cannot_disable_native_assertions(registered_engine, monkeypatch, phase):
    engine, case = registered_engine
    project = create(engine) if phase == 'revision' else None
    (case.root / 'verify.py').write_text('assert False, "independent check rejected"\n' + VERIFY)
    monkeypatch.setenv('PYTHONOPTIMIZE', '1')
    if phase == 'baseline':
        with pytest.raises(RuntimeError, match='independent check rejected'):
            create(engine)
    else:
        result = engine.run_revision(project, base_revision=1)
        assert result['job']['status'] == 'failed'
        assert engine.projects.load(project)['revision'] == 1
