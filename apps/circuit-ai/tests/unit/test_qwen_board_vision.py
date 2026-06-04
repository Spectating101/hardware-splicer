import json
from types import SimpleNamespace

from src.vision import qwen_board_vision
from src.vision.qwen_board_vision import (
    analyze_board_image_with_qwen,
    parse_qwen_board_response,
    qwen_vision_status,
)


def _settings(**overrides):
    base = {
        "qwen_api_key": None,
        "dashscope_api_key": None,
        "qwen_vision_model": "qwen3-vl-flash",
        "qwen_base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "qwen_json_mode_disabled": False,
        "qwen_disabled": False,
        "qwen_out_of_quota": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_qwen_status_requires_key_and_budget(monkeypatch):
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("VISION_MONTHLY_USD_LIMIT", raising=False)
    monkeypatch.setattr(qwen_board_vision, "settings", _settings())

    status = qwen_vision_status()

    assert status["api_key_configured"] is False
    assert status["ready_for_live_model"] is False
    assert status["dry_run_available"] is True


def test_qwen_dry_run_builds_redacted_board_evidence_request(monkeypatch):
    monkeypatch.setenv("VISION_MONTHLY_USD_LIMIT", "1")
    monkeypatch.setattr(qwen_board_vision, "settings", _settings(qwen_api_key="test-key"))

    result = analyze_board_image_with_qwen(
        b"fake-png-bytes",
        filename="board.png",
        goal="reuse this board as a USB UART debug adapter",
        device_hint="USB UART board",
        symptoms=("unknown pinout",),
        live=False,
    )
    image_url = result["request_preview"]["messages"][0]["content"][1]["image_url"]["url"]

    assert result["mode"] == "dry_run"
    assert result["preflight"]["estimated_output_tokens"] == qwen_board_vision.DEFAULT_MAX_TOKENS
    assert result["preflight"]["estimated_usd"] > 0
    assert "board_evidence.v1" in result["request_preview"]["messages"][0]["content"][0]["text"]
    assert "omitted" in image_url
    assert "fake-png-bytes" not in image_url


def test_qwen_dry_run_routes_away_from_low_quota_model(monkeypatch):
    monkeypatch.setenv("QWEN_VISION_MODEL", "qwen-plus")
    monkeypatch.setenv("QWEN_LOW_QUOTA_MODELS", "qwen-plus")
    monkeypatch.setenv("VISION_MONTHLY_USD_LIMIT", "1")
    monkeypatch.setattr(qwen_board_vision, "settings", _settings(qwen_api_key="test-key"))

    result = analyze_board_image_with_qwen(
        b"fake-png-bytes",
        filename="board.png",
        live=False,
    )

    assert result["model"] == "qwen3-vl-flash"
    assert result["preflight"]["model_rotation"][0] == "qwen3-vl-flash"
    assert "qwen-plus" not in result["preflight"]["model_rotation"]


def test_qwen_disabled_blocks_live_call_before_provider_http(monkeypatch, tmp_path):
    monkeypatch.setenv("QWEN_DISABLED", "true")
    monkeypatch.setenv("VISION_MONTHLY_USD_LIMIT", "1")
    monkeypatch.setattr(qwen_board_vision, "settings", _settings(qwen_api_key="test-key"))

    def fail_urlopen(*_args, **_kwargs):
        raise AssertionError("Qwen HTTP must not be called when QWEN_DISABLED is set")

    monkeypatch.setattr(qwen_board_vision.urllib.request, "urlopen", fail_urlopen)

    status = qwen_vision_status()
    result = analyze_board_image_with_qwen(
        b"fake-png-bytes",
        filename="board.png",
        live=True,
        ledger_path=tmp_path / "ledger.json",
    )

    assert status["disabled"] is True
    assert status["ready_for_live_model"] is False
    assert result["mode"] == "blocked_disabled"
    assert result["budget"]["reason"] == "qwen_disabled_or_out_of_quota"


def test_parse_qwen_response_accepts_top_level_components_as_board_evidence():
    parsed = parse_qwen_board_response(
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "safety_level": "caution",
                                "components": [{"id": "u1", "label": "CH340C marking", "kind": "ic", "confidence": 0.8}],
                                "connectors": [{"id": "j1", "label": "UART header", "kind": "header"}],
                            }
                        )
                    }
                }
            ]
        }
    )

    evidence = parsed["board_evidence"]

    assert evidence["schema_version"] == "board_evidence.v1"
    assert evidence["components"][0]["label"] == "CH340C marking"
    assert evidence["connectors"][0]["label"] == "UART header"
    assert parsed["parse_diagnostics"]["json_valid"] is True


