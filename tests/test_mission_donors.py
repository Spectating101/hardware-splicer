"""Donor facts are resolved by HS; agent findings cannot become physical facts."""
import copy
import json

import pytest

from hardware_splicer.donor.interface_contract import (
    Contact, InterfaceContract, SignalContract, SignalDirection, accepted_measurement,
)
from hardware_splicer.evidence import EvidenceValue, EpistemicStatus
from hardware_splicer.mission_store import MissionStateError, MissionValidationError
from test_mission_feedback import (
    AGENT, HUMAN, _store, _snapshot, _candidate, _evaluate, _propose, _need, _supply,
)

DONOR = "donor:radio:buttons"
OTHER = "donor:radio:display"


def _open(missions, donors=None, accept=True, **extra):
    mission = missions.open_mission("monitor", intake={
        "goal": "Reuse the donor", "inventory": ["ESP32", "BME280", "OLED"],
        "donors": donors if donors is not None else [{"donor_id": DONOR, "label": "Buttons", "optional": False}],
        **extra}, author=AGENT)
    return missions.accept_mission("monitor", mission["mission_id"], author=HUMAN) if accept else mission


def _contract(missions, *, measured=False, evidence_id="ev-env-1", donor=DONOR):
    board, block = donor.split(":")[1:]
    value = (lambda v: accepted_measurement(v, unit=None, evidence_id=evidence_id, method="fixture")) if measured else (
        lambda v: EvidenceValue(value=v, status=EpistemicStatus.REFERENCE_ONLY))
    contract = InterfaceContract("if:" + board + ":" + block, board, block, "button_input",
        contacts=[Contact("J1.1")], signals=[SignalContract(
            "KEY", "J1.1", SignalDirection.INPUT, voltage_max_v=value(3.3),
            active_level=value("low"), controller_pin=value("GP4"))], interface_complete=value(True))
    contract.recompute_status()
    # Existing InterfaceContract bytes, at the documented read-only resolver location.
    path = missions.project_store.root / "monitor" / "donors" / "contracts" / (donor.replace(":", "__") + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contract.to_dict()))
    return path


def _spec(*donors):
    from hardware_splicer.device_plan import example_specs
    return {**copy.deepcopy(example_specs()["esp32_oled_bme280_usb"]), "donors_used": list(donors)}


def _ready(missions, mid):
    _evaluate(missions, mid)
    _evaluate(missions, mid, operation="device_engineering")
    return _propose(missions, mid, {"type": "terminal_proposed", "state": "READY_FOR_HUMAN_BUILD",
                                  "candidate_id": "A", "reason": "software checks"})


def _finding(**extra):
    return {"type": "finding_offered", "finding": {"donor_id": DONOR, "signal": "KEY",
        "claim": "The marking suggests a button input", "method": "document", "source": "RE fixture",
        "artifacts": [{"name": "photo.png", "sha256": "A" * 64}], **extra}}


def _request(signal="KEY", target=DONOR):
    return {"kind": "electrical", "target": target, "signal": signal, "quantity": "voltage",
            "instructions": "A person must establish the signal voltage."}


def test_donor_read_precedes_acceptance_and_unknown_is_not_fabricated(tmp_path):
    missions = _store(tmp_path)
    view = _open(missions)
    reading = next(e for e in view["events"] if e["type"] == "donor_read")
    accepted = next(e for e in view["events"] if e["type"] == "accepted")
    assert reading["seq"] < accepted["seq"] and reading["author"]["kind"] == "system"
    assert view["donors"][0]["contract_state"] == "unknown"
    assert view["donors"][0]["can_generate_firmware"] is False
    assert not (missions.project_store.root / "monitor" / "donors").exists()
    assert '"status":' not in json.dumps(reading)


def test_acceptance_retry_reuses_frozen_donor_read(tmp_path, monkeypatch):
    missions = _store(tmp_path)
    mid = _open(missions, accept=False)["mission_id"]
    original = missions._write_event
    def interrupted(project, mission, seq, event):
        if event["type"] == "accepted":
            raise OSError("interrupted before human acceptance")
        return original(project, mission, seq, event)
    monkeypatch.setattr(missions, "_write_event", interrupted)
    with pytest.raises(OSError):
        missions.accept_mission("monitor", mid, author=HUMAN)
    before = missions.get_mission("monitor", mid)
    _contract(missions, measured=True)
    monkeypatch.setattr(missions, "_write_event", original)
    after = missions.accept_mission("monitor", mid, author=HUMAN)
    assert before["donors"] == after["donors"]
    assert len([e for e in after["events"] if e["type"] == "donor_read"]) == 1


