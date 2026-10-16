from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from hardware_splicer.engineering_artifact_store import EngineeringArtifactStore
from hardware_splicer.fabricator_digital_thread_workbench import FabricatorDigitalThreadWorkbench
from hardware_splicer.freecad_export_operator import FreeCadExportOperator, FreeCadModelRegistry
from hardware_splicer.kicad_cli_operator import KicadProjectRegistry
from hardware_splicer.kicad_fabrication_pipeline import KicadFabricationPipeline
from hardware_splicer.pcb_fabrication_request import PcbFabricationSpec
from hardware_splicer.product_api import create_product_app
from hardware_splicer.stored_handoff_service import StoredHandoffService


class FakeFreeCadRunner:
    def run(self, argv, *, cwd: Path, timeout_seconds: float):
        script = Path(argv[1])
        output = Path(argv[-2])
        assert "App.openDocument" in script.read_text(encoding="utf-8")
        output.write_bytes(b"ISO-10303-21; fake STEP")
        return subprocess.CompletedProcess(argv, 0, stdout=b"ok", stderr=b"")


def test_freecad_export_stores_non_executable_geometry_without_path_leak(tmp_path):
    source = tmp_path / "bracket.FCStd"
    source.write_bytes(b"fake-fcstd")
    models = FreeCadModelRegistry()
    models.register(model_id="bracket-v1", source=source)
    store = EngineeringArtifactStore(tmp_path / "artifacts")
    operator = FreeCadExportOperator(
        models=models,
        artifacts=store,
        runner=FakeFreeCadRunner(),
        version="test",
    )
    result = operator.export(model_id="bracket-v1", output_format="step", artifact_id="bracket-step-v1")
    artifact = result["artifact"]
    assert artifact["kind"] == "geometry"
    assert artifact["executable"] is False
    assert artifact["physical_correctness"] == "UNPROVEN"
    assert "path" not in artifact and "source" not in artifact
    assert store.bytes("bracket-step-v1").startswith(b"ISO-10303")


class FakeKicadFabricationRunner:
    def run(self, argv, *, cwd: Path, timeout_seconds: float):
        if argv[1:4] == ["pcb", "export", "gerbers"]:
            out = Path(argv[argv.index("--output") + 1])
            out.mkdir(parents=True, exist_ok=True)
            (out / "board-F_Cu.gbr").write_bytes(b"gerber")
        elif argv[1:4] == ["pcb", "export", "drill"]:
            out = Path(argv[argv.index("--output") + 1])
            out.mkdir(parents=True, exist_ok=True)
            (out / "board.drl").write_bytes(b"drill")
        elif argv[1:4] == ["pcb", "export", "pos"]:
            Path(argv[argv.index("--output") + 1]).write_bytes(b"Ref,X,Y\nR1,1,2\n")
        elif argv[1:4] == ["sch", "export", "bom"]:
            Path(argv[argv.index("--output") + 1]).write_bytes(b"Refs,Value\nR1,1k\n")
        return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")


def test_kicad_pipeline_stores_vendor_neutral_pcb_request(tmp_path):
    (tmp_path / "board.kicad_pcb").write_text("(kicad_pcb)\n", encoding="utf-8")
    (tmp_path / "board.kicad_sch").write_text("(kicad_sch)\n", encoding="utf-8")
    projects = KicadProjectRegistry()
    projects.register(
        project_id="logger",
        root=tmp_path,
        board="board.kicad_pcb",
        schematic="board.kicad_sch",
    )
    store = EngineeringArtifactStore(tmp_path / "artifacts")
    pipeline = KicadFabricationPipeline(
        projects=projects,
        artifacts=store,
        runner=FakeKicadFabricationRunner(),
    )
    result = pipeline.prepare_request(
        project_id="logger",
        revision_id="r1",
        request_artifact_id="pcb-request-r1",
        spec=PcbFabricationSpec(3, 2, 1.6, 1.0, "ENIG", "green", "white", True),
    )
    assert result["vendor_selected"] is False
    assert result["order_submitted"] is False
    assert result["artifact"]["kind"] == "pcb_fab_request"
    assert result["artifact"]["executable"] is False
    assert store.bytes("pcb-request-r1").startswith(b"PK")


def test_stored_handoff_composes_existing_artifacts_without_returning_bytes(tmp_path):
    store = EngineeringArtifactStore(tmp_path / "artifacts")
    store.put(
        artifact_id="geom",
        kind="geometry",
        content=b"mesh",
        media_type="model/stl",
        producer="cad",
    )
    store.put(
        artifact_id="pcb",
        kind="pcb_fab_request",
        content=b"package",
        media_type="application/zip",
        producer="eda",
    )
    result = StoredHandoffService(artifacts=store).build(
        project_id="p1",
        mission_id="m1",
        revision_id="r1",
        source_artifact_ids=["geom", "pcb"],
        output_artifact_id="handoff-r1",
    )
    assert result["artifact"]["kind"] == "handoff_bundle"
    assert result["grants_physical_authority"] is False
    assert "content" not in result["artifact"] and "bytes" not in result["artifact"]
    assert store.bytes("handoff-r1").startswith(b"PK")


def test_configured_digital_api_lists_artifacts_without_payload_bytes(tmp_path):
    store = EngineeringArtifactStore(tmp_path / "artifacts")
    store.put(
        artifact_id="doc",
        kind="inspection_document",
        content=b"secret-ish raw bytes",
        media_type="text/plain",
        producer="test",
    )
    workbench = FabricatorDigitalThreadWorkbench(artifacts=store)
    client = TestClient(create_product_app(fabricator_digital_thread_workbench=workbench))
    response = client.get("/v1/fabricator/digital/artifacts")
    assert response.status_code == 200
    artifact = response.json()["artifacts"][0]
    assert artifact["artifact_id"] == "doc"
    assert "content" not in artifact and "payload" not in artifact
    missing = client.get("/v1/fabricator/digital/freecad/models")
    assert missing.status_code == 422
