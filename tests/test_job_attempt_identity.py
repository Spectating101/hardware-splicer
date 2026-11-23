"""A superseded worker must never complete, fail or publish a newer attempt."""
from concurrent.futures import ThreadPoolExecutor
import sqlite3
import threading

import pytest

from hardware_splicer import jobs
from hardware_splicer.jobs import JobBackend, JobStore


def queued(store, name='task', *, kind='compose', project='project'):
    return store.create_job(job_id=name, request_id=name, project_name=name, output_dir='/unused', spec={},
                            options={'job_type': kind, 'payload': {'project_id': project, 'phrase': 'test'}})


def test_existing_database_is_migrated_without_losing_jobs(tmp_path):
    path = tmp_path / 'jobs.db'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE jobs (job_id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL, '
                           'project_name TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, '
                           'updated_at TEXT NOT NULL, started_at TEXT, finished_at TEXT, output_dir TEXT NOT NULL, '
                           'spec_json TEXT NOT NULL, options_json TEXT NOT NULL, result_json TEXT, error_json TEXT)')
        connection.execute("INSERT INTO jobs VALUES ('old','old','Existing','queued','then','then',NULL,NULL,'/old','{}','{}',NULL,NULL)")
    store = JobStore(path)
    assert store.get_job('old').project_name == 'Existing'
    assert store.get_job('old').attempt_id is None
    assert store.claim_next().attempt_id
    assert JobStore(path).get_job('old').status == 'running'


def test_attempt_identity_changes_even_when_clock_is_frozen(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, '_utc_now', lambda: '2026-11-17T00:00:00+00:00')
    store = JobStore(tmp_path / 'jobs.db')
    queued(store)
    first = store.claim_next()
    store.fail_job(first.job_id, {'type': 'Timeout'}, attempt_id=first.attempt_id)
    assert store.retry_job(first.job_id)
    second = store.claim_next()
    assert first.started_at == second.started_at
    assert first.attempt_id != second.attempt_id
    store.complete_job(first.job_id, {'old': True}, attempt_id=first.attempt_id)
    store.fail_job(first.job_id, {'old': True}, attempt_id=first.attempt_id)
    assert store.get_job(first.job_id).status == 'running'
    assert not store.complete_with_publication(first, lambda: pytest.fail('old attempt published'))
    assert store.complete_with_publication(second, lambda: {'new': True})
    assert store.get_job(first.job_id).result == {'new': True}


@pytest.mark.parametrize('outcome', ['complete', 'fail'])
def test_real_worker_late_callback_cannot_overwrite_retry(tmp_path, monkeypatch, outcome):
    monkeypatch.setattr(jobs, '_utc_now', lambda: '2026-11-17T00:00:00+00:00')
    backend = JobBackend(JobStore(tmp_path / 'jobs.db'), worker_count=0)
    queued(backend.store)
    old = backend.store.claim_next()
    entered, release = threading.Event(), threading.Event()
    def compose(**kwargs):
        entered.set()
        assert release.wait(5)
        if outcome == 'fail':
            raise RuntimeError('old worker failed late')
        return {'old': True}
    monkeypatch.setattr('hardware_splicer.compose_dispatch.compose_dispatch', compose)
    monkeypatch.setattr('hardware_splicer.sdk.finalize_compose_job_result', lambda result, **kwargs: result)
    thread = threading.Thread(target=backend._run_job, args=(old,))
    thread.start()
    try:
        assert entered.wait(5)
        backend.store.fail_job(old.job_id, {'type': 'Timeout'}, attempt_id=old.attempt_id)
        assert backend.store.retry_job(old.job_id)
        current = backend.store.claim_next()
        release.set()
        thread.join(5)
        assert not thread.is_alive()
        state = backend.store.get_job(old.job_id)
        assert state.status == 'running' and state.result is None and state.error is None
        assert state.attempt_id == current.attempt_id
    finally:
        release.set(); thread.join(5)


def test_two_stores_submit_one_idempotent_job(tmp_path):
    path = tmp_path / 'jobs.db'
    stores = [JobStore(path), JobStore(path)]
    barrier = threading.Barrier(2)
    def submit(index):
        barrier.wait(timeout=5)
        return stores[index].create_job(job_id=f'candidate-{index}', request_id='shared', project_name='Shared',
                                        output_dir='/unused', spec={}, options={})
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, [0,1]))
    assert results[0].job_id == results[1].job_id
    assert len(stores[0].list_jobs()) == 1


def test_scoped_worker_leaves_other_projects_and_task_types_queued(tmp_path, monkeypatch):
    backend = JobBackend(JobStore(tmp_path / 'jobs.db'), worker_count=0)
    queued(backend.store, 'compile', kind='compile_bundle')
    queued(backend.store, 'other-project', kind='digital_study', project='other')
    queued(backend.store, 'selected', kind='digital_study')
    monkeypatch.setattr(backend, '_execute_job', lambda j: backend.store.complete_job(j.job_id, {}, attempt_id=j.attempt_id))
    assert backend.run_next(job_type='digital_study', project_id='project').job_id == 'selected'
    assert backend.store.get_job('compile').status == 'queued'
    assert backend.store.get_job('other-project').status == 'queued'


def test_interrupted_headless_worker_finishes_its_own_attempt(tmp_path, monkeypatch):
    backend = JobBackend(JobStore(tmp_path / 'jobs.db'), worker_count=0)
    queued(backend.store)
    def interrupted(job):
        raise KeyboardInterrupt
    monkeypatch.setattr(backend, '_run_job', interrupted)
    with pytest.raises(KeyboardInterrupt):
        backend.run_next(job_id='task')
    assert backend.store.get_job('task').status == 'failed'
    assert backend.store.get_job('task').error['type'] == 'WorkerInterrupted'
