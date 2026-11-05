"""Worker registry and capacity admission regressions (no actual dispatch)."""
from __future__ import annotations

import concurrent.futures
import json
from pathlib import Path

import pytest

from hardware_splicer import github_signal_remote_dispatch as dispatch
from hardware_splicer.github_signal_worker_registry import (
    DEFAULT_WORKER, WORKER_ID, RegistryError, choose_worker, configure_worker,
    discover_github_self_hosted, read_registry,
)

SHA = "b" * 40


class Client:
    def __init__(self):
        self.sent = []

    def get(self, path):
        assert path.endswith("/git/ref/heads/main")
        return {"object": {"sha": SHA}}

    def dispatch(self, *, task, request_id):
        self.sent.append((task, request_id))


def test_previously_approved_github_actions_pool_is_migration_safe(tmp_path):
    ledger = tmp_path / "ledger"
    inventory = read_registry(ledger)
    assert inventory["source"] == "pr283_approved_github_actions_pool"
    assert inventory["workers"][0]["id"] == WORKER_ID
    assert not ledger.exists()  # read-only inventory is side-effect-free
    choice = choose_worker(ledger, "review_schematic")
    assert choice["capability"] == "signal-akcli-schematic-review"
    assert choice["physical_authority"] is False


def test_registry_requires_explicit_approval_and_can_pause(tmp_path):
    ledger = tmp_path / "ledger"
    with pytest.raises(RegistryError, match="approve"):
        configure_worker(ledger, state="paused")
    assert not ledger.exists()
    managed = configure_worker(ledger, approve=True, state="paused",
                               allowed_tasks=["review_schematic"], max_inflight=1)
    assert managed["workers"][0]["state"] == "paused"
    with pytest.raises(RegistryError, match="no approved worker"):
        choose_worker(ledger, "review_schematic")
    configure_worker(ledger, approve=True, state="approved",
                     allowed_tasks=["review_schematic"], max_inflight=1)
    assert choose_worker(ledger, "review_schematic")["worker_id"] == WORKER_ID
    with pytest.raises(RegistryError, match="no approved worker"):
        choose_worker(ledger, "compare_board_revisions")


@pytest.mark.parametrize("change", [
    {"executor": "shell"}, {"id": "lab-robot-1"}, {"runner_label": "self-hosted"},
    {"physical_authority": True}, {"max_inflight": 100},
    {"allowed_tasks": ["print_part"]}, {"state": "unknown"},
])
def test_unapproved_worker_or_authority_is_rejected(tmp_path, change):
    ledger = tmp_path / "ledger"
    configure_worker(ledger, approve=True)
    data = read_registry(ledger)
    data["workers"][0].update(change)
    (ledger / "workers.json").write_text(json.dumps(data))
    with pytest.raises(RegistryError):
        choose_worker(ledger, "review_schematic")


def test_dangling_registry_symlink_cannot_restore_default_worker(tmp_path):
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    (ledger / "workers.json").symlink_to(ledger / "missing")
    with pytest.raises(RegistryError, match="unsafe"):
        read_registry(ledger)


def test_duplicate_or_corrupt_worker_ledger_blocks_scheduling(tmp_path):
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    (ledger / "hs-1234567890abcdef.json").write_text('{"request_id":null}')
    with pytest.raises(RegistryError, match="unverified"):
        choose_worker(ledger, "review_schematic")


