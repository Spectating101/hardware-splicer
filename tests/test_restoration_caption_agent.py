"""Source-window, no-hindsight and AGY invocation regression tests."""
import json
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from hardware_splicer.restoration_caption_ingest import parse_early_vtt, caption_case_context
from hardware_splicer.integrations.agy_text_client import call_agy_chat
from hardware_splicer.restoration_reasoning_agent import build_messages, agy_chat, validate_model_output


def _fake_vtt():
    return """WEBVTT

00:00:10.000 --> 00:00:10.010 align:start
Phone display is bright but touch does not work.

00:00:15.000 --> 00:00:15.010 align:start
The owner needs access to saved photos.

00:03:05.000 --> 00:03:05.010 align:start
I found the answer: a damaged ribbon connector.
"""


def test_caption_window_excludes_later_spoiler(tmp_path):
    v=tmp_path/"video.en-orig.vtt"
    v.write_text(_fake_vtt())
    early=parse_early_vtt(v,cutoff_s=120)
    assert early["total_early_final_cues"]==2
    joined=str(early["chunks"])
    assert "bright but touch" in joined
    assert "ribbon" not in joined
    assert early["raw_vtt_sha256"]
    context=caption_case_context(case_id="x",device="Smartphone",
                title_symptom="Touch does not respond",video_url="https://www.youtube.com/watch?v=xxxx",
                hazards=["lithium_ion","data_loss"],vtt_path=v,cutoff_s=120)
    assert context["native_HS_repair_intake_schema"]=="hardware_splicer.repair_intake.v1"
    assert context["caption_provenance"]["no_video_frames"] is True
    assert "ribbon" not in str(build_messages(context))

def test_non_vtt_and_outcome_title_rejected(tmp_path):
    v=tmp_path/"bad.vtt"
    v.write_text("This is not subtitles")
    with pytest.raises(ValueError,match="not a WebVTT"):
        parse_early_vtt(v)
    v.write_text(_fake_vtt())
    with pytest.raises(ValueError,match="reveals repair"):
        caption_case_context(case_id="x",device="Smartphone",
                title_symptom="Fixed by soldering the connector",
                video_url="https://www.youtube.com/watch?v=xxxx",
                hazards=["lithium_ion"],vtt_path=v)

def test_existing_agy_client_uses_correct_argument_shape():
    got=[]
    def fake_run(cmd,**kwargs):
        got.append(cmd)
        return subprocess.CompletedProcess(cmd,0,stdout='{"hello": "world"}\n',stderr='')
    with mock.patch("hardware_splicer.integrations.agy_text_client.agy_configured",return_value=True), \
         mock.patch("hardware_splicer.integrations.agy_text_client.subprocess.run",side_effect=fake_run):
        result=call_agy_chat('Return JSON', model='gemini-3.8-flash-low', json_mode=True, timeout_s=30)
    assert result["ok"]
    assert got and "--mode" in got[0]
    assert "plan" in got[0]
    assert any(arg.startswith("--print=") for arg in got[0])
    assert "--print" not in got[0]

def test_restoration_uses_existing_agy_backend_no_api_fallback():
    captured=[]
    def fake_agy(prompt,**kwargs):
        captured.append((prompt,kwargs))
        return {"ok":True,"provider":"agy","model":"gemini-3.8-flash-low",
            "content":json.dumps({
                "summary":"Unknown","hypotheses":[],"abstain":True,
                "next_safe_check":"Document physical condition",
                "uncertainty":"No measurements yet"
            }),
            "usage":{"estimated":True,"prompt_tokens":100,"completion_tokens":80}}
    messages=[{"role":"system","content":"Instructions"},{"role":"user","content":"Evidence only"}]
    with mock.patch("hardware_splicer.restoration_reasoning_agent.call_agy_chat",side_effect=fake_agy):
        result=agy_chat(messages,model="gemini-3.8-flash-low")
    assert captured[0][1]["json_mode"] is True
    assert result["provider"]=="agy_antigravity_subscription_cli"
    assert result["usage_estimated"] is True

def test_missing_agy_auth_fails_closed():
    messages=[{"role":"system","content":"Instructions"},{"role":"user","content":"Evidence only"}]
    with mock.patch("hardware_splicer.restoration_reasoning_agent.call_agy_chat",
                    return_value={"ok":False,"error":"agy_nonzero_exit"}):
        with pytest.raises(ValueError,match="unavailable"):
            agy_chat(messages)
