"""Retrospective repair video replay: leak barriers, native HS intake, safety.

It is a human-authored rules benchmark; cannot be claimed as independent
AI video diagnosis, successful physical repair or even full transcript analysis.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from hardware_splicer.restoration_video_triage import triage

ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/"examples/restoration_video_bench"
spec=importlib.util.spec_from_file_location("restoration_trial",HERE/"run_trial.py")
trial=importlib.util.module_from_spec(spec)
spec.loader.exec_module(trial)
PRED=json.loads((HERE/"evidence/blind_predictions.json").read_text())
EVAL=json.loads((HERE/"evidence/evaluation.json").read_text())

def test_all_real_creator_source_urls_are_honest_and_gold_separated():
    assert len(PRED["predictions"])==4
    assert all(c["source_url"].startswith("https://www.youtube.com/watch?v=")
               for c in PRED["predictions"])
    for p in (HERE/"cases").glob("*.json"):
        case=json.loads(p.read_text())
        assert "root_cause" not in case
        assert "repair_steps" not in case
        assert "reported_outcome" not in case
        assert "source_outcome" not in case
        assert case["repair_intake"]["symptoms"]
        assert case["source_context"]["retrieval_limit"]


def test_predictions_can_be_regenerated_without_opening_hidden_gold():
    assert PRED==trial.prepare()
    # The evaluator reads gold only AFTER writing the actual predictions.
    src=(HERE/"run_trial.py").read_text()
    assert src.index('(out/"blind_predictions.json").write_text(') < src.index("evaluated=score(predicted)")
    assert PRED["gold_labels_loaded_in_prediction_stage"] is False
    assert PRED["source_kind"]=="YouTube public descriptions, not full video analysis"


def test_predictions_are_insensitive_to_gold_fix_text():
    for entry in PRED["predictions"]:
        case=json.loads((HERE/"cases"/(entry["case_id"]+".json")).read_text())
        expected=entry["initial"]
        assert expected==triage(case,stage=0)
        # Out-of-band publication metadata must not influence diagnosis.
        mutated=deepcopy(case)
        mutated["source_context"]["url"]="https://www.youtube.com/watch?v=xxxx"
        mutated["source_context"]["creator"]="different creator"
        assert expected==triage(mutated,stage=0)


def test_leaking_an_outcome_is_rejected_before_ranking():
    case=json.loads(next((HERE/"cases").glob("*.json")).read_text())
    for key in ("root_cause","repair_steps","reported_outcome","hidden_outcome","answer"):
        corrupted={**case,key:"open_power_trace"}
        with pytest.raises(ValueError,match="gold answer"):
            triage(corrupted,0)


def test_unseen_observation_must_fail_closed_not_auto_replace():
    case=json.loads(next((HERE/"cases").glob("*.json")).read_text())
    case["initial_codes"]+=["unknown_gadget_fault_from_social_media"]
    with pytest.raises(ValueError,match="unrecognized"):
        triage(case,0)


def test_initial_and_followup_have_real_differences_without_telling_the_answer():
    gbc=json.loads((HERE/"cases/gbc_2020_broken_power_path.json").read_text())
    initial=triage(gbc,0)
    after=triage(gbc,1)
    assert initial["ranked_differential"][0]["hypothesis_id"]=="corroded_battery_contact"
    assert "open_power_trace" in [r["hypothesis_id"] for r in initial["ranked_differential"]]
    assert after["ranked_differential"][0]["hypothesis_id"]=="open_power_trace"
    assert "battery_path_continuity_open" in after["evidence_codes_used"]
    assert after["new_observations"]
    assert after["native_HS_repair_intake_schema"]=="hardware_splicer.repair_intake.v1"
    for r in after["ranked_differential"]:
        assert len(r["tests_before_repair"])>=2
        assert r["conditional_repair_only_after_measurements"]


def test_recovery_workflow_never_issues_power_repair_or_parts_authority():
    for p in PRED["predictions"]:
        for s in ("initial","followup"):
            result=p[s]
            assert result["scoring"].startswith("explicit human-authored")
            assert result["safety"]["unpowered_visual_and_continuity_checks_first"]
            assert all(v is False for k,v in result["safety"].items()
                       if k!="unpowered_visual_and_continuity_checks_first" and
                       k!="no_unsupported_board_or_parts_substitution")
            assert result["safety"]["no_unsupported_board_or_parts_substitution"]
            assert set(result["release"].values())=={False}


def test_honest_retrospective_scores_and_creator_reporting():
    assert EVAL["status"]=="RETROSPECTIVE_HUMAN_AUTHORED_TRIAGE_REPLAY_NO_PHYSICAL_REPAIR"
    assert EVAL["case_count"]==4
    assert EVAL["metrics_denominator"]==4
    assert EVAL["metrics_counts"]=={
         "initial_hit_at_1":3,"initial_hit_at_3":4,
         "after_observations_hit_at_1":4,"after_observations_hit_at_3":4}
    for row in EVAL["case_results"]:
        assert row["creator_reported_outcome"]
        assert row["HS_did_not_execute_repair"]
        assert row["human_electrical_confirmation_required"]
        assert len(row["creator_outcome_SHA256"])==64


def test_replay_and_scoring_have_exact_receipt_provenance(tmp_path):
    new=trial.run(tmp_path)
    assert (tmp_path/"blind_predictions.json").read_bytes()==(
        HERE/"evidence/blind_predictions.json").read_bytes()
    assert (tmp_path/"evaluation.json").read_bytes()==(
        HERE/"evidence/evaluation.json").read_bytes()
    assert new==EVAL
    assert EVAL["predictions_file_sha256"]==hashlib.sha256(
        (HERE/"evidence/blind_predictions.json").read_bytes()).hexdigest()


def test_no_independence_or_video_vision_overclaim():
    m=EVAL["methodology"]
    for key in ("NOT_scientifically_independent_blind_test",
               "NOT_a_proof_of_generalization",
               "NOT_actual_video_frame_or_transcript_processing",
               "NOT_an_LLM_autonomous_diagnosis",
               "human_authored_rule_taxonomy_postdated_public_case_outcomes",
               "root_cause_is_creator_report_not_independent_test"):
        assert m[key] is True
    assert m["actual_restoration_repaired_by_HS"] is False
    assert m["any_tools_or_parts_purchased"] is False
    assert len(EVAL["open_improvements"])>=4


def test_corroded_contact_is_not_same_as_broken_trace():
    dmg=trial.triage(json.loads((HERE/"cases/dmg_2016_battery_contact_corrosion.json").read_text()),0)
    gbc=trial.triage(json.loads((HERE/"cases/gbc_2020_broken_power_path.json").read_text()),0)
    assert dmg["ranked_differential"][0]["hypothesis_id"]=="corroded_battery_contact"
    assert gbc["ranked_differential"][0]["hypothesis_id"]=="corroded_battery_contact"
    gbc_after=trial.triage(json.loads((HERE/"cases/gbc_2020_broken_power_path.json").read_text()),1)
    assert gbc_after["ranked_differential"][0]["hypothesis_id"]=="open_power_trace"