def test_forged_measurement_ids_do_not_verify_a_contract(tmp_path):
    missions = _store(tmp_path)
    _contract(missions, measured=True)
    view = _open(missions)
    donor = view["donors"][0]
    assert donor["contract_state"] == "partial"
    assert donor["signals"][0]["voltage_max_v"]["grade"] != "person_measurement"
    assert donor["can_generate_firmware"] is False
    _candidate(missions, view["mission_id"], _spec(DONOR))
    with pytest.raises(MissionStateError, match="KEY.*voltage_max_v"):
        _ready(missions, view["mission_id"])


def _retained_envelope(missions, *, project="monitor", target=DONOR, tamper=False, simulated=False):
    from test_mission_feedback import _envelope
    from hardware_splicer.physical_evidence_ledger import build_physical_evidence_envelope
    env = _envelope("fixture-mission", 1, [])
    record = {**env["record"], "project_id": project, "target_ids": [target], "metadata": {"simulated": simulated}}
    env = build_physical_evidence_envelope(envelope_id=env["envelope_id"], record=record,
        raw_files=env["raw_files"], created_at=env["created_at"], created_by=env["created_by"]).model_dump(mode="json")
    if tamper:
        env["record"]["operator"] = "tampered"
    snapshot = _snapshot()
    snapshot["physicalValidation"] = {"audited_physical_evidence": {"envelopes": [env]}}
    missions.project_store.save("monitor", snapshot, expected_revision=1)


@pytest.mark.parametrize("problem", ["other_project", "other_target", "tampered", "simulated"])
def test_only_matching_untampered_physical_records_count(tmp_path, problem):
    missions = _store(tmp_path)
    _contract(missions, measured=True)
    _retained_envelope(missions, **{"other_project": {"project": "other"}, "other_target": {"target": OTHER},
        "tampered": {"tamper": True}, "simulated": {"simulated": True}}[problem])
    assert _open(missions)["donors"][0]["contract_state"] == "partial"


def test_verified_donor_can_pass_with_full_coverage_and_usual_checks(tmp_path):
    missions = _store(tmp_path)
    path = _contract(missions, measured=True)
    original = path.read_bytes()
    _retained_envelope(missions)
    view = _open(missions)
    donor = view["donors"][0]
    assert donor["contract_state"] == "verified"
    assert donor["capabilities"][0]["grade"] == "person_measurement"
    _candidate(missions, view["mission_id"], _spec(DONOR))
    final = _ready(missions, view["mission_id"])
    assert final["terminal"]["state"] == "READY_FOR_HUMAN_BUILD"
    assert final["physical_correctness"] == "UNPROVEN"
    assert not final["firmware_authorized"] and not final["power_on_authorized"]
    assert path.read_bytes() == original


def test_required_donors_cannot_be_omitted_but_optional_ones_can(tmp_path):
    missions = _store(tmp_path)
    mid = _open(missions)["mission_id"]
    _candidate(missions, mid, _spec())
    with pytest.raises(MissionStateError, match="donor:radio:buttons"):
        _ready(missions, mid)
    optional = _open(missions, donors=[{"donor_id": DONOR, "label": "Buttons", "optional": True}])["mission_id"]
    _candidate(missions, optional, _spec())
    assert _ready(missions, optional)["terminal"]["state"] == "READY_FOR_HUMAN_BUILD"


def test_donors_used_are_canonical_and_repairs_cannot_drop_them(tmp_path):
    missions = _store(tmp_path)
    mid = _open(missions, donors=[{"donor_id": d, "label": d, "optional": False} for d in [DONOR, OTHER]])["mission_id"]
    view = _candidate(missions, mid, _spec(OTHER, DONOR, DONOR))
    assert view["candidates"][0]["spec"]["donors_used"] == sorted([DONOR, OTHER])
    _evaluate(missions, mid, errors=1)
    with pytest.raises(MissionStateError, match=DONOR):
        _propose(missions, mid, {"type": "repair_proposed", "candidate_id": "A", "spec": _spec(OTHER), "rationale": "drop"})


