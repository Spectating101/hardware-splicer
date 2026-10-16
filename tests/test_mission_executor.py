"""HS runs its own software-only device checks for an accepted mission and records what they found.

The executor is the only path from a candidate's spec to a recorded evaluation. It calls the canonical device
functions, keeps their full output as a hashed file inside the mission, and turns their own verdicts into errors
and warnings. A check that refuses or cannot run is recorded as a failure, never as a pass. Nothing physical.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from hardware_splicer.device_plan import example_specs
from hardware_splicer.device_draft import draft_from_parts_text
from hardware_splicer.mission_executor import MISSION_OPERATIONS, run_mission_operation
from hardware_splicer.mission_store import MissionStateError, MissionStore, MissionValidationError
from hardware_splicer.project_store import ProjectStore

AGENT = {"kind": "agent", "id": "planner-model"}
HUMAN = {"kind": "human", "id": "bench-lead"}


def snapshot() -> dict:
    return {"projectId": "monitor", "projectName": "Field monitor", "currentStage": "design", "mode": "greenfield",
            "graph": {"nodes": [], "edges": []},
            "machineProject": {"project_id": "monitor", "name": "Field monitor", "purpose": "Portable environmental monitor"}}


def _mission(tmp_path: Path, spec: dict, *, accepted: bool = True, **budgets):
    projects = ProjectStore(tmp_path)
    projects.save("monitor", snapshot(), expected_revision=0)
    missions = MissionStore(projects)
    intake = {"goal": "A portable environmental monitor", "inventory": ["ESP32", "BME280", "OLED"]}
    if budgets:
        intake["budgets"] = budgets
    mission = missions.open_mission("monitor", intake=intake, author=AGENT)
    if accepted:
        missions.accept_mission("monitor", mission["mission_id"], author=HUMAN)
    missions.propose("monitor", mission["mission_id"], {"type": "candidate_proposed", "candidate": {
        "id": "A", "kind": "clean_sheet", "label": "Example", "spec": spec, "rationale": "the inventory as drafted"}}, author=AGENT)
    return projects, missions, mission["mission_id"]


def _run(missions, mission_id, operation):
    return run_mission_operation(missions, "monitor", mission_id, candidate_id="A", operation=operation)


def _last_evaluation(view):
    return view["candidates"][0]["evaluations"][-1]


def _broken_spec():
    spec = copy.deepcopy(example_specs()["esp32_oled_bme280_usb"])
    spec["connections"] = [c for c in spec["connections"] if not c["from"].endswith("SDA")]
    return spec


def test_clean_hs_checks_cannot_make_an_incomplete_inventory_ready(tmp_path):
    spec = draft_from_parts_text({"text": "ESP32\nBME280"})["spec"]
    _projects, missions, mid = _mission(tmp_path, spec)
    for operation in ("device_plan", "device_engineering"):
        view = _run(missions, mid, operation)
        assert _last_evaluation(view)["result"]["errors"] == 0
    with pytest.raises(MissionStateError, match="OLED"):
        missions.propose("monitor", mid, {"type": "terminal_proposed", "state": "READY_FOR_HUMAN_BUILD",
                                          "candidate_id": "A", "reason": "HS checks are clean"}, author=AGENT)


def test_acceptance_draft_counts_match_the_canonical_executor_plan(tmp_path):
    spec = example_specs()["esp32_oled_bme280_usb"]
    _projects, missions, mid = _mission(tmp_path, spec)
    draft_spec = draft_from_parts_text({"text": "ESP32\nBME280\nOLED"})["spec"]
    missions.propose("monitor", mid, {"type": "candidate_proposed", "candidate": {
        "id": "B", "kind": "clean_sheet", "label": "HS draft", "spec": draft_spec, "rationale": "compare planners"}}, author=AGENT)
    view = run_mission_operation(missions, "monitor", mid, candidate_id="B", operation="device_plan")
    result = view["candidates"][1]["evaluations"][-1]["result"]
    assert view["inventory"]["draft"]["plan_errors"] == result["errors"]
    assert view["inventory"]["draft"]["plan_warnings"] == result["warnings"]


def test_the_operations_are_the_software_only_device_checks():
    assert set(MISSION_OPERATIONS) == {"device_plan", "device_engineering", "device_case", "device_application", "device_application_run"}


def test_a_clean_plan_and_its_engineering_review_are_recorded_with_their_verdicts(tmp_path):
    projects, missions, mid = _mission(tmp_path, example_specs()["esp32_oled_bme280_usb"])
    plan = _last_evaluation(_run(missions, mid, "device_plan"))
    assert plan["operation"] == "device_plan" and plan["result"]["errors"] == 0 and plan["result"]["warnings"] == 0
    review = _last_evaluation(_run(missions, mid, "device_engineering"))
    # The review never passes anything: a limit exceeded is an error, an advisory is a warning.
    assert review["result"]["errors"] == 0 and review["result"]["warnings"] > 0
    done = missions.propose("monitor", mid, {"type": "terminal_proposed", "state": "READY_FOR_HUMAN_BUILD",
                                              "candidate_id": "A", "reason": "plan clean, review within limits"}, author=AGENT)
    assert done["terminal"]["state"] == "READY_FOR_HUMAN_BUILD" and done["power_on_authorized"] is False


def test_every_evaluation_keeps_hs_output_as_a_hashed_file_inside_the_mission(tmp_path):
    projects, missions, mid = _mission(tmp_path, example_specs()["esp32_oled_bme280_usb"])
    view = _run(missions, mid, "device_plan")
    evaluation = _last_evaluation(view)
    path = projects.root / "monitor" / "missions" / mid / evaluation["artifact"]
    assert evaluation["artifact"].startswith("runs/") and path.is_file()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == evaluation["result"]["result_sha256"]
    assert "findings" in json.loads(path.read_text())


def test_a_broken_wiring_plan_is_recorded_as_failing_with_the_planners_reason(tmp_path):
    _projects, missions, mid = _mission(tmp_path, _broken_spec())
    plan = _last_evaluation(_run(missions, mid, "device_plan"))
    assert plan["result"]["errors"] > 0
    assert "error" in plan["result"]["summary"].lower()


def test_a_check_that_refuses_the_spec_is_a_failing_evaluation_not_an_exception(tmp_path):
    _projects, missions, mid = _mission(tmp_path, _broken_spec())
    for operation in ("device_case", "device_application"):
        evaluation = _last_evaluation(_run(missions, mid, operation))
        assert evaluation["operation"] == operation and evaluation["result"]["errors"] >= 1
        assert evaluation["result"]["summary"]


def test_a_case_and_an_application_that_build_are_recorded_clean(tmp_path):
    _projects, missions, mid = _mission(tmp_path, example_specs()["esp32_oled_bme280_usb"])
    for operation in ("device_case", "device_application"):
        evaluation = _last_evaluation(_run(missions, mid, operation))
        assert evaluation["result"]["errors"] == 0, evaluation["result"]["summary"]


def test_an_off_hardware_run_that_cannot_run_is_recorded_as_not_run_never_as_a_pass(tmp_path, monkeypatch):
    monkeypatch.delenv("HS_DEVICE_RUNTIME_ENABLED", raising=False)
    _projects, missions, mid = _mission(tmp_path, example_specs()["esp32_oled_bme280_usb"])
    evaluation = _last_evaluation(_run(missions, mid, "device_application_run"))
    assert evaluation["result"]["errors"] >= 1
    assert "not run" in evaluation["result"]["summary"].lower()


def test_nothing_runs_for_a_mission_no_person_accepted(tmp_path):
    projects, missions, mid = _mission(tmp_path, example_specs()["esp32_oled_bme280_usb"], accepted=False)
    with pytest.raises(MissionStateError, match="accepted"):
        _run(missions, mid, "device_plan")
    assert not (projects.root / "monitor" / "missions" / mid / "runs").exists()


@pytest.mark.parametrize("operation", ["device_reclaim_match", "device_firmware_flash", "shell", ""])
def test_only_the_listed_operations_run(tmp_path, operation):
    _projects, missions, mid = _mission(tmp_path, example_specs()["esp32_oled_bme280_usb"])
    with pytest.raises(MissionValidationError):
        _run(missions, mid, operation)


def test_the_operator_budget_stops_the_executor(tmp_path):
    _projects, missions, mid = _mission(tmp_path, example_specs()["esp32_oled_bme280_usb"], max_operator_jobs=1)
    _run(missions, mid, "device_plan")
    with pytest.raises(MissionStateError, match="budget"):
        _run(missions, mid, "device_engineering")


def test_the_executor_never_changes_the_project(tmp_path):
    projects, missions, mid = _mission(tmp_path, example_specs()["esp32_oled_bme280_usb"])
    before = projects.load("monitor")
    _run(missions, mid, "device_plan")
    _run(missions, mid, "device_case")
    after = projects.load("monitor")
    assert after["revision"] == before["revision"] and after["snapshot"] == before["snapshot"]


# Found in review of the first executor and evaluation files.


def test_a_refused_result_leaves_no_file_and_never_blocks_the_next_evaluation(tmp_path):
    projects, missions, mid = _mission(tmp_path, example_specs()["esp32_oled_bme280_usb"])
    with pytest.raises(MissionValidationError):
        missions.record_evaluation("monitor", mid, candidate_id="A", operation="device_plan",
                                   result={"errors": 0, "warnings": 0, "summary": "bad\x00summary"}, artifact={"x": 1})
    runs = projects.root / "monitor" / "missions" / mid / "runs"
    assert not runs.exists() or not any(runs.iterdir())
    assert _last_evaluation(_run(missions, mid, "device_plan"))["result"]["errors"] == 0


def test_identical_output_is_stored_once_and_each_evaluation_still_counts(tmp_path):
    projects, missions, mid = _mission(tmp_path, example_specs()["esp32_oled_bme280_usb"])
    first = _last_evaluation(_run(missions, mid, "device_plan"))
    view = _run(missions, mid, "device_plan")
    assert _last_evaluation(view)["artifact"] == first["artifact"]
    assert view["budgets"]["operator_jobs_used"] == 2


def test_a_finished_or_spent_mission_runs_nothing(tmp_path, monkeypatch):
    import hardware_splicer.mission_executor as executor
    calls = []
    real = executor.build_device_plan
    monkeypatch.setattr(executor, "build_device_plan", lambda spec: calls.append(1) or real(spec))
    _projects, missions, mid = _mission(tmp_path, example_specs()["esp32_oled_bme280_usb"], max_operator_jobs=1)
    _run(missions, mid, "device_plan")
    with pytest.raises(MissionStateError, match="budget"):
        _run(missions, mid, "device_plan")
    assert len(calls) == 1, "the over-budget check ran the planner anyway"


@pytest.mark.parametrize("status, scenarios, errors, warnings", [
    ("PASSED", [{"scenario": "boot_ok", "pass": True}], 0, 0),
    ("PARTIAL", [{"scenario": "boot_ok", "pass": True}], 0, 1),
    ("FAILED", [], 1, 1),
    ("FAILED", [{"scenario": "boot_ok", "pass": False}], 1, 1),
])
def test_the_off_hardware_run_uses_the_runtimes_own_verdict(tmp_path, monkeypatch, status, scenarios, errors, warnings):
    import hardware_splicer.mission_executor as executor
    vendor = {"status": "NOT_RUN" if status == "PARTIAL" else status, "scenarios": []}
    monkeypatch.setattr(executor, "run_device_application",
                        lambda spec: {"status": status, "host": {"pass": status != "FAILED", "scenarios": scenarios}, "vendor_host": vendor,
                                      "physical_correctness": "UNPROVEN"})
    _projects, missions, mid = _mission(tmp_path, example_specs()["esp32_oled_bme280_usb"])
    result = _last_evaluation(_run(missions, mid, "device_application_run"))["result"]
    assert (result["errors"], result["warnings"]) == (errors, warnings), result["summary"]
