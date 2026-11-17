"""Requirement interpretation, persistent evidence and native-job publication."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import copy
import json
from pathlib import Path
import shutil
import threading
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from hardware_splicer import digital_project as digital
from hardware_splicer.digital_project_api import create_digital_project_router
from hardware_splicer.jobs import JobBackend, JobStore
from hardware_splicer.project_api import create_project_router
from hardware_splicer.project_store import CorruptProject, ProjectStore, RevisionConflict


@pytest.fixture
def service(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path / 'projects')
    backend = JobBackend(JobStore(tmp_path / 'jobs.db'), worker_count=0)
    backend.project_store = store
    monkeypatch.setattr(digital, 'runtime', lambda: {'available': True, 'setup_hint': ''})
    app = FastAPI()
    app.include_router(create_digital_project_router(store, backend))
    app.include_router(create_project_router(store))
    return store, backend, TestClient(app)


def create(service):
    _, _, client = service
    response = client.post('/v1/digital/projects', json={})
    assert response.status_code == 201, response.text
    return response.json()['project']


@pytest.mark.parametrize('text,expected', [('Add 10 g of payload', 10), ('add 2.5 grams payload', 2.5),
                                          ('Set payload to 20 g', 20), ('set 3 g payload', 3)])
def test_requirement_changes_resolve_to_explicit_mass(text, expected):
    assert digital.requirement_tools().resolve({}, text)['payload_mass_g'] == expected


def test_changes_are_relative_to_saved_requirements_and_do_not_mutate_them():
    current = {'payload_mass_g': 12, 'gust_scale': 2, 'max_mass_g': 250}
    result = digital.requirement_tools().resolve(current, 'Remove 5 g of payload', {'gust_scale': 3})
    assert result == {'payload_mass_g': 7, 'gust_scale': 3, 'max_mass_g': 250}
    assert current['payload_mass_g'] == 12


@pytest.mark.parametrize('value', [{'payload_mass_g': -1}, {'payload_mass_g': 51}, {'gust_scale': 3.1},
                                  {'max_mass_g': 149}, {'payload_mass_g': True}, {'gust_scale': float('nan')},
                                  {'path': '/etc/passwd'}])
def test_invalid_or_unbounded_requirements_are_rejected(value):
    with pytest.raises(ValueError):
        digital.requirement_tools().validate(value)


def test_unsupported_design_language_is_not_silently_accepted():
    with pytest.raises(ValueError, match='Supported changes'):
        digital.requirement_tools().resolve({}, 'replace all motors with something faster')


def test_requirement_checks_are_unique_and_include_the_uncertainty_margin():
    model = {'mass_kg': .2449, 'inertia_off_diagonal_relative_max': .01}
    checks = digital.requirement_tools().constraints(model, {})
    assert len({check['id'] for check in checks}) == len(checks)
    uncertainty = next(c for c in checks if c['id'] == 'mass_uncertainty')
    assert uncertainty['margin'] == pytest.approx(.1)
    assert uncertainty['passed']


def test_project_starts_from_owned_verified_artifacts_and_survives_reload(service):
    store, _, client = service
    project = create(service)
    project_id = project['project_id']
    response = client.get(f'/v1/projects/{project_id}/digital').json()
    study = response['study']
    assert study['summary']['mass_g'] == pytest.approx(234.9)
    assert study['summary']['requirements_met'] is True
    assert study['summary']['physical_work_requested'] is False
    assert digital.describe(ProjectStore(store.root), project_id) == study
    viewer = client.get(study['artifacts']['VIEWER.html'])
    assert viewer.status_code == 200
    assert 'sandbox allow-scripts' in viewer.headers['content-security-policy']
    assert 'connect-src \'none\'' in viewer.headers['content-security-policy']
    assert 'model-data' in viewer.text
    assert len(response['history']) == 1


def test_unsupported_change_and_stale_base_never_queue_a_job(service):
    store, backend, client = service
    project = create(service); project_id = project['project_id']
    response = client.post(f'/v1/projects/{project_id}/digital/runs', json={
        'base_revision': 1, 'change_request': 'Invent new motors'})
    assert response.status_code == 422
    envelope = store.load(project_id)
    store.save(project_id, envelope['snapshot'], expected_revision=1)
    response = client.post(f'/v1/projects/{project_id}/digital/runs', json={
        'base_revision': 1, 'change_request': 'Add 10 g of payload'})
    assert response.status_code == 409
    assert backend.store.list_digital_jobs(project_id) == []


def test_submission_is_idempotent_and_records_resolved_requirements(service):
    _, backend, client = service
    project_id = create(service)['project_id']
    payload = {'base_revision': 1, 'change_request': 'Add 10 g of payload', 'request_id': str(uuid4())}
    url = f'/v1/projects/{project_id}/digital/runs'
    first = client.post(url, json=payload)
    second = client.post(url, json=payload)
    assert first.status_code == second.status_code == 202
    assert first.json()['job']['job_id'] == second.json()['job']['job_id']
    assert len(backend.store.list_digital_jobs(project_id)) == 1
    assert first.json()['resolved_requirements']['payload_mass_g'] == 10
    payload['change_request'] = 'Add 20 g of payload'
    assert client.post(url, json=payload).status_code == 409


def test_snapshot_put_cannot_forge_digital_results_or_replace_saved_study(service):
    _, _, client = service
    project = create(service); project_id = project['project_id']
    snapshot = copy.deepcopy(project['snapshot'])
    snapshot['digitalStudy']['requirements'] = {'payload_mass_g': 999}
    assert client.put(f'/v1/projects/{project_id}/snapshot', json={'snapshot': snapshot}).status_code == 422
    assert client.put(f'/v1/projects/{project_id}/snapshot', json={'snapshot': {'mode': 'greenfield'}}).status_code == 422


def test_tampered_or_linked_artifacts_are_never_served(service):
    store, _, client = service
    project_id = create(service)['project_id']
    study = digital.describe(store, project_id)
    _, directory, _ = digital.load_run(store, project_id)
    (directory / 'nominal.csv').write_text('forged')
    assert client.get(study['artifacts']['nominal.csv']).status_code == 500
    (directory / 'VIEWER.html').unlink()
    (directory / 'VIEWER.html').symlink_to(digital.CASE / 'reference/VIEWER.html')
    assert client.get(study['artifacts']['VIEWER.html']).status_code == 500
    assert client.get(f'/v1/projects/{project_id}/digital/revisions/1/artifacts/secret.env').status_code == 404


def test_duplicate_has_its_own_immutable_artifacts(service):
    store, _, client = service
    source = create(service)['project_id']
    response = client.post(f'/v1/projects/{source}/duplicate', json={'target_project_id': 'digital-copy'})
    assert response.status_code == 201, response.text
    clone = response.json()['project']
    assert clone['revision'] == 1
    assert clone['snapshot']['digitalStudy']['run_id'] != store.load(source)['snapshot']['digitalStudy']['run_id']
    store.delete(source)
    study = digital.describe(store, 'digital-copy')
    assert client.get(study['artifacts']['nominal.csv']).status_code == 200


def test_product_spa_fallback_does_not_shadow_digital_api(service, monkeypatch):
    import hardware_splicer.product_api as product
    store, backend, _ = service
    engine = FastAPI()
    engine.state.job_backend = backend
    @engine.get('/{spa_path:path}', name='splice_ui_spa')
    def fallback(spa_path: str):
        return {'spa': True}
    monkeypatch.setattr(product, 'create_engine_app', lambda: engine)
    app = product.create_product_app(store)
    client = TestClient(app)
    project = client.post('/v1/digital/projects', json={}).json()['project']
    response = client.get(f'/v1/projects/{project["project_id"]}/digital')
    assert response.status_code == 200
    assert 'study' in response.json()
    assert client.get('/some-ui-route').json() == {'spa': True}


def test_revision_publication_is_exclusive_across_store_instances(tmp_path, monkeypatch):
    import hardware_splicer.project_store as module
    root = tmp_path / 'projects'
    store = ProjectStore(root)
    store.save('shared', {'name': 'original'}, expected_revision=0)
    barrier = threading.Barrier(2)
    original_write = module._atomic_write_json
    def synchronized_write(path, value, **kwargs):
        if kwargs.get('exclusive'):
            barrier.wait(timeout=10)
        return original_write(path, value, **kwargs)
    monkeypatch.setattr(module, '_atomic_write_json', synchronized_write)
    def save(name):
        try:
            return ProjectStore(root).save('shared', {'name': name}, expected_revision=1)
        except RevisionConflict:
            return None
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(save, ['agent-one', 'agent-two']))
    winner, = [result for result in results if result]
    assert store.load('shared', 2) == winner
    assert store.load('shared', 1)['snapshot']['name'] == 'original'


def _claimed(service, change=''):
    _, backend, client = service
    project_id = create(service)['project_id']
    response = client.post(f'/v1/projects/{project_id}/digital/runs', json={'base_revision': 1, 'change_request': change})
    assert response.status_code == 202
    job = backend.store.claim_next()
    assert job
    return project_id, job


def _reuse_verified_baseline(monkeypatch):
    # Only the costly solver boundary is replaced in publication tests. The
    # separate native test below runs generation and independent verification.
    def command(backend, job, args, log):
        if '--out' in args:
            out = Path(args[args.index('--out') + 1])
            if Path(args[0]).name == 'verify_digital.py':
                # The verifier writes its receipt outside the package it inspects.
                shutil.copyfile(digital.CASE / 'reference' / 'verification.json', out)
            else:
                shutil.copytree(digital.CASE / 'reference', out,
                                ignore=shutil.ignore_patterns('__pycache__'))
        return 0
    monkeypatch.setattr(digital, '_command', command)


def test_successful_job_saves_exactly_one_revision_and_keeps_parent(service, monkeypatch):
    store, backend, _ = service
    project_id, job = _claimed(service)
    parent = store.load(project_id, 1)
    _reuse_verified_baseline(monkeypatch)
    digital.execute_study(backend, job)
    assert backend.store.get_job(job.job_id).status == 'succeeded'
    assert store.load(project_id)['revision'] == 2
    assert store.load(project_id, 1) == parent
    assert digital.describe(store, project_id)['parent_revision'] == 1


def test_intact_run_for_different_requirements_is_not_published(service, monkeypatch):
    store, backend, _ = service
    project_id, job = _claimed(service, 'Add 10 g of payload')
    _reuse_verified_baseline(monkeypatch)
    with pytest.raises(CorruptProject, match='requested requirements'):
        digital.execute_study(backend, job)
    assert store.load(project_id)['revision'] == 1


def test_api_startup_processes_persisted_queued_jobs(tmp_path, monkeypatch):
    from hardware_splicer import api
    backend = JobBackend(JobStore(tmp_path / 'jobs.db'), worker_count=1)
    backend.store.create_job(job_id='persisted', request_id='persisted-request', project_name='Persisted',
                             output_dir=str(tmp_path / 'out'), spec={}, options={})
    monkeypatch.setattr(api.JobBackend, 'from_env', classmethod(lambda cls: backend))
    monkeypatch.setattr(backend, '_execute_job', lambda job: backend.store.complete_job(job.job_id, {'resumed': True}))
    with TestClient(api.create_app()):
        completed = backend.wait_for_terminal('persisted', timeout_s=5)
        assert completed.status == 'succeeded'
        assert completed.result == {'resumed': True}


@pytest.mark.parametrize('terminal', ['cancelled', 'failed', 'retried'])
def test_cancelled_timed_out_or_superseded_attempt_cannot_publish(service, monkeypatch, terminal):
    store, backend, _ = service
    project_id, job = _claimed(service)
    _reuse_verified_baseline(monkeypatch)
    original_stage = digital.stage_run
    def stage(*args, **kwargs):
        seal = original_stage(*args, **kwargs)
        if terminal == 'cancelled':
            assert backend.store.cancel_job(job.job_id)
        else:
            backend.store.fail_job(job.job_id, {'type': 'JobTimeout'})
            if terminal == 'retried':
                backend.store.retry_job(job.job_id)
                assert backend.store.claim_next().started_at != job.started_at
        return seal
    monkeypatch.setattr(digital, 'stage_run', stage)
    digital.execute_study(backend, job)
    assert store.load(project_id)['revision'] == 1
    assert len(list((store.root / project_id / 'digital-runs').iterdir())) == 1


def test_concurrent_project_revision_wins_over_late_study(service, monkeypatch):
    store, backend, _ = service
    project_id, job = _claimed(service)
    _reuse_verified_baseline(monkeypatch)
    original_stage = digital.stage_run
    def stage(*args, **kwargs):
        seal = original_stage(*args, **kwargs)
        store.save(project_id, store.load(project_id)['snapshot'], expected_revision=1)
        return seal
    monkeypatch.setattr(digital, 'stage_run', stage)
    with pytest.raises(RevisionConflict):
        digital.execute_study(backend, job)
    assert store.load(project_id)['revision'] == 2
    assert len(list((store.root / project_id / 'digital-runs').iterdir())) == 1


@pytest.mark.requires_cadquery
def test_native_payload_job_rebuilds_mass_geometry_physics_and_retains_failed_requirement(service, monkeypatch):
    pytest.importorskip('cadquery'); pytest.importorskip('pybullet')
    import sys
    monkeypatch.setenv('HARDWARE_SPLICER_DIGITAL_PYTHON', sys.executable)
    store, backend, client = service
    project_id, job = _claimed(service, 'Add 10 g of payload')
    baseline = digital.describe(store, project_id)
    digital.execute_study(backend, job)
    assert backend.store.get_job(job.job_id).status == 'succeeded'
    current = digital.describe(store, project_id)
    assert current['revision'] == 2
    assert current['summary']['mass_g'] == pytest.approx(244.9)
    assert current['summary']['requirements_met']
    assert current['summary']['parts'] == baseline['summary']['parts'] + 1
    assert current['summary']['centre_of_mass_mm'] != baseline['summary']['centre_of_mass_mm']
    assert current['summary']['inertia_diagonal_kg_m2'] != baseline['summary']['inertia_diagonal_kg_m2']
    assert current['summary']['metrics']['peak_current_a_est'] > baseline['summary']['metrics']['peak_current_a_est']
    # A tighter mass requirement is a completed, valid computation with an
    # honest failed design result. It still gets a revision and full evidence.
    response = client.post(f'/v1/projects/{project_id}/digital/runs', json={
        'base_revision': 2, 'requirements': {'max_mass_g': 240}})
    assert response.status_code == 202
    job = backend.store.claim_next()
    digital.execute_study(backend, job)
    failed = digital.describe(store, project_id)
    assert backend.store.get_job(job.job_id).status == 'succeeded'
    assert failed['revision'] == 3
    assert not failed['summary']['requirements_met']
    assert failed['summary']['artifact_integrity']
    assert any(c['id'] == 'nominal_mass' and not c['passed'] for c in failed['summary']['constraints'])
    assert digital.describe(store, project_id, 1) == baseline
    assert digital.describe(store, project_id, 2) == current