def test_parse_qwen_response_flags_truncated_json():
    parsed = parse_qwen_board_response(
        {
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {
                        "content": '{"safety_level":"safe","board_evidence":{"schema_version":"board_evidence.v1","components":['
                    },
                }
            ]
        }
    )

    diagnostics = parsed["parse_diagnostics"]

    assert diagnostics["json_valid"] is False
    assert diagnostics["truncated"] is True
    assert diagnostics["finish_reason"] == "length"
    assert "Increase max_tokens" in diagnostics["recommendation"]


def test_qwen_live_call_returns_bridge_and_records_spend(monkeypatch, tmp_path):
    monkeypatch.delenv("QWEN_DISABLED", raising=False)
    monkeypatch.delenv("QWEN_OUT_OF_QUOTA", raising=False)
    monkeypatch.setenv("VISION_MONTHLY_USD_LIMIT", "1")
    monkeypatch.setenv("VISION_DAILY_USD_LIMIT", "1")
    monkeypatch.setenv("VISION_MAX_USD_PER_CALL", "0.1")
    monkeypatch.setattr(qwen_board_vision, "settings", _settings(qwen_api_key="test-key"))

    response_payload = {
        "model": "qwen3-vl-flash",
        "usage": {"prompt_tokens": 1200, "completion_tokens": 240},
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "safety_level": "caution",
                            "board_evidence": {
                                "schema_version": "board_evidence.v1",
                                "components": [
                                    {"id": "u1", "label": "CH340C USB serial bridge", "kind": "integrated_circuit", "confidence": 0.82}
                                ],
                                "connectors": [{"id": "h1", "label": "UART header", "kind": "header", "confidence": 0.7}],
                                "markings": [],
                                "regions": [],
                                "damage": [],
                                "test_points": [],
                                "salvage_candidates": [],
                            },
                        }
                    )
                }
            }
        ],
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(response_payload).encode("utf-8")

    monkeypatch.setattr(qwen_board_vision.urllib.request, "urlopen", lambda request, timeout: FakeResponse())

    result = analyze_board_image_with_qwen(
        b"fake-png-bytes",
        filename="board.png",
        goal="reuse as a debug adapter",
        live=True,
        ledger_path=tmp_path / "ledger.json",
    )

    bridge = result["vision_evidence_bridge"]

    assert result["mode"] == "live"
    assert result["parse_diagnostics"]["json_valid"] is True
    assert result["board_evidence"]["components"]
    assert bridge["available"] is True
    assert any(resource["resource_id"] == "vision_u1" for resource in bridge["resource_candidates"])
    assert (tmp_path / "ledger.json").exists()


def test_qwen_live_call_blocks_without_monthly_budget(monkeypatch, tmp_path):
    monkeypatch.delenv("QWEN_DISABLED", raising=False)
    monkeypatch.delenv("QWEN_OUT_OF_QUOTA", raising=False)
    monkeypatch.delenv("VISION_MONTHLY_USD_LIMIT", raising=False)
    monkeypatch.setattr(qwen_board_vision, "settings", _settings(qwen_api_key="test-key"))

    result = analyze_board_image_with_qwen(
        b"fake-png-bytes",
        filename="board.png",
        live=True,
        ledger_path=tmp_path / "ledger.json",
    )

    assert result["mode"] == "blocked_budget"
    assert result["budget"]["reason"] == "monthly_limit_required"
