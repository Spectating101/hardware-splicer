"""Native donor placement consumes frozen evidence, never caller-supplied catalog analogies."""
import copy
import json

import pytest

from hardware_splicer.device_plan import DevicePlanError, build_device_plan
from hardware_splicer.donor.interface_contract import Contact, SignalContract, SignalDirection, accepted_measurement
from test_mission_donors import DONOR, _contract, _open, _retained_envelope, _spec
from test_mission_feedback import AGENT, HUMAN, _store, _propose, _candidate


def _native(missions):
    path = _contract(missions, measured=True)
    raw = json.loads(path.read_text())
    def fact(value, eid="ev-env-1"):
        return accepted_measurement(value, unit=None, evidence_id=eid, method="fixture").to_dict()
    raw["signals"][0].update(direction="output", controller_pin=fact("IO4"), protocol=fact("switch_to_ground"))
    raw["contacts"].append(Contact("J1.2").to_dict())
    ground = SignalContract("GND", "J1.2", SignalDirection.PASSIVE,
        voltage_max_v=accepted_measurement(0.0, unit="V", evidence_id="ev-env-1", method="fixture"))
    raw["signals"].append({**ground.to_dict(), "protocol": fact("ground_reference")})
    raw["planner_geometry"] = fact({"pcb_mm": {"x": 20, "y": 12, "z": 1.6},
        "above_board_mm": 5, "below_board_mm": 0, "connector": "male_header_2_54",
        "contacts": [{"contact_id": "J1.1", "x_mm": 2.54, "y_mm": 2.54, "z_mm": 4.6},
                     {"contact_id": "J1.2", "x_mm": 5.08, "y_mm": 2.54, "z_mm": 4.6}]}, "ev-geometry")
    path.write_text(json.dumps(raw))
    _retained_envelope(missions)
    snapshot = missions.project_store.load("monitor")["snapshot"]
    envelopes = snapshot["physicalValidation"]["audited_physical_evidence"]["envelopes"]
    from hardware_splicer.physical_evidence_ledger import build_physical_evidence_envelope
    original = envelopes[0]
    record = {**original["record"], "evidence_id": "ev-geometry", "kind": "dimensional_measurement"}
    env = build_physical_evidence_envelope(envelope_id="geometry", record=record, raw_files=original["raw_files"],
        created_at=original["created_at"], created_by=original["created_by"]).model_dump(mode="json")
    envelopes.append(env)
    missions.project_store.save("monitor", snapshot, expected_revision=2)
    return path


def _wired():
    spec = _spec(DONOR)
    spec["modules"].append({"id": "buttons", "module": DONOR})
    spec["connections"] += [{"from": "buttons.KEY", "to": "mcu.IO4"},
                            {"from": "buttons.GND", "to": "mcu.GND"}]
    return spec


def _context(missions):
    from hardware_splicer.donor_device_plan import mission_donor_modules
    view = _open(missions)
    return mission_donor_modules(view, _wired()), view


def test_native_donor_is_placed_and_wired_from_frozen_geometry(tmp_path):
    missions = _store(tmp_path)
    _native(missions)
    context, view = _context(missions)
    plan = build_device_plan(_wired(), donor_modules=context)
    donor = next(m for m in plan["modules"] if m["module"] == DONOR)
    assert donor["kind"] == "donor_passive"
    assert donor["pcb_mm"] == {"x": 20, "y": 12, "z": 1.6}
    assert plan["counts"]["errors"] == 0 and plan["counts"]["warnings"] == 0, [f for f in plan["findings"] if f["severity"] == "error"]
    assert len([w for w in plan["wires"] if w["from"]["module"] == "buttons"]) == 2
    assert plan["donor_scope"]["firmware_implemented"] is False
    assert view["power_on_authorized"] is False
    assert any(step["kind"] == "place" and step.get("parts") == ["buttons"] for step in plan["steps"])


def test_contract_geometry_round_trips_existing_evidence_store(tmp_path):
    from hardware_splicer.mission_donors import resolve_donor_contract
    missions = _store(tmp_path)
    path = _native(missions)
    assert resolve_donor_contract(missions.project_store, "monitor", DONOR).to_dict()["planner_geometry"] == json.loads(path.read_text())["planner_geometry"]