def test_donor_order_duplicates_are_not_distinct_designs(tmp_path):
    from hardware_splicer.mission_store import _engineering_content
    assert _engineering_content(_spec(DONOR, OTHER, DONOR)) == _engineering_content(_spec(OTHER, DONOR))


def test_omitted_and_empty_donor_lists_are_not_distinct_designs():
    from hardware_splicer.mission_store import _engineering_content
    spec = _spec()
    omitted = {k: v for k, v in spec.items() if k != "donors_used"}
    assert _engineering_content(spec) == _engineering_content(omitted)


@pytest.mark.parametrize("donors", ["bad", [{"donor_id": "../../else", "label": "x", "optional": False}],
    [{"donor_id": DONOR, "label": "x", "optional": "false"}],
    [{"donor_id": DONOR, "label": "x", "optional": False, "contract": {}}]])
def test_donor_intake_is_strictly_references(tmp_path, donors):
    with pytest.raises(MissionValidationError):
        _open(_store(tmp_path), donors=donors)


def test_candidate_cannot_name_a_donor_outside_intake(tmp_path):
    missions = _store(tmp_path)
    mid = _open(missions)["mission_id"]
    with pytest.raises(MissionValidationError, match="intake"):
        _candidate(missions, mid, _spec(OTHER))


def test_findings_are_always_re_observations_and_citable_not_grounding(tmp_path):
    missions = _store(tmp_path)
    _contract(missions)
    mid = _open(missions)["mission_id"]
    _candidate(missions, mid, _spec(DONOR))
    view = _propose(missions, mid, _finding())
    finding_seq = view["last_event_seq"]
    assert view["donors"][0]["findings"][0]["grade"] == "re_observation"
    assert view["donors"][0]["signals"][0]["voltage_max_v"]["grade"] == "document"
    need = _propose(missions, mid, {"type": "evidence_required", "blocker": "BLOCKED_NEEDS_REVERSE_ENGINEERING",
        "need": "Confirm the observation", "request": _request(), "cites": [finding_seq]})["last_event_seq"]
    final = _propose(missions, mid, {"type": "terminal_proposed", "state": "BLOCKED_NEEDS_REVERSE_ENGINEERING",
        "candidate_id": "A", "reason": "observation only", "cites": [need]})
    assert final["terminal"]["grounding"] == "agent_assertion"


@pytest.mark.parametrize("extra", [{"grade": "person_measurement"}, {"accepted": True}, {"measured": True},
    {"author": HUMAN}, {"artifacts": [{"name": "x", "sha256": "bad"}]},
    {"artifacts": [{"name": "x", "sha256": "a" * 64}] * 21}, {"method": "magic"}, {"donor_id": OTHER}])
def test_finding_grade_and_identity_cannot_be_overridden(tmp_path, extra):
    missions = _store(tmp_path)
    mid = _open(missions)["mission_id"]
    with pytest.raises(MissionValidationError):
        _propose(missions, mid, _finding(**extra))


@pytest.mark.parametrize("author", [HUMAN, {"kind": "system", "id": "hardware-splicer"}])
def test_only_agents_can_offer_findings(tmp_path, author):
    missions = _store(tmp_path)
    mid = _open(missions)["mission_id"]
    with pytest.raises(MissionValidationError):
        missions.propose("monitor", mid, _finding(), author=author)


def test_re_grounding_comes_from_frozen_unknown_donor_read(tmp_path):
    missions = _store(tmp_path)
    mid = _open(missions)["mission_id"]
    need = _need(missions, mid, _request(), blocker="BLOCKED_NEEDS_REVERSE_ENGINEERING")
    final = _propose(missions, mid, {"type": "terminal_proposed", "state": "BLOCKED_NEEDS_REVERSE_ENGINEERING",
        "reason": "read missing", "cites": [need]})
    assert final["terminal"]["grounding"] == "hs_donor_reading"


