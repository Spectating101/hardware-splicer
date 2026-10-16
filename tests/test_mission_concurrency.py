"""Mission mutations and expensive checks must share a cross-worker boundary."""

from concurrent.futures import ThreadPoolExecutor
import subprocess
import sys
from threading import Event

import pytest

from hardware_splicer.device_plan import example_specs
from hardware_splicer.mission_executor import run_mission_operation
from hardware_splicer.mission_store import MissionConflict, MissionError, MissionStateError, MissionStore
from hardware_splicer.project_store import ProjectStore

AGENT = {"kind": "agent", "id": "planner"}
HUMAN = {"kind": "human", "id": "operator"}


def setup_mission(tmp_path, *, accepted=True):
    projects = ProjectStore(tmp_path)
    projects.save("monitor", {"projectId": "monitor", "graph": {"nodes": [], "edges": []}}, expected_revision=0)
    store = MissionStore(projects)
    mission = store.open_mission("monitor", intake={
        "goal": "Monitor the environment", "inventory": ["ESP32", "BME280", "OLED"],
        "budgets": {"max_operator_jobs": 2}}, author=AGENT)
    mid = mission["mission_id"]
    if accepted:
        store.accept_mission("monitor", mid, author=HUMAN)
    store.propose("monitor", mid, {"type": "candidate_proposed", "candidate": {
        "id": "A", "kind": "clean_sheet", "label": "Monitor",
        "spec": example_specs()["esp32_oled_bme280_usb"], "rationale": "Use the inventory"}}, author=AGENT)
    return store, mid


def run(store, mid):
    return run_mission_operation(store, "monitor", mid, candidate_id="A", operation="device_plan")


@pytest.mark.parametrize("other_instance", [False, True])
@pytest.mark.parametrize("contender", ["run", "repair", "record"])
def test_in_flight_check_excludes_competing_mutations(tmp_path, monkeypatch, other_instance, contender):
    import hardware_splicer.mission_executor as executor

    store, mid = setup_mission(tmp_path)
    # Make repair legal before starting a later check. A stale result must never
    # be credited after that repair, even from a distinct API worker's store.
    store.record_evaluation("monitor", mid, candidate_id="A", operation="device_plan",
                            result={"errors": 1, "warnings": 0, "result_sha256": "0" * 64, "summary": "broken"})
    peer = MissionStore(tmp_path) if other_instance else store
    entered, release = Event(), Event()
    calls = []

    def check(operation, spec):
        calls.append(operation)
        if len(calls) == 1:
            entered.set()
            assert release.wait(10), "test did not release the simulated operator"
        return 0, 0, "clean", {"checked": spec}

    monkeypatch.setattr(executor, "_run_operation", check)
    with ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(run, store, mid)
        try:
            assert entered.wait(10)
            # Readers remain available while a potentially slow compile runs.
            assert peer.get_mission("monitor", mid)["budgets"]["operator_jobs_used"] == 1
            with pytest.raises(MissionConflict, match="busy"):
                if contender == "run":
                    run(peer, mid)
                elif contender == "repair":
                    spec = example_specs()["esp32_oled_bme280_usb"]
                    spec["name"] = "Repaired monitor"
                    peer.propose("monitor", mid, {"type": "repair_proposed", "candidate_id": "A",
                                                   "spec": spec, "rationale": "repair"}, author=AGENT)
                else:
                    peer.record_evaluation("monitor", mid, candidate_id="A", operation="device_plan",
                                           result={"errors": 0, "warnings": 0, "summary": "competing"}, artifact={"x": 1})
        finally:
            release.set()
        view = running.result(timeout=10)
    assert calls == ["device_plan"], "a competing check consumed resources before refusal"
    assert view["budgets"]["operator_jobs_used"] == 2
    assert view["candidates"][0]["repairs"] == 0
    with pytest.raises(MissionStateError, match="budget"):
        run(peer, mid)