def test_public_device_spec_cannot_inject_a_donor_module_context(tmp_path):
    missions = _store(tmp_path)
    _native(missions)
    context, _ = _context(missions)
    spec = {**_wired(), "donor_modules": context}
    with pytest.raises(DevicePlanError):
        build_device_plan(spec)


@pytest.mark.parametrize("problem", ["missing_geometry", "unmatched_geometry", "reference_geometry", "bad_geometry",
    "active_protocol", "unmeasured_protocol", "supply_domain", "duplicate_contact", "wrong_voltage"])
def test_incomplete_or_out_of_scope_donors_are_not_projected(tmp_path, problem):
    missions = _store(tmp_path)
    path = _native(missions)
    raw = json.loads(path.read_text())
    if problem == "missing_geometry":
        raw.pop("planner_geometry")
    elif problem == "unmatched_geometry":
        raw["planner_geometry"]["evidence_ids"] = ["invented"]
    elif problem == "reference_geometry":
        raw["planner_geometry"]["status"] = "reference_only"
    elif problem == "bad_geometry":
        raw["planner_geometry"]["value"]["pcb_mm"]["x"] = -2
    elif problem == "active_protocol":
        raw["signals"][0]["protocol"]["value"] = "h_bridge"
    elif problem == "unmeasured_protocol":
        raw["signals"][0]["protocol"]["status"] = "reference_only"
    elif problem == "supply_domain":
        raw["power_domains"] = [{"name": "external power"}]
    elif problem == "duplicate_contact":
        raw["signals"][1]["contact_id"] = "J1.1"
    else:
        raw["signals"][0]["voltage_max_v"]["value"] = 1.8
    path.write_text(json.dumps(raw))
    with pytest.raises(DevicePlanError):
        _context(missions)


@pytest.mark.parametrize("target", ["mcu.5V", "mcu.GND", "mcu.IO16", "sensor.SDI"])
def test_native_switch_may_only_connect_to_declared_unreserved_controller_pin(tmp_path, target):
    missions = _store(tmp_path)
    _native(missions)
    context, _ = _context(missions)
    spec = _wired()
    spec["connections"][-2]["to"] = target
    plan = build_device_plan(spec, donor_modules=context)
    assert any(f["rule"] == "donor_controller_pin" and f["severity"] == "error" for f in plan["findings"])


@pytest.mark.parametrize("missing", ["KEY", "GND"])
def test_every_donor_contact_needs_implemented_wiring(tmp_path, missing):
    missions = _store(tmp_path)
    _native(missions)
    context, _ = _context(missions)
    spec = _wired()
    spec["connections"] = [c for c in spec["connections"] if c["from"] != "buttons." + missing]
    assert build_device_plan(spec, donor_modules=context)["counts"]["errors"] > 0


def test_native_donor_geometry_cannot_be_overridden_by_candidate(tmp_path):
    missions = _store(tmp_path)
    _native(missions)
    context, _ = _context(missions)
    spec = _wired()
    spec["modules"][-1]["overrides"] = {"pcb_mm": {"x": 1}}
    with pytest.raises(DevicePlanError, match="frozen"):
        build_device_plan(spec, donor_modules=context)


def test_frozen_geometry_survives_source_replacement(tmp_path):
    from hardware_splicer.donor_device_plan import mission_donor_modules
    missions = _store(tmp_path)
    path = _native(missions)
    context, view = _context(missions)
    raw = json.loads(path.read_text())
    raw["planner_geometry"]["value"]["pcb_mm"]["x"] = 200
    path.write_text(json.dumps(raw))
    assert mission_donor_modules(missions.get_mission("monitor", view["mission_id"]), _wired()) == context


@pytest.mark.parametrize("abuse", ["missing_usage", "duplicate_physical_block"])
def test_native_donor_usage_cannot_be_omitted_or_duplicated(tmp_path, abuse):
    from hardware_splicer.donor_device_plan import mission_donor_modules
    missions = _store(tmp_path)
    _native(missions)
    _, view = _context(missions)
    spec = _wired()
    if abuse == "missing_usage":
        spec["donors_used"] = []
    else:
        spec["modules"].append({"id": "clone", "module": DONOR})
    with pytest.raises(DevicePlanError):
        mission_donor_modules(view, spec)


