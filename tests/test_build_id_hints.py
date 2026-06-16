from __future__ import annotations

from unittest import mock

import pytest

from hardware_splicer.integrations.build_id_hints import keyword_build_id, reconcile_build_pick
from hardware_splicer.module_picker import pick_modules_for_goal
from hardware_splicer.project_intake import load_project_intake
from hardware_splicer.salvage_bridge import build_intake_salvage_package


def test_keyword_fan_airflow_maps_to_fume_extractor() -> None:
    intake = load_project_intake("examples/intakes/fan_controller_brief.json")
    got = keyword_build_id(str(intake.get("goal") or ""), list(intake.get("available_parts") or []))
    assert got == "usb_fume_extractor"


def test_reconcile_prefers_keyword_over_generic_llm() -> None:
    got = reconcile_build_pick(
        "generic_low_voltage_build",
        "usb_fume_extractor",
        diy_build_id="usb_fume_extractor",
        llm_confidence=0.6,
    )
    assert got == "usb_fume_extractor"


def test_reconcile_keeps_confident_llm_when_no_keyword() -> None:
    got = reconcile_build_pick(
        "sensor_logger",
        None,
        llm_confidence=0.95,
    )
    assert got == "sensor_logger"


def test_online_compose_uses_regex_for_trained_phrase(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hardware_splicer.integrations.llm_policy.offline_compose_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "hardware_splicer.integrations.qwen_module_pick.qwen_module_pick_enabled",
        lambda: True,
    )
    with mock.patch(
        "hardware_splicer.integrations.qwen_module_pick.call_qwen_module_pick",
    ) as llm_pick:
        pick = pick_modules_for_goal("something that measures temperature")
        llm_pick.assert_not_called()
    assert "dht22" in pick.module_ids
    assert "esp32-devkit" in pick.module_ids


def test_online_compose_calls_llm_for_novel_phrase(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def _fake_pick(goal: str, **kwargs: object) -> dict[str, object]:
        calls.append(goal)
        return {
            "ok": True,
            "module_ids": ["usb-power-5v", "esp32-devkit", "bme280", "mosfet-irlz44n"],
            "reasoning": "novel",
        }

    monkeypatch.setattr(
        "hardware_splicer.integrations.llm_policy.offline_compose_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "hardware_splicer.integrations.qwen_module_pick.qwen_module_pick_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "hardware_splicer.integrations.qwen_module_pick.call_qwen_module_pick",
        _fake_pick,
    )
    pick = pick_modules_for_goal("mystery greenhouse telemetry with odd wording")
    assert len(calls) == 1
    assert "bme280" in pick.module_ids


def test_salvage_fan_intake_uses_keyword_when_llm_generic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_SALVAGE", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_WORKSHOP", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_SALVAGE_RESOLVE", "heuristic")
    monkeypatch.setattr(
        "hardware_splicer.integrations.qwen_build_pick.qwen_build_pick_enabled",
        lambda: True,
    )
    intake = load_project_intake("examples/intakes/fan_controller_brief.json")
    with mock.patch(
        "hardware_splicer.integrations.qwen_build_pick.call_qwen_build_pick",
        return_value={
            "ok": True,
            "build_id": "generic_low_voltage_build",
            "confidence": 0.55,
        },
    ):
        pkg = build_intake_salvage_package(
            goal=str(intake.get("goal") or ""),
            parts=list(intake.get("available_parts") or []),
            constraints=dict(intake.get("constraints") or {}),
            project_name="fan_controller",
        )
    assert pkg.get("recommended_build_id") == "usb_fume_extractor"
