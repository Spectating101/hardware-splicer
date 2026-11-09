"""Verify saved, real Antigravity inference receipts; CI never calls a provider."""
import importlib.util
import json
from pathlib import Path

from hardware_splicer.restoration_reasoning_agent import sha

ROOT=Path(__file__).resolve().parents[1]
D=ROOT/"examples/restoration_video_bench/diversity"
spec=importlib.util.spec_from_file_location("hs_live_runner",D/"run_live_agent.py")
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
CONTEXTS={c["case_id"]:c for c in runner.prepare()}

def _valid_receipt(row):
    signed={k:v for k,v in row.items() if k not in ("receipt_sha256","elapsed_seconds")}
    assert sha(signed)==row["receipt_sha256"]
    assert row["model_called"] is True
    assert row["repair_authorized"] is False
    assert row["device_repaired_by_HS"] is False
    assert row["physical_measurements_by_HS"] is False
    assert row["actual_video_frames_analyzed"] is False
    assert row["parts_purchase_authorized"] is False
    assert row["prompt_sha256"]
    assert row["raw_model_output_sha256"] if row["status"]!="rejected_model_output_or_unavailable" else True
    assert row["status"] in ("proposed_unverified_differential","model_abstained",
                             "rejected_model_output_or_unavailable")
    if row["plan"]:
        ids={e["id"] for e in CONTEXTS[row["case_id"]]["evidence"]}
        if row.get("caption_provenance"):
            # Real captions can add E IDs; their original VTT SHA and intake
            # evidence digest are locked in the receipt, never guessed.
            ids={f"E{i}" for i in range(1,30)}
        for h in row["plan"]["hypotheses"]:
            assert set(h["evidence_ids"])<=ids

def test_saved_live_nine_models_and_native_sources():
    source=D/"evidence/agy_gemini38_flash_low_nine_live.json"
    d=json.loads(source.read_text())
    assert d["schema"]=="hs.restoration.live_local_inference_batch.v1"
    assert d["selected_count"]==9
    assert len(d["results"])==9
    assert d["provider"]=="agy_antigravity_subscription_cli"
    assert d["model_requested"]=="gemini-3.8-flash-low"
    assert d["preoutcome_inputs_only"] is True
    assert d["no_gold_files_loaded"] is True
    assert set(CONTEXTS)=={r["case_id"] for r in d["results"]}
    for r in d["results"]:
        assert r["provider_reported"]=="agy_antigravity_subscription_cli"
        assert r["evidence_sha256"]==CONTEXTS[r["case_id"]]["evidence_sha256"]
        assert r["model_reported"]=="gemini-3.8-flash-low"
        _valid_receipt(r)

def test_saved_raw_video_caption_experiment_is_source_bounded():
    folder=D/"evidence/live_raw_vtt"
    expected={
        "a53_touch_failure","tab_s6_lite_dead","delonghi_eletta_faults",
        "dewalt_blower_intermittent","bosch_dryer_slow_heat",
        "canon_eos2000d_no_power","reebok_treadmill_dead",
        "ps5_pro_no_power_hdmi",
    }
    observed=set()
    for p in sorted(folder.glob("*.json")):
        d=json.loads(p.read_text())
        assert d["selected_count"]==1
        assert d["preoutcome_inputs_only"] is True
        r=d["results"][0]
        assert r["case_id"]==p.stem
        provenance=r.get("caption_provenance")
        assert provenance["cutoff_seconds"]==120
        assert provenance["no_video_frames"] is True
        assert provenance["caption_reliability"]=="unverified_auto_generated"
        assert len(provenance["raw_vtt_sha256"])==64
        assert r["provider_reported"]=="agy_antigravity_subscription_cli"
        _valid_receipt(r)
        observed.add(r["case_id"])
    assert observed==expected

def test_all_saved_output_is_never_mistaken_for_model_accuracy():
    d=json.loads((D/"evidence/agy_gemini38_flash_low_nine_live.json").read_text())
    assert d["valid_plans"]<=9
    for r in d["results"]:
        assert "creator_reported_root_cause" not in r
        assert "correct_diagnosis" not in r
        assert r["repair_authorized"] is False