def test_real_mission_executes_native_plan_review_and_deterministic_enclosure_package(tmp_path):
    import io
    import zipfile
    from hardware_splicer.mission_executor import run_mission_operation
    from hardware_splicer.mission_delivery import build_mission_package, read_mission_package
    missions = _store(tmp_path)
    _native(missions)
    _, view = _context(missions)
    mid = view["mission_id"]
    _candidate(missions, mid, _wired())
    for operation in ["device_plan", "device_engineering", "device_case"]:
        result = run_mission_operation(missions, "monitor", mid, candidate_id="A", operation=operation)
        evaluation = result["candidates"][0]["evaluations"][-1]
        assert evaluation["result"]["errors"] == 0, evaluation
    # No implementation of switch input behavior may be credited as a library firmware pass.
    result = run_mission_operation(missions, "monitor", mid, candidate_id="A", operation="device_application")
    assert result["candidates"][0]["evaluations"][-1]["result"]["errors"] > 0
    _propose(missions, mid, {"type": "terminal_proposed", "state": "READY_FOR_HUMAN_BUILD", "candidate_id": "A", "reason": "bounded software checks"})
    first = build_mission_package(missions, "monitor", mid)
    second = build_mission_package(missions, "monitor", mid)
    assert first["package_sha256"] == second["package_sha256"]
    assert first["deliverables"]["enclosure"]["status"] == "generated"
    assert first["deliverables"]["firmware"]["status"] == "blocked"
    with zipfile.ZipFile(io.BytesIO(read_mission_package(missions, "monitor", mid))) as archive:
        assert archive.testzip() is None
        assert "01_requirements/donor_read.json" in archive.namelist()
        plan = json.loads(archive.read("02_design/plan.json"))
        assert any(m["module"] == DONOR for m in plan["modules"])
        assert "04_enclosure/case_base.stl" in archive.namelist()
        assert "03_firmware/BLOCKED.md" in archive.namelist()
    assert missions.project_store.load("monitor")["revision"] == 3


def test_repair_cannot_downgrade_native_donor_to_unwired_tracking_reference(tmp_path):
    from hardware_splicer.mission_store import MissionStateError
    from test_mission_feedback import _evaluate
    missions = _store(tmp_path)
    _native(missions)
    _, view = _context(missions)
    mid = view["mission_id"]
    _candidate(missions, mid, _wired())
    _evaluate(missions, mid, errors=1)
    with pytest.raises(MissionStateError, match="wired donor"):
        _propose(missions, mid, {"type": "repair_proposed", "candidate_id": "A", "spec": _spec(DONOR), "rationale": "omit donor implementation"})


def test_real_mission_requirements_use_native_context(tmp_path):
    from hardware_splicer.mission_executor import run_mission_operation
    missions = _store(tmp_path)
    _native(missions)
    view = _open(missions, requirements=[{"path": "power.source", "equals": "usb"}])
    mid = view["mission_id"]
    assert _candidate(missions, mid, _wired())["candidates"][0]["violated_requirements"] == []
    for operation in ["device_plan", "device_engineering"]:
        run_mission_operation(missions, "monitor", mid, candidate_id="A", operation=operation)
    assert _propose(missions, mid, {"type": "terminal_proposed", "state": "READY_FOR_HUMAN_BUILD", "candidate_id": "A", "reason": "checked"})["terminal"]["grounding"] == "hs_evaluation"


@pytest.mark.parametrize("problem", ["overlapping_housings", "housing_outside_board", "wrong_units"])
def test_measured_coordinates_must_fit_the_supported_connector_geometry(tmp_path, problem):
    missions = _store(tmp_path)
    path = _native(missions)
    raw = json.loads(path.read_text())
    geometry = raw["planner_geometry"]
    if problem == "overlapping_housings":
        geometry["value"]["contacts"][1]["x_mm"] = 3
    elif problem == "housing_outside_board":
        geometry["value"]["contacts"][0]["x_mm"] = 0
    else:
        geometry["unit"] = "cm"
    path.write_text(json.dumps(raw))
    with pytest.raises(DevicePlanError):
        _context(missions)


