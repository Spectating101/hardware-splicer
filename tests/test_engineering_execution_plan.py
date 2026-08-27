from __future__ import annotations

from hardware_splicer.engineering_execution_plan import build_engineering_execution_plan
from hardware_splicer.engineering_source_graph import build_engineering_source_graph


def test_execution_plan_compiles_repository_firmware_ros_and_release_checks() -> None:
    graph = build_engineering_source_graph(
        [
            {
                "source_id": "repo",
                "source_type": "repository",
                "revision": "abc",
                "content_hash": "sha256:repo",
                "claims": [],
            },
            {
                "source_id": "firmware",
                "source_type": "repository",
                "revision": "def",
                "content_hash": "sha256:fw",
                "claims": [],
                "metadata": {
                    "artifact_kind": "firmware_manifest",
                    "firmware_manifest": {
                        "workspace": "firmware",
                        "toolchain": "platformio",
                        "board_profile": "esp32dev",
                    },
                },
            },
            {
                "source_id": "ros",
                "source_type": "manual",
                "revision": "jazzy-r1",
                "content_hash": "sha256:ros",
                "claims": [],
                "metadata": {
                    "artifact_kind": "ros_interface_manifest",
                    "ros_interface_manifest": {"workspace": "ros_ws"},
                },
            },
        ]
    )
    plan = build_engineering_execution_plan(
        {
            "machine_project": {"project_id": "execution-plan"},
            "normalized_intake": {
                "fabrication_artifacts": [
                    {"artifact_id": "schematic", "path": "electrical/main.kicad_sch"},
                    {"artifact_id": "board", "path": "electrical/main.kicad_pcb"},
                    {"artifact_id": "spice", "path": "electrical/power.cir"},
                ]
            },
        },
        source_graph=graph,
    )

    operations = [row.operation.value for row in plan.checks]
    assert "python_compile" in operations
    assert "pytest" in operations
    assert "platformio_build" in operations
    assert "colcon_build" in operations
    assert "colcon_test" in operations
    assert "ros2_doctor" in operations
    assert "kicad_erc" in operations
    assert "kicad_drc" in operations
    assert "ngspice" in operations
    assert operations.count("artifact_hash") == 3
    assert all(row.execute is False for row in plan.checks)
    assert plan.metadata["automatic_execution"] is False
    assert plan.metadata["flash_authorized"] is False
    assert not ({row.operation.value for row in plan.checks} & set(plan.prohibited_operations))


def test_remote_urdf_becomes_preparation_work_not_execution() -> None:
    graph = build_engineering_source_graph(
        [
            {
                "source_id": "remote-urdf",
                "source_type": "cad",
                "uri": "package://robot/model.urdf",
                "revision": "r1",
                "content_hash": "sha256:model",
                "claims": [],
                "metadata": {"artifact_kind": "urdf"},
            }
        ]
    )

    plan = build_engineering_execution_plan(
        {"machine_project": {"project_id": "remote-model"}},
        source_graph=graph,
    )

    assert not [row for row in plan.checks if row.operation.value == "urdf_check"]
    assert plan.unresolved == [
        {
            "source_id": "remote-urdf",
            "operation": "urdf_check",
            "reason": "URDF source is not available as a local workspace path.",
        }
    ]


def test_duplicate_release_artifacts_do_not_duplicate_execution_checks() -> None:
    graph = build_engineering_source_graph([])
    artifact = {"artifact_id": "board", "path": "board.kicad_pcb"}
    plan = build_engineering_execution_plan(
        {
            "machine_project": {"project_id": "dedup"},
            "normalized_intake": {"fabrication_artifacts": [artifact]},
            "fabrication_artifacts": [artifact],
        },
        source_graph=graph,
    )

    assert len([row for row in plan.checks if row.operation.value == "artifact_hash"]) == 1
    assert len([row for row in plan.checks if row.operation.value == "kicad_drc"]) == 1
