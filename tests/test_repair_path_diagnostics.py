from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from hardware_splicer.repair_path_diagnostics import rank_repair_hypotheses

DATA = Path(__file__).resolve().parents[1] / "benchmarks/real_repairs_20261023/blind_cases.json"


def cases():
    return {
        c["case_id"]: c
        for c in json.loads(DATA.read_text(encoding="utf-8"))["cases"]
    }


@pytest.mark.parametrize("case_id,expected", [
    ("case_A_2013", "internal_flex"),
    ("case_B_2014", "sata_host_port"),
    ("case_C_synthetic", "suspect_drive"),
])
def test_ranked_causes_follow_actual_path_substitution_not_fixed_repair_rule(case_id, expected):
    result = rank_repair_hypotheses(cases()[case_id])
    assert result["candidates"][0]["component_id"] == expected
    assert result["verdict"] == "triage_hypothesis_only"
    assert result["physical_repair_verified"] is False
    assert result["known_successful_repair"] is False
    assert result["model_inference_used"] is False


def test_single_joystick_drift_symptom_abstains():
    report = rank_repair_hypotheses(cases()["case_D_2025"])
    assert report["verdict"] == "insufficient_discriminating_evidence"
    assert report["candidate_count"] == 0
    assert report["candidates"] == []


def test_reference_labels_never_enter_inference():
    x = cases()["case_A_2013"]
    for secret_key in ("ground_truth", "confirmed_root_cause", "resolution", "answer_key"):
        with pytest.raises(ValueError):
            rank_repair_hypotheses({**x, secret_key: "internal_flex"})


def test_post_repair_success_is_not_allowed_into_blind_input():
    x = copy.deepcopy(cases()["case_A_2013"])
    x["interventions"] = [{"component_id": "internal_flex", "outcome": "restored"}]
    with pytest.raises(ValueError):
        rank_repair_hypotheses(x)


def test_unknown_topology_or_bad_risk_rank_rejected():
    x = copy.deepcopy(cases()["case_A_2013"])
    x["path_tests"][0]["path"] = ["fake"]
    with pytest.raises(ValueError):
        rank_repair_hypotheses(x)
    y = copy.deepcopy(cases()["case_B_2014"])
    y["components"][0]["service_cost_rank"] = -1
    with pytest.raises(ValueError):
        rank_repair_hypotheses(y)


def test_ineffective_cable_replacement_reduces_cable_priority():
    x = copy.deepcopy(cases()["case_B_2014"])
    with_replacements = rank_repair_hypotheses(x)
    x["interventions"] = []
    without_replacements = rank_repair_hypotheses(x)
    def lookup(report, cid):
        return next(v for v in report["candidates"] if v["component_id"] == cid)
    assert lookup(with_replacements, "internal_flex")["triage_evidence_score_not_probability"] \
           < lookup(without_replacements, "internal_flex")["triage_evidence_score_not_probability"]


def test_no_new_device_or_power_authority_claimed():
    for case in cases().values():
        report = rank_repair_hypotheses(case)
        assert report["authority"] == "symptom_and_test_evidence_only"
        assert report["physical_repair_verified"] is False
        assert "POWER_ON_AUTHORIZED" not in str(report)
        assert "fabrication_authorized" not in str(report)


def test_real_repair_intake_workflow_surfaces_hypotheses_only_from_structured_tests():
    from hardware_splicer.repair_intake import (
        apply_repair_intake_context, repair_intake_report
    )
    for case in cases().values():
        enriched = apply_repair_intake_context(case)
        report = repair_intake_report(case)
        assert enriched["repair_path_diagnostic"] == report["repair_path_diagnostic"]
        assert report["repair_path_diagnostic"]["physical_repair_verified"] is False
        assert report["repair_path_diagnostic"]["authority"] == "symptom_and_test_evidence_only"


def test_plain_repair_intake_without_structured_paths_does_not_invent_a_diagnosis():
    from hardware_splicer.repair_intake import apply_repair_intake_context
    intake = {"repair_intake": {"device_hint": "Unknown device", "symptoms": ["Does not start"]}}
    output = apply_repair_intake_context(intake)
    assert "repair_path_diagnostic" not in output
