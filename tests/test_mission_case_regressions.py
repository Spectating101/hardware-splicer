"""Regression controls from public-document trials, not new live-agent scores."""
import copy
import json

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.device_plan import _validate_spec
from hardware_splicer.mission_executor import run_mission_operation
from hardware_splicer.mission_store import MissionStateError, MissionStore
from hardware_splicer.product_api import create_product_app
from hardware_splicer.salvage_fabrication import build_salvage_fabrication_context
from test_mission_donors import DONOR, OTHER, _open, _spec
from test_mission_feedback import AGENT, _candidate, _evaluate, _propose, _store


def _context(missions, mid):
    return build_salvage_fabrication_context(
        mission_store=missions, project_id="monitor", mission_id=mid)


def test_unsafe_warning_survives_reload_and_is_not_a_measured_finding(tmp_path):
    missions = _store(tmp_path)
    mid = _open(missions)["mission_id"]
    project_before = missions.project_store.load_latest_with_recovery("monitor")
    client = TestClient(create_product_app(missions.project_store))
    base = f"/v1/projects/monitor/missions/{mid}"
    seq = missions.get_mission("monitor", mid)["last_event_seq"]
    response = client.post(base + "/events", json={
        "event": {"type": "evidence_required", "blocker": "BLOCKED_UNSAFE",
                  "need": "Do not proceed with this hazardous goal; consider a separate documented low-voltage task."},
        "author": AGENT, "expected_event_seq": seq})
    assert response.status_code == 201, response.text
    view = response.json()["mission"]
    concern = view["safety_concerns"][0]
    assert concern["need_seq"] == view["last_event_seq"]
    assert concern["grounding"] == "agent_assertion"
    assert concern["author"] == AGENT
    assert concern["state"] == "open"
    assert "Do not proceed" in concern["concern"]
    assert view["needs"][0]["grounding"] == "agent_assertion"
    resumed = MissionStore(missions.project_store)
    assert resumed.get_mission("monitor", mid)["safety_concerns"] == [concern]
    context = _context(resumed, mid)
    assert context["safety_concerns"] == [concern]
    assert context["next_state"]["state"] == "safety_concern_recorded"
    assert "propose_grounded_unsafe_terminal" in context["next_state"]["recommended_intents"]
    assert "await_human_physical_evidence" not in context["next_state"]["recommended_intents"]
    assert view["physical_correctness"] == "UNPROVEN"
    assert not view["power_on_authorized"] and not view["firmware_authorized"]
    assert missions.project_store.load_latest_with_recovery("monitor") == project_before
    final = _propose(resumed, mid, {
        "type": "terminal_proposed", "state": "BLOCKED_UNSAFE",
        "reason": "Unsafe goal, not a request for powered measurements.", "cites": [concern["need_seq"]]})
    assert final["terminal"]["grounding"] == "agent_assertion"
    assert final["safety_concerns"] == [concern]
    assert "build_or_read_package" not in _context(resumed, mid)["next_state"]["recommended_intents"]


def test_hazard_words_do_not_create_a_deterministic_safety_finding(tmp_path):
    missions = _store(tmp_path)
    mid = _open(missions, goal="Microwave transformer high voltage capacitor")["mission_id"]
    _propose(missions, mid, {"type": "evidence_required", "blocker": "BLOCKED_NEEDS_PART_DATA",
                            "need": "Missing documentation, not a safety assessment."})
    context = _context(missions, mid)
    assert context["safety_concerns"] == []
    assert context["truth_contract"]["absence_of_safety_concerns_means_safe"] is False
    assert context["next_state"]["state"] == "evidence_required"


def test_safety_concern_remains_visible_after_independent_proposal(tmp_path):
    missions = _store(tmp_path)
    mid = _open(missions)["mission_id"]
    _propose(missions, mid, {"type": "evidence_required", "blocker": "BLOCKED_UNSAFE",
                            "need": "Do not implement the hazardous proposal."})
    _candidate(missions, mid, _spec())
    context = _context(missions, mid)
    assert context["phase"] == "ARCHITECTING"
    assert context["next_state"]["state"] == "safety_concern_recorded"
    assert context["safety_concerns"][0]["grounding"] == "agent_assertion"


