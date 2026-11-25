"""The model-backed module pick retries once when the model's JSON misses the schema, and never for a rule failure."""

from __future__ import annotations

from types import SimpleNamespace

from hardware_splicer.integrations import qwen_module_pick as pick
from hardware_splicer.semantic_module_selector import SemanticSelectionError


def _trace():
    selection = SimpleNamespace(selected_module_ids=["esp32-devkit", "sg90"], rationale="ok", unresolved_questions=[], assumptions=[],
                                model_dump=lambda **_: {})
    dump = SimpleNamespace(model_dump=lambda **_: {})
    return SimpleNamespace(selection=selection, intent=dump, candidate_set=dump)


def test_one_retry_after_a_schema_miss(monkeypatch):
    calls = []

    def pipeline(goal, constraints=None):
        calls.append(goal)
        if len(calls) == 1:
            raise SemanticSelectionError("1 validation error for SemanticModuleSelection")
        return _trace()

    monkeypatch.setattr(pick, "qwen_module_pick_enabled", lambda: True)
    monkeypatch.setattr(pick, "semantic_module_selection_pipeline", pipeline)
    assert pick.call_qwen_module_pick("a servo arm")["ok"] and len(calls) == 2


def test_rule_failures_are_not_retried(monkeypatch):
    calls = []

    def pipeline(goal, constraints=None):
        calls.append(goal)
        raise SemanticSelectionError("selection referenced module IDs outside deterministic candidate set: invented")

    monkeypatch.setattr(pick, "qwen_module_pick_enabled", lambda: True)
    monkeypatch.setattr(pick, "semantic_module_selection_pipeline", pipeline)
    result = pick.call_qwen_module_pick("a servo arm")
    assert not result["ok"] and len(calls) == 1
