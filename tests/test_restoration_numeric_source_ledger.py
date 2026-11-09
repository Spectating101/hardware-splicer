"""Source-anchored numeric trust tests: expected values never become readings."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from hardware_splicer.restoration_source_numeric_ledger import (
    register_source_numeric_claims
)
from hardware_splicer.restoration_numeric_case import build_numeric_case_context
from hardware_splicer.restoration_reasoning_agent import (
    build_messages,validate_model_output,sha
)
from hardware_splicer.restoration_numeric_truth_gate import UnsupportedQuantitativeThreshold

DATA=Path(__file__).resolve().parents[1]/"examples/restoration_video_bench/real_schematic"
REAL_VTT=Path("/tmp/hs-restoration-video-intake-20261110/xbp8lIggbxY.en-orig.vtt")
REAL_ARTICLE=Path("/tmp/hs-gameboy-bench-article-20261110.html")

def synthetic(tmp_path):
    v=tmp_path/"video.en-orig.vtt"
    v.write_text("""WEBVTT

00:02:06.000 --> 00:02:06.010
We have exactly zero volts from the PSU while it is still installed.

00:05:04.000 --> 00:05:04.010
With motherboard out we have 12 volts.

00:05:35.000 --> 00:05:35.010
That is 2 ohms across the board input pins.

