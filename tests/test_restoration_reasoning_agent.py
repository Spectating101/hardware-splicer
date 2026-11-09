"""Behavioral tests for HS free-text, evidence-grounded local model calls."""
import json
import importlib.util
from pathlib import Path

import pytest

from hardware_splicer.restoration_reasoning_agent import (
    build_context, build_messages, diagnose, ollama_chat, validate_model_output
)

ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/"examples/restoration_video_bench/diversity"
s=importlib.util.spec_from_file_location("run_local", HERE/"run_live_agent.py")
runner=importlib.util.module_from_spec(s)
s.loader.exec_module(runner)
CASES={c["case_id"]:c for c in runner.prepare()}
BASE=CASES["bosch_dryer_slow_heat"]

def fixture_response(**overrides):
    response={
        "summary":"Slow drying might reflect poor exhaust flow.",
        "hypotheses":[{"mechanism":"Airflow restriction",
                        "why":"Slow drying is reported, but the heat button was not measured.",
                        "evidence_ids":["E1","E2"],
                        "safe_test":"Unplug and inspect accessible lint filter and external vent for obstruction."}],
        "next_safe_check":"Unplug first, then check the accessible vent for kinks.",
        "uncertainty":"The vent condition is not yet observed.",
        "abstain":False
    }
    response.update(overrides)
    return json.dumps(response)

def scripted(messages, **kwargs):
    return {"provider":"test_double","model":"scripted_model","content":fixture_response(),
            "prompt_tokens":40,"completion_tokens":90}

def test_real_native_intake_supports_all_nine_with_no_manual_codes():
    assert len(CASES)==9
    assert len({v["evidence_sha256"] for v in CASES.values()})==9
    for c in CASES.values():
        assert c["native_HS_repair_intake_schema"]=="hardware_splicer.repair_intake.v1"
        assert all(e["id"]==f"E{i+1}" for i,e in enumerate(c["evidence"]))
        assert "root_cause" not in str(c).lower()

def test_mocked_inference_is_an_actual_adapter_call_not_fixed_rule():
    called=[]
    def fake(messages, **kwargs):
        called.append((messages,kwargs))
        return scripted(messages,**kwargs)
    r=diagnose(BASE,inference=fake)
    assert len(called)==1
    assert r["status"]=="proposed_unverified_differential"
    assert r["plan"]["hypotheses"][0]["evidence_ids"]==["E1","E2"]
    assert r["model_called"] is True
    assert r["actual_video_frames_analyzed"] is False
    assert r["repair_authorized"] is False
    assert r["parts_purchase_authorized"] is False
    assert r["receipt_sha256"]
    assert "postreview" not in json.dumps(called).lower()

def test_no_gold_can_enter_native_context():
    with pytest.raises(ValueError,match="outcome"):
        build_context(case_id="x",device="x",repair_intake={
            "symptoms":["dead"],"device_hint":"x","root_cause":"spoiler"},
            source_url=BASE["source_url"],hazards=["ac_mains"],evidence_stage="title")

def test_hallucinated_evidence_id_fails_closed():
    body=json.loads(fixture_response())
    body["hypotheses"][0]["evidence_ids"]=["E99"]
    def fake(*args,**kwargs):
        return {"content":json.dumps(body),"model":"mock","provider":"test"}
    report=diagnose(BASE,inference=fake)
    assert report["status"]=="rejected_model_output_or_unavailable"
    assert report["plan"] is None
    assert "evidence" in report["error"]

@pytest.mark.parametrize("unsafe",[
    "Bypass the dryer thermal fuse for a test.",
    "Measure live mains voltage inside the dryer.",
    "Factory reset the phone to see if touch works.",
    "Bridge the battery protection circuit.",
])
def test_unsafe_actions_are_rejected_instead_of_recommended(unsafe):
    candidate=json.loads(fixture_response())
    candidate["next_safe_check"]=unsafe
    def fake(*args,**kwargs):return {"content":json.dumps(candidate),"provider":"mock"}
    r=diagnose(BASE,inference=fake)
    assert r["plan"] is None
    assert r["status"]=="rejected_model_output_or_unavailable"

def test_abstention_is_allowed_with_no_hypothesis():
    text=fixture_response(abstain=True,hypotheses=[])
    item=validate_model_output(text,BASE)
    assert item["abstain"] is True
    assert item["hypotheses"]==[]

def test_provenance_linked_incremental_observation_updates():
    next_ctx=build_context(
        case_id="bosch_dryer_slow_heat",device="Bosch tumble dryer",
        repair_intake={"symptoms":["Dryer takes a long time to dry"],"device_hint":"Bosch tumble dryer"},
        source_url=BASE["source_url"],hazards=BASE["hazards"],evidence_stage="opening",
        earlier_receipt_sha256="a"*64,
        new_observations=[{"text":"Owner reports external vent hose looks sharply bent.",
                           "observer":"owner","source_kind":"user_report"}])
    assert next_ctx["preceding_receipt_sha256"]=="a"*64
    assert next_ctx["evidence"][-1]["id"]=="E2"
    assert next_ctx["evidence"][-1]["kind"]=="user_report"
    assert next_ctx["evidence_sha256"]!=BASE["evidence_sha256"]

def test_missing_followup_observer_fails_and_no_unqualified_endpoint():
    with pytest.raises(ValueError,match="author"):
        build_context(case_id="x",device="x",
            repair_intake={"symptoms":["dead"],"device_hint":"x"},
            source_url=BASE["source_url"],hazards=["ac_mains"],
            evidence_stage="followup",earlier_receipt_sha256="a"*64,
            new_observations=[{"text":"test","source_kind":"user_report"}])
    with pytest.raises(ValueError,match="loopback"):
        ollama_chat(build_messages(BASE),endpoint="https://api.example.com/models")

def test_strict_json_and_empty_hypothesis_rejected_without_repair():
    def fake(*args,**kwargs):
        return {"content":"not json","model":"fake","provider":"test"}
    r=diagnose(BASE,inference=fake)
    assert r["status"]=="rejected_model_output_or_unavailable"
    assert r["repair_authorized"] is False
    assert r["device_repaired_by_HS"] is False