def test_physical_grounding_requires_specific_missing_used_signal(tmp_path):
    missions = _store(tmp_path)
    _contract(missions)
    mid = _open(missions)["mission_id"]
    _candidate(missions, mid, _spec(DONOR))
    need = _need(missions, mid, _request(), cid="A")
    final = _propose(missions, mid, {"type": "terminal_proposed", "state": "BLOCKED_NEEDS_PHYSICAL_MEASUREMENT",
        "candidate_id": "A", "reason": "measure KEY", "cites": [need]})
    assert final["terminal"]["grounding"] == "hs_donor_contract"


def test_person_donor_reading_is_shown_without_promoting_contract(tmp_path):
    missions = _store(tmp_path)
    path = _contract(missions)
    original = path.read_bytes()
    mid = _open(missions)["mission_id"]
    _candidate(missions, mid, _spec(DONOR))
    need = _need(missions, mid, _request(), cid="A")
    values = [{"quantity": "voltage", "value": 3.3, "unit": "V"}]
    view = missions.supply_evidence("monitor", mid, need, envelope=_donor_envelope(mid, need, values),
        values=values, author=HUMAN)
    donor = view["donors"][0]
    assert donor["person_measurements"][0]["grade"] == "person_measurement"
    assert donor["contract_state"] == "partial" and path.read_bytes() == original
    with pytest.raises(MissionStateError, match="donor"):
        _ready(missions, mid)


def _donor_envelope(mid, need, values, *, target=DONOR, simulated=False):
    from test_mission_feedback import _envelope
    from hardware_splicer.physical_evidence_ledger import build_physical_evidence_envelope
    env = _envelope(mid, need, values)
    record = {**env["record"], "target_ids": [target], "metadata": {"simulated": simulated}}
    return build_physical_evidence_envelope(envelope_id=env["envelope_id"], record=record,
        raw_files=env["raw_files"], created_at=env["created_at"], created_by=env["created_by"],
        metadata=env["metadata"]).model_dump(mode="json")


@pytest.mark.parametrize("problem", ["target", "simulated"])
def test_donor_person_measurements_need_matching_nonsimulated_record(tmp_path, problem):
    missions = _store(tmp_path)
    _contract(missions)
    mid = _open(missions)["mission_id"]
    need = _need(missions, mid, _request())
    values = [{"quantity": "voltage", "value": 3.3, "unit": "V"}]
    envelope = _donor_envelope(mid, need, values, target=OTHER if problem == "target" else DONOR,
        simulated=problem == "simulated")
    before = missions.get_mission("monitor", mid)["last_event_seq"]
    with pytest.raises(MissionValidationError, match="donor"):
        missions.supply_evidence("monitor", mid, need, envelope=envelope, values=values, author=HUMAN)
    assert missions.get_mission("monitor", mid)["last_event_seq"] == before


@pytest.mark.parametrize("include", [False, True])
def test_no_feasible_requires_donor_coverage_and_distinct_designs(tmp_path, include):
    missions = _store(tmp_path)
    mid = _open(missions, budgets={"max_candidates": 2, "max_repairs_per_candidate": 1, "max_operator_jobs": 20})["mission_id"]
    for cid in ["A", "B"]:
        spec = _spec(DONOR, DONOR) if include else _spec()
        _candidate(missions, mid, spec, cid=cid)
        _evaluate(missions, mid, cid=cid, errors=1)
        _propose(missions, mid, {"type": "repair_proposed", "candidate_id": cid, "spec": spec, "rationale": "try again"})
        _evaluate(missions, mid, cid=cid, errors=1)
    # Same designs with different names/order do not establish infeasibility.
    with pytest.raises(MissionStateError, match="distinct"):
        _propose(missions, mid, {"type": "terminal_proposed", "state": "NO_FEASIBLE_ARCHITECTURE", "reason": "spent"})


def test_no_feasible_cannot_drop_a_required_donor(tmp_path):
    missions = _store(tmp_path)
    mid = _open(missions, budgets={"max_candidates": 1, "max_repairs_per_candidate": 1, "max_operator_jobs": 20})["mission_id"]
    spec = _spec()
    _candidate(missions, mid, spec)
    _evaluate(missions, mid, errors=1)
    _propose(missions, mid, {"type": "repair_proposed", "candidate_id": "A", "spec": spec, "rationale": "try"})
    _evaluate(missions, mid, errors=1)
    with pytest.raises(MissionStateError, match=DONOR):
        _propose(missions, mid, {"type": "terminal_proposed", "state": "NO_FEASIBLE_ARCHITECTURE", "reason": "spent"})


