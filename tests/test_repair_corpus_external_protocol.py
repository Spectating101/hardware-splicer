"""Prompt leakage and external-scoring authenticity gates."""
from __future__ import annotations
import importlib.util
import json
import sys
from pathlib import Path
import pytest
from hardware_splicer.repair_intake import apply_repair_intake_context

ROOT=Path(__file__).resolve().parents[1]/"benchmarks/repair_corpus_v2_20261023"


def _load(name):
    if str(ROOT) not in sys.path:
        sys.path.insert(0,str(ROOT))
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+".py"))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_external_prompts_hide_source_url_and_post_repair_results():
    mod=_load("prepare_external_prompts")
    cases=json.loads((ROOT/"blind_observations.json").read_text())["cases"]
    prompts=mod.make_model_prompts(cases)
    assert len(prompts)==16
    assert len({p["case_id"] for p in prompts})==16
    for prompt in prompts:
        s=json.dumps(prompt).lower()
        for forbidden in ["ifixit","https://","ground_truth","confirmed_root_cause","reported_resolution_component","source_url"]:
            assert forbidden not in s


def test_external_scoring_requires_actual_transcript_receipts(tmp_path):
    mod=_load("score_external_baseline")
    p=tmp_path/"responses.json"
    p.write_text(json.dumps({"provider":"actual-provider","model":"some-model","predictions":[]}))
    with pytest.raises(ValueError):
        mod.score_predictions(ROOT,p)


def test_naive_baseline_and_hs_both_see_identical_case_observations():
    harness=_load("evaluate")
    cases=json.loads((ROOT/"blind_observations.json").read_text())["cases"]
    for case in cases:
        h=apply_repair_intake_context(case)["repair_path_diagnostic"]
        base=harness.naive_frequency_baseline(case)
        assert base["method"]=="most_frequent_failed_path"
        assert h["model_inference_used"] is False
        assert h["authority"]=="symptom_and_test_evidence_only"


def test_temperature_or_power_load_alone_not_a_fake_replacement_component():
    cases=json.loads((ROOT/"blind_observations.json").read_text())["cases"]
    case=next(c for c in cases if c["case_id"]=="R08")
    all_ids={x["id"] for x in case["repair_intake"]["path_evidence"]["components"]}
    assert "console_load" not in all_ids
    assert "console_idle" not in all_ids
    routes={tuple(sorted(test["path"])) for test in case["repair_intake"]["path_evidence"]["path_tests"]}
    assert len(routes)==1
