from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from unittest import mock

import pytest

from hardware_splicer.vision_evidence_assistant import (
    VisionAssistantError,
    _vision_config,
    build_vision_evidence_report,
)


def test_vision_config_defaults_to_gemini_model_when_provider_is_gemini():
    config = _vision_config({"vision_assistance": {"provider": "gemini"}})
    assert config["provider"] == "gemini"
    assert config["model"] == "gemini-2.5-flash-lite"
    assert config["max_images"] == 3


def test_vision_config_defaults_to_qwen_even_when_gemini_key_present(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    config = _vision_config({"vision_assistance": {"enabled": True}})
    assert config["provider"] == "qwen"
    assert config["model"] == "qwen3-vl-flash-2026-01-22"


def test_gemini_live_call_parses_json_response(tmp_path):
    image = tmp_path / "bench.jpg"
    image.write_bytes(b"\xff\xd8\xff\xd8fake-jpeg")
    intake = {
        "goal": "automatic plant watering",
        "source_file": str(tmp_path / "brief.json"),
        "vision_assistance": {
            "enabled": True,
            "provider": "gemini",
            "live": True,
            "apply": False,
            "api_key": "test-gemini-key",
        },
        "attachments": [{"id": "bench_photo", "kind": "image", "path": str(image)}],
    }
    response_body = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "evidence_notes": [
                                        "measure: pump_mount width value_mm=55 status=observed artifact=evidence://vision/bench"
                                    ],
                                    "observations": ["Pump mount visible in photo."],
                                    "needs_human_review": ["Confirm scale reference."],
                                    "confidence": 0.62,
                                }
                            )
                        }
                    ]
                }
            }
        ],
        "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 40, "totalTokenCount": 160},
    }

    def fake_urlopen(request, timeout=0):
        assert "models/gemini-2.5-flash-lite:generateContent" in request.full_url
        payload = json.loads(request.data.decode("utf-8"))
        assert payload["generationConfig"]["responseMimeType"] == "application/json"
        assert payload["contents"][0]["parts"][0]["text"].startswith("You are assisting Hardware-Splicer")
        assert payload["contents"][0]["parts"][1]["inline_data"]["mime_type"] == "image/jpeg"
        return BytesIO(json.dumps(response_body).encode("utf-8"))

    with mock.patch("hardware_splicer.vision_evidence_assistant.urllib.request.urlopen", fake_urlopen):
        report = build_vision_evidence_report(intake)

    assert report["provider"] == "gemini"
    assert report["candidate_count"] == 1
    assert report["error_count"] == 0
    candidate = report["candidates"][0]
    assert candidate["provider"] == "gemini"
    assert candidate["evidence_notes"][0].startswith("measure: pump_mount")
    assert candidate["usage"]["total_tokens"] == 160


def test_gemini_live_call_requires_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(
        "hardware_splicer.vision_evidence_assistant._env_files",
        lambda: [],
    )
    image = tmp_path / "bench.jpg"
    image.write_bytes(b"\xff\xd8\xff\xd8fake-jpeg")
    intake = {
        "goal": "automatic plant watering",
        "source_file": str(tmp_path / "brief.json"),
        "vision_assistance": {"enabled": True, "provider": "gemini", "live": True},
        "attachments": [{"id": "bench_photo", "kind": "image", "path": str(image)}],
    }

    report = build_vision_evidence_report(intake)

    assert report["candidate_count"] == 0
    assert report["error_count"] == 1
    assert report["errors"][0]["provider"] == "gemini"
    assert "no API key" in report["errors"][0]["message"]


@pytest.mark.skipif(
    __import__("os").getenv("HARDWARE_SPLICER_GEMINI_LIVE_TEST") != "1",
    reason="set HARDWARE_SPLICER_GEMINI_LIVE_TEST=1 to run live Gemini smoke test",
)
def test_gemini_live_smoke_optional(tmp_path):
    image = tmp_path / "bench.jpg"
    image.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    intake = {
        "goal": "bench photo smoke test",
        "source_file": str(tmp_path / "brief.json"),
        "vision_assistance": {"enabled": True, "provider": "gemini", "live": True},
        "attachments": [{"id": "tiny", "kind": "image", "path": str(image)}],
    }
    report = build_vision_evidence_report(intake)
    if report["error_count"]:
        raise VisionAssistantError(report["errors"][0]["message"])
    assert report["candidate_count"] >= 0
