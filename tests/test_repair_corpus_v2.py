"""Independent corpus harness controls; never load outcome labels in HS intake."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import pytest
from hardware_splicer.repair_path_diagnostics import rank_repair_hypotheses
from hardware_splicer.repair_intake import apply_repair_intake_context

BASE = Path(__file__).resolve().parents[1]/"benchmarks/repair_corpus_v2_20261023"


def _inputs():
    return json.loads((BASE/"blind_observations.json").read_text())["cases"]


def test_inputs_are_separate_from_outcomes_and_all_sources_present():
    x=_inputs()
    assert len(x)==16 and len({c["case_id"] for c in x})==16
    assert all(c["source_url"].startswith("https://www.ifixit.com/") for c in x)
    for case in x:
        assert not {"gold","resolution","answer_key","confirmed_root_cause"} & set(case)
        assert "physical_repair_verified" not in str(case)
        assert case["repair_intake"]["path_evidence"]["path_tests"]


@pytest.mark.parametrize("case_id", [f"R{i:02d}" for i in range(1,17)])
def test_every_case_runs_without_outcome_or_device_specific_logic(case_id):
    case=next(c for c in _inputs() if c["case_id"]==case_id)
    out=apply_repair_intake_context(case)["repair_path_diagnostic"]
    assert out["physical_repair_verified"] is False
    assert out["model_inference_used"] is False
    assert out["known_successful_repair"] is False
    assert out["authority"]=="symptom_and_test_evidence_only"


def test_shuffling_candidate_components_does_not_change_inference():
    for case in _inputs():
        obj=case["repair_intake"]["path_evidence"]
        from copy import deepcopy
        before=rank_repair_hypotheses(obj)
        shuffled=deepcopy(obj)
        shuffled["components"]=list(reversed(shuffled["components"]))
        assert before["candidates"]==rank_repair_hypotheses(shuffled)["candidates"]


def test_zero_successful_repair_outcome_can_be_inserted_into_blind_input():
    candidate=copy.deepcopy(_inputs()[0]["repair_intake"]["path_evidence"])
    candidate["ground_truth"]="charger_flex"
    with pytest.raises(ValueError):
        rank_repair_hypotheses(candidate)
