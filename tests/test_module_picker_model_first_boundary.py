from __future__ import annotations

import hardware_splicer.integrations.llm_policy as llm_policy
import hardware_splicer.integrations.qwen_module_pick as qwen_module_pick
import hardware_splicer.module_picker as module_picker
from hardware_splicer.module_picker import ModulePick, pick_modules_for_goal


def test_model_enabled_picker_never_evaluates_regex_first(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_compose_enabled", lambda: False)
    monkeypatch.setattr(qwen_module_pick, "qwen_module_pick_enabled", lambda: True)
    monkeypatch.setattr(
        qwen_module_pick,
        "call_qwen_module_pick",
        lambda goal: {
            "ok": True,
            "module_ids": ["semantic-a", "semantic-b"],
            "reasoning": "typed capability selection",
        },
    )

    def fail_if_regex_runs(*args, **kwargs):
        raise AssertionError("legacy regex picker executed before model selection")

    monkeypatch.setattr(module_picker, "_pick_modules_regex", fail_if_regex_runs)

    result = pick_modules_for_goal("rover watering fan keywords should not preempt the model")

    assert result.module_ids == ["semantic-a", "semantic-b"]
    assert result.hints == ["typed capability selection"]


def test_model_failure_stays_unresolved_instead_of_falling_back_to_regex(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_compose_enabled", lambda: False)
    monkeypatch.setattr(qwen_module_pick, "qwen_module_pick_enabled", lambda: True)
    monkeypatch.setattr(
        qwen_module_pick,
        "call_qwen_module_pick",
        lambda goal: {
            "ok": False,
            "error": "semantic_module_selection_failed",
            "message": "missing electrical facts",
        },
    )

    def fail_if_regex_runs(*args, **kwargs):
        raise AssertionError("model failure silently fell through to legacy regex")

    monkeypatch.setattr(module_picker, "_pick_modules_regex", fail_if_regex_runs)

    result = pick_modules_for_goal("watering rover fan")

    assert result.module_ids == []
    assert result.labels == []
    assert result.hints == ["unresolved:missing electrical facts"]


def test_explicit_offline_policy_can_still_use_legacy_picker(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_compose_enabled", lambda: True)
    monkeypatch.setattr(qwen_module_pick, "qwen_module_pick_enabled", lambda: True)
    sentinel = ModulePick(
        module_ids=["legacy-a", "legacy-b"],
        labels=["legacy"],
        hints=["legacy-offline"],
    )
    monkeypatch.setattr(module_picker, "_pick_modules_regex", lambda goal: sentinel)

    def fail_if_model_runs(*args, **kwargs):
        raise AssertionError("explicit offline mode attempted model selection")

    monkeypatch.setattr(qwen_module_pick, "call_qwen_module_pick", fail_if_model_runs)

    result = pick_modules_for_goal("offline regression fixture")

    assert result is sentinel
