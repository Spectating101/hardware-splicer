from __future__ import annotations

import hardware_splicer.integrations.qwen_build_pick as build_pick_module
import hardware_splicer.integrations.qwen_intake_normalize as intake_module
from hardware_splicer.integrations.build_id_hints import (
    reconcile_build_pick,
    reconcile_build_pick_with_provenance,
)


def test_valid_model_build_cannot_be_overridden_by_keyword_even_at_low_confidence() -> None:
    selected = reconcile_build_pick(
        "sensor_logger",
        "automatic_plant_watering",
        diy_build_id="automatic_plant_watering",
        splice_build_id="automatic_plant_watering",
        llm_confidence=0.05,
    )

    assert selected == "sensor_logger"

    decision = reconcile_build_pick_with_provenance(
        "sensor_logger",
        "automatic_plant_watering",
        diy_build_id="automatic_plant_watering",
        splice_build_id="automatic_plant_watering",
        llm_confidence=0.05,
    )
    assert decision["build_id"] == "sensor_logger"
    assert decision["source"] == "model_proposed"
    assert decision["legacy_fallback_used"] is False
    assert decision["authority_effect"] == "none"


def test_model_first_reconciliation_can_refuse_all_legacy_fallbacks() -> None:
    decision = reconcile_build_pick_with_provenance(
        None,
        "robot_drive_base",
        diy_build_id="robot_drive_base",
        splice_build_id="robot_drive_base",
        allow_legacy_fallback=False,
    )

    assert decision["build_id"] is None
    assert decision["source"] == "unresolved"
    assert decision["legacy_fallback_used"] is False


def test_model_build_prompt_is_not_seeded_with_keyword_answer(monkeypatch) -> None:
    captured: dict[str, str] = {}

    monkeypatch.setattr(build_pick_module, "qwen_build_pick_enabled", lambda: True)

    def fake_chat(prompt: str, **kwargs: object) -> dict:
        captured["prompt"] = prompt
        return {
            "ok": True,
            "provider": "semantic-test",
            "model": "deterministic-fixture",
            "content": '{"build_id":"sensor_logger","reasoning":"Fits the structured observation/logging function.","confidence":0.7,"unresolved_questions":[]}',
        }

    monkeypatch.setattr(build_pick_module, "call_qwen_chat", fake_chat)
    result = build_pick_module.call_qwen_build_pick(
        goal="water moves when an observation crosses a threshold",
        parts=[{"name": "unknown transducer", "type": "sensor"}],
    )

    assert result["ok"] is True
    assert result["build_id"] == "sensor_logger"
    prompt = captured["prompt"]
    assert "keyword_build_hint" not in prompt
    assert "Prefer keyword_build_hint" not in prompt
    assert "Fan, airflow, ventilation" not in prompt
    assert "Soil, plant, pump, irrigation" not in prompt
    assert "Rover, wheels, mobile robot →" not in prompt


def test_model_first_archetype_failure_stays_unresolved_without_keyword_fallback(monkeypatch) -> None:
    monkeypatch.setattr(intake_module, "qwen_llm_first", lambda: True)
    monkeypatch.setattr(intake_module, "offline_salvage_enabled", lambda: False)
    monkeypatch.setattr(
        intake_module,
        "call_qwen_build_pick",
        lambda **kwargs: {
            "ok": False,
            "error": "provider_failed",
            "message": "model unavailable",
        },
    )

    def fail_if_keyword_runs(*args, **kwargs):
        raise AssertionError("model-first intake executed legacy keyword routing")

    monkeypatch.setattr(intake_module, "keyword_build_id", fail_if_keyword_runs)

    proposal = intake_module.detect_archetype_proposal(
        "soil pump irrigation rover fan",
        [{"name": "unknown board", "type": "unknown"}],
    )

    assert proposal["status"] == "unresolved"
    assert proposal["source"] == "unresolved"
    assert proposal["archetype"] == "generic_mechatronics"
    assert proposal["build_id"] is None
    assert proposal["unresolved_questions"]
    assert proposal["authority_effect"] == "none"


def test_model_first_archetype_accepts_model_proposal_without_consulting_keyword_router(monkeypatch) -> None:
    monkeypatch.setattr(intake_module, "qwen_llm_first", lambda: True)
    monkeypatch.setattr(intake_module, "offline_salvage_enabled", lambda: False)
    monkeypatch.setattr(
        intake_module,
        "call_qwen_build_pick",
        lambda **kwargs: {
            "ok": True,
            "build_id": "sensor_logger",
            "confidence": 0.2,
            "reasoning": "The supplied evidence supports an observation/logging architecture.",
            "unresolved_questions": [],
        },
    )

    def fail_if_keyword_runs(*args, **kwargs):
        raise AssertionError("valid model proposal consulted legacy keyword routing")

    monkeypatch.setattr(intake_module, "keyword_build_id", fail_if_keyword_runs)

    proposal = intake_module.detect_archetype_proposal(
        "plant pump rover fan words intentionally conflict with old triggers",
        [{"name": "measurement interface", "type": "sensor"}],
    )

    assert proposal["status"] == "model_proposed"
    assert proposal["build_id"] == "sensor_logger"
    assert proposal["archetype"] == "sensor_logger"
    assert proposal["source"] == "model_proposed"
    assert proposal["confidence"] == 0.2
    assert proposal["authority_effect"] == "none"


def test_explicit_offline_mode_retains_legacy_classifier_with_visible_provenance(monkeypatch) -> None:
    monkeypatch.setattr(intake_module, "qwen_llm_first", lambda: False)
    monkeypatch.setattr(intake_module, "offline_salvage_enabled", lambda: True)

    proposal = intake_module.detect_archetype_proposal(
        "watering pump for a plant",
        [],
    )

    assert proposal["status"] == "legacy_heuristic"
    assert proposal["source"] == "legacy_keyword"
    assert proposal["build_id"] == "automatic_plant_watering"
    assert proposal["archetype"] == "automatic_watering"
    assert proposal["confidence"] == 0.0
    assert proposal["authority_effect"] == "none"