@pytest.mark.parametrize("detail", ["absent_signal", "not_used", "already_measured"])
def test_physical_blockers_cannot_claim_unearned_donor_grounding(tmp_path, detail):
    missions = _store(tmp_path)
    _contract(missions, measured=detail == "already_measured")
    if detail == "already_measured":
        _retained_envelope(missions)
    mid = _open(missions)["mission_id"]
    _candidate(missions, mid, _spec() if detail == "not_used" else _spec(DONOR))
    request = _request(signal="invented" if detail == "absent_signal" else "KEY")
    need = _need(missions, mid, request, cid="A")
    final = _propose(missions, mid, {"type": "terminal_proposed", "state": "BLOCKED_NEEDS_PHYSICAL_MEASUREMENT",
        "candidate_id": "A", "reason": "claim", "cites": [need]})
    assert final["terminal"]["grounding"] == "agent_assertion"


def test_unknown_signal_fact_grounds_re_but_invented_signal_does_not(tmp_path):
    missions = _store(tmp_path)
    path = _contract(missions)
    raw = json.loads(path.read_text())
    raw["signals"][0]["controller_pin"] = EvidenceValue().to_dict()
    path.write_text(json.dumps(raw))
    for signal, expected in [("KEY", "hs_donor_reading"), ("invented", "agent_assertion")]:
        mid = _open(missions)["mission_id"]
        need = _need(missions, mid, _request(signal), blocker="BLOCKED_NEEDS_REVERSE_ENGINEERING")
        view = _propose(missions, mid, {"type": "terminal_proposed", "state": "BLOCKED_NEEDS_REVERSE_ENGINEERING",
            "reason": "unknown", "cites": [need]})
        assert view["terminal"]["grounding"] == expected


def test_a_finding_cannot_make_a_donor_ready_or_be_cited_as_a_terminal_need(tmp_path):
    missions = _store(tmp_path)
    mid = _open(missions)["mission_id"]
    _candidate(missions, mid, _spec(DONOR))
    view = _propose(missions, mid, _finding())
    with pytest.raises(MissionStateError, match="donor"):
        _ready(missions, mid)
    with pytest.raises(MissionStateError, match="evidence_required"):
        _propose(missions, mid, {"type": "terminal_proposed", "state": "BLOCKED_NEEDS_REVERSE_ENGINEERING",
            "reason": "finding", "cites": [view["last_event_seq"]]})


@pytest.mark.parametrize("layer", ["file", "directory"])
def test_resolver_refuses_symlinks_without_touching_target(tmp_path, layer):
    from hardware_splicer.mission_donors import resolve_donor_contract
    missions = _store(tmp_path)
    path = _contract(missions)
    original = path.read_bytes()
    external = tmp_path / "external.json"
    external.write_bytes(original)
    if layer == "file":
        path.unlink()
        path.symlink_to(external)
    else:
        moved = path.parent.with_name("moved-contracts")
        path.parent.rename(moved)
        path.parent.symlink_to(moved, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        resolve_donor_contract(missions.project_store, "monitor", DONOR)
    assert external.read_bytes() == original


def test_resolver_refuses_identity_substitution(tmp_path):
    from hardware_splicer.mission_donors import resolve_donor_contract
    missions = _store(tmp_path)
    path = _contract(missions)
    raw = json.loads(path.read_text())
    raw["block_id"] = "different"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="identity"):
        resolve_donor_contract(missions.project_store, "monitor", DONOR)


def test_embedded_contract_is_422_and_finding_proposals_cannot_raise_grades(tmp_path):
    from fastapi.testclient import TestClient
    from hardware_splicer.product_api import create_product_app
    missions = _store(tmp_path)
    client = TestClient(create_product_app(missions.project_store))
    base = "/v1/projects/monitor/missions"
    bad = client.post(base, json={"intake": {"goal": "g", "donors": [{"donor_id": DONOR,
        "label": "x", "contract": {"measured": True}}]}, "author": AGENT})
    assert bad.status_code == 422
    mid = _open(missions)["mission_id"]
    route = f"{base}/{mid}/events"
    for extra in [{"grade": "person_measurement"}, {"accepted": True}, {"measured": True}, {"authority": "verified"}]:
        result = client.post(route, json={"event": _finding(**extra), "author": AGENT})
        assert result.status_code == 422, result.text
    offered = client.post(route, json={"event": _finding(), "author": AGENT})
    assert offered.status_code == 201, offered.text
    assert offered.json()["mission"]["donors"][0]["findings"][0]["grade"] == "re_observation"


