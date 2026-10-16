from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.engineering_artifact_store import EngineeringArtifactStore
from hardware_splicer.fabrication_digital_thread import FabricationDigitalThread
from hardware_splicer.fabrication_handoff_bundle import FabricationHandoffBuilder, HandoffArtifact
from hardware_splicer.fabrication_operator import FabricationValidationError
from hardware_splicer.fabricator_digital_thread_manifest import fabricator_digital_thread_manifest
from hardware_splicer.mechanical_fabrication_pipeline import MechanicalFabricationPipeline
from hardware_splicer.motion_plan_dry_run import JointLimit, MotionPlanDryRun
from hardware_splicer.openocd_programmer import (
    OpenOcdProgrammerHandle,
    OpenOcdRunnerBackend,
    OpenOcdTargetRegistry,
)
from hardware_splicer.openscad_operator import OpenScadGeometryRegistry, OpenScadOperator
from hardware_splicer.opcua_observer import OpcUaMeasurementRegistry, OpcUaObserver
from hardware_splicer.pcb_fabrication_request import PcbFabricationRequestBuilder, PcbFabricationSpec
from hardware_splicer.physical_artifact import PhysicalArtifactRegistry
from hardware_splicer.physical_observation_store import PhysicalObservationStore
from hardware_splicer.physical_operator import PhysicalOperatorRegistry, programmer_descriptor
from hardware_splicer.product_api import create_product_app
from hardware_splicer.ros2_observer import Ros2GraphObserver
from hardware_splicer.slicer_operator import SlicerOperator, SlicerProfile
from hardware_splicer.slicer_registry import SlicerProfileRegistry


class FakeOpenScadRunner:
    def run(self, argv, *, cwd: Path, timeout_seconds: float):
        output = Path(argv[argv.index("-o") + 1])
        output.write_bytes(b"solid fake\nendsolid fake\n")
        return subprocess.CompletedProcess(argv, 0, stdout=b"rendered", stderr=b"")


class FakeSlicerRunner:
    name = "fake_slicer"
    version = "1.0"

    def slice(self, *, source_filename, geometry, profile):
        assert geometry.startswith(b"solid fake")
        return b"G21\nG90\nG1 X1 Y1 F300\n", {"estimated_seconds": 10}


def test_mechanical_pipeline_registers_exact_gcode_without_exposing_raw_profile(tmp_path):
    (tmp_path / "case.scad").write_text("cube([10,10,10]);\n", encoding="utf-8")
    geometries = OpenScadGeometryRegistry()
    geometries.register(geometry_id="case-v1", root=tmp_path, source="case.scad")
    cad = OpenScadOperator(geometries=geometries, runner=FakeOpenScadRunner(), version="test")
    profile = SlicerProfile(
        profile_id="pla-safe",
        printer_id="printer-a",
        filename="profile.ini",
        content=b"layer_height = 0.2\n",
        material="PLA",
    )
    artifacts = PhysicalArtifactRegistry()
    pipeline = MechanicalFabricationPipeline(
        cad=cad,
        slicer=SlicerOperator(FakeSlicerRunner()),
        profiles=SlicerProfileRegistry([profile]),
        artifacts=artifacts,
    )
    result = pipeline.prepare_print_artifact(
        geometry_id="case-v1",
        profile_id="pla-safe",
        artifact_id="case-v1-gcode",
    )
    assert result["artifact"]["kind"] == "gcode"
    assert result["fabrication_authorized"] is False
    assert result["physical_correctness"] == "UNPROVEN"
    assert artifacts.bytes("case-v1-gcode").startswith(b"G21")
    assert "content" not in pipeline.list_profiles()[0]


class FakeOpenOcdRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, argv, *, cwd: Path, timeout: int):
        self.calls.append((list(argv), cwd, timeout))
        assert (cwd / "firmware.elf").is_file()
        return subprocess.CompletedProcess(argv, 0, stdout=b"verified", stderr=b"")


