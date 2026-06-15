"""Material mode — scratch vs salvage on same engine."""

from __future__ import annotations

from hardware_splicer.material_modes import (
    can_add_module,
    expand_module_ids_for_safety,
    resolve_material_mode,
)


def test_scratch_vs_salvage_classification() -> None:
    assert resolve_material_mode(constraints={"graph_mode": "scratch"}) == "scratch"
    assert resolve_material_mode(salvage_mode=True) == "salvage"
    assert resolve_material_mode(constraints={"strategy_mode": "open"}) == "scratch"


def test_salvage_can_buy_level_shifter_not_random_motor() -> None:
    inventory = ["esp32-devkit", "hc-sr04", "usb-power-5v"]
    assert can_add_module("level-shifter-4ch", material_mode="salvage", inventory_ids=inventory)
    assert not can_add_module("l298n", material_mode="salvage", inventory_ids=inventory)


def test_open_scratch_adds_level_shifter_from_safety_message() -> None:
    ids = expand_module_ids_for_safety(
        ["esp32-devkit", "hc-sr04", "usb-power-5v"],
        safety_messages=["ESP32 uses 3.3V logic, HC-SR04 uses 5V logic. Add a level shifter."],
        material_mode="scratch",
    )
    assert "level-shifter-4ch" in ids


def test_salvage_adds_only_allowed_purchase() -> None:
    ids = expand_module_ids_for_safety(
        ["esp32-devkit", "hc-sr04", "usb-power-5v"],
        safety_messages=["Add a level shifter."],
        material_mode="salvage",
        inventory_ids=["esp32-devkit", "hc-sr04", "usb-power-5v"],
    )
    assert "level-shifter-4ch" in ids
    assert "l298n" not in ids