def test_acceptance_write_interruption_never_leaves_accepted_without_inventory(tmp_path, monkeypatch):
    import hardware_splicer.mission_store as module

    store, mid = setup_mission(tmp_path, accepted=False)
    write = store._write_event
    writes = []

    def interrupted(project_id, mission_id, sequence, record):
        writes.append(record["type"])
        if len(writes) == 2:
            raise OSError("simulated interruption between acceptance writes")
        return write(project_id, mission_id, sequence, record)

    monkeypatch.setattr(store, "_write_event", interrupted)
    with pytest.raises(OSError, match="interruption"):
        store.accept_mission("monitor", mid, author=HUMAN)
    # Use a fresh store, as a process restart would, not in-memory recovery.
    restarted = MissionStore(tmp_path)
    partial = restarted.get_mission("monitor", mid)
    assert partial["accepted"] is None
    assert partial["inventory"] is not None
    with pytest.raises(MissionStateError, match="accepted"):
        run(restarted, mid)
    monkeypatch.setattr(module, "_read_inventory", lambda _: pytest.fail("retry must reuse the frozen inventory"))
    accepted = restarted.accept_mission("monitor", mid, author=HUMAN)
    assert accepted["accepted"]["by"] == HUMAN
    assert sum(event["type"] == "inventory_read" for event in accepted["events"]) == 1
    assert sum(event["type"] == "accepted" for event in accepted["events"]) == 1
    assert accepted["physical_correctness"] == "UNPROVEN"
    assert accepted["power_on_authorized"] is False


def test_inventory_preparation_failure_records_no_acceptance(tmp_path, monkeypatch):
    import hardware_splicer.mission_store as module

    store, mid = setup_mission(tmp_path, accepted=False)
    before = store.get_mission("monitor", mid)

    def fail(_inventory):
        raise RuntimeError("inventory reader unavailable")

    monkeypatch.setattr(module, "_read_inventory", fail)
    with pytest.raises(RuntimeError, match="unavailable"):
        store.accept_mission("monitor", mid, author=HUMAN)
    assert store.get_mission("monitor", mid) == before


def test_an_independent_python_process_observes_the_mission_lock(tmp_path):
    store, mid = setup_mission(tmp_path)
    script = """
import sys
from hardware_splicer.mission_store import MissionConflict, MissionStore
store = MissionStore(sys.argv[1])
assert store.get_mission('monitor', sys.argv[2])['accepted'] is not None
try:
    with store.mutation('monitor', sys.argv[2]):
        pass
except MissionConflict:
    print('busy')
else:
    raise AssertionError('another process acquired the same mission')
"""
    with store.mutation("monitor", mid):
        completed = subprocess.run([sys.executable, "-c", script, str(tmp_path), mid],
                                   capture_output=True, text=True, timeout=20)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "busy"
    with MissionStore(tmp_path).mutation("monitor", mid):
        pass


def test_a_crashed_worker_releases_its_lock(tmp_path):
    store, mid = setup_mission(tmp_path)
    script = """
import os, sys
from hardware_splicer.mission_store import MissionStore
with MissionStore(sys.argv[1]).mutation('monitor', sys.argv[2]):
    os._exit(17)
"""
    completed = subprocess.run([sys.executable, "-c", script, str(tmp_path), mid],
                               capture_output=True, text=True, timeout=20)
    assert completed.returncode == 17, completed.stderr
    assert run(store, mid)["budgets"]["operator_jobs_used"] == 1


def test_an_unexpected_operator_exception_releases_the_lock(tmp_path, monkeypatch):
    import hardware_splicer.mission_executor as executor

    store, mid = setup_mission(tmp_path)
    real = executor._run_operation

    def fail(*_args):
        raise RuntimeError("unexpected operator error")

    monkeypatch.setattr(executor, "_run_operation", fail)
    with pytest.raises(RuntimeError, match="unexpected"):
        run(store, mid)
    monkeypatch.setattr(executor, "_run_operation", real)
    assert run(MissionStore(tmp_path), mid)["budgets"]["operator_jobs_used"] == 1


def test_other_missions_are_not_serialized_together(tmp_path):
    store, mid = setup_mission(tmp_path)
    other = store.open_mission("monitor", intake={"goal": "Another independent monitor"}, author=AGENT)
    with store.mutation("monitor", mid):
        accepted = MissionStore(tmp_path).accept_mission("monitor", other["mission_id"], author=HUMAN)
    assert accepted["accepted"]["by"] == HUMAN


def test_missing_platform_lock_support_fails_closed_without_breaking_reads(tmp_path, monkeypatch):
    import hardware_splicer.mission_store as module

    store, mid = setup_mission(tmp_path)
    before = store.get_mission("monitor", mid)
    monkeypatch.setattr(module, "fcntl", None)
    with pytest.raises(MissionError, match="POSIX"):
        run(store, mid)
    assert store.get_mission("monitor", mid) == before
