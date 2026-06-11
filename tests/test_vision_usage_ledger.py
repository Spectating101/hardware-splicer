from __future__ import annotations

import json
from io import BytesIO
from unittest import mock

from hardware_splicer.vision_evidence_assistant import _vision_config, build_vision_evidence_report
from hardware_splicer.vision_usage_ledger import record_vision_usage, usage_summary


def test_record_and_summarize_vision_usage(tmp_path, monkeypatch):
    ledger = tmp_path / "vision-usage.json"
    monkeypatch.setenv("HARDWARE_SPLICER_VISION_LEDGER", str(ledger))
    record_vision_usage(
        provider="qwen",
        model="qwen3-vl-flash",
        usage={"prompt_tokens": 900, "completion_tokens": 120, "total_tokens": 1020},
        source_ids=["photo_1"],
        goal="plant watering",
        path=ledger,
    )
    summary = usage_summary(path=ledger, provider="qwen")
    assert summary["call_count"] == 1
    assert summary["total_tokens"] == 1020
    assert summary["by_model"]["qwen3-vl-flash"]["total_tokens"] == 1020
    assert summary["free_tier_estimates"]["qwen3-vl-flash"]["estimated_remaining_tokens"] == 998_980


def test_qwen_live_call_records_usage_in_report(tmp_path, monkeypatch):
    ledger = tmp_path / "ledger.json"
    monkeypatch.setenv("HARDWARE_SPLICER_VISION_LEDGER", str(ledger))
    image = tmp_path / "bench.jpg"
    image.write_bytes(b"\xff\xd8\xff\xd8fake-jpeg")
    intake = {
        "goal": "automatic plant watering",
        "source_file": str(tmp_path / "brief.json"),
        "vision_assistance": {
            "enabled": True,
            "provider": "qwen",
            "live": True,
            "apply": False,
            "api_key": "test-qwen-key",
        },
        "attachments": [{"id": "bench_photo", "kind": "image", "path": str(image)}],
    }
    response_body = {
        "model": "qwen3-vl-flash",
        "choices": [{"message": {"content": json.dumps({"evidence_notes": [], "observations": [], "confidence": 0.4})}}],
        "usage": {"prompt_tokens": 500, "completion_tokens": 80, "total_tokens": 580},
    }

    def fake_urlopen(request, timeout=0):
        return BytesIO(json.dumps(response_body).encode("utf-8"))

    with mock.patch("hardware_splicer.vision_evidence_assistant.urllib.request.urlopen", fake_urlopen):
        report = build_vision_evidence_report(intake)

    assert report["usage_tracking"]["total_tokens"] == 580
    assert ledger.exists()


def test_qwen_plus_is_routed_to_qwen3_vl_flash():
    config = _vision_config({"vision_assistance": {"provider": "qwen", "model": "qwen-plus"}})
    assert config["model"] == "qwen3-vl-flash"
