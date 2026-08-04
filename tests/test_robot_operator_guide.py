from __future__ import annotations

from hardware_splicer.guided_engineering_planner import plan_guided_engineering_project
from hardware_splicer.machine_project import MachineProject
from hardware_splicer.robot_operator_guide import GuidePhase


def test_guided_rover_plan_covers_full_build_lifecycle_without_authority() -> None:
    plan = plan_guided_engineering_project(
        {
            "project_name": "guided-rover",
            "goal": "Design and build a low-speed indoor inspection rover.",
            "available_parts": [
                {"name": "drive motor", "type": "dc_motor", "quantity": 2},
                {"name": "battery", "type": "power_source", "quantity": 1},
                {"name": "depth camera", "type": "camera", "quantity": 1},
            ],
            "constraints": {
                "battery_energy_wh": 100,
                "continuous_power_w": 40,
                "runtime_min": 90,
                "supply_current_limit_a": 10,
                "peak_current_a": 8,
            },
        },
        skip_vision=True,
    )

    guide = plan["operator_guide"]
    phases = [row["phase"] for row in guide["steps"]]
    assert phases == [
        GuidePhase.SCOPE.value,
        GuidePhase.SOURCES.value,
        GuidePhase.PROCUREMENT.value,
        GuidePhase.MECHANICAL.value,
        GuidePhase.ELECTRICAL.value,
        GuidePhase.FIRMWARE.value,
        GuidePhase.MIDDLEWARE.value,
        GuidePhase.SIMULATION.value,
        GuidePhase.CALIBRATION.value,
        GuidePhase.FIRST_POWER.value,
        GuidePhase.FIRST_MOTION.value,
        GuidePhase.INTEGRATION.value,
        GuidePhase.REGRESSION.value,
        GuidePhase.ROLLBACK.value,
        GuidePhase.RELEASE.value,
    ]
    assert guide["metadata"]["power_on_authorized"] is False
    assert guide["metadata"]["motion_authorized"] is False
    assert guide["metadata"]["release_authorized"] is False
    first_power = next(row for row in guide["steps"] if row["phase"] == "first_power")
    assert "current-limited bench supply" in first_power["tools"]
    assert any("rail" in row.lower() for row in first_power["stop_conditions"])
    assert first_power["blocking"] is True
    project = MachineProject.model_validate(plan["machine_project"])
    assert "robot_operator_guide" in project.discipline_payloads
    assert "engineering_verification_bridge" in project.discipline_payloads
    assert plan["engineering_readiness"]["operator_guide_generated"] is True
    assert plan["engineering_readiness"]["verification_method_count"] > 0


def test_quadruped_guide_adds_supported_body_and_gait_progression() -> None:
    plan = plan_guided_engineering_project(
        {
            "project_name": "guided-quadruped",
            "goal": "Build a twelve actuator quadruped for indoor inspection.",
            "available_parts": [
                {"name": "joint actuator", "type": "smart_servo", "quantity": 12},
                {"name": "body IMU", "type": "imu"},
            ],
            "constraints": {"leg_count": 4, "joints_per_leg": 3},
        },
        skip_vision=True,
    )

    first_motion = next(
        row for row in plan["operator_guide"]["steps"]
        if row["phase"] == "first_motion"
    )
    joined = " ".join(first_motion["instructions"]).lower()
    assert "body supported" in joined
    assert "static stance" in joined
    assert "bounded gait" in joined
    assert len(first_motion["target_ids"]) == 12


def test_field_revision_guide_requires_change_regression_and_rollback() -> None:
    plan = plan_guided_engineering_project(
        {
            "project_name": "field-revision-rover",
            "goal": "Revise the rover after tipping and a logic-rail brownout.",
            "baseline_revision": 7,
            "field_failure": "A tall camera mast caused tipping and controller reset during acceleration.",
            "available_parts": [
                {"name": "drive motor", "type": "dc_motor", "quantity": 2},
                {"name": "camera mast", "type": "mechanical_structure"},
            ],
            "constraints": {
                "support_width_mm": 200,
                "combined_cg_height_mm": 400,
                "static_tilt_margin_deg": 20,
                "supply_current_limit_a": 5,
                "peak_current_a": 12,
            },
        },
        skip_vision=True,
    )

    guide = plan["operator_guide"]
    regression = next(row for row in guide["steps"] if row["phase"] == "regression")
    rollback = next(row for row in guide["steps"] if row["phase"] == "rollback")
    assert guide["mode"] == "field_evolution"
    assert regression["blocking"] is True
    assert any("baseline" in row.lower() for row in regression["required_inputs"])
    assert any("known-good revision" in row.lower() for row in rollback["required_inputs"])
    assert guide["current_blockers"]
    assert plan["engineering_readiness"]["release_authorized"] is False