def test_finding_top_level_author_override_is_refused(tmp_path):
    missions = _store(tmp_path)
    mid = _open(missions)["mission_id"]
    with pytest.raises(MissionValidationError, match="override"):
        _propose(missions, mid, {**_finding(), "author": HUMAN})


def test_donor_findings_remain_readable_after_store_restart(tmp_path):
    from hardware_splicer.mission_store import MissionStore
    missions = _store(tmp_path)
    mid = _open(missions)["mission_id"]
    before = _propose(missions, mid, _finding())
    after = MissionStore(missions.project_store).get_mission("monitor", mid)
    assert before == after


@pytest.mark.parametrize("state,expected", [("observed", "re_observation"), ("inferred", "agent_assertion"),
    ("assumed", "agent_assertion"), ("reference_only", "document"), ("unknown", None)])
def test_contract_fact_grades_follow_epistemic_state_not_accepted_label(tmp_path, state, expected):
    missions = _store(tmp_path)
    path = _contract(missions, measured=True)
    _retained_envelope(missions)
    raw = json.loads(path.read_text())
    raw["signals"][0]["voltage_max_v"]["status"] = state
    path.write_text(json.dumps(raw))
    donor = _open(missions)["donors"][0]
    assert donor["signals"][0]["voltage_max_v"]["grade"] == expected
    assert donor["capabilities"][0]["grade"] == expected
    assert donor["contract_state"] != "verified"


@pytest.mark.parametrize("verified", [True, False])
def test_actual_executor_preserves_donor_gate_without_mock_evaluations(tmp_path, verified):
    from hardware_splicer.mission_executor import run_mission_operation
    missions = _store(tmp_path)
    _contract(missions, measured=verified)
    if verified:
        _retained_envelope(missions)
    mid = _open(missions)["mission_id"]
    _candidate(missions, mid, _spec(DONOR))
    for operation in ["device_plan", "device_engineering"]:
        view = run_mission_operation(missions, "monitor", mid, candidate_id="A", operation=operation)
        assert view["candidates"][0]["evaluations"][-1]["result"]["errors"] == 0
    terminal = {"type": "terminal_proposed", "state": "READY_FOR_HUMAN_BUILD", "candidate_id": "A", "reason": "checked"}
    if verified:
        assert _propose(missions, mid, terminal)["terminal"]["grounding"] == "hs_evaluation"
    else:
        with pytest.raises(MissionStateError, match="voltage_max_v"):
            _propose(missions, mid, terminal)


def test_canonical_projection_does_not_follow_arbitrary_snapshot_evidence(tmp_path):
    missions = _store(tmp_path)
    _contract(missions, measured=True)
    _retained_envelope(missions)
    snapshot = missions.project_store.load("monitor")["snapshot"]
    snapshot["agent_claims"] = snapshot.pop("physicalValidation")
    missions.project_store.save("monitor", snapshot, expected_revision=2)
    assert _open(missions)["donors"][0]["contract_state"] == "partial"


def test_duplicate_physical_evidence_ids_receive_no_credit(tmp_path):
    missions = _store(tmp_path)
    _contract(missions, measured=True)
    _retained_envelope(missions)
    snapshot = missions.project_store.load("monitor")["snapshot"]
    envelopes = snapshot["physicalValidation"]["audited_physical_evidence"]["envelopes"]
    envelopes.append(copy.deepcopy(envelopes[0]))
    missions.project_store.save("monitor", snapshot, expected_revision=2)
    assert _open(missions)["donors"][0]["contract_state"] == "partial"


def test_unknown_direction_does_not_give_a_capability_measurement_grade(tmp_path):
    missions = _store(tmp_path)
    path = _contract(missions, measured=True)
    _retained_envelope(missions)
    raw = json.loads(path.read_text())
    raw["signals"][0]["direction"] = "unknown"
    path.write_text(json.dumps(raw))
    donor = _open(missions)["donors"][0]
    assert donor["capabilities"][0]["grade"] is None
