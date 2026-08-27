from __future__ import annotations

import hardware_splicer.integrations.llm_policy as llm_policy
from hardware_splicer.phrase_expander import (
    expand_user_phrase,
    expand_user_phrase_with_provenance,
)


def test_offline_mode_does_not_imply_semantic_rewrite(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_phrase_expand_enabled", lambda: True)
    monkeypatch.setattr(llm_policy, "offline_semantic_rewrite_enabled", lambda: False)

    result = expand_user_phrase_with_provenance("where do I start")

    assert result["text"] == "where do I start"
    assert result["semantic_rewrite_applied"] is False
    assert "water my plants" not in result["text"].lower()
    assert result["authority_effect"] == "none"


def test_lexical_typo_fix_can_run_without_semantic_rewrite(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_phrase_expand_enabled", lambda: True)
    monkeypatch.setattr(llm_policy, "offline_semantic_rewrite_enabled", lambda: False)

    result = expand_user_phrase_with_provenance("read tempurature and humdity")

    assert result["text"] == "read temperature and humidity"
    assert result["lexical_normalization_applied"] is True
    assert result["semantic_rewrite_applied"] is False


def test_semantic_rewrite_requires_explicit_compatibility_opt_in(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_phrase_expand_enabled", lambda: True)
    monkeypatch.setattr(llm_policy, "offline_semantic_rewrite_enabled", lambda: True)

    result = expand_user_phrase_with_provenance("where do I start")

    assert result["semantic_rewrite_applied"] is True
    assert "water my plants when soil is dry" in result["text"].lower()
    assert result["semantic_rewrite_source"]
    assert result["authority_effect"] == "none"


def test_model_first_policy_preserves_original_phrase(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_phrase_expand_enabled", lambda: False)
    monkeypatch.setattr(llm_policy, "offline_semantic_rewrite_enabled", lambda: True)

    text = "where do I start with tempurature sensing"
    result = expand_user_phrase_with_provenance(text)

    assert result["text"] == text
    assert result["lexical_normalization_applied"] is False
    assert result["semantic_rewrite_applied"] is False
    assert expand_user_phrase(text) == text
