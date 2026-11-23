"""Headless operation, canonical backend parity and artifact integrity."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4
import zipfile

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from hardware_splicer import digital_project as digital
from hardware_splicer.digital_engine import DigitalStudyEngine
from hardware_splicer.digital_project_api import create_digital_project_router
from hardware_splicer.jobs import JobBackend, JobStore
from hardware_splicer.project_store import CorruptProject, ProjectStore, RevisionConflict

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def engine(tmp_path, monkeypatch):
    backend = JobBackend(JobStore(tmp_path / 'jobs.db'), worker_count=0)
    engine = DigitalStudyEngine(ProjectStore(tmp_path / 'projects'), backend)
    monkeypatch.setattr(digital, 'runtime', lambda: {'available': True, 'setup_hint': ''})
    yield engine
    backend.stop()


def new_project(engine):
    return engine.create()['project']['project_id']


def test_headless_state_exposes_hashed_artifacts_without_http_links(engine):
    project = new_project(engine)
    study = engine.study(project)
    assert 'artifacts' not in study
    assert study['artifact_manifest']['HS3G_B_ASSEMBLY.step']['bytes'] > 10000
    assert study['summary']['mass_g'] == pytest.approx(234.9)
    assert engine.audit(project)['ok']


@pytest.mark.parametrize('tamper', ['summary', 'requirements', 'lineage', 'attempt', 'seal_type'])
def test_cached_claims_cannot_override_the_verified_result(engine, tamper):
    project = new_project(engine)
    _, directory, seal = digital.load_run(engine.projects, project)
    if tamper == 'summary':
        seal['summary']['mass_g'] = 1
        digital.write_json(directory / 'sealed-run.json', seal)
    elif tamper == 'requirements':
        seal['summary']['requirements']['payload_mass_g'] = 50
        digital.write_json(directory / 'sealed-run.json', seal)
    elif tamper == 'lineage':
        envelope = engine.projects.load(project)
        engine.projects.save(project, envelope['snapshot'], expected_revision=1)
    elif tamper == 'attempt':
        seal['attempt_id'] = uuid4().hex
        digital.write_json(directory / 'sealed-run.json', seal)
    else:
        (directory / 'sealed-run.json').write_text('[]')
    with pytest.raises(CorruptProject):
        engine.study(project)
    assert engine.audit(project)['ok'] is False


def test_history_uses_the_archived_contract_when_current_defaults_change(engine, tmp_path, monkeypatch):
    project = new_project(engine)
    original = engine.study(project)
    other = tmp_path / 'other-case'
    other.mkdir()
    digital.write_json(other / 'simulation.json', {'acceptance': {'tracking_rms_m': 999}})
    monkeypatch.setattr(digital, 'CASE', other)
    assert engine.study(project) == original


def test_changed_telemetry_is_rejected_before_export(engine, tmp_path):
    project = new_project(engine)
    _, directory, _ = digital.load_run(engine.projects, project)
    with (directory / 'nominal.csv').open('ab') as handle:
        handle.write(b'corrupt')
    assert not engine.audit(project)['artifact_integrity']
    with pytest.raises(CorruptProject):
        engine.export(project, tmp_path / 'blocked.zip')
    assert not (tmp_path / 'blocked.zip').exists()


def test_zip_inventory_is_checked_even_if_its_outer_hash_is_resealed(engine):
    project = new_project(engine)
    _, directory, seal = digital.load_run(engine.projects, project)
    with zipfile.ZipFile(directory / 'STUDY.zip', 'a') as archive:
        archive.writestr('unexpected.txt', 'unverified addition')
    seal['artifact_sha256']['STUDY.zip'] = digital.digest(directory / 'STUDY.zip')
    digital.write_json(directory / 'sealed-run.json', seal)
    audit = engine.audit(project)
    assert not audit['ok'] and 'inventory' in audit['error']


def test_export_never_overwrites_existing_files_or_revisions(engine, tmp_path):
    project = new_project(engine)
    original = engine.projects.load(project)
    destination = tmp_path / 'deliverable.zip'
    result = engine.export(project, destination)
    before = destination.read_bytes()
    assert result['sha256'] == hashlib.sha256(before).hexdigest()
    with pytest.raises(FileExistsError):
        engine.export(project, destination)
    assert destination.read_bytes() == before
    assert engine.projects.load(project) == original


def test_unavailable_runtime_never_queues_or_publishes_a_revision(engine, monkeypatch):
    project = new_project(engine)
    monkeypatch.setattr(digital, 'runtime', lambda: {'available': False, 'setup_hint': 'Native environment unavailable'})
    with pytest.raises(RuntimeError, match='Native environment unavailable'):
        engine.enqueue_revision(project, base_revision=1, change_request='Add 10 g of payload')
    assert engine.backend.store.list_digital_jobs(project) == []
    assert engine.projects.load(project)['revision'] == 1
    assert engine.audit(project)['ok']


def test_native_audit_timeout_does_not_rewrite_published_evidence(engine, monkeypatch):
    project = new_project(engine)
    _, directory, _ = digital.load_run(engine.projects, project)
    before = (directory / 'verification.json').read_bytes()
    def timed_out(args, **kwargs):
        raise subprocess.TimeoutExpired(args, 120)
    monkeypatch.setattr('hardware_splicer.digital_engine.subprocess.run', timed_out)
    audited = engine.audit(project, native=True)
    assert not audited['ok'] and audited['artifact_integrity']
    assert audited['native_verification']['passed'] is False
    assert (directory / 'verification.json').read_bytes() == before


def test_boolean_revision_is_rejected_by_both_python_and_http(engine):
    project = new_project(engine)
    with pytest.raises(ValueError, match='positive integer'):
        engine.enqueue_revision(project, base_revision=True)
    app = FastAPI()
    app.include_router(create_digital_project_router(engine.projects, engine.backend))
    assert TestClient(app).post(f'/v1/projects/{project}/digital/runs', json={'base_revision': True}).status_code == 422
    assert engine.backend.store.list_digital_jobs(project) == []


def test_retry_cannot_reset_a_job_completed_after_preflight(engine, monkeypatch):
    project = new_project(engine)
    queued = engine.enqueue_revision(project, base_revision=1)['job']['job_id']
    first = engine.backend.store.claim_next(job_id=queued)
    engine.backend.store.fail_job(queued, {'type': 'Timeout'}, attempt_id=first.attempt_id)
    original = engine.backend.store.retry_job
    def completed_between_checks(job_id, **kwargs):
        assert original(job_id)
        new = engine.backend.store.claim_next(job_id=job_id)
        engine.backend.store.complete_job(job_id, {'other_worker': True}, attempt_id=new.attempt_id)
        return original(job_id, **kwargs)
    monkeypatch.setattr(engine.backend.store, 'retry_job', completed_between_checks)
    with pytest.raises(RevisionConflict):
        engine.retry(project, queued)
    assert engine.job(project, queued).status == 'succeeded'


def test_opening_a_second_engine_does_not_recover_or_stop_another_worker(engine):
    project = new_project(engine)
    queued = engine.enqueue_revision(project, base_revision=1)
    active = engine.backend.store.claim_next(job_id=queued['job']['job_id'])
    with DigitalStudyEngine(project_root=engine.projects.root, job_db=engine.backend.store.db_path) as observer:
        assert observer.job(project, active.job_id).attempt_id == active.attempt_id
    assert engine.job(project, active.job_id).status == 'running'
    assert not engine.backend._stop.is_set()


def test_request_id_is_shared_between_direct_engine_and_http(engine):
    project = new_project(engine)
    request_id = str(uuid4())
    request = {'base_revision': 1, 'change_request': 'Add 10 g of payload', 'request_id': request_id}
    submitted = engine.enqueue_revision(project, **request)
    app = FastAPI()
    app.include_router(create_digital_project_router(engine.projects, engine.backend))
    response = TestClient(app).post(f'/v1/projects/{project}/digital/runs', json=request)
    assert response.status_code == 202
    assert response.json()['job']['job_id'] == submitted['job']['job_id']
    assert len(engine.backend.store.list_digital_jobs(project)) == 1


def test_invalid_large_numeric_requirements_do_not_escape_validation(engine):
    project = new_project(engine)
    with pytest.raises(ValueError):
        engine.enqueue_revision(project, base_revision=1, requirements={'payload_mass_g': 10**400})
    assert engine.backend.store.list_digital_jobs(project) == []


def test_retry_is_project_scoped_and_refuses_stale_base(engine):
    project, other = new_project(engine), new_project(engine)
    submitted = engine.enqueue_revision(project, base_revision=1)
    job_id = submitted['job']['job_id']
    with pytest.raises(FileNotFoundError):
        engine.cancel(other, job_id)
    assert engine.cancel(project, job_id)['ok']
    envelope = engine.projects.load(project)
    engine.projects.save(project, envelope['snapshot'], expected_revision=1)
    with pytest.raises(RevisionConflict, match='project changed'):
        engine.retry(project, job_id)


def cli(tmp_path, *args, timeout=30):
    env = dict(os.environ)
    env.update({'PYTHONPATH': str(ROOT / 'src'), 'DISPLAY': '', 'WAYLAND_DISPLAY': '',
                'HARDWARE_SPLICER_DIGITAL_PYTHON': sys.executable,
                'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'})
    return subprocess.run([sys.executable, '-B', '-m', 'hardware_splicer.digital_engine_cli',
                           '--project-root', str(tmp_path / 'projects'), '--jobs-db', str(tmp_path / 'jobs.db'),
                           *map(str, args)], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=timeout)


def test_cli_reads_and_exports_without_an_api_process(tmp_path):
    initialized = cli(tmp_path, 'init')
    assert initialized.returncode == 0, initialized.stderr
    project = json.loads(initialized.stdout)['project']['project_id']
    audited = cli(tmp_path, 'audit', project)
    assert audited.returncode == 0, audited.stdout
    assert json.loads(audited.stdout)['artifact_integrity']
    exported = cli(tmp_path, 'export', project, tmp_path / 'cli-export.zip')
    assert exported.returncode == 0, exported.stdout
    code = ('from hardware_splicer.sdk import digital_engine; import sys; '
            'engine=digital_engine(project_root=sys.argv[1],job_db=sys.argv[2]); '
            'assert "hardware_splicer.api" not in sys.modules; '
            'assert "hardware_splicer.product_api" not in sys.modules; '
            'assert "uvicorn" not in sys.modules; engine.close()')
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
    checked = subprocess.run([sys.executable, '-B', '-c', code, str(tmp_path/'projects'), str(tmp_path/'jobs.db')],
                             cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert checked.returncode == 0, checked.stderr


@pytest.mark.requires_cadquery
def test_native_headless_pipeline_persists_compares_audits_and_exports_failed_design(tmp_path, monkeypatch):
    pytest.importorskip('cadquery'); pytest.importorskip('pybullet')
    monkeypatch.setenv('HARDWARE_SPLICER_DIGITAL_PYTHON', sys.executable)
    created = cli(tmp_path, 'init')
    assert created.returncode == 0, created.stdout
    project = json.loads(created.stdout)['project']['project_id']
    # The producer exits with a queued job. A separate process owns execution.
    queued = cli(tmp_path, 'revise', project, '--base-revision', 1, '--change', 'Add 10 g of payload', '--enqueue')
    assert queued.returncode == 0, queued.stdout
    assert json.loads(queued.stdout)['job']['status'] == 'queued'
    worked = cli(tmp_path, 'work', project, timeout=240)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    with DigitalStudyEngine(project_root=tmp_path/'projects', job_db=tmp_path/'jobs.db') as engine:
        baseline, payload = engine.study(project, 1), engine.study(project, 2)
        assert payload['attempt_id'] == json.loads(worked.stdout)['jobs'][0]['attempt_id']
        assert payload['attempt_id']
        assert payload['summary']['mass_g'] == pytest.approx(244.9)
        assert payload['summary']['requirements_met']
        assert payload['summary']['parts'] == baseline['summary']['parts'] + 1
        comparison = engine.compare(project, before_revision=1, after_revision=2)
        assert comparison['metrics']['mass_g']['delta'] == pytest.approx(10)
        assert comparison['metrics']['peak_current_a_est']['delta'] > 0
        assert any(comparison['metrics']['inertia_diagonal_kg_m2']['delta'])
        envelope, directory, _ = digital.load_run(engine.projects, project, 2)
        original_receipt = (directory / 'verification.json').read_bytes()
        audited = engine.audit(project, 2, native=True)
        assert audited['ok'] and audited['native_verification']['performed']
        assert (directory / 'verification.json').read_bytes() == original_receipt
        failed = cli(tmp_path, 'revise', project, '--base-revision', 2, '--max-mass-g', 240, timeout=240)
        assert failed.returncode == 2, failed.stdout + failed.stderr
        result = json.loads(failed.stdout)
        assert result['job']['status'] == 'succeeded'
        assert result['study']['summary']['requirements_met'] is False
        comparison = engine.compare(project, before_revision=2, after_revision=3)
        assert len([c for c in comparison['constraints'] if c['transition'] == 'regressed']) == 2
        assert comparison['metrics']['mass_g']['delta'] == 0
        exported = engine.export(project, tmp_path/'failed-design.zip', 3)
        assert not exported['requirements_met']
        assert engine.audit(project, 3, native=True)['ok']
        assert engine.study(project, 1) == baseline
        assert engine.study(project, 2) == payload
        app = FastAPI()
        app.include_router(create_digital_project_router(engine.projects, engine.backend))
        response = TestClient(app).get(f'/v1/projects/{project}/digital/compare?before_revision=2&after_revision=3')
        assert response.status_code == 200 and response.json() == comparison
