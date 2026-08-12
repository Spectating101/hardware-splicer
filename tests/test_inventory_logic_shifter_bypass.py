from __future__ import annotations

from hardware_splicer.catalog import get_catalog_build
from hardware_splicer.inventory_topology import adapt_recipe_to_inventory


def _module_ids(recipe: dict) -> dict[str, str]:
    return {
        str(row.get("role") or ""): str(row.get("moduleId") or "")
        for row in recipe.get("modules") or []
    }


def test_nano_direct_drive_removes_redundant_esp32_level_shifter() -> None:
    recipe = get_catalog_build("usb_fume_extractor")
    adapted, _ = adapt_recipe_to_inventory(
        recipe,
        {
            "module_overrides": {"mcu": "arduino-nano"},
            "resolved_modules": [],
            "strategy_mode": "flexible",
        },
    )

    modules = _module_ids(adapted)
    assert modules["mcu"] == "arduino-nano"
    assert "shift" not in modules
    assert {
        "from": {"role": "mcu", "pin": "D2"},
        "to": {"role": "drv", "pin": "SIG"},
    } in (adapted.get("wires") or [])


def test_esp32_keeps_level_shifter_when_receiver_requires_4v5_logic() -> None:
    recipe = get_catalog_build("usb_fume_extractor")
    adapted, _ = adapt_recipe_to_inventory(
        recipe,
        {
            "module_overrides": {"mcu": "esp32-devkit"},
            "resolved_modules": [],
            "strategy_mode": "flexible",
        },
    )

    modules = _module_ids(adapted)
    assert modules["mcu"] == "esp32-devkit"
    assert modules["shift"] == "level-shifter-4ch"
    assert {
        "from": {"role": "shift", "pin": "HV1"},
        "to": {"role": "drv", "pin": "SIG"},
    } in (adapted.get("wires") or [])