@pytest.mark.parametrize("pin", ["IO0", "TX", "IO12", "IO34"])
def test_declared_pin_does_not_override_controller_reservation_or_input_limit(tmp_path, pin):
    missions = _store(tmp_path)
    path = _native(missions)
    raw = json.loads(path.read_text())
    raw["signals"][0]["controller_pin"]["value"] = pin
    path.write_text(json.dumps(raw))
    context, _ = _context(missions)
    spec = _wired()
    spec["connections"][-2]["to"] = "mcu." + pin
    assert build_device_plan(spec, donor_modules=context)["counts"]["errors"] > 0


def test_pico_passive_switch_uses_its_actual_controller_pin(tmp_path):
    from hardware_splicer.device_plan import example_specs
    from hardware_splicer.donor_device_plan import mission_donor_modules
    missions = _store(tmp_path)
    path = _native(missions)
    raw = json.loads(path.read_text())
    raw["signals"][0]["controller_pin"]["value"] = "GP2"
    path.write_text(json.dumps(raw))
    view = _open(missions)
    spec = copy.deepcopy(example_specs()["pico_oled_bme280_usb"])
    spec["donors_used"] = [DONOR]
    spec["modules"].append({"id": "buttons", "module": DONOR})
    spec["connections"] += [{"from": "buttons.KEY", "to": "mcu.GP2"}, {"from": "buttons.GND", "to": "mcu.GND"}]
    assert build_device_plan(spec, donor_modules=mission_donor_modules(view, spec))["counts"]["errors"] == 0


def test_public_http_cannot_inject_context_but_mission_executor_resolves_it(tmp_path):
    from fastapi.testclient import TestClient
    from hardware_splicer.product_api import create_product_app
    missions = _store(tmp_path)
    _native(missions)
    context, view = _context(missions)
    mid = view["mission_id"]
    _candidate(missions, mid, _wired())
    client = TestClient(create_product_app(missions.project_store))
    refused = client.post("/v1/devices/plan", json={"spec": {**_wired(), "donor_modules": context}})
    assert refused.status_code == 422, refused.text
    run = client.post(f"/v1/projects/monitor/missions/{mid}/candidates/A/run", json={"operation": "device_plan", "donor_modules": {}})
    assert run.status_code == 200, run.text
    assert run.json()["evaluation"]["result"]["errors"] == 0
    mission = run.json()["mission"]
    assert mission["physical_correctness"] == "UNPROVEN" and not mission["power_on_authorized"]
    assert not mission["firmware_authorized"]


def test_candidate_cannot_place_unlisted_or_duplicate_donor(tmp_path):
    from hardware_splicer.mission_store import MissionValidationError
    missions = _store(tmp_path)
    _native(missions)
    _, view = _context(missions)
    mid = view["mission_id"]
    for problem in ["unlisted", "duplicate", "no_usage"]:
        spec = _wired()
        if problem == "unlisted":
            spec["modules"][-1]["module"] = "donor:other:block"
        elif problem == "duplicate":
            spec["modules"].append({"id": "clone", "module": DONOR})
        else:
            spec["donors_used"] = []
        with pytest.raises(MissionValidationError):
            _candidate(missions, mid, spec)


def test_project_donor_schema_is_opt_in_and_does_not_change_standalone_catalogue():
    from hardware_splicer.device_plan import device_spec_json_schema
    from jsonschema import Draft202012Validator
    base = device_spec_json_schema()
    assert "enum" in base["properties"]["modules"]["items"]["properties"]["module"]
    assert list(Draft202012Validator(base).iter_errors(_wired()))
    assert list(Draft202012Validator(device_spec_json_schema(include_project_donors=True)).iter_errors(_wired())) == []


def test_huge_geometry_integer_is_a_bounded_refusal_not_an_overflow(tmp_path):
    missions = _store(tmp_path)
    path = _native(missions)
    raw = json.loads(path.read_text())
    raw["planner_geometry"]["value"]["pcb_mm"]["x"] = 10 ** 400
    path.write_text(json.dumps(raw))
    with pytest.raises(DevicePlanError):
        _context(missions)


@pytest.mark.parametrize("field", ["signals", "contacts", "power_domains"])
def test_malformed_contract_rows_are_not_silently_discarded_for_native_projection(tmp_path, field):
    from hardware_splicer.mission_store import MissionValidationError
    missions = _store(tmp_path)
    path = _native(missions)
    raw = json.loads(path.read_text())
    raw[field].append("malformed but potentially significant row")
    path.write_text(json.dumps(raw))
    with pytest.raises(MissionValidationError):
        _context(missions)