00:08:10.000 --> 00:08:10.010
Now we have repaired a bad component.
""")
    a=tmp_path/"article.html"
    a.write_text("""<html><p>Expect 6.0 to 6.4 V open circuit.</p>
    <p>Under load at least 5.4 V is recommended.</p>
    <p>Below 4.5 V may be unreliable.</p></html>""")
    claims=json.loads((DATA/"source_numeric_claims.json").read_text())
    claims["sources"][0]["artifact_sha256"]=hashlib.sha256(v.read_bytes()).hexdigest()
    claims["sources"][1]["artifact_sha256"]=hashlib.sha256(a.read_bytes()).hexdigest()
    return claims,{"ps5pro_early_captions":v,"dmg_published_expectations":a}

def assert_ledger(data,paths):
    out=register_source_numeric_claims(data,local_artifacts=paths)
    assert out["claim_count"]==6
    assert out["source_count"]==2
    assert out["conflicts"]==[]
    assert out["source_authority_ceiling"]=="declared"
    assert out["measurements_physically_taken_by_HS"] is False
    assert out["independent_verified_numeric_thresholds"] is False
    assert out["board_identity_independently_verified"] is False
    assert out["repair_authorized"] is False
    assert len(out["native_HS_source_graph_sha256"])==64
    assert all(c["authority"]=="declared" for c in out["claims"])
    assert all(c["independent_bench_truth"] is False for c in out["claims"])
    return out

def test_synthetic_real_source_pipeline_and_separated_conditions(tmp_path):
    data,paths=synthetic(tmp_path)
    out=assert_ledger(data,paths)
    actual={c["claim_id"]:c for c in out["claims"]}
    assert actual["M1"]["value"]==0 and actual["M1"]["claim_type"]=="creator_reported_reading"
    assert actual["M2"]["value"]==12 and actual["M2"]["condition_id"]!="psu_connected_before_board_extraction"
    assert actual["M3"]["value"]==2 and actual["M3"]["unit"]=="ohm"
    assert actual["R1"]["upper_value"]==6.4
    assert actual["R2"]["claim_type"]=="published_reference_expectation"
    assert actual["R3"]["independent_bench_truth"] is False

def test_real_web_and_video_bytes_are_identically_anchored_when_present():
    if not REAL_VTT.exists() or not REAL_ARTICLE.exists():
        pytest.skip("public source raw files are uncommitted and unavailable on CI")
    data=json.loads((DATA/"source_numeric_claims.json").read_text())
    out=assert_ledger(data,{"ps5pro_early_captions":REAL_VTT,
                            "dmg_published_expectations":REAL_ARTICLE})
    committed=json.loads((DATA/"source_numeric_claims_validated.json").read_text())
    assert out==committed

def test_expected_reference_cannot_masquerade_as_a_real_observation(tmp_path):
    d,p=synthetic(tmp_path)
    d["sources"][1]["claims"][0]["claim_type"]="creator_reported_reading"
    with pytest.raises(ValueError,match="publisher recommendations"):
        register_source_numeric_claims(d,local_artifacts=p)

def test_creator_video_cannot_masquerade_as_a_manufacturer_spec(tmp_path):
    d,p=synthetic(tmp_path)
    d["sources"][0]["claims"][0]["claim_type"]="published_reference_expectation"
    with pytest.raises(ValueError,match="publisher recommendations"):
        register_source_numeric_claims(d,local_artifacts=p)

def test_fake_numeric_value_rejected_against_source_bytes(tmp_path):
    d,p=synthetic(tmp_path)
    d["sources"][0]["claims"][2]["value"]=200
    with pytest.raises(ValueError,match="no matching source passage"):
        register_source_numeric_claims(d,local_artifacts=p)

def test_future_repair_segment_outside_source_window_excluded(tmp_path):
    d,p=synthetic(tmp_path)
    d["sources"][0]["claims"][2]["anchor"]="repaired a bad component"
    with pytest.raises(ValueError,match="no matching source passage"):
        register_source_numeric_claims(d,local_artifacts=p)

def test_window_change_cannot_reassign_earlier_meter_number(tmp_path):
    d,p=synthetic(tmp_path)
    d["sources"][0]["claims"][0]["window_start_s"]=300
    d["sources"][0]["claims"][0]["window_end_s"]=330
    with pytest.raises(ValueError,match="not present at claimed source and time"):
        register_source_numeric_claims(d,local_artifacts=p)

def test_raw_source_replacement_blocked(tmp_path):
    d,p=synthetic(tmp_path)
    p["ps5pro_early_captions"].write_text(p["ps5pro_early_captions"].read_text()+"\n")
    with pytest.raises(ValueError,match="digest mismatch"):
        register_source_numeric_claims(d,local_artifacts=p)

def test_source_symlink_rejected(tmp_path):
    d,p=synthetic(tmp_path)
    redirect=tmp_path/"captions_alias"
    redirect.symlink_to(p["ps5pro_early_captions"])
    p["ps5pro_early_captions"]=redirect
    with pytest.raises(ValueError,match="symlinked"):
        register_source_numeric_claims(d,local_artifacts=p)

@pytest.mark.parametrize("bad",[
    "VERIFIED",True,1,"unknown"
])
def test_cannot_assert_target_board_verified_from_public_article(tmp_path,bad):
    d,p=synthetic(tmp_path)
    d["sources"][1]["claims"][0]["device_board_verified"]=bad
    with pytest.raises(ValueError,match="cannot independently verify"):
        register_source_numeric_claims(d,local_artifacts=p)

def test_extra_authority_fields_cannot_override_source_bound(tmp_path):
    d,p=synthetic(tmp_path)
    d["sources"][0]["authority_ceiling"]="verified"
    with pytest.raises(ValueError,match="unexpected source-level authority"):
        register_source_numeric_claims(d,local_artifacts=p)

def test_disagreeing_same_condition_is_flagged_without_merging_readings(tmp_path):
    d,p=synthetic(tmp_path)
    # Author a separate synthetic observation under exactly the same
    # load/connection condition as the initial 0-V narration.
    current=p["ps5pro_early_captions"].read_text()
    current=current.replace(
      "00:05:04.000 --> 00:05:04.010",
      "00:02:07.000 --> 00:02:07.010\nNow it is 4 volts from the same installed supply.\n\n00:05:04.000 --> 00:05:04.010",
    )
    p["ps5pro_early_captions"].write_text(current)
    d["sources"][0]["artifact_sha256"]=hashlib.sha256(current.encode()).hexdigest()
    clone=copy.deepcopy(d["sources"][0]["claims"][0])
    clone.update({"id":"M4","value":4,"anchor":"4 volts",
                  "window_start_s":120,"window_end_s":151})
    d["sources"][0]["claims"].append(clone)
    out=register_source_numeric_claims(d,local_artifacts=p)
    assert len(out["conflicts"])==1
    assert set(out["conflicts"][0]["claim_ids"])=={"M1","M4"}
    assert out["conflicts"][0]["disposition"]=="unresolved_conflicting_creator_reports"

def test_same_text_evidence_in_plain_and_HS_tool_arms(tmp_path):
    d,p=synthetic(tmp_path)
    ledger=assert_ledger(d,p)
    for case in ("ps5_pro_no_power_hdmi","dmg_reported_battery_only_failure"):
        normal=build_numeric_case_context(ledger,case_id=case,assisted=False)
        enhanced=build_numeric_case_context(ledger,case_id=case,assisted=True)
        assert normal["evidence_sha256"]==enhanced["evidence_sha256"]
        assert normal["evidence"]==enhanced["evidence"]
        assert build_messages(normal)[1]==build_messages(enhanced)[1]
        assert build_messages(normal)[0]!=build_messages(enhanced)[0]
        assert "SOURCE_NUMERIC_CLAIMS_JSON" in build_messages(enhanced)[0]["content"]
        assert enhanced["numeric_source_tool"]["target_board_physically_verified"] is False
        assert len([c for c in enhanced["evidence"] if "numeric_claim" in c["stage"]])==3
        assert all(e["source_artifact_sha256"] for e in enhanced["evidence"] if "numeric_claim" in e["stage"])

def test_manufacturer_threshold_does_not_become_verified_test_limit(tmp_path):
    d,p=synthetic(tmp_path)
    ledger=assert_ledger(d,p)
    ctx=build_numeric_case_context(ledger,case_id="dmg_reported_battery_only_failure",assisted=True)
    proposed={
        "summary":"No actual bench readings provided.",
        "hypotheses":[{"mechanism":"Possible battery path loss","why":"AA failure in report",
                       "evidence_ids":["E1","E2"],
                       "safe_test":"Inspect exterior terminals with battery removed."}],
        "next_safe_check":"Check above 5.4V on the actual device to prove the board is good.",
        "uncertainty":"No calibrated data.",
        "abstain":False,
    }
    with pytest.raises(UnsupportedQuantitativeThreshold):
        validate_model_output(proposed,ctx)

def test_invalid_cross_device_source_claim_cannot_enter_model(tmp_path):
    d,p=synthetic(tmp_path)
    out=assert_ledger(d,p)
    altered=copy.deepcopy(out)
    altered["claims"][0]["case_id"]="dmg_reported_battery_only_failure"
    with pytest.raises(ValueError,match="source does not match"):
        build_numeric_case_context(altered,case_id="dmg_reported_battery_only_failure",assisted=True)

def test_source_graph_is_real_native_and_not_assigned_trust(tmp_path):
    d,p=synthetic(tmp_path)
    out=assert_ledger(d,p)
    assert out["native_HS_source_graph_schema"]=="hardware_splicer.engineering_source_graph.v1"
    assert out["conditions_are_distinct"] is True
    assert all(c["calibrated_instrument_data_present"] is False for c in out["claims"])
    assert all(c["manufacturer_specification_verified"] is False for c in out["claims"])
