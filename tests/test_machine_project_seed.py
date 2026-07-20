from __future__ import annotations

from hardware_splicer.machine_project import AuthorityState, Domain, LifecycleState
from hardware_splicer.machine_project_seed import machine_project_from_intake


def pan_tilt_intake() -> dict:
    return {
        "project_name": "physical_pan_tilt_closed_loop",
        "goal": "Build a pan-tilt inspection camera mount with two SG90 servos and ESP32 for remote aim.",
        "salvage_mode": True,
        "available_parts": [
            {
                "name": "ESP32 DevKit",
                "type": "microcontroller",
                "module_id": "esp32-devkit",
                "condition": "salvaged",
            },
            {
                "name": "SG90 pan servo",
                "type": "servo",
                "module_id": "sg90",
                "condition": "salvaged",
            },
            {
                "name": "SG90 tilt servo",
                "type": "servo",
                "module_id": "sg90",
                "condition": "salvaged",
            },
            {
                "name": "USB 5V power bank",
                "type": "power_source",
                "module_id": "usb-power-5v",
                "voltage_v": 5.0,
                "condition": "salvaged",
            },
        ],
        "constraints": {
            "strategy_mode": "constrained",
            "prefer_salvage": True,
            "battery_voltage_v": 5.0,
            "runtime_min": 45,
        },
        "evidence_notes": [
            "splice:power servos from USB 5V rail — not MCU 3V3",
        ],
    }


def test_pan_tilt_intake_seeds_complete_machine_architecture_without_fake_interfaces() -> None:
    project = machine_project_from_intake(pan_tilt_intake())

    assert project.project_id == "physical_pan_tilt_closed_loop"
    assert project.lifecycle_state == LifecycleState.ARCHITECTURE
    assert {row.subsystem_id for row in project.subsystems} >= {
        "system",
        "power-system",
        "control-electronics",
        "actuation-system",
        "firmware-control",
        "mechanical-structure",
    }
    assert len(project.components) == 4
    assert all(component.authority == AuthorityState.DECLARED for component in project.components)
    assert all(component.source.value == "donor" for component in project.components)
    assert {row.domain for row in project.components} >= {Domain.ELECTRICAL, Domain.MECHANICAL}
    assert {row.requirement_id for row in project.requirements} == {
        "req-primary-purpose",
        "req-runtime",
    }
    assert project.interfaces == []
    assert project.metadata["interfaces_inferred"] is False
    assert project.metadata["verification_inferred"] is False
    assert project.discipline_payloads["project_intake"]["evidence_notes"]


def test_runtime_requirement_allocates_to_power_even_without_declared_power_part() -> None:
    project = machine_project_from_intake(
        {
            "project_name": "runtime_only",
            "goal": "Build a mobile logger.",
            "constraints": {"runtime_min": 90},
            "available_parts": [{"name": "ESP32", "type": "microcontroller"}],
        }
    )

    assert "power-system" in {row.subsystem_id for row in project.subsystems}
    runtime = next(row for row in project.requirements if row.requirement_id == "req-runtime")
    assert runtime.allocated_to == ["power-system"]
    assert not [issue for issue in project.traceability_issues() if issue.code == "invalid_ref"]


def test_seed_reports_verification_gaps_instead_of_claiming_release() -> None:
    project = machine_project_from_intake(pan_tilt_intake())

    issues = project.traceability_issues()
    assert {issue.code for issue in issues} == {"unverified_requirement"}
    assessment = project.assess_release()
    assert assessment.allowed is False
    assert assessment.achieved_state.value in {"design_ready", "concept"}