def test_openocd_flash_uses_registered_target_and_does_not_reset_run(tmp_path):
    cfg = tmp_path / "board.cfg"
    cfg.write_text("# target config\n", encoding="utf-8")
    targets = OpenOcdTargetRegistry()
    targets.register(target_id="stm32-board", config_files=[cfg])
    runner = FakeOpenOcdRunner()
    backend = OpenOcdRunnerBackend(targets=targets, runner=runner)
    artifacts = PhysicalArtifactRegistry()
    firmware = artifacts.register(
        artifact_id="firmware-v1",
        kind="firmware",
        content=b"ELF-not-real",
        generator="compiler",
        metadata={"format": "elf"},
    )
    handle = OpenOcdProgrammerHandle(
        operator_id="openocd-a",
        target_id="stm32-board",
        artifacts=artifacts,
        backend=backend,
    )
    operators = PhysicalOperatorRegistry()
    operators.register(programmer_descriptor(operator_id="openocd-a", display_name="OpenOCD bench"), handle)
    stage = operators.plan(
        operator_id="openocd-a",
        project_id="p1",
        mission_id="m1",
        action="stage_firmware",
        payload={"artifact_id": "firmware-v1"},
    )
    handle.execute(stage)
    flash = artifacts.build_actuation_plan(
        operators=operators,
        operator_id="openocd-a",
        project_id="p1",
        mission_id="m1",
        action="flash",
        artifact_id="firmware-v1",
        bindings={"target_id": "stm32-board"},
    )
    receipt = handle.execute(flash)
    assert receipt["verified"] is True
    assert receipt["auto_execute"] is False and receipt["auto_reboot"] is False
    command = runner.calls[0][0][runner.calls[0][0].index("-c") + 1]
    assert command == "program firmware.elf verify exit"
    assert "reset" not in command
    assert firmware.sha256 == receipt["artifact_sha256"]


class FakeOpcUaBackend:
    def read_values(self, node_ids):
        return {node_id: index + 1.25 for index, node_id in enumerate(node_ids)}


def test_opcua_observation_is_read_only_and_retained(tmp_path):
    measurements = OpcUaMeasurementRegistry()
    measurements.register(measurement_id="spindle_temp", node_id="ns=2;s=Temp", unit="C")
    observations = PhysicalObservationStore(tmp_path / "obs")
    observer = OpcUaObserver(
        source_id="machine-a",
        measurements=measurements,
        backend=FakeOpcUaBackend(),
        observations=observations,
    )
    result = observer.read(["spindle_temp"])
    assert result["read_only"] is True
    assert result["physical_correctness"] == "UNPROVEN"
    retained = observations.read_bytes(result["observation"]["observation_id"])
    assert b"spindle_temp" in retained
    assert "node_id" not in measurements.list_public()[0]


class FakeRos2Runner:
    def __call__(self, argv, *, timeout):
        if argv[1:3] == ["node", "list"]:
            return subprocess.CompletedProcess(argv, 0, stdout=b"/camera\n/robot_state_publisher\n", stderr=b"")
        return subprocess.CompletedProcess(argv, 0, stdout=b"/joint_states [sensor_msgs/msg/JointState]\n", stderr=b"")


def test_ros2_graph_is_observation_only(tmp_path):
    observations = PhysicalObservationStore(tmp_path / "obs")
    observer = Ros2GraphObserver(source_id="cell-a", observations=observations, runner=FakeRos2Runner())
    result = observer.capture_graph()
    assert result["read_only"] is True
    assert result["graph"]["nodes"] == ["/camera", "/robot_state_publisher"]
    assert result["physical_correctness"] == "UNPROVEN"


def test_motion_plan_dry_run_blocks_limit_violation():
    artifacts = PhysicalArtifactRegistry()
    plan = {
        "joints": ["j1", "j2"],
        "points": [
            {"time_s": 0.0, "positions": {"j1": 0.0, "j2": 0.0}},
            {"time_s": 1.0, "positions": {"j1": 2.0, "j2": 0.25}},
        ],
    }
    artifacts.register(
        artifact_id="trajectory-v1",
        kind="motion_plan",
        content=json.dumps(plan).encode(),
        generator="planner",
    )
    analyzer = MotionPlanDryRun(
        artifacts=artifacts,
        joint_limits={
            "j1": JointLimit(-1.0, 1.0, 1.0),
            "j2": JointLimit(-1.0, 1.0, 1.0),
        },
    )
    result = analyzer.analyze("trajectory-v1")
    assert result["ready_for_live_execution"] is False
    assert any(item["type"] == "position_limit" for item in result["blockers"])


