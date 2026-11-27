"""Duty-cycle battery runtime on the head-to-head LoRa brief, checked by hand."""

from __future__ import annotations

import pytest

from hardware_splicer.battery_runtime import CITED, runtime


def test_the_lora_node_by_hand():
    """2600 mAh, a wake every 600 s: 0.5 s LoRa at 120 mA and 3 s awake at 31 mA, 10 uA asleep.

    Charge per wake = 60 + 93 + 0.01 x 596.5 = 158.965 mA.s, so 0.26494 mA average. Ceiling = 2600 x 0.8 / 0.26494 h = 327.1 days.
    Self-discharge at 5 %/month = 2600 x 0.05 / 730 = 0.17808 mA extra: 2080 / 0.44302 h = 195.6 days.
    """
    phases = [{"label": "LoRa transmit", "ma": CITED["sx127x_tx_20dbm_ma"]["value"], "seconds": 0.5, "basis": "cited"},
              {"label": "ESP32 awake", "ma": 31, "seconds": 3, "basis": "cited upper end"}]
    r = runtime(2600, 600, phases, sleep_ua=CITED["esp32_deep_sleep_ua"]["value"], sleep_basis="cited chip figure")
    assert r["average_ma"] == pytest.approx(0.26494, abs=1e-4)
    assert r["runtime_days"]["ceiling"][0] == pytest.approx(327.1, abs=0.1)
    assert r["runtime_days"]["with_self_discharge"][0] == pytest.approx(195.6, abs=0.1)
    assert r["inputs"]["usable_share"]["basis"] == "assumed" and r["inputs"]["self_discharge_pct_month"]["basis"] == "cited"


def test_phases_longer_than_the_period_are_refused():
    with pytest.raises(ValueError, match="longer than"):
        runtime(1000, 10, [{"label": "x", "ma": 10, "seconds": 11}], sleep_ua=5)
