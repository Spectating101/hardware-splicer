"""The mission gate: does one persisted mission, using only capabilities HS already has, reach the CORRECT terminal state?

The runner is an agent with no privileged path: it may only open nothing, read the mission, propose events and ask
the executor to run checks. A person accepts each mission first. Every scenario declares its correct terminal
state in advance, with the reason; reaching READY_FOR_HUMAN_BUILD where a blocker is correct counts as a failure.
"""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from hardware_splicer.device_plan import example_specs
from hardware_splicer.mission_runner import run_mission
from hardware_splicer.mission_store import MissionStore
from hardware_splicer.project_store import ProjectStore

AGENT = {"kind": "agent", "id": "mission-runner"}
HUMAN = {"kind": "human", "id": "bench-lead"}


def _missing_sda():
    spec = copy.deepcopy(example_specs()["esp32_oled_bme280_usb"])
    # The BME280 breakout labels its data pin SDI.
    spec["connections"] = [c for c in spec["connections"] if c["from"] != "sensor.SDI"]
    return spec


# name, inventory, budgets, starting spec, correct terminal state, why that state is correct
SCENARIOS = [
    ("clean_esp32", ["ESP32", "BME280", "0.96 inch OLED"], {}, None, "READY_FOR_HUMAN_BUILD",
     "every part is in the library, the plan is clean and the engineering review exceeds no limit"),
    ("clean_pico", ["Raspberry Pi Pico", "BH1750", "DS3231", "OLED"], {}, None, "READY_FOR_HUMAN_BUILD",
     "the same on the other controller, three I2C parts at distinct addresses"),
    ("unknown_part", ["ESP32", "BME280", "HC-SR04 ultrasonic"], {}, None, "BLOCKED_NEEDS_PART_DATA",
     "the person listed a part HS has no data for; dropping it silently would be a different device"),
    ("unknown_controller", ["ESP32-S3", "BME280"], {}, None, "BLOCKED_NEEDS_PART_DATA",
     "ESP32-S3 is a different board from the library's ESP32-DevKitC; nothing can be planned without data for it"),
    ("address_clash", ["Raspberry Pi Pico", "2x BME280"], {}, None, "BLOCKED_NEEDS_PART_DATA",
     "two BME280 answer at the same address and the planner offers no repair HS can express"),
    ("repairable", ["ESP32", "BME280", "OLED"], {}, _missing_sda(), "READY_FOR_HUMAN_BUILD",
     "the starting wiring misses a wire; the planner's own suggestion repairs it"),
    ("budget", ["ESP32", "BME280", "OLED"], {"max_operator_jobs": 1}, None, "BUDGET_EXHAUSTED",
     "one check pays for the plan but not the engineering review that READY needs"),
]


def _run(tmp_path: Path, inventory, budgets, starting_spec):
    projects = ProjectStore(tmp_path)
    projects.save("monitor", {"projectId": "monitor", "projectName": "Field monitor", "currentStage": "design", "mode": "greenfield",
                              "graph": {"nodes": [], "edges": []},
                              "machineProject": {"project_id": "monitor", "name": "Field monitor", "purpose": "monitor"}},
                  expected_revision=0)
    missions = MissionStore(projects)
    intake = {"goal": "A small sensor device from the parts I have", "inventory": inventory}
    if budgets:
        intake["budgets"] = budgets
    mission = missions.open_mission("monitor", intake=intake, author=AGENT)
    missions.accept_mission("monitor", mission["mission_id"], author=HUMAN)
    view = run_mission(missions, "monitor", mission["mission_id"], author=AGENT, starting_spec=starting_spec)
    return projects, missions, mission["mission_id"], view


@pytest.mark.parametrize("name, inventory, budgets, starting_spec, expected, why", SCENARIOS, ids=[s[0] for s in SCENARIOS])
def test_each_mission_reaches_its_correct_terminal_state(tmp_path, name, inventory, budgets, starting_spec, expected, why):
    projects, _missions, mid, view = _run(tmp_path, inventory, budgets, starting_spec)
    assert view["phase"] == "TERMINAL", f"{name}: the runner stopped without a terminal state"
    assert view["terminal"]["state"] == expected, f"{name}: expected {expected} because {why}; got {view['terminal']}"
    # The mission is persisted: a fresh store replays the same verdict from disk.
    assert MissionStore(projects).get_mission("monitor", mid)["terminal"] == view["terminal"]
    assert view["physical_correctness"] == "UNPROVEN" and view["power_on_authorized"] is False


def test_a_ready_mission_carries_its_evidence_trail(tmp_path):
    _projects, _missions, _mid, view = _run(tmp_path, ["ESP32", "BME280", "OLED"], {}, None)
    candidate = view["candidates"][0]
    operations = [e["operation"] for e in candidate["evaluations"]]
    assert operations[-2:] == ["device_plan", "device_engineering"]
    assert all(e["artifact"] and e["artifact"].startswith("runs/") for e in candidate["evaluations"])
    assert view["terminal"]["physical_evidence_required"]


def test_a_blocked_mission_says_what_is_missing(tmp_path):
    _projects, _missions, _mid, view = _run(tmp_path, ["ESP32", "BME280", "HC-SR04 ultrasonic"], {}, None)
    cited = [e for e in view["events"] if e["seq"] in view["terminal"]["cites"]]
    assert cited and all(e["type"] == "evidence_required" for e in cited)
    assert any("HC-SR04" in e["need"] for e in cited)


def test_the_repairable_mission_repaired_from_the_planners_suggestion_and_re_planned(tmp_path):
    _projects, _missions, _mid, view = _run(tmp_path, ["ESP32", "BME280", "OLED"], {}, _missing_sda())
    candidate = view["candidates"][0]
    assert candidate["repairs"] >= 1
    plans = [e["result"] for e in candidate["evaluations"] if e["operation"] == "device_plan"]
    assert plans[0]["errors"] > 0 and plans[-1]["errors"] == 0
    assert {"from": "sensor.SDI", "to": "mcu.IO21"} in candidate["spec"]["connections"]


def test_the_runner_only_proposes_and_asks_for_checks(tmp_path):
    _projects, _missions, _mid, view = _run(tmp_path, ["ESP32", "BME280", "OLED"], {}, None)
    for event in view["events"]:
        if event["type"] == "evaluation_recorded":
            assert event["author"] == {"kind": "system", "id": "hardware-splicer"}
        elif event["type"] == "accepted":
            assert event["author"] == HUMAN
        elif event["type"] != "opened":
            assert event["author"] == AGENT, event


def test_the_runner_never_runs_an_unaccepted_mission(tmp_path):
    projects = ProjectStore(tmp_path)
    projects.save("monitor", {"projectId": "monitor", "projectName": "m", "currentStage": "design", "mode": "greenfield",
                              "graph": {"nodes": [], "edges": []}, "machineProject": {"project_id": "monitor", "name": "m", "purpose": "m"}},
                  expected_revision=0)
    missions = MissionStore(projects)
    mission = missions.open_mission("monitor", intake={"goal": "x", "inventory": ["ESP32", "BME280"]}, author=AGENT)
    from hardware_splicer.mission_store import MissionStateError
    with pytest.raises(MissionStateError, match="accepted"):
        run_mission(missions, "monitor", mission["mission_id"], author=AGENT)
