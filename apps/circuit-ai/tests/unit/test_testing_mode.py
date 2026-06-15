from __future__ import annotations

import pytest

from src.intelligence.salvage_splice_planner import SalvageSplicePlanner


@pytest.fixture()
def planner():
    return SalvageSplicePlanner()


def test_swollen_battery_holds_without_testing_mode(planner, monkeypatch):
    monkeypatch.delenv("HARDWARE_SPLICER_TESTING_MODE", raising=False)
    plan = planner.plan(
        {
            "title": "swollen lithium power bank",
            "goal": "reuse cells",
            "available_parts": ["swollen lithium battery pack", "USB charging board"],
        }
    )
    assert plan.get("verdict") == "unsafe_hold"


def test_swollen_battery_proceeds_in_testing_mode(planner, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_TESTING_MODE", "1")
    plan = planner.plan(
        {
            "title": "swollen lithium power bank",
            "goal": "reuse cells",
            "available_parts": ["swollen lithium battery pack", "USB charging board", "DC motor"],
        }
    )
    assert plan.get("verdict") != "unsafe_hold"
