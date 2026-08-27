from __future__ import annotations

from hardware_splicer.complete_engineering_planner import plan_complete_engineering_project
from hardware_splicer.engineering_source_adapters import adapt_engineering_sources
from hardware_splicer.machine_project import MachineProject


URDF = """
<robot name="camera_arm">
  <link name="base_link"/>
  <link name="camera_link"/>
  <joint name="camera_pan" type="revolute">
    <parent link="base_link"/>
    <child link="camera_link"/>
    <axis xyz="0 0 1"/>
    <limit lower="-1.57" upper="1.57" effort="2" velocity="1"/>
  </joint>
</robot>
"""


def test_adapters_create_pinned_claim_sources_for_multiple_artifact_types() -> None:
    bundle = adapt_engineering_sources(
        [
            {
                "source_id": "arm-urdf",
                "artifact_kind": "urdf",
                "uri": "package://camera_arm/robot.urdf",
                "revision": "commit-abc",
                "content": URDF,
            },
            {
                "source_id": "firmware-build",
                "artifact_kind": "firmware_manifest",
                "manifest": {
                    "firmware_component_id": "main-controller",
                    "source_revision": "commit-def",
                    "toolchain": "platformio",
                    "toolchain_version": "6.1",
                    "build_command": "pio run",
                    "binary_hash": "sha256:binary",
                    "flash_command": "pio run -t upload",
                    "pin_map_hash": "sha256:pins",
                },
            },
            {
                "source_id": "ros-contract",
                "artifact_kind": "ros_interface_manifest",
                "revision": "jazzy-r1",
                "manifest": {
                    "node_id": "camera-arm-node",
                    "distribution": "jazzy",
                    "topics": [{"name": "/joint_states", "type": "sensor_msgs/msg/JointState"}],
                    "services": [{"name": "/home", "type": "std_srvs/srv/Trigger"}],
                    "frames": ["base_link", "camera_link"],
                },
            },
            {
                "source_id": "rail-capture",
                "artifact_kind": "measurement",
                "capture_id": "scope-12",
                "instrument_id": "scope-a",
                "calibration_id": "cal-2026",
                "measurements": [
                    {
                        "subject_id": "logic-rail",
                        "predicate": "minimum_voltage_v",
                        "value": 4.92,
                        "units": "V",
                    }
                ],
            },
            {
                "source_id": "mission-telemetry",
                "artifact_kind": "telemetry",
                "run_id": "run-4",
                "sample_rate_hz": 100,
                "values": {
                    "peak_pitch_deg": 8.2,
                    "maximum_current_a": 6.4,
                },
            },
        ]
    )

    assert len(bundle.sources) == 5
    assert set(bundle.robot_models) == {"arm-urdf"}
    assert bundle.unresolved == []
    by_id = {row["source_id"]: row for row in bundle.sources}
    assert by_id["arm-urdf"]["content_hash"].startswith("sha256:")
    assert by_id["firmware-build"]["revision"] == "commit-def"
    assert {row["predicate"] for row in by_id["firmware-build"]["claims"]} >= {
        "source_revision",
        "toolchain",
        "binary_hash",
        "pin_map_hash",
    }
    assert {row["predicate"] for row in by_id["ros-contract"]["claims"]} >= {
        "ros_topics",
        "ros_services",
        "coordinate_frames",
    }
    assert by_id["rail-capture"]["authority_ceiling"] == "measured"
    assert by_id["mission-telemetry"]["metadata"]["sample_rate_hz"] == 100


def test_complete_planner_selects_single_structured_robot_model() -> None:
    plan = plan_complete_engineering_project(
        {
            "project_name": "camera-arm",
            "goal": "Build a camera pan arm from the declared robot model.",
            "available_parts": [
                {"name": "pan actuator", "type": "smart_servo"},
                {"name": "camera", "type": "camera"},
            ],
            "constraints": {
                "payload_mass_kg": 0.2,
                "payload_lever_arm_m": 0.1,
                "actuator_continuous_torque_nm": 1.0,
            },
        },
        engineering_sources=[
            {
                "source_id": "arm-urdf",
                "artifact_kind": "urdf",
                "revision": "commit-abc",
                "content": URDF,
            }
        ],
        skip_vision=True,
    )

    assert plan["source_adapter"]["selected_robot_model_source_id"] == "arm-urdf"
    assert plan["robot_topology"]["topology_id"].startswith("model-camera_arm-")
    assert {row["joint_id"] for row in plan["robot_topology"]["joints"]} == {"camera_pan"}
    assert plan["engineering_identity_map"]["topology_to_machine_component"]["camera_pan"] == "robot-joint-camera_pan"
    project = MachineProject.model_validate(plan["machine_project"])
    assert any(row.component_id == "robot-link-camera_link" for row in project.components)
    assert not [row for row in project.traceability_issues() if row.code == "invalid_ref"]
    assert plan["engineering_readiness"]["structured_robot_model_selected"] is True
    assert plan["engineering_readiness"]["motion_authorized"] if "motion_authorized" in plan["engineering_readiness"] else False is False


def test_multiple_robot_models_require_explicit_selection() -> None:
    sources = [
        {
            "source_id": "model-a",
            "artifact_kind": "urdf",
            "revision": "a",
            "content": URDF,
        },
        {
            "source_id": "model-b",
            "artifact_kind": "urdf",
            "revision": "b",
            "content": URDF.replace("camera_arm", "camera_arm_v2"),
        },
    ]

    unresolved = plan_complete_engineering_project(
        {
            "project_name": "ambiguous-arm",
            "goal": "Reconstruct the arm from two model revisions.",
            "available_parts": [{"name": "servo", "type": "smart_servo"}],
        },
        engineering_sources=sources,
        skip_vision=True,
    )
    assert unresolved["engineering_readiness"]["status"] == "blocked"
    assert any("Select one robot model source" in row for row in unresolved["missing_info"])

    selected = plan_complete_engineering_project(
        {
            "project_name": "selected-arm",
            "goal": "Reconstruct the arm using the selected revision.",
            "selected_robot_model_source_id": "model-b",
            "available_parts": [{"name": "servo", "type": "smart_servo"}],
        },
        engineering_sources=sources,
        skip_vision=True,
    )
    assert selected["source_adapter"]["selected_robot_model_source_id"] == "model-b"
    assert selected["robot_topology"]["metadata"]["source_model_id"] == "camera_arm_v2"
