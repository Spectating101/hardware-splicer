"""Independent, newly authored test scenarios for physical repair fault isolation.

These cases are synthetic negative and behavioral tests. They are NOT new
confirmed repair examples, not physical test outcomes, and not part of frozen v2.
"""
from __future__ import annotations

import copy

from hardware_splicer.repair_discrimination import evaluate_path_evidence
from hardware_splicer.repair_intake import apply_repair_intake_context
from hardware_splicer.repair_path_diagnostics import rank_repair_hypotheses


def _component(cid: str, *, cost: int=2, reversible: bool=True) -> dict:
    return {
        "id": cid, "label": cid,
        "service_cost_rank": cost,
        "reversible_test_available": reversible,
    }


def _case(components, observations, interventions=None):
    return {
        "components": [_component(k, cost=5 if k=="controller" else 2,
                                  reversible=k!="controller") for k in components],
        "path_tests": [
            {"id": f"obs-{i}", "path": list(path), "outcome": outcome,
             "condition": condition}
            for i,(path,outcome,condition) in enumerate(observations)
        ],
        "interventions": interventions or [],
    }


def test_load_failure_and_idle_pass_on_same_hardware_path_abstains():
    case=_case(
        ("source","driver","load"),
        [
            (["source","driver","load"],"pass","idle"),
            (["source","driver","load"],"fail","high_load"),
        ],
    )
    report=rank_repair_hypotheses(case)
    assert report["verdict"] == "insufficient_discriminating_evidence"
    assert report["reason"] == "operating_condition_confounded"
    assert report["candidate_count"] == 0
    assert report["evidence_quality"]["distinct_component_route_count"] == 1
    assert len(report["evidence_quality"]["contradictory_same_route_observations"])==1
    assert report["recommended_tests"][0]["code"] == "record_operating_condition_delta"
    assert "load" in report["next_test_strategy"]
    assert report["recommended_tests"][0]["power_on_authorized"] is False


def test_confounded_route_with_extra_working_route_still_abstains():
    case=_case(
        ("source","driver","load","backup"),
        [
            (["source","driver","load"],"pass","cold"),
            (["source","driver","load"],"fail","hot"),
            (["source","backup"],"pass","cold"),
        ],
    )
    report=rank_repair_hypotheses(case)
    assert report["reason"] == "operating_condition_confounded"
    assert report["candidate_count"] == 0
    assert report["evidence_quality"]["distinct_component_route_count"] == 2


def test_same_path_repeated_failures_cannot_become_independent_topology():
    case=_case(
        ("motor","supply","controller"),
        [
            (["motor","supply","controller"],"fail","first_try"),
            (["motor","supply","controller"],"fail","second_try"),
        ],
    )
    report=rank_repair_hypotheses(case)
    assert report["reason"] == "insufficient_distinct_routes"
    assert report["recommended_tests"][0]["code"] == "obtain_second_independent_path_observation"


def test_distinct_failed_and_working_routes_propose_reversible_test():
    case=_case(
        ("shared_supply","bad_driver","working_driver","motor"),
        [
            (["shared_supply","bad_driver","motor"],"fail","normal"),
            (["shared_supply","working_driver","motor"],"pass","normal"),
        ],
    )
    report=rank_repair_hypotheses(case)
    assert report["verdict"] == "triage_hypothesis_only"
    assert report["candidates"][0]["component_id"] == "bad_driver"
    assert report["evidence_quality"]["distinct_component_route_count"] == 2
    assert report["recommended_tests"][0]["component_id"] == "bad_driver"
    assert report["recommended_tests"][0]["code"] == "controlled_known_good_substitution_review"
    assert report["recommended_tests"][0]["physical_repair_verified"] is False


def test_expensive_controller_is_not_automatically_replacement_authorized():
    case=_case(
        ("controller","sensor","spare_sensor"),
        [
            (["controller","sensor"],"fail","normal"),
            (["controller","spare_sensor"],"pass","normal"),
        ],
    )
    report=rank_repair_hypotheses(case)
    assert report["candidates"][0]["component_id"] == "sensor"
    assert all(p["status"]=="proposal_only" for p in report["recommended_tests"])
    assert all(not p["power_on_authorized"] for p in report["recommended_tests"])
    assert not report["physical_repair_verified"]


def test_no_change_intervention_does_not_get_repeated_replacement_advice():
    case=_case(
        ("supply","motor","driver","known_good_motor"),
        [
            (["supply","motor","driver"],"fail","normal"),
            (["supply","known_good_motor","driver"],"pass","normal"),
        ],
        [{"component_id":"motor","outcome":"no_change"}],
    )
    report=rank_repair_hypotheses(case)
    target=next(p for p in report["recommended_tests"] if p["component_id"]=="motor")
    assert target["code"] == "verify_ineffective_substitution"
    assert "do not repeat" in target["proposed_observation"]


def test_optional_structured_evidence_survives_without_prose_symptoms():
    case=_case(
        ("motor","source","spare_source"),
        [
            (["motor","source"],"fail","normal"),
            (["motor","spare_source"],"pass","normal"),
        ],
    )
    report=apply_repair_intake_context({"case_id":"structured-only","repair_intake":{"path_evidence":case}})
    assert report["repair_path_diagnostic"]["verdict"]=="triage_hypothesis_only"
    assert report["repair_path_diagnostic"]["case_id"]=="structured-only"


def test_condition_labels_do_not_influence_physical_path_adequacy():
    observations=[
        {"outcome":"pass","path":["a","b"],"condition":"fan_off"},
        {"outcome":"fail","path":["b","a"],"condition":"fan_on"},
    ]
    result=evaluate_path_evidence(observations)
    assert result["distinct_component_route_count"]==1
    assert result["status"]=="operating_condition_confounded"
    assert result["discriminating_topology_supported"] is False


def test_adding_extra_duplicate_observations_does_not_promote_abstention():
    case=_case(
        ("a","b"),
        [
            (["a","b"],"fail","attempt_1"),
            (["a","b"],"fail","attempt_2"),
        ],
    )
    before=rank_repair_hypotheses(case)
    extended=copy.deepcopy(case)
    extended["path_tests"].extend(copy.deepcopy(case["path_tests"]))
    after=rank_repair_hypotheses(extended)
    assert before["verdict"]==after["verdict"]=="insufficient_discriminating_evidence"
    assert before["candidate_count"]==after["candidate_count"]==0