def test_caller_cannot_promote_an_unsafe_warning_through_extra_event_fields(tmp_path):
    missions = _store(tmp_path)
    mid = _open(missions)["mission_id"]
    view = _propose(missions, mid, {
        "type": "evidence_required", "blocker": "BLOCKED_UNSAFE",
        "need": "Explicit concern, not a deterministic HS result.", "grounding": "hs_donor_contract"})
    # Historical proposal envelopes ignore extra non-authority fields; the
    # projection must use the canonical meaning, never that caller label.
    assert "grounding" not in view["events"][-1]
    assert view["safety_concerns"][0]["grounding"] == "agent_assertion"


def test_clean_partial_checks_do_not_hide_missing_required_donor(tmp_path):
    missions = _store(tmp_path)
    mid = _open(missions, inventory=["ESP32"])["mission_id"]
    spec = {"modules": [{"id": "mcu", "module": "esp32-devkitc-v4"}], "connections": [],
            "donor_refs": [DONOR], "reserved_keypad_gpio": ["GPIO4"]}
    _candidate(missions, mid, spec)
    for operation in ("device_plan", "device_engineering"):
        view = run_mission_operation(missions, "monitor", mid, candidate_id="A", operation=operation)
        assert view["candidates"][0]["evaluations"][-1]["result"]["errors"] == 0
    candidate = view["candidates"][0]
    assert candidate["covers_inventory"] is True
    coverage = candidate["donor_coverage"]
    assert coverage["covers_required_donors"] is False
    assert coverage["missing_required_donors"] == [DONOR]
    assert coverage["used_donors"] == []
    assert coverage["coverage_establishes_implementation"] is False
    summary = _context(missions, mid)["candidates"][0]
    assert summary["donor_coverage"] == coverage
    assert summary["spec_diagnostics"] == candidate["spec_diagnostics"]
    with pytest.raises(MissionStateError, match="required donors not covered"):
        _propose(missions, mid, {"type": "terminal_proposed", "state": "READY_FOR_HUMAN_BUILD",
                                "candidate_id": "A", "reason": "Only partial checks passed"})


def test_donor_reference_coverage_is_separate_from_verification_and_implementation(tmp_path):
    missions = _store(tmp_path)
    mid = _open(missions, donors=[
        {"donor_id": DONOR, "label": "Required", "optional": False},
        {"donor_id": OTHER, "label": "Optional", "optional": True}])["mission_id"]
    view = _candidate(missions, mid, _spec(DONOR))
    coverage = view["candidates"][0]["donor_coverage"]
    assert coverage["covers_required_donors"] is True
    assert coverage["missing_required_donors"] == []
    assert coverage["used_donors"] == [DONOR]
    assert coverage["unverified_used_donors"] == [{"donor_id": DONOR, "missing_facts": ["contract"]}]
    assert coverage["coverage_establishes_implementation"] is False
    assert OTHER not in json.dumps(coverage)


def test_invented_fields_are_retained_but_explicitly_unchecked(tmp_path):
    missions = _store(tmp_path)
    mid = _open(missions)["mission_id"]
    spec = _spec()
    spec.update({"donor_refs": [DONOR], "reserved_keypad_gpio": ["GPIO4"]})
    spec["case"]["made_up_case_setting"] = 9
    spec["modules"][0]["invented_pin"] = "GPIO4"
    spec["connections"][0]["invented_protocol"] = "SPI"
    _candidate(missions, mid, spec)
    view = MissionStore(missions.project_store).get_mission("monitor", mid)
    candidate = view["candidates"][0]
    assert candidate["spec"] == spec
    # Reproduce the distinction: event storage kept these keys, the planner drops them.
    clean = _validate_spec(copy.deepcopy(spec))
    assert "reserved_keypad_gpio" not in clean
    assert "invented_pin" not in clean["modules"][0]
    diagnostics = candidate["spec_diagnostics"]
    assert diagnostics["scope"] == "catalog_device_spec"
    assert diagnostics["unrecognized_fields"] == [
        "/case/made_up_case_setting", "/connections/0/invented_protocol",
        "/donor_refs", "/modules/0/invented_pin", "/reserved_keypad_gpio"]
    assert diagnostics["effect"] == "retained_in_proposal_not_checked_by_catalog_planner"
    assert "/donors_used" not in diagnostics["unrecognized_fields"]
    assert _context(missions, mid)["candidates"][0]["spec_diagnostics"] == diagnostics


