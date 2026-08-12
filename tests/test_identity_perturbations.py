from __future__ import annotations

from hardware_splicer.identity_perturbations import (
    remove_identity_field,
    rename_bound_part_label,
    rename_donor_block_label,
    reverse_inventory_order,
)


def test_inventory_reordering_is_an_equivalence_perturbation() -> None:
    snapshot = {
        "available_parts": [
            {"component_id": "a", "module_id": "esp32-devkit", "name": "controller"},
            {"component_id": "b", "module_id": "bme280", "name": "sensor"},
        ]
    }
    result = reverse_inventory_order(snapshot)

    assert result["classification"] == "equivalence"
    assert result["equivalence_expected"] is True
    assert [row["component_id"] for row in result["snapshot"]["available_parts"]] == ["b", "a"]
    assert snapshot["available_parts"][0]["component_id"] == "a"


def test_bound_module_label_rename_preserves_identity_equivalence() -> None:
    snapshot = {
        "available_parts": [
            {
                "component_id": "sensor-1",
                "module_id": "bme280",
                "name": "BME280 breakout",
                "type": "sensor",
            }
        ]
    }
    result = rename_bound_part_label(
        snapshot,
        component_id="sensor-1",
        new_name="weather transducer alpha",
    )

    assert result["classification"] == "equivalence"
    assert result["equivalence_expected"] is True
    assert "module_id" in result["reason"]
    assert result["snapshot"]["available_parts"][0]["module_id"] == "bme280"
    assert result["snapshot"]["available_parts"][0]["name"] == "weather transducer alpha"


def test_unanchored_part_label_rename_is_evidence_change_not_equivalence() -> None:
    snapshot = {
        "available_parts": [
            {
                "component_id": "fet-1",
                "name": "AO3400 MOSFET",
                "type": "mosfet",
            }
        ]
    }
    result = rename_bound_part_label(
        snapshot,
        component_id="fet-1",
        new_name="mystery transistor",
    )

    assert result["classification"] == "evidence_change"
    assert result["equivalence_expected"] is False
    assert "no persisted identity anchor" in result["reason"]


def test_donor_display_name_rename_is_equivalent_when_block_id_and_capabilities_persist() -> None:
    snapshot = {
        "donor_context": {
            "reusable_blocks": [
                {
                    "block_id": "drv-7",
                    "name": "left motor driver",
                    "function_type": "actuator_driver",
                    "capabilities": ["bidirectional_dc_motor_drive"],
                    "connector_refs": ["J3"],
                }
            ]
        }
    }
    result = rename_donor_block_label(
        snapshot,
        block_id="drv-7",
        new_name="unfamiliar switching block",
    )

    assert result["classification"] == "equivalence"
    block = result["snapshot"]["donor_context"]["reusable_blocks"][0]
    assert block["block_id"] == "drv-7"
    assert block["function_type"] == "actuator_driver"
    assert block["capabilities"] == ["bidirectional_dc_motor_drive"]
    assert block["name"] == "unfamiliar switching block"


def test_removing_mpn_is_explicit_evidence_change() -> None:
    snapshot = {
        "available_parts": [
            {
                "component_id": "fet-1",
                "name": "power transistor",
                "mpn": "IRLZ44N",
                "type": "mosfet",
            }
        ]
    }
    result = remove_identity_field(
        snapshot,
        component_id="fet-1",
        field="mpn",
    )

    assert result["classification"] == "evidence_change"
    assert result["equivalence_expected"] is False
    assert "mpn" not in result["snapshot"]["available_parts"][0]
    assert "must not be scored as equivalence instability" in result["reason"]
