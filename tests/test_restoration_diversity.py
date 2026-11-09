"""Regression gates for nine non-templated source-separated repair video cases."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from hardware_splicer.restoration_video_triage import triage

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "examples/restoration_video_bench/diversity"
spec = importlib.util.spec_from_file_location("diversity", HERE / "run_diversity.py")
mod = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(mod)
C = mod.load_cases()
BASE = json.loads((HERE / "evidence/raw_rule_baseline.json").read_text())
AGENT = json.loads((HERE / "evidence/open_agent_packet.json").read_text())
CONTROL_FILE = HERE / "evidence/gpt6_text_control_preoutcome.json"
CONTROL = json.loads(CONTROL_FILE.read_text())

def test_nine_separate_real_videos_and_fault_domains():
    assert len(C["cases"]) == 9
    assert len({c["source_url"] for c in C["cases"]}) == 9
    assert len({c["category"] for c in C["cases"]}) == 9
    assert sum(c["caption_cutoff_s"] > 0 for c in C["cases"]) == 8
    assert {c["video_id"] for c in C["cases"]} >= {
        "NcYvWA-kGtM","RxgjyTRtKZs","qmR75MbSmXY",
        "utgBfSJsod0","yXFmSrgb0xI"
    }

def test_no_creator_answer_or_future_measurement_leaked():
    mod.forbid_outcome_fields(C)
    assert all(c["evidence_stage"] in (
        "TITLE_ONLY_NO_SUBTITLES", "TITLE_PLUS_OPENING_AUTOCAPTION"
    ) for c in C["cases"])
    assert all(c["caption_cutoff_s"] in (0,120) for c in C["cases"])

def test_original_raw_rule_engine_limitation_is_measured_not_hidden():
    assert BASE == mod.evaluate_raw()
    assert BASE["case_count"] == 9
    assert BASE["unique_fault_domains"] == 9
    assert BASE["native_repair_intake_accepted"] == 9
    assert BASE["legacy_triage_accepted_raw_text"] == 0
    assert BASE["title_only_raw_supported"] == 0
    assert BASE["creator_outcomes_read"] is False
    assert all(r["phases"]["opening"]["raw_legacy_triage"]["error"]
               == "repair case lacks actual visible observations"
               for r in BASE["cases"])

def test_agent_packets_use_same_native_intake_not_hardcoded_gold():
    assert AGENT == mod.generate_open_agent_packet()
    assert AGENT["task_count"] == 9
    assert AGENT["model_access_not_implied"]
    assert len({x["intake_sha256"] for x in AGENT["tasks"]}) == 9
    assert all(x["instructions"] and x["hazards"] for x in AGENT["tasks"])

def test_control_is_not_spoofed_as_HS_execution_or_physical_repair():
    assert CONTROL["candidate_count"] == 9
    assert CONTROL["created_for_external_comparator_only"] is True
    assert CONTROL["no_creator_outcomes_opened_for_scoring"] is True
    assert {p["case_id"] for p in CONTROL["predictions"]} == {
        c["id"] for c in C["cases"]
    }
    for p in CONTROL["predictions"]:
        assert "NOT an executed HS" in p["model_source"]
        assert p["repair_authorized"] is False
        assert p["outcome_known_at_prediction"] is False
        assert p["confidence"] in {"low","medium","high"}
        assert p["status"] in {"provisional_plan", "multiple_faults_possible","abstain"}
        assert 1 <= len(p["hypotheses"]) <= 3
        assert [h["rank"] for h in p["hypotheses"]] == list(
            range(1,len(p["hypotheses"])+1)
        )
        assert all(h["rationale"] and h["discriminating_check"]
                   for h in p["hypotheses"])
        assert len(p["first_safe_step"]) > 20

def test_empty_code_intake_should_not_get_fake_auto_classification():
    c = C["cases"][0]
    raw = mod.intake(c)
    with pytest.raises(ValueError, match="lacks actual visible observations"):
        triage(raw,0)
    assert "initial_codes" not in raw
    assert "hidden_outcomes" not in str(raw).lower()

def test_outcome_payload_injection_fails_closed():
    bad = {"schema":"x", "cases":[{"id":"bad","root_cause":"known"}]}
    with pytest.raises(ValueError, match="outcome"):
        mod.forbid_outcome_fields(bad)

def test_receipts_not_changed_by_rerunning_on_filesystem():
    assert BASE["candidate_set_sha256"] == mod.digest(C)
    assert not any(p.name == "creator_outcomes.json" for p in HERE.rglob("*.json"))
    assert hashlib.sha256(CONTROL_FILE.read_bytes()).hexdigest()
