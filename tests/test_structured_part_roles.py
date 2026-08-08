from __future__ import annotations

import hardware_splicer.integrations.llm_policy as llm_policy
from hardware_splicer.machine_project import Domain
from hardware_splicer.machine_project_seed import machine_project_from_intake
from hardware_splicer.structured_part_roles import (
    declared_part_domain,
    declared_part_role,
    structured_part_tokens,
)


def test_structured_role_projection_ignores_human_facing_name() -> None:
    row = {
        "component_id": "mystery-1",
        "name": "servo motor camera battery ESP32 rover",
        "type": "unknown_interface",
    }
    assert "servo_motor_camera_battery_esp32_rover" not in structured_part_tokens(row)
    assert declared_part_role(row) == ("unknown", "unresolved")


def test_structured_type_and_capability_are_bounded_role_inputs() -> None:
    assert declared_part_role({"name": "camera words", "type": "dc_motor"}) == (
        "actuator",
        "declared_structured_fields",
    )
    assert declared_part_role({"type": "custom", "capabilityTags": ["sensor_or_adc"]}) == (
        "sensor",
        "declared_structured_fields",
    )
    assert declared_part_domain({"domain": "firmware", "name": "battery"}) == "firmware"


def test_model_first_machine_seed_does_not_allocate_unknown_part_from_name(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    project = machine_project_from_intake(
        {
            "project_name": "name-invariance",
            "goal": "Preserve declared structure only.",
            "available_parts": [
                {
                    "component_id": "unknown-1",
                    "name": "servo motor camera battery controller",
                    "type": "unknown_interface",
                }
            ],
        }
    )

    component = project.components[0]
    assert component.domain == Domain.SYSTEM
    assert component.subsystem_id == "unclassified-components"
    assert component.metadata["domain_projection_source"] == "unresolved"
    assert component.metadata["discipline_allocation_unresolved"] is True
    assert project.metadata["unresolved_component_allocation_ids"] == [component.component_id]


def test_model_first_machine_seed_preserves_explicit_domain(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    project = machine_project_from_intake(
        {
            "goal": "Use explicit discipline allocation.",
            "available_parts": [
                {
                    "component_id": "fw-1",
                    "name": "battery motor camera words do not matter",
                    "domain": "firmware",
                    "type": "custom_blob",
                }
            ],
        }
    )
    component = project.components[0]
    assert component.domain == Domain.FIRMWARE
    assert component.subsystem_id == "firmware-control"
    assert component.metadata["domain_projection_source"] == "declared_domain"


def test_offline_compatibility_can_still_use_legacy_name_projection(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: True)
    project = machine_project_from_intake(
        {
            "goal": "offline fixture",
            "available_parts": [{"component_id": "legacy-1", "name": "left servo motor"}],
        }
    )
    component = project.components[0]
    assert component.domain == Domain.MECHANICAL
    assert component.subsystem_id == "actuation-system"
    assert component.metadata["domain_projection_source"] == "legacy_name_keyword"
