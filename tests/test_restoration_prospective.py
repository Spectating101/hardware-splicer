"""Tests for the first independent-of-outcome power-architecture challenge."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "examples/restoration_video_bench"
P = HERE / "prospective"
sys.path.insert(0, str(P))
from predict import predict, validate_receipt
from score import adjudicate
sys.path.remove(str(P))

CASE_FILE = P / "cases/xbox_series_s_2021_no_power.json"
CASE = json.loads(CASE_FILE.read_text())


def test_unseen_case_does_not_recycle_gold_or_sources():
    old_sources = {
        json.loads(p.read_text())["source_context"]["url"]
        for p in (HERE / "cases").glob("*.json")
    }
    assert CASE["source_context"]["url"] not in old_sources
    assert CASE["initial_codes"] == ["no_power"]
    assert CASE["challenge"]["outcome_label_present"] is False
    assert not list(P.rglob("hidden_outcomes/*.json"))
    assert CASE["device_power"]["architecture"] == "ac_mains_internal_psu"


def test_real_hs_baseline_diagnosis_fails_architecture_gate():
    receipt = predict(CASE_FILE)
    assert receipt["baseline_first_choice"] == "corroded_battery_contact"
    assert receipt["baseline_hypothesis_ids"] == [
        "corroded_battery_contact", "open_power_trace", "power_switch_fault"
    ]
    assert receipt["decision"] == "ABSTAIN_DEVICE_INCOMPATIBLE"
    assert len(receipt["rejected_as_device_incompatible"]) == 3
    assert receipt["qualified_hypothesis_ids"] == []
    assert receipt["repair_authorized"] is False
    assert receipt["HS_repair_executed"] is False
    assert receipt["outcome_opened_by_predictor"] is False
    assert receipt["score_available"] is False


def test_receipt_is_tamper_evident_and_independent_of_output_path():
    r = predict(CASE_FILE)
    validate_receipt(r, r["receipt_sha256"])
    modified = deepcopy(r)
    modified["decision"] = "REPAIRED"
    with pytest.raises(ValueError, match="tampering"):
        validate_receipt(modified, r["receipt_sha256"])
    with pytest.raises(ValueError, match="preregistered"):
        validate_receipt(r, "0" * 64)
    assert r["case_sha256"] == hashlib.sha256(CASE_FILE.read_bytes()).hexdigest()


def test_gold_leak_blocked_recursively(tmp_path):
    c = deepcopy(CASE)
    c["repair_intake"]["hint"] = {"root_cause": "spoiler"}
    path = tmp_path / "leak.json"
    path.write_text(json.dumps(c))
    with pytest.raises(ValueError, match="gold field"):
        predict(path)


def test_followups_and_missing_architecture_fail_closed(tmp_path):
    c = deepcopy(CASE)
    c["followup_codes"] = ["battery_path_continuity_open"]
    path = tmp_path / "followup.json"
    path.write_text(json.dumps(c))
    with pytest.raises(ValueError, match="no follow-up"):
        predict(path)
    c = deepcopy(CASE)
    c["device_power"]["architecture"] = "not_declared"
    path.write_text(json.dumps(c))
    with pytest.raises(ValueError, match="unqualified architecture"):
        predict(path)


def test_synthetic_unresolved_label_neither_scores_nor_repairs():
    r = predict(CASE_FILE)
    external = {
        "case_id": r["case_id"],
        "source_url": r["source_url"],
        "adjudication_status": "unresolved",
        "reviewer": "SYNTHETIC_UNIT_TEST_ONLY",
        "evidence_description": "Not a real review or observed video outcome",
    }
    scored = adjudicate(r, external, r["receipt_sha256"])
    assert scored["qualified_candidate_hit"] is None
    assert scored["raw_baseline_top1_hit"] is None
    assert scored["HS_abstained"] is True
    assert scored["HS_diagnosed_repair"] is False
    with pytest.raises(ValueError, match="source mismatch"):
        adjudicate(r, {**external, "source_url": "wrong"}, r["receipt_sha256"])


def test_committed_pre_outcome_prediction_is_reproducible():
    sealed = json.loads((P / "evidence/xbox_series_s_sealed_prediction.json").read_text())
    expected = predict(CASE_FILE)
    assert sealed == expected
    validate_receipt(sealed, sealed["receipt_sha256"])
    assert sealed["case_sha256"] == hashlib.sha256(CASE_FILE.read_bytes()).hexdigest()
