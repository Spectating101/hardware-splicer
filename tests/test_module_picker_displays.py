"""One display per goal unless the goal names two, and the "led" in "oled" is not an indicator LED."""

from __future__ import annotations

import pytest

from hardware_splicer.module_picker import _pick_modules_regex
from hardware_splicer.pcb.module_registry import find_module


def _displays(ids):
    return [m for m in ids if "display_or_ui" in (find_module(m) or {}).get("capabilityTags", [])]


@pytest.mark.parametrize("goal", ["add a small oled display", "room monitor with a small screen"])
def test_a_goal_asking_for_one_screen_gets_one(goal):
    assert _displays(_pick_modules_regex(goal).module_ids) == ["ssd1306-128x64"]


def test_oled_does_not_trigger_the_indicator_led_hint():
    assert "indicator LED" not in _pick_modules_regex("add a small oled display").hints
    assert "indicator LED" in _pick_modules_regex("add an led that blinks").hints
