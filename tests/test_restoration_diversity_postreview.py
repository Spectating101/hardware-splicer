"""Check sealed comparison against creator-narrated postreview faults."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/"examples/restoration_video_bench/diversity"
S=HERE/"postreview/score_faults.py"
spec=importlib.util.spec_from_file_location("postfreeze_score",S)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def test_review_counts_and_specificity():
    score=m.assess()
    assert score["n_cases"]==9
    assert score["n_resolved_cases"]==7
    assert score["n_unscored_cases"]==2
    assert score["n_creator_reported_faults_scored"]==9
    assert score["exact_fault_family"]==5
    assert score["broad_domain_only"]==3
    assert score["missed_faults"]==1
    assert score["exact_fault_family_top1"]==2
    assert score["cases_all_reported_faults_exact"]==3
    for key in ("NOT_native_HS_diagnostic_result",
                "NOT_independent_ground_truth",
                "NOT_video_frame_evaluation",
                "NOT_a_proof_of_generalization"):
        assert score[key] is True
    committed=json.loads((HERE/"postreview/score.json").read_text())
    assert committed==score

def test_creator_outcomes_only_exist_in_postreview():
    manifest=json.loads((HERE/"cases.json").read_text())
    assert all("root_cause" not in c for c in manifest["cases"])
    assert not list((HERE/"evidence").glob("*creator_outcome*"))
    raw=json.loads((HERE/"evidence/raw_rule_baseline.json").read_text())
    assert raw["creator_outcomes_read"] is False
    assert raw["legacy_triage_accepted_raw_text"]==0

def test_canon_and_xbox_not_forced_to_success():
    scored={r["case_id"]:r for r in m.assess()["case_results"]}
    for case in ("canon_eos2000d_no_power","xbox_series_s_dead"):
        assert not scored[case]["faults"]
        assert scored[case]["status"]!="resolved"

def test_coffee_machine_has_two_distinct_faults_not_one_generic_win():
    r=next(r for r in m.assess()["case_results"]
           if r["case_id"]=="delonghi_eletta_faults")
    assert len(r["faults"])==2
    assert {f["match_quality"] for f in r["faults"]}=={"miss","exact_family"}

def test_broad_component_guesses_are_not_exact():
    r={x["case_id"]:x for x in m.assess()["case_results"]}
    for name in ("a53_touch_failure","dewalt_blower_intermittent",
                 "reebok_treadmill_dead"):
        assert any(f["match_quality"]=="partial_domain" for f in r[name]["faults"])

def test_tampering_with_prediction_invalidates_postreview(tmp_path):
    prediction=json.loads(m.PRED.read_text())
    prediction["predictions"][0]["hypotheses"][0]["mechanism"]="hindsight_edit"
    p=tmp_path/"modified_prediction.json"
    p.write_text(json.dumps(prediction))
    with pytest.raises(ValueError,match="changed after sealed"):
        m.assess(prediction_file=p)

def test_unknown_mechanism_cannot_be_inserted_by_reviewer(tmp_path):
    data=json.loads(m.REVIEW.read_text())
    row=next(r for r in data["outcomes"] if r["case_id"]=="ps5_pro_no_power_hdmi")
    row["faults"][0]["matched_hypothesis"]="injected_spoiler"
    p=tmp_path/"fake_outcomes.json"
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError,match="cannot credit"):
        m.assess(review_file=p)

def test_unresolved_cases_cannot_accumulate_lucky_hits(tmp_path):
    data=json.loads(m.REVIEW.read_text())
    row=next(r for r in data["outcomes"] if r["case_id"]=="xbox_series_s_dead")
    row["faults"]=[{"fault":"test","timestamp":"0:01","rationale":"test",
                   "match_quality":"miss","matched_hypothesis":None}]
    p=tmp_path/"fake_outcomes.json"
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError,match="must remain unscored"):
        m.assess(review_file=p)
