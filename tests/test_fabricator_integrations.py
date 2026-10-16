from __future__ import annotations

import json
import subprocess
from pathlib import Path

import httpx

from hardware_splicer.fabrication_capability_registry import (
    FabricationCapabilityDescriptor,
    FabricationCapabilityRegistry,
)
from hardware_splicer.fabricator_benchmarks import assess_trace
from hardware_splicer.gcode_dry_run import GcodeDryRunAnalyzer, MachineEnvelope
from hardware_splicer.kicad_cli_operator import KicadCliOperator, KicadProjectRegistry
from hardware_splicer.mtconnect_observer import MtconnectObserver
from hardware_splicer.ngspice_operator import NgspiceCircuitRegistry, NgspiceOperator
from hardware_splicer.openpnp_simulation import OpenPnpJobRegistry, OpenPnpSimulationInspector
from hardware_splicer.physical_artifact import PhysicalArtifactRegistry
from hardware_splicer.physical_observation_store import PhysicalObservationStore


def test_capability_registry_matches_requirements_without_exposing_configuration():
    registry = FabricationCapabilityRegistry()
    registry.register(FabricationCapabilityDescriptor(
        operator_id="printer-a",
        kind="printer",
        display_name="Lab printer",
        capabilities=("additive_fabrication", "pla"),
        limits={"build_x_mm": 220, "build_y_mm": 220, "build_z_mm": 250},
    ))
    registry.register(FabricationCapabilityDescriptor(
        operator_id="sim-cnc",
        kind="cnc",
        display_name="CNC simulator",
        capabilities=("subtractive_fabrication",),
        limits={"build_x_mm": 500},
        simulated_only=True,
    ))
    matches = registry.match(
        required_capabilities=["additive_fabrication", "pla"],
        kind="printer",
        numeric_minimums={"build_x_mm": 200},
        allow_simulated=False,
    )
    assert [row["operator_id"] for row in matches] == ["printer-a"]
    assert all("endpoint" not in row and "credential" not in row for row in registry.list_public())