def test_diagnostics_follow_repairs_without_rewriting_old_events(tmp_path):
    missions = _store(tmp_path)
    mid = _open(missions)["mission_id"]
    spec = _spec(DONOR)
    spec["reserved_keypad_gpio"] = ["GPIO4"]
    _candidate(missions, mid, spec)
    _evaluate(missions, mid, errors=1)
    event_paths = sorted((missions.project_store.root / "monitor" / "missions" / mid / "events").glob("*.json"))
    original = {path: path.read_bytes() for path in event_paths}
    view = _propose(missions, mid, {"type": "repair_proposed", "candidate_id": "A",
                                   "spec": _spec(DONOR), "rationale": "Remove the unchecked extension."})
    candidate = view["candidates"][0]
    assert candidate["spec_diagnostics"]["unrecognized_fields"] == []
    assert candidate["donor_coverage"]["covers_required_donors"] is True
    assert all(path.read_bytes() == data for path, data in original.items())
    assert _context(missions, mid)["candidates"][0]["spec_diagnostics"] == candidate["spec_diagnostics"]


def test_diagnostic_paths_escape_untrusted_keys_and_do_not_claim_type_validation(tmp_path):
    missions = _store(tmp_path)
    mid = _open(missions)["mission_id"]
    spec = _spec()
    spec["extension/with~punctuation"] = {"secret_meaning": "not a checked field"}
    spec["case"]["wall_mm"] = "not a number"
    view = _candidate(missions, mid, spec)
    assert view["candidates"][0]["spec_diagnostics"]["unrecognized_fields"] == ["/extension~1with~0punctuation"]
    # Known keys are not necessarily valid: this is omission reporting, not validation.
    with pytest.raises(ValueError, match="wall_mm"):
        _validate_spec(spec)


@pytest.mark.parametrize("spec", [{}, {"alternatives": [{"label": "Keep the device intact"}]}])
def test_generic_partial_proposals_are_not_rejected_by_catalog_diagnostics(tmp_path, spec):
    missions = _store(tmp_path)
    mid = _open(missions)["mission_id"]
    # _candidate's helper substitutes its default for {}, so propose directly here.
    view = _propose(missions, mid, {"type": "candidate_proposed", "candidate": {
        "id": "A", "kind": "reclaim_heavy", "label": "Bounded proposal",
        "spec": spec, "rationale": "Not a catalog implementation."}})
    assert view["candidates"][0]["spec"] == spec
    assert view["terminal"] is None


def test_intact_reuse_is_not_mislabelled_as_unknown_catalog_fields(tmp_path):
    missions = _store(tmp_path)
    mid = _open(missions)["mission_id"]
    spec = {"design_class": "intact_input_reuse", "donors_used": [DONOR],
            "source_ids": ["reference"], "interface": {}, "mechanical": {}}
    view = _candidate(missions, mid, spec)
    diagnostics = view["candidates"][0]["spec_diagnostics"]
    assert diagnostics["scope"] == "intact_reuse_check_required"
    assert diagnostics["unrecognized_fields"] == []
    assert view["terminal"] is None


def test_discoverable_guidance_distinguishes_useful_progress_and_explicit_unsafe_refusal():
    from hardware_splicer.mission_agent_contract import mission_event_openapi
    from hardware_splicer.salvage_fabrication_manifest import salvage_fabrication_manifest
    from pathlib import Path

    schema = mission_event_openapi()["requestBody"]["content"]["application/json"]["schema"]
    need = next(item for item in schema["properties"]["event"]["oneOf"]
                if item["properties"]["type"]["const"] == "evidence_required")
    assert "BLOCKED_UNSAFE" in need["description"]
    assert "agent_assertion" in need["description"]
    manifest = salvage_fabrication_manifest()
    instructions = " ".join(manifest["workflow"])
    assert "donor_coverage" in instructions and "spec_diagnostics" in instructions
    quickstart = (Path(__file__).resolve().parents[1] / "docs" / "AGENT_QUICKSTART.md").read_text()
    assert "BLOCKED_UNSAFE" in quickstart and "not checked by the catalog planner" in quickstart
    assert "A chat-only plan is not a saved deliverable" in quickstart