def test_capacity_reservation_blocks_new_dispatch_until_job_finished(tmp_path, monkeypatch):
    monkeypatch.setattr(dispatch, "_source_at_ref", lambda *args: b"fixed HS input")
    ledger = tmp_path / "ledger"
    configure_worker(ledger, approve=True, max_inflight=1)
    client = Client()
    first = dispatch.submit("Review schematic", ledger=ledger, workspace=tmp_path,
                            client=client, request_id="hs-1111111111111111", execute=True)
    assert first["worker_id"] == WORKER_ID
    assert first["worker_assignment"]["inflight_before_assignment"] == 0
    assert len(client.sent) == 1
    with pytest.raises(RegistryError, match="capacity"):
        dispatch.submit("Compare board revisions", ledger=ledger, workspace=tmp_path,
                        client=client, request_id="hs-2222222222222222", execute=True)
    assert len(client.sent) == 1
    assert not (ledger / "hs-2222222222222222.json").exists()
    first["status"] = "remote_succeeded"
    (ledger / "hs-1111111111111111.json").write_text(json.dumps(first))
    next_job = dispatch.submit("Compare board revisions", ledger=ledger, workspace=tmp_path,
                               client=client, request_id="hs-2222222222222222", execute=True)
    assert next_job["worker_assignment"]["capability"] == "signal-kdif-board-revision-diff"
    assert len(client.sent) == 2


def test_ambiguous_dispatch_preserves_capacity(tmp_path, monkeypatch):
    monkeypatch.setattr(dispatch, "_source_at_ref", lambda *args: b"fixed HS input")
    ledger = tmp_path / "ledger"
    configure_worker(ledger, approve=True, max_inflight=1)
    client = Client()
    def fail(**kwargs):
        raise RuntimeError("connection lost after send")
    client.dispatch = fail
    with pytest.raises(RuntimeError):
        dispatch.submit("Review schematic", ledger=ledger, workspace=tmp_path,
                        client=client, request_id="hs-3333333333333333", execute=True)
    with pytest.raises(RegistryError, match="capacity"):
        choose_worker(ledger, "compare_board_revisions")


def test_concurrent_submit_cannot_oversubscribe_one_slot(tmp_path, monkeypatch):
    monkeypatch.setattr(dispatch, "_source_at_ref", lambda *args: b"fixed HS input")
    ledger = tmp_path / "ledger"
    configure_worker(ledger, approve=True, max_inflight=1)
    client = Client()
    def go(rid):
        return dispatch.submit("Inspect schematic", ledger=ledger, workspace=tmp_path,
                               client=client, request_id=rid, execute=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(go, "hs-4444444444444444"),
                   pool.submit(go, "hs-5555555555555555")]
        outcomes = []
        for f in futures:
            try:
                outcomes.append(f.result())
            except RegistryError as exc:
                outcomes.append(str(exc))
    assert len([x for x in outcomes if isinstance(x, dict)]) == 1
    assert sum("capacity" in x for x in outcomes if isinstance(x, str)) == 1
    assert len(client.sent) == 1


def test_empty_github_runner_inventory_does_not_enroll_local_machine(tmp_path):
    class Empty:
        def get(self, path):
            assert path.endswith("/actions/runners?per_page=100&page=1")
            return {"total_count": 0, "runners": []}
    found = discover_github_self_hosted(Empty())
    assert found["total_count"] == 0
    assert found["runners"] == []
    assert found["registration_is_execution_authority"] is False
    assert not tmp_path.joinpath("workers.json").exists()


def test_discovered_online_runner_cannot_gain_hs_execution_permission():
    class One:
        def get(self, path):
            return {"total_count": 1, "runners": [{
                "id": 42, "name": "optiplex", "status": "online", "busy": False,
                "labels": [{"name": "self-hosted"}, {"name": "Linux"}],
            }]}
    found = discover_github_self_hosted(One())
    runner = found["runners"][0]
    assert runner["github_runner_id"] == 42
    assert runner["status"] == "online"
    assert runner["hs_approved"] is False
    assert runner["schedulable_by_hs"] is False


def test_runner_discovery_rejects_duplicate_id_and_partial_pages():
    class Bad:
        def get(self, path):
            return {"total_count": 2, "runners": [{
                "id": 7, "name": "a", "labels": []},
                {"id": 7, "name": "b", "labels": []},
            ]}
    with pytest.raises(RegistryError, match="duplicate"):
        discover_github_self_hosted(Bad())
    class Partial:
        def get(self, path):
            return {"total_count": 2, "runners": [{
                "id": 7, "name": "a", "labels": []},
            ]}
    with pytest.raises(RegistryError, match="incomplete"):
        discover_github_self_hosted(Partial())
