"""Async compose/splice job backend."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from hardware_splicer.jobs import JobBackend, JobStore


def test_compose_job_runs_to_terminal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_COMPOSE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")
    store = JobStore(tmp_path / "jobs.sqlite3")
    backend = JobBackend(store, worker_count=1, poll_interval_s=0.05)
    out_dir = tmp_path / "compose_out"
    job = backend.submit_task(
        job_id="job-compose-1",
        request_id="req-compose-1",
        project_name="compose-test",
        output_dir=out_dir,
        job_type="compose",
        payload={
            "phrase": "plant watering with soil moisture sensor and pump",
            "export_gerber": False,
            "wire_only": True,
        },
    )
    deadline = time.time() + 30
    while time.time() < deadline:
        current = store.get_job(job.job_id)
        assert current is not None
        if current.status in {"succeeded", "failed"}:
            break
        time.sleep(0.05)
    backend.stop()
    final = store.get_job(job.job_id)
    assert final is not None
    assert final.status == "succeeded"
    assert final.result is not None
    assert final.result.get("wire_only") is True
