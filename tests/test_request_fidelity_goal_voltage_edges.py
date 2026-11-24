"""Edge cases for reading a goal's mains voltage and named parts (review of PR #387)."""

import pytest

from hardware_splicer.request_fidelity import assess_goal_fidelity, detect_high_voltage_goal


@pytest.mark.parametrize("goal", [
    "switch a two-thirty volt heater",
    "a one twenty volt lamp dimmer",
    "two hundred forty volts fan control",
    "run it from household power",
    "switch a 230 V 300 W heater",
    "120 Vac pump",
])
def test_mains_loads_are_flagged_however_they_are_written(goal):
    assert detect_high_voltage_goal(goal) is not None


@pytest.mark.parametrize("goal", [
    "ESP32 sensor board with a 100 V capacitor rating on the input",
    "use an LM317-100V for a 12 V supply",
    "TVS diode rated 1000 V ESD on the USB lines",
    "5 V servo and 3.3 V logic from a 12 V barrel jack",
])
def test_component_ratings_and_low_voltages_are_not_flagged(goal):
    assert detect_high_voltage_goal(goal) is None


def test_no_load_is_a_condition_not_a_missing_part():
    result = assess_goal_fidelity("test an SSR under no-load conditions", {"nodes": [{"moduleId": "esp32-devkit"}]})
    assert [row["label"] for row in result["named_parts_missing"]] == ["solid-state relay (SSR)"]


def test_without_still_means_absent():
    result = assess_goal_fidelity("an ESP32 logger without an SSR", {"nodes": [{"moduleId": "esp32-devkit"}]})
    assert result["named_parts_missing"] == []
