from __future__ import annotations

import json
from unittest import mock

from hardware_splicer.integrations.llm_text_client import call_llm_chat
from hardware_splicer.llm_response_cache import cache_key, read_cached_response, write_cached_response
from hardware_splicer.text_usage_ledger import record_text_usage, usage_summary


def test_text_usage_ledger(tmp_path, monkeypatch):
    ledger = tmp_path / "text.json"
    monkeypatch.setenv("HARDWARE_SPLICER_TEXT_LEDGER", str(ledger))
    record_text_usage(
        provider="qwen",
        model="qwen3.5-flash",
        stage="build_pick",
        usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        prompt_excerpt="fan intake",
        path=ledger,
    )
    summary = usage_summary(path=ledger)
    assert summary["call_count"] == 1
    assert summary["total_tokens"] == 120
    assert summary["by_stage"]["build_pick"]["calls"] == 1


def test_llm_response_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_LLM_CACHE_DIR", str(tmp_path))
    key = cache_key(
        stage="compose",
        prompt="water plants",
        system=None,
        model="qwen3-coder-flash",
        temperature=0,
        json_mode=True,
        provider="qwen",
    )
    payload = {"ok": True, "provider": "qwen", "model": "qwen3-coder-flash", "content": "{}", "usage": {"total_tokens": 10}}
    write_cached_response(key, payload, root=tmp_path)
    hit = read_cached_response(key, root=tmp_path)
    assert hit is not None
    assert hit["content"] == "{}"


def test_call_llm_chat_uses_cache_without_http(tmp_path, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_LLM_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("HARDWARE_SPLICER_TEXT_LEDGER", str(tmp_path / "ledger.json"))
    monkeypatch.setenv("HARDWARE_SPLICER_LLM_PROVIDER", "qwen")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")

    key = cache_key(
        stage="general",
        prompt="hello",
        system=None,
        model="qwen3.5-flash",
        temperature=0,
        json_mode=False,
        provider="qwen",
    )
    write_cached_response(
        key,
        {
            "ok": True,
            "provider": "qwen",
            "model": "qwen3.5-flash",
            "content": "cached-ok",
            "usage": {"total_tokens": 5},
        },
        root=tmp_path,
    )

    with mock.patch("hardware_splicer.integrations.qwen_text_client._call_qwen_http") as http_mock:
        out = call_llm_chat("hello", stage="general")
    http_mock.assert_not_called()
    assert out["ok"] is True
    assert out["cached"] is True
    assert out["content"] == "cached-ok"


def test_call_llm_chat_falls_back_to_agy_on_qwen_quota(tmp_path, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_LLM_CACHE", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_TEXT_LEDGER", str(tmp_path / "ledger.json"))
    monkeypatch.setenv("HARDWARE_SPLICER_LLM_PROVIDER", "qwen_then_agy")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")

    with mock.patch(
        "hardware_splicer.integrations.llm_text_client._call_qwen_http",
        return_value={"ok": False, "error": "qwen_http_error", "status": 403, "detail": "quota exhausted"},
    ), mock.patch(
        "hardware_splicer.integrations.llm_text_client.call_agy_chat",
        return_value={"ok": True, "provider": "agy", "model": "gemini-2.5-flash", "content": "agy-ok", "usage": {"total_tokens": 8}},
    ), mock.patch("hardware_splicer.integrations.llm_text_client.agy_configured", return_value=True):
        out = call_llm_chat("goal", stage="build_pick")

    assert out["ok"] is True
    assert out["provider"] == "agy"
    assert out["content"] == "agy-ok"
