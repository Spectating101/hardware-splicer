from __future__ import annotations

from hardware_splicer.integrations import llm_policy


def _clear_provider(monkeypatch) -> None:
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(llm_policy, "_llm_configured", lambda: False)
    monkeypatch.setattr(llm_policy, "_qwen_configured", lambda: False)


def test_explicit_offline_salvage_false_keeps_identity_model_first_without_provider(monkeypatch) -> None:
    _clear_provider(monkeypatch)
    monkeypatch.setenv("QWEN_DISABLED", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_DISABLED", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_SALVAGE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_SALVAGE", "0")

    assert llm_policy.offline_salvage_enabled() is False


def test_unset_policy_preserves_no_provider_compatibility_default(monkeypatch) -> None:
    _clear_provider(monkeypatch)
    monkeypatch.setenv("QWEN_DISABLED", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_DISABLED", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_SALVAGE", "1")
    monkeypatch.delenv("HARDWARE_SPLICER_OFFLINE_SALVAGE", raising=False)

    assert llm_policy.offline_salvage_enabled() is True


def test_qwen_disabled_remains_explicit_compatibility_switch(monkeypatch) -> None:
    _clear_provider(monkeypatch)
    monkeypatch.setenv("QWEN_DISABLED", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_SALVAGE", "0")

    assert llm_policy.offline_salvage_enabled() is True


def test_explicit_offline_compose_false_also_blocks_no_provider_regex_fallback(monkeypatch) -> None:
    _clear_provider(monkeypatch)
    monkeypatch.setenv("QWEN_DISABLED", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_DISABLED", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_COMPOSE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_COMPOSE", "0")

    assert llm_policy.offline_compose_enabled() is False
