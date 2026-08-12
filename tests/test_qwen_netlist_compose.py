"""Model-first compose tests across semantic-review and explicit offline paths."""

from __future__ import annotations

import pytest

import hardware_splicer.integrations.qwen_netlist_compose as compose_module
from hardware_splicer.integrations.qwen_netlist_compose import compose_netlist_from_goal


def test_disabling_qwen_does_not_implicitly_authorize_legacy_picker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_COMPOSE", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_COMPOSE", "1")

    import hardware_splicer.module_picker as legacy_picker

    monkeypatch.setattr(
        legacy_picker,
        "pick_modules_for_goal",
        lambda goal: (_ for _ in ()).throw(AssertionError("legacy picker ran without explicit permission")),
    )

    result = compose_netlist_from_goal(
        "wifi temperature logger with esp32 and dht22",
        allow_qwen=False,
    )

    assert result.get("ok") is False
    assert result.get("compose_mode") == "legacy_offline_blocked"
    assert result.get("error") == "legacy_offline_permission_required"
    assert result.get("legacy_offline_available") is True
    assert result.get("netlist") is None


def test_explicit_legacy_offline_compose_remains_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_COMPOSE", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_COMPOSE", "1")

    result = compose_netlist_from_goal(
        "wifi temperature logger with esp32 and dht22",
        allow_qwen=False,
        allow_legacy_offline=True,
    )

    assert result.get("compose_mode") == "module_picker_offline_compat"
    assert result.get("legacy_semantic_fallback") is True
    assert result.get("legacy_offline_explicitly_authorized") is True
    assert result.get("ok") is True
    assert len(result.get("netlist", {}).get("components") or []) >= 2


def test_online_model_failure_returns_semantic_review_before_legacy_picker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_COMPOSE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_COMPOSE", "0")

    monkeypatch.setattr(
        compose_module,
        "call_qwen_netlist_compose",
        lambda goal, constraints=None: {
            "ok": False,
            "error": "invalid_netlist_json",
            "message": "model output did not satisfy netlist schema",
        },
    )
    monkeypatch.setattr(
        compose_module,
        "semantic_module_proposal_from_goal",
        lambda goal, constraints=None: {
            "ok": False,
            "error": "semantic_module_review_required",
            "compose_mode": "semantic_module_proposal",
            "requires_human_review": True,
            "module_ids": ["candidate-a", "candidate-b"],
            "semantic_intent": {"goal_summary": "typed intent"},
            "semantic_candidate_set": {"candidates_by_requirement": {}},
            "semantic_selection": {"selected_module_ids": ["candidate-a", "candidate-b"]},
            "authority_effect": "none",
            "automatic_execution": False,
        },
    )

    import hardware_splicer.module_picker as legacy_picker

    monkeypatch.setattr(
        legacy_picker,
        "pick_modules_for_goal",
        lambda goal: (_ for _ in ()).throw(AssertionError("legacy picker executed online")),
    )

    result = compose_netlist_from_goal("novel hardware goal", allow_qwen=True)

    assert result.get("compose_mode") == "semantic_module_proposal"
    assert result.get("requires_human_review") is True
    assert result.get("automatic_execution") is False
    assert result.get("authority_effect") == "none"
    assert result.get("module_ids") == ["candidate-a", "candidate-b"]
    assert result.get("netlist") is None
    assert result.get("qwen_netlist_error") == "invalid_netlist_json"
