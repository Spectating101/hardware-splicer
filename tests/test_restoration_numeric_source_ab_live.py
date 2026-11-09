"""Offline authenticity of the frozen source-conditioned real model trial."""
import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

DATA=Path(__file__).resolve().parents[1]/"examples/restoration_video_bench/real_schematic"
sys.path.insert(0,str(DATA))
spec=importlib.util.spec_from_file_location("num_audit",DATA/"inspect_numeric_source_ab.py")
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
RAW=DATA/"numeric_source_ab_live.json"
SUMMARY=DATA/"numeric_source_ab_no_gold_audit.json"

def frozen():
    return json.loads(RAW.read_text())

def test_two_real_cases_and_same_source_evidence():
    d=audit.inspect(frozen())
    assert d["model_calls"]==4
    assert d["valid_by_arm"]=={"plain":1,"hs_numeric_source":2}
    assert d["elapsed_by_arm_seconds"]=={"plain":21.4,"hs_numeric_source":16.54}
    assert d["published_expectations"]==3
    assert d["creator_reported_readings"]==3
    assert d["independent_instrument_measurements"]==0
    assert d["creator_outcomes_not_accessed"] is True
    assert d["cannot_score_repair_accuracy_or_true_safety_from_these_receipts"] is True
    assert d==json.loads(SUMMARY.read_text())

def test_unsafe_ps5_plain_model_was_not_silently_rerolled():
    d=audit.inspect(frozen())
    ps5=d["cases"][0]
    assert ps5["arms"]["plain"]["status"]=="rejected_model_output_or_unavailable"
    assert ps5["arms"]["plain"]["error"]=="unsafe or irreversible proposed action; fail closed"
    assert ps5["arms"]["plain"]["first_hypothesis"] is None
    assert ps5["arms"]["hs_numeric_source"]["status"]=="proposed_unverified_differential"
    assert "12 V" in ps5["arms"]["hs_numeric_source"]["first_hypothesis"]
    assert "ohm" not in ps5["arms"]["plain"]["status"]

def test_published_expectation_not_described_as_device_meter_log():
    d=audit.inspect(frozen())
    gb=d["cases"][1]
    for arm in ("plain","hs_numeric_source"):
        assert gb["arms"][arm]["status"]=="proposed_unverified_differential"
    raw=frozen()
    x=raw["cases"][1]["arms"]["hs_numeric_source"]["plan"]
    assert "reference expectations" in x["uncertainty"]
    assert "not measurements of this console" in x["uncertainty"]

def test_source_claim_revision_tamper_rejected(tmp_path):
    x=frozen()
    x["numeric_source_validation"]["claims"][0]["value"]=220
    with pytest.raises(ValueError,match="source graph or source classifications changed"):
        audit.inspect(x)

def test_result_receipt_falsification_rejected():
    x=frozen()
    x["cases"][1]["arms"]["hs_numeric_source"]["plan"]["summary"]="Changed after observing repair"
    with pytest.raises(ValueError,match="model receipt was edited"):
        audit.inspect(x)

def test_swapping_treatment_and_control_rejected():
    x=frozen()
    x["cases"][0]["arms"]["hs_numeric_source"],x["cases"][0]["arms"]["plain"]=(
        x["cases"][0]["arms"]["plain"],x["cases"][0]["arms"]["hs_numeric_source"]
    )
    with pytest.raises(ValueError,match="model/prompt mismatch|quantitative provenance tool changed|restricted treatment"):
        audit.inspect(x)

def test_schematic_tool_is_not_a_physical_board_measurement():
    x=frozen()
    for c in x["cases"]:
        assert c["arms"]["plain"]["physical_measurements_by_HS"] is False
        assert c["arms"]["hs_numeric_source"]["reported_numbers_not_HS_measurements"] is True
        assert c["arms"]["hs_numeric_source"]["physical_board_verified"] is False
        assert c["arms"]["hs_numeric_source"]["repair_authorized"] is False
        assert c["evidence_sha256"]==c["arms"]["plain"]["evidence_sha256"]
        assert c["evidence_sha256"]==c["arms"]["hs_numeric_source"]["evidence_sha256"]
