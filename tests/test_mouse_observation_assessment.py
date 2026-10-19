"""Software-only observation/mission trial, including negative provenance tests."""
from __future__ import annotations

import copy
import hashlib
import json

import pytest

from hardware_splicer.mouse_observation_assessment import (
    ObservationAssessmentRefused, assess_observation, assessment_bytes,
)
from scripts.run_mouse_observation_mission_trial import TRACE, trial


PROJECT = "unit"
MISSION = "mission-unit"
BASE = {"device_alias": "donor_mouse", "button": "left", "action": "activate"}


def run(trace=TRACE, interface=None, origin="synthetic_fixture", expected_actions=1):
    return assess_observation(
        trace, interface=BASE if interface is None else interface,
        origin=origin, expected_actions=expected_actions,
        project_id=PROJECT, mission_id=MISSION, candidate_id="x",
    )


def test_declared_synthetic_success_is_never_physical_evidence():
    result = run()
    assert result["assessment"] == "software_binding_matches_trace"
    assert result["symbolic_actions"] == 1
    assert result["physical_correctness"] == "UNPROVEN"
    assert result["source_authenticity_verified"] is False
    assert result["human_review_required"] is True
    assert result["physical_authority_granted"] is False
    assert result["capture_sha256"] == hashlib.sha256(TRACE).hexdigest()
    assert assessment_bytes(result).endswith(b"\n")
    assert assessment_bytes(result) == assessment_bytes(copy.deepcopy(result))


def test_wrong_alias_yields_failed_software_mapping_even_if_offline_adapter_is_internally_clean():
    expected = {**BASE, "device_alias": "wrong_alias"}
    result = run(interface=expected)
    assert result["assessment"] == "proposed_alias_mismatch"
    assert result["symbolic_actions"] == 0
    assert result["observed_alias"] == "donor_mouse"
    assert result["source_authenticity_verified"] is False


def test_operator_supplied_origin_does_not_self_certify_capture_authenticity():
    report = run(origin="operator_supplied_unverified_host_capture")
    assert report["assessment"] == "software_binding_matches_trace"
    assert report["source_authenticity_verified"] is False
    assert report["physical_correctness"] == "UNPROVEN"


@pytest.mark.parametrize("mode", ["physical_measurement", "calibrated_capture", "trusted_sensor"])
def test_refuses_invented_origin_authority(mode):
    with pytest.raises(ObservationAssessmentRefused, match="origin"):
        run(origin=mode)


@pytest.mark.parametrize("invalid", [
    b"",
    b"not JSONL\n",
    b'{"type":"connected","device":"mouse"}\n',
    b'{"type":"connected","device":"donor_mouse","device_id":"sensitive"}\n{"type":"disconnected","device":"donor_mouse"}\n',
    b'{"type":"connected","device":"donor_mouse"}\n{"type":"pressed","device":"other","button":"left"}\n{"type":"disconnected","device":"donor_mouse"}\n',
    b'{"type":"connected","device":"donor_mouse"}\n{"type":"pressed","device":"donor_mouse","button":"middle"}\n{"type":"disconnected","device":"donor_mouse"}\n',
    b'{"type":"connected","device":"donor_mouse"}\n{"type":"released","device":"donor_mouse","button":"left"}\n',
    b'{"type":"connected","device":"donor_mouse"}\n{"type":"connected","device":"donor_mouse"}\n{"type":"disconnected","device":"donor_mouse"}\n',
    b'{"type":"connected","device":"donor_mouse"}\n{"type":"disconnected","device":"donor_mouse"}\n{"type":"pressed","device":"donor_mouse","button":"left"}\n',
    b'\xff\x80\n',
])
def test_corrupt_trace_or_unsafe_assumptions_refuse(invalid):
    with pytest.raises(ObservationAssessmentRefused):
        run(trace=invalid)


