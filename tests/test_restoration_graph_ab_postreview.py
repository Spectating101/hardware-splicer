"""Post-freeze, no-model A/B grader tests. The outcome snapshot lives only
in a separate postreview PR stacked above the pre-outcome inference PR.
"""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
D=ROOT/"examples/restoration_video_bench/diversity"
spec=importlib.util.spec_from_file_location("postreview",D/"score_graph_ab_postreview.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
PRED=D/"evidence/graph_ab_six_live.json"
REVIEW=D/"evidence/graph_ab_postreview_annotations.json"
CREATOR=D/"evidence/graph_ab_review_source_PR321.json"
SCORE=D/"evidence/graph_ab_postreview_score.json"

def test_reproducible_postfreeze_scores():
    result=mod.score(PRED,REVIEW,CREATOR)
    assert result["case_count"]==6
    assert result["reviewed_distinct_faults"]==8
    assert result["grade_counts"]=={
        "plain":{"exact_family":4,"partial_domain":4,"miss":0},
        "hs_graph":{"exact_family":3,"partial_domain":4,"miss":1},
    }
    assert result["cases_with_top_ranked_exact_family"]=={"plain":3,"hs_graph":2}
    assert result["cases_with_all_distinct_faults_exact_family"]=={"plain":2,"hs_graph":1}
    assert result["HS_cases_with_unsourced_numeric_thresholds"]==1
    assert result["no_independent_blinded_reviewer"] is True
    assert result["runtime_results"]["plain"]["valid"]==6
    assert result["runtime_results"]["hs_graph"]["valid"]==6
    assert result==json.loads(SCORE.read_text())

def test_nonindependent_human_review_disclosed():
    text=REVIEW.read_text().lower()
    assert "not an independent blinded reviewer" in text
    assert "postreview" in text
    assert "one disjunctive hypothesis" in text

def test_tampered_predictions_fail_closed(tmp_path):
    altered=json.loads(PRED.read_text())
    altered["cases"][0]["arms"]["plain"]["receipt"]["plan"]["summary"]="rewritten after creator fixes"
    dest=tmp_path/"pred.json"
    dest.write_text(json.dumps(altered))
    with pytest.raises(ValueError,match="predictions changed"):
        mod.score(dest,REVIEW,CREATOR)

def test_tampered_creator_outcome_file_fails_closed(tmp_path):
    altered=json.loads(CREATOR.read_text())
    altered["outcomes"][0]["creator_reported_result"]="fabricated result"
    path=tmp_path/"creator.json"
    path.write_text(json.dumps(altered))
    with pytest.raises(ValueError,match="creator outcome source changed"):
        mod.score(PRED,REVIEW,path)

def test_false_manual_rank_is_rejected(tmp_path):
    ann=json.loads(REVIEW.read_text())
    ann["cases"][0]["faults"][0]["plain"]["hypothesis_rank"]=50
    path=tmp_path/"review.json"
    path.write_text(json.dumps(ann))
    with pytest.raises(ValueError,match="rank outside"):
        mod.score(PRED,path,CREATOR)

def test_unknown_outcome_labels_cannot_be_substituted(tmp_path):
    ann=json.loads(REVIEW.read_text())
    ann["cases"][0]["faults"][0]["fault"]="A different, invented failure mechanism"
    path=tmp_path/"review.json"
    path.write_text(json.dumps(ann))
    with pytest.raises(ValueError,match="fault labels differ"):
        mod.score(PRED,path,CREATOR)

def test_manual_review_does_not_report_unverified_accuracy_as_truth():
    data=json.loads(SCORE.read_text())
    assert data["not_a_reliability_or_statistical_significance_claim"] is True
    assert data["no_independent_blinded_reviewer"] is True
    assert data["analysis_not_accessible_to_initial_model_prompts"] is True
