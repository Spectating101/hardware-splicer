from __future__ import annotations

from hardware_splicer.complete_engineering_planner import plan_complete_engineering_project
from hardware_splicer.engineering_artifact_projection import project_engineering_artifacts
from hardware_splicer.engineering_source_adapters import adapt_engineering_sources
from hardware_splicer.engineering_source_graph import EngineeringSourceGraph, build_engineering_source_graph
from hardware_splicer.machine_project import MachineProject, VerificationStatus


def _base_project_and_sources():
    sources = adapt_engineering_sources(
        [
            {
                "source_id": "firmware-build",
                "artifact_kind": "firmware_manifest",
                "manifest": {
                    "firmware_component_id": "main-controller",
                    "source_revision": "commit-123",
                    "toolchain": "platformio",
                    "toolchain_version": "6.1",
                    "build_command": "pio run",
                    "binary_hash": "sha256:binary",
                    "flash_command": "pio run -t upload",
                    "flash_result": "success",
                    "pin_map_hash": "sha256:pins",
                    "hardware_revision": "rev-b",
                },
            },
            {
                "source_id": "ros-contract",
                "artifact_kind": "ros_interface_manifest",
                "revision": "jazzy-r1",
                "manifest": {
                    "node_id": "rover-node",
                    "distribution": "jazzy",
                    "topics": [{"name": "/cmd_vel", "type": "geometry_msgs/msg/Twist"}],
                    "services": [{"name": "/stop", "type": "std_srvs/srv/Trigger"}],
                    "frames": ["base_link", "camera_link"],
                },
            },
            {
                "source_id": "rail-capture",
                "artifact_kind": "measurement",
                "capture_id": "scope-12",
                "instrument_id": "scope-a",
                "measurements": [
                    {
                        "subject_id": "power-system",
                        "predicate": "minimum_voltage_v",
                        "value": 4.92,
                        "units": "V",
                    }
                ],
            },
        ]
    )
    plan = plan_complete_engineering_project(
        {
            "project_name": "artifact-rover",
            "goal": "Build a differential drive rover.",
            "available_parts": [
                {"name": "drive motor", "type": "dc_motor", "quantity": 2},
                {"name": "camera", "type": "camera"},
            ],
        },
        skip_vision=True,
    )
    project = MachineProject.model_validate(plan["machine_project"])
    graph = build_engineering_source_graph(sources.sources)
    return project, graph, plan["engineering_identity_map"]


def test_structured_sources_project_into_machine_artifacts_and_evidence() -> None:
    project, graph, identity_map = _base_project_and_sources()

    projected = project_engineering_artifacts(
        project,
        source_graph=graph,
        identity_map=identity_map,
    )

    component_ids = {row.component_id for row in projected.components}
    artifact_ids = {row.artifact_id for row in projected.artifacts}
    evidence_ids = {row.evidence_id for row in projected.evidence}
    interface_ids = {row.interface_id for row in projected.interfaces}
    assert "source-firmware-main-controller" in component_ids
    assert "source-middleware-rover-node" in component_ids
    assert "artifact-firmware-source-firmware-build" in artifact_ids
    assert "artifact-firmware-binary-firmware-build" in artifact_ids
    assert "artifact-middleware-manifest-ros-contract" in artifact_ids
    assert "evidence-source-claim-claim-" not in evidence_ids
    assert any(row.startswith("evidence-source-claim-") for row in evidence_ids)
    assert "interface-middleware-contract-ros-contract" in interface_ids
    firmware_verification = next(
        row for row in projected.verifications
        if row.verification_id == "verification-firmware-lineage-firmware-build"
    )
    assert firmware_verification.status == VerificationStatus.PASSED
    assert firmware_verification.metadata["declared_manifest_does_not_authorize_flash"] is True
    measurement = next(
        row for row in projected.evidence
        if row.kind == "measurement"
    )
    assert measurement.authority.value == "measured"
    assert measurement.supports == ["power-system"]
    assert not [row for row in projected.traceability_issues() if row.code == "invalid_ref"]


def test_firmware_manifest_without_binary_or_flash_remains_blocked() -> None:
    bundle = adapt_engineering_sources(
        [
            {
                "source_id": "incomplete-firmware",
                "artifact_kind": "firmware_manifest",
                "manifest": {
                    "firmware_component_id": "controller",
                    "source_revision": "commit-abc",
                    "toolchain": "platformio",
                },
            }
        ]
    )
    plan = plan_complete_engineering_project(
        {
            "project_name": "incomplete-firmware-rover",
            "goal": "Build a rover.",
            "available_parts": [{"name": "motor", "type": "dc_motor", "quantity": 2}],
        },
        skip_vision=True,
    )
    project = project_engineering_artifacts(
        MachineProject.model_validate(plan["machine_project"]),
        source_graph=build_engineering_source_graph(bundle.sources),
        identity_map=plan["engineering_identity_map"],
    )

    verification = next(
        row for row in project.verifications
        if row.verification_id == "verification-firmware-lineage-incomplete-firmware"
    )
    assert verification.status == VerificationStatus.BLOCKED
    assert verification.evidence_ids == ["evidence-firmware-manifest-incomplete-firmware"]