def test_bounded_trace_and_expected_actions():
    with pytest.raises(ObservationAssessmentRefused):
        run(trace=TRACE * 6000)
    with pytest.raises(ObservationAssessmentRefused):
        run(expected_actions=-1)
    with pytest.raises(ObservationAssessmentRefused):
        run(expected_actions=True)


def test_trace_hash_changes_with_actual_bytes_not_guessable_metadata():
    modified = TRACE.replace(b'"pressed"', b'"released"')
    report = run(modified)
    assert report["capture_sha256"] != run()["capture_sha256"]
    assert report["symbolic_actions"] != run()["symbolic_actions"]
    assert report["assessment"] == "insufficient_activation_evidence"


def test_binding_scope_rejects_unmodeled_buttons_and_authority_fields():
    with pytest.raises(ObservationAssessmentRefused):
        run(interface={**BASE, "physical_validated": "true"})
    with pytest.raises(ObservationAssessmentRefused):
        run(interface={**BASE, "button": "right"})


def test_actual_hs_mission_uses_two_candidate_checks_and_ends_blocked():
    receipt = trial()
    assert receipt["schema_version"] == "hardware_splicer.observation_trial_receipt.v1"
    assert receipt["scope"] == "SYNTHETIC_SOFTWARE_ONLY"
    assert receipt["initial_assessment"]["assessment"] == "proposed_alias_mismatch"
    assert receipt["revised_assessment"]["assessment"] == "software_binding_matches_trace"
    assert receipt["synthetic_trace_sha256"] == receipt["revised_assessment"]["capture_sha256"]
    assert receipt["tested_candidates"] == ["initial", "revised"]
    assert len(receipt["review_bundle_sha256"]) == 2
    assert all(entry["errors"] == 0 for entry in receipt["software_checks"])
    assert receipt["mission_terminal"] == "BLOCKED_NEEDS_PHYSICAL_MEASUREMENT"
    assert receipt["prototype_package_status"] == "blocked"
    assert receipt["no_physical_device_access"] is True
    assert receipt["human_acceptance_on_mission"] is True
    assert receipt["human_review_required"] is True
    assert receipt["power_on_authorized"] is False
    assert receipt["firmware_authorized"] is False
    assert receipt["physical_correctness"] == "UNPROVEN"
    assert receipt["unresolved_evidence_need"]["blocker"] == "BLOCKED_NEEDS_PHYSICAL_MEASUREMENT"
    assert "SYNTHETIC-ONLY" in receipt["unresolved_evidence_need"]["need"]


def test_duplicate_json_keys_cannot_replace_an_event_field():
    duplicate = (b'{"type":"connected","device":"donor_mouse","device":"unexpected"}\n'
                 b'{"type":"disconnected","device":"donor_mouse"}\n')
    with pytest.raises(ObservationAssessmentRefused, match="duplicate"):
        run(trace=duplicate)


def test_no_press_does_not_claim_binding_verified():
    no_activity = (b'{"type":"connected","device":"donor_mouse"}\n'
                   b'{"type":"disconnected","device":"donor_mouse"}\n')
    report = run(trace=no_activity, expected_actions=0)
    assert report["assessment"] == "insufficient_activation_evidence"
    assert report["source_authenticity_verified"] is False


def test_assess_cli_reads_existing_file_only(tmp_path):
    import subprocess
    import sys

    trace_path = tmp_path / "synthetic.jsonl"
    trace_path.write_bytes(TRACE)
    cmd = [
        sys.executable, "-m", "hardware_splicer.mouse_observation_assessment",
        "--trace", str(trace_path), "--device-alias", "donor_mouse",
        "--origin", "synthetic_fixture", "--expected-actions", "1",
        "--project-id", PROJECT, "--mission-id", MISSION, "--candidate-id", "x",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["assessment"] == "software_binding_matches_trace"
    denied = subprocess.run(cmd[:], capture_output=True, text=True, check=False)
    assert denied.returncode == 0
    denied_origin = subprocess.run([*cmd, "--origin", "physical_measurement"], capture_output=True, text=True)
    assert denied_origin.returncode != 0
