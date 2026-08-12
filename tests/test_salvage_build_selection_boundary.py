from __future__ import annotations

import hardware_splicer.integrations.llm_policy as llm_policy
import hardware_splicer.integrations.qwen_build_pick as qwen_build_pick
import hardware_splicer.salvage_bridge as salvage_bridge


def _legacy_plans() -> tuple[dict, dict]:
    splice = {
        "target": {"recommended_build_id": "automatic_plant_watering"},
    }
    diy = {
        "project_intent": {"mapped_build_id": "robot_drive_base"},
    }
    return splice, diy


def _explode_keyword(*args, **kwargs):
    raise AssertionError("model-first salvage executed legacy keyword build routing")


def test_model_first_salvage_build_uses_model_without_executing_keyword_shadow(monkeypatch) -> None:
    splice, diy = _legacy_plans()
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    monkeypatch.setattr(qwen_build_pick, "qwen_build_pick_enabled", lambda: True)
    monkeypatch.setattr(
        qwen_build_pick,
        "call_qwen_build_pick",
        lambda **kwargs: {
            "ok": True,
            "build_id": "sensor_logger",
            "confidence": 0.12,
            "reasoning": "The bounded observation/logging architecture fits the supplied evidence.",
            "unresolved_questions": [],
        },
    )
    monkeypatch.setattr(salvage_bridge, "_keyword_build_id", _explode_keyword)

    decision = salvage_bridge._pick_build_decision(
        "plant rover fan trigger words",
        [{"name": "measurement interface", "type": "sensor"}],
        splice,
        diy,
    )

    assert decision["build_id"] == "sensor_logger"
    assert decision["source"] == "model_proposed"
    assert decision["legacy_fallback_used"] is False
    assert decision["legacy_planner_ids_ignored"] == {
        "keyword": None,
        "diy": "robot_drive_base",
        "splice": "automatic_plant_watering",
    }
    assert decision["authority_effect"] == "none"


def test_model_first_salvage_failure_stays_unresolved_without_legacy_execution(monkeypatch) -> None:
    splice, diy = _legacy_plans()
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    monkeypatch.setattr(qwen_build_pick, "qwen_build_pick_enabled", lambda: True)
    monkeypatch.setattr(
        qwen_build_pick,
        "call_qwen_build_pick",
        lambda **kwargs: {
            "ok": False,
            "error": "provider_failed",
            "message": "semantic build selector unavailable",
        },
    )
    monkeypatch.setattr(salvage_bridge, "_keyword_build_id", _explode_keyword)

    decision = salvage_bridge._pick_build_decision(
        "watering rover fan",
        [],
        splice,
        diy,
    )

    assert decision["build_id"] is None
    assert decision["source"] == "unresolved"
    assert decision["legacy_fallback_used"] is False
    assert decision["unresolved_questions"]
    assert decision["legacy_planner_ids_ignored"]["keyword"] is None
    assert decision["legacy_planner_ids_ignored"]["diy"] == "robot_drive_base"
    assert decision["legacy_planner_ids_ignored"]["splice"] == "automatic_plant_watering"


def test_model_first_salvage_without_model_does_not_execute_profiles(monkeypatch) -> None:
    splice, diy = _legacy_plans()
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    monkeypatch.setattr(qwen_build_pick, "qwen_build_pick_enabled", lambda: False)
    monkeypatch.setattr(salvage_bridge, "_keyword_build_id", _explode_keyword)

    decision = salvage_bridge._pick_build_decision("repair donor rover", [], splice, diy)

    assert decision["build_id"] is None
    assert decision["source"] == "unresolved"
    assert "unavailable" in decision["reasoning"].lower()
    assert decision["legacy_planner_ids_ignored"]["keyword"] is None


def test_explicit_offline_salvage_preserves_legacy_selection_with_provenance(monkeypatch) -> None:
    splice, diy = _legacy_plans()
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: True)
    monkeypatch.setattr(
        salvage_bridge,
        "_keyword_build_id",
        lambda *args, **kwargs: "automatic_plant_watering",
    )

    decision = salvage_bridge._pick_build_decision("water plants", [], splice, diy)

    assert decision["build_id"] == "automatic_plant_watering"
    assert decision["source"] == "legacy_keyword"
    assert decision["legacy_fallback_used"] is True
    assert decision["confidence"] == 0.0
    assert decision["authority_effect"] == "none"
