"""/health and /v1/status return states, not filesystem paths, and /health stays in-process."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hardware_splicer import api
from hardware_splicer.state_paths import repo_root

ROOT = Path(__file__).resolve().parents[1]


def _strings(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, str):
        yield value


def _assert_no_paths(payload):
    secrets = {str(ROOT), str(repo_root()), sys.executable, str(Path.home()), str(Path(api.__file__).parent)}
    for text in _strings(payload):
        assert not text.startswith("/"), text
        assert not any(secret in text for secret in secrets), text


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_JOB_DB", str(tmp_path / "jobs.sqlite"))
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>ui</html>", encoding="utf-8")
    monkeypatch.setenv("HARDWARE_SPLICER_SERVE_UI", "1")
    with TestClient(api.create_app(ui_dist=dist)) as test_client:
        yield test_client


def test_health_returns_states_without_filesystem_paths(client):
    body = client.get("/health").json()
    _assert_no_paths(body)
    assert body["ui"]["served"] is True and body["ui"]["source"] == "argument"
    assert set(body["app_roots"]) == {"root", "circuit_ai", "mecha_splicer", "splicer3d"}
    assert all(set(row) == {"available"} for row in body["app_roots"].values())
    assert client.app.state.ui_dist  # kept server-side for logs


def test_status_returns_states_without_filesystem_paths(client):
    body = client.get("/v1/status").json()
    _assert_no_paths(body)
    assert body["app_roots"]["circuit_ai"]["exists"] is True


def test_health_spawns_no_process_and_answers_quickly(client, monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError(f"/health started a process: {args[:1]}")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    client.get("/health")  # warm imports
    started = time.perf_counter()
    for _ in range(5):
        assert client.get("/health").status_code == 200
    assert (time.perf_counter() - started) / 5 < 0.5