class FakeKicadRunner:
    def run(self, argv, *, cwd: Path, timeout_seconds: float):
        if "--output" in argv:
            out = Path(argv[argv.index("--output") + 1])
            if argv[1:4] == ["pcb", "export", "gerbers"]:
                out.mkdir(parents=True, exist_ok=True)
                (out / "board-F_Cu.gbr").write_text("G04 fake gerber*\n", encoding="utf-8")
            elif argv[1:4] == ["pcb", "export", "drill"]:
                out.mkdir(parents=True, exist_ok=True)
                (out / "board.drl").write_text("M48\n", encoding="utf-8")
            else:
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text("{}\n", encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")


def test_kicad_operator_runs_fixed_checks_and_manufacturing_exports(tmp_path):
    (tmp_path / "board.kicad_sch").write_text("(kicad_sch)\n", encoding="utf-8")
    (tmp_path / "board.kicad_pcb").write_text("(kicad_pcb)\n", encoding="utf-8")
    registry = KicadProjectRegistry()
    registry.register(
        project_id="logger",
        root=tmp_path,
        schematic="board.kicad_sch",
        board="board.kicad_pcb",
    )
    operator = KicadCliOperator(projects=registry, runner=FakeKicadRunner())
    verification = operator.verify("logger")
    assert verification["passed"] is True
    assert [row["operation"] for row in verification["checks"]] == ["erc", "drc"]
    assert verification["physical_correctness"] == "UNPROVEN"
    bundle = operator.export_manufacturing("logger")
    assert "board-F_Cu.gbr" in bundle["artifacts"]
    assert "board.drl" in bundle["artifacts"]
    assert "positions.csv" in bundle["artifacts"]
    assert "board.step" in bundle["artifacts"]


class FakeNgspiceRunner:
    def run(self, argv, *, cwd: Path, timeout_seconds: float):
        if "-o" in argv:
            Path(argv[argv.index("-o") + 1]).write_text("simulation complete\n", encoding="utf-8")
        if "-r" in argv:
            Path(argv[argv.index("-r") + 1]).write_bytes(b"raw")
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")


def test_ngspice_receipt_remains_model_evidence(tmp_path):
    (tmp_path / "logger.cir").write_text("V1 out 0 3.3\n.op\n.end\n", encoding="utf-8")
    circuits = NgspiceCircuitRegistry(tmp_path)
    circuits.register(circuit_id="power", path="logger.cir")
    receipt = NgspiceOperator(circuits=circuits, runner=FakeNgspiceRunner()).run("power", mode="raw")
    assert receipt["model_correctness"] == "TOOL_EXECUTED"
    assert receipt["physical_correctness"] == "UNPROVEN"
    assert set(receipt["artifacts"]) == {"simulation.log", "simulation.raw"}


def test_mtconnect_is_read_only_and_retains_exact_xml(tmp_path):
    xml = b'''<?xml version="1.0"?><MTConnectStreams><Header instanceId="9" nextSequence="42"/><Streams><DeviceStream><ComponentStream><Samples><Position dataItemId="x" sequence="41">12.5</Position></Samples></ComponentStream></DeviceStream></Streams></MTConnectStreams>'''

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path in {"/probe", "/current", "/sample"}
        return httpx.Response(200, headers={"content-type": "application/xml"}, content=xml)

    observations = PhysicalObservationStore(tmp_path / "observations")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    observer = MtconnectObserver(
        source_id="mill-telemetry",
        base_url="http://mtconnect.test",
        observations=observations,
        client=client,
    )
    value = observer.current()
    assert value["read_only"] is True
    assert value["physical_correctness"] == "UNPROVEN"
    assert value["summary"]["header"]["nextSequence"] == "42"
    assert value["summary"]["stream_value_count"] == 1
    retained = observations.read_bytes(value["observation"]["observation_id"])
    assert retained == xml
    client.close()


def test_gcode_dry_run_flags_hazards_and_envelope_violations():
    artifacts = PhysicalArtifactRegistry()
    artifacts.register(
        artifact_id="panel-job",
        kind="machine_job",
        generator="cam",
        content=b"G21\nG90\nG0 X0 Y0 Z0\nM3 S1000\nG1 X120 Y10 F500\nM5\n",
    )
    analyzer = GcodeDryRunAnalyzer(
        artifacts=artifacts,
        envelope=MachineEnvelope(0, 100, 0, 100, -10, 50, max_feed_mm_min=1000),
    )
    report = analyzer.analyze("panel-job")
    assert report["dry_run_only"] is True
    assert report["ready_for_live_execution"] is False
    assert report["hazardous_commands"][0]["code"] == "M3"
    assert report["envelope_violations"][0]["axis"] == "X"


def test_openpnp_job_is_packaged_for_simulation_without_live_execution(tmp_path):
    job = tmp_path / "demo.job.xml"
    board = tmp_path / "demo.board.xml"
    board.write_text("<openpnp-board><placements><placement id='R1'/></placements></openpnp-board>", encoding="utf-8")
    job.write_text("<openpnp-job><board-locations><board-location file='demo.board.xml'/></board-locations></openpnp-job>", encoding="utf-8")
    registry = OpenPnpJobRegistry()
    registry.register(job_id="demo", root=tmp_path, job_file="demo.job.xml")
    package = OpenPnpSimulationInspector(jobs=registry).inspect("demo")
    assert package["simulation_only"] is True
    assert package["live_machine_execution"] is False
    assert set(package["artifacts"]) == {"demo.board.xml", "demo.job.xml"}


def test_benchmark_rejects_false_physical_truth():
    records = [
        {"schema": "hardware_splicer.kicad_verification.v1"},
        {"schema": "hardware_splicer.ngspice_receipt.v1"},
        {"schema": "hardware_splicer.physical_dispatch_receipt.v1", "physical_correctness": "PROVEN"},
        {"schema": "hardware_splicer.serial_observation.v1", "physical_correctness": "UNPROVEN"},
        {"schema": "hardware_splicer.physical_evidence.v1", "kind": "electrical_measurement", "passed": False},
        {"schema": "hardware_splicer.physical_evidence.v1", "kind": "dimensional_measurement", "passed": True},
        {"schema": "hardware_splicer.physical_revision_proposal.v1", "needs_revision": True},
    ]
    assessment = assess_trace("B1_CLOSED_LOOP_LOGGER", records)
    assert assessment["passed"] is False
    assert assessment["false_persisted_truth"][0]["schema"] == "hardware_splicer.physical_dispatch_receipt.v1"