def test_engineering_artifact_store_detects_tampering_and_never_marks_executable(tmp_path):
    store = EngineeringArtifactStore(tmp_path / "artifacts")
    record = store.put(
        artifact_id="pcb-request-v1",
        kind="pcb_fab_request",
        content=b"zip-like-bytes",
        media_type="application/zip",
        producer="test",
    )
    assert record.executable is False and record.physical_correctness == "UNPROVEN"
    payload = tmp_path / "artifacts" / "pcb-request-v1" / "payload.bin"
    payload.write_bytes(b"tampered")
    with pytest.raises(FabricationValidationError, match="no longer matches"):
        store.describe("pcb-request-v1")


def test_handoff_bundle_is_deterministic_and_authority_neutral():
    builder = FabricationHandoffBuilder()
    kwargs = dict(
        project_id="p1",
        mission_id="m1",
        revision_id="r1",
        artifacts=[
            HandoffArtifact("03_firmware/app.bin", b"fw", "firmware", "compiler"),
            HandoffArtifact("05_validation/checks.json", b"{}", "validation", "hs"),
        ],
    )
    first = builder.build(**kwargs)
    second = builder.build(**kwargs)
    assert first.zip_bytes == second.zip_bytes
    assert first.sha256 == second.sha256
    assert first.manifest["fabrication_authorized"] is False
    assert first.manifest["physical_correctness"] == "UNPROVEN"


def test_pcb_request_requires_assembly_files_and_never_submits_order():
    builder = PcbFabricationRequestBuilder()
    spec = PcbFabricationSpec(5, 2, 1.6, 1.0, "ENIG", "green", "white", assembly_requested=True)
    with pytest.raises(FabricationValidationError, match="BOM"):
        builder.build(
            project_id="p1",
            revision_id="r1",
            spec=spec,
            gerbers={"top.gbr": b"gerber"},
            drill_files={"holes.drl": b"drill"},
        )
    result = builder.build(
        project_id="p1",
        revision_id="r1",
        spec=spec,
        gerbers={"top.gbr": b"gerber"},
        drill_files={"holes.drl": b"drill"},
        bom_csv=b"Refs,Value\nR1,1k\n",
        positions_csv=b"Ref,X,Y\nR1,1,2\n",
    )
    assert result["order_submitted"] is False
    assert result["manifest"]["vendor"] is None


def test_digital_thread_hash_chains_tool_activity_without_granting_truth():
    thread = FabricationDigitalThread(project_id="p1", mission_id="m1", revision_id="r1")
    thread.add_artifact(
        artifact_id="schematic",
        kind="schematic",
        sha256="1" * 64,
        producer="kicad",
    )
    thread.add_artifact(
        artifact_id="gerbers",
        kind="manufacturing_bundle",
        sha256="2" * 64,
        producer="kicad",
    )
    event = thread.record_activity(
        activity_id="export-gerbers",
        activity_type="eda_export",
        actor="hardware-splicer",
        inputs=["schematic"],
        outputs=["gerbers"],
        receipt={"tool": "kicad-cli", "exit_code": 0},
        evidence_class="deterministic_tool",
    )
    manifest = thread.manifest()
    assert event["previous_event_sha256"] is None
    assert manifest["head_event_sha256"] == event["event_sha256"]
    assert manifest["grants_physical_authority"] is False
    assert all(row["physical_correctness"] == "UNPROVEN" for row in manifest["artifacts"])


def test_canonical_digital_thread_routes_exist_but_fail_closed_without_runtime():
    app = create_product_app()
    client = TestClient(app)
    response = client.get("/v1/fabricator/digital/artifacts")
    assert response.status_code == 503
    manifest = fabricator_digital_thread_manifest(app)
    paths = {row["path"] for row in manifest["operations"]}
    assert "/v1/fabricator/digital/mechanics/print-artifacts" in paths
    assert "/v1/fabricator/digital/opcua/{source_id}/read" in paths
    assert manifest["authority_contract"]["projection_grants_physical_authority"] is False
