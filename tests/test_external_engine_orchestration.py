"""Executable adapter contract tests (simulated executables, no native engines installed).

All simulated output is explicitly distinguished from native SolidCraft/ato/tsci.
"""
import json
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from hardware_splicer.api import create_app
from hardware_splicer.product_api import create_product_app
from hardware_splicer.external_engine_orchestration import (
    EnginePlanError, SCHEMA, validate_plan, preview_engine_plan,
    run_external_engine_plan,
)

def plan(*tasks):
    return {"schema": SCHEMA, "id": "rover-e2e", "tasks": list(tasks)}

CAD = {"id": "envelope", "engine": "solidcraft", "operation": "run_script",
       "source": "cad/envelope.json"}
CHECK = {"id": "inspect", "engine": "freecad", "operation": "inspect_step",
         "source_task": "envelope"}
ATO = {"id": "board", "engine": "atopile", "operation": "build",
       "source": "eda/board.ato", "artifact_paths": ["eda/build/board.kicad_pcb"]}
TSCI = {"id": "tsx_board", "engine": "tscircuit", "operation": "build",
        "source": "tsx/index.tsx", "artifact_paths": ["tsx/dist/circuit.json"]}


def test_plan_supports_cross_engine_step_handoff():
    p = validate_plan(plan(CAD, CHECK))
    assert p["tasks"][1]["depends_on"] == ["envelope"]
    assert p["tasks"][1]["source"] is None
    assert p["tasks"][1]["source_task"] == "envelope"


@pytest.mark.parametrize("bad", [
    lambda p: p["tasks"][0].update({"source": "../escape.json"}),
    lambda p: p["tasks"][0].update({"operation": "execute_shell"}),
    lambda p: p["tasks"][0].update({"source": "/etc/passwd"}),
    lambda p: p["tasks"][0].update({"artifact_paths": ["../../leak.step"]}),
    lambda p: p["tasks"][0].update({"extra_shell": "rm -rf /"}),
    lambda p: p["tasks"][0].update({"engine": "unknown"}),
])
def test_reject_invalid_or_untrusted_actions(bad):
    p = plan(dict(CAD))
    bad(p)
    with pytest.raises(EnginePlanError):
        validate_plan(p)


def test_wrong_format_cannot_silently_route_ato_to_tscircuit():
    bad = dict(TSCI, source="eda/board.ato")
    with pytest.raises(EnginePlanError):
        validate_plan(plan(bad))


def test_execution_requires_explicit_operator_approval(tmp_path):
    with pytest.raises(EnginePlanError, match="opt-in"):
        run_external_engine_plan(plan(CAD), workspace=tmp_path,
                                 output_dir=tmp_path / "output", confirm_execute=False)


def test_native_engine_absence_is_reported_not_faked(monkeypatch):
    monkeypatch.setattr("hardware_splicer.external_engine_orchestration.shutil.which",
                        lambda x: None)
    result = preview_engine_plan(plan(CAD, CHECK, ATO, TSCI))
    assert all(x["status"] == "blocked_missing_external_engine" for x in result["tasks"])
    assert result["fabrication_authorized"] is False


def test_solidcraft_to_freecad_real_workflow_contract_with_mocked_executables(tmp_path, monkeypatch):
    workspace = tmp_path / "inputs"
    (workspace / "cad").mkdir(parents=True)
    (workspace / "cad/envelope.json").write_text(json.dumps({"commands": []}))
    monkeypatch.setattr("hardware_splicer.external_engine_orchestration.shutil.which",
                        lambda name: "/usr/bin/" + name)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        assert kwargs["cwd"] == str(workspace.resolve())
        if cmd[0].endswith("solidcraft-cli"):
            assert cmd[1:3] == ["run", str((workspace / "cad/envelope.json").resolve())]
            Path(cmd[cmd.index("--out") + 1]).write_text("ISO-10303-21;\nEND-ISO-10303-21;")
            Path(cmd[cmd.index("--json-out") + 1]).write_text('{"volume": 200}')
        elif cmd[0].endswith("FreeCADCmd"):
            script = Path(cmd[1]).read_text()
            assert "model.step" in script and "Part.Shape()" in script
            result_file = Path(cmd[1]).parent / "step_inspection.json"
            result_file.write_text(json.dumps({
                "shape_valid": True, "solid_count": 1,
                "volume_mm3": 200, "bbox_mm": [10, 5, 4]
            }))
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("hardware_splicer.external_engine_orchestration.subprocess.run", fake_run)
    out = tmp_path / "proof"
    report = run_external_engine_plan(plan(CAD, CHECK), workspace=workspace,
                                      output_dir=out, confirm_execute=True)
    assert len(calls) == 2
    assert report["completed"] == 2 and report["blocked"] == 0
    assert report["tasks"][1]["artifacts"][0]["path"] == "inspect/step_inspection.json"
    assert report["plan_sha256"].startswith("sha256:")
    assert not report["fabrication_authorized"]
    assert json.loads((out / "ENGINE_ORCHESTRATION_REPORT.json").read_text()) == report


def test_provider_failure_cascades_and_never_calls_freecad(tmp_path, monkeypatch):
    root = tmp_path / "source"
    (root / "cad").mkdir(parents=True)
    (root / "cad/envelope.json").write_text('{"commands":[]}')
    monkeypatch.setattr("hardware_splicer.external_engine_orchestration.shutil.which",
                        lambda name: "/fake/" + name)
    commands = []

    def fail(cmd, **kwargs):
        commands.append(cmd)
        return SimpleNamespace(returncode=1, stdout="", stderr="CAD kernel error")

    monkeypatch.setattr("hardware_splicer.external_engine_orchestration.subprocess.run", fail)
    report = run_external_engine_plan(plan(CAD, CHECK), workspace=root,
                                      output_dir=tmp_path / "results", confirm_execute=True)
    assert report["blocked"] == 2
    assert report["tasks"][0]["status"] == "blocked_tool_error"
    assert report["tasks"][1]["status"] == "blocked_dependency"
    assert len(commands) == 1


@pytest.mark.parametrize("item,expected", [
    (ATO, ["ato", "build"]),
    (TSCI, ["tsci", "build"]),
])
def test_electronics_providers_own_build_and_artifacts(tmp_path, monkeypatch, item, expected):
    root = tmp_path / "source"
    source = root / item["source"]
    source.parent.mkdir(parents=True)
    source.write_text("synthetic source for orchestration tests")
    monkeypatch.setattr("hardware_splicer.external_engine_orchestration.shutil.which",
                        lambda x: "/bin/" + x)
    def fake(cmd, **kwargs):
        assert Path(cmd[0]).name == expected[0] and cmd[1:] == expected[1:]
        output = root / item["artifact_paths"][0]
        output.parent.mkdir(parents=True, exist_ok=True)
        if item["engine"] == "atopile":
            output.write_text("(kicad_pcb)")
        else:
            example = Path(__file__).parent / "fixtures" / "upstream_circuit_json.json"
            output.write_bytes(example.read_bytes())
        return SimpleNamespace(returncode=0, stdout="exported", stderr="")
    monkeypatch.setattr("hardware_splicer.external_engine_orchestration.subprocess.run", fake)
    report = run_external_engine_plan(plan(item), workspace=root,
                                      output_dir=tmp_path / "report", confirm_execute=True)
    assert report["completed"] == 1
    assert report["tasks"][0]["artifacts"][0]["sha256"].startswith("sha256:")
    assert report["source_evidence_authenticated"] is False
    if item["engine"] == "tscircuit":
        projected = report["tasks"][0]["canonical_electrical_interchange"]
        assert projected["canonical_component_count"] >= 3
        assert projected["canonical_net_count"] >= 1
        assert not projected["fabrication_authorized"]


def test_zero_output_never_promotes_success(tmp_path, monkeypatch):
    root = tmp_path / "source"
    source = root / ATO["source"]
    source.parent.mkdir(parents=True)
    source.write_text("test")
    monkeypatch.setattr("hardware_splicer.external_engine_orchestration.shutil.which",
                        lambda x: "/bin/" + x)
    monkeypatch.setattr("hardware_splicer.external_engine_orchestration.subprocess.run",
                        lambda *a, **kw: SimpleNamespace(returncode=0, stdout="ok", stderr=""))
    result = run_external_engine_plan(plan(ATO), workspace=root,
                                      output_dir=tmp_path / "report", confirm_execute=True)
    assert result["completed"] == 0
    assert result["tasks"][0]["status"] == "blocked_missing_or_invalid_output"


def test_api_discovery_preview_only_no_execution_endpoint():
    for app in (create_app(), create_product_app()):
        client = TestClient(app)
        got = client.get("/v1/external-engines")
        assert got.status_code == 200, got.text
        assert {p["id"] for p in got.json()["engines"]} == {
            "solidcraft", "freecad", "atopile", "tscircuit"}
        assert all("executable" not in p for p in got.json()["engines"])
        preview = client.post("/v1/external-engines/preview", json=plan(CAD, CHECK))
        assert preview.status_code == 200, preview.text
        assert not preview.json()["preview"]["execution_authorized"]
        assert client.post("/v1/external-engines/execute", json=plan(CAD)).status_code == 404
        assert client.post("/v1/external-engines/preview",
                           json=plan(dict(CAD, operation="arbitrary"))).status_code == 422

def test_external_specialist_results_feed_real_device_work_package_without_authority():
    from hardware_splicer.real_device_work_package import compile_work_package
    case = {"id": "rover", "device": "Salvaged drive rover", "kind": "new_build",
            "deliverables": ["CAD and PCB"], "acceptance": ["bench test"]}
    review = {"operator_casefile": {
        "build_or_repair_sequence": ["Inspect donor motors"],
        "critical_technical_unknowns": ["Unknown winding current"],
        "compatible_parts_or_requirements": ["Power controller"],
    }}
    third_party = {
        "schema": "hardware_splicer.external_engine_execution.v1",
        "plan_id": "rover-cad",
        "plan_sha256": "sha256:" + "0" * 64,
        "tasks": [
            {"id": "cad", "engine": "solidcraft",
             "status": "tool_passed_artifact_observed",
             "artifacts": [{"sha256": "sha256:" + "1"*64}]},
            {"id": "pcb", "engine": "atopile",
             "status": "blocked_missing_external_engine", "artifacts": []},
        ],
        "fabrication_authorized": False, "release_authorized": False,
    }
    package = compile_work_package(case, review, external_engine_execution=third_party)
    assert package["engineering_readiness"] == "blocked"
    assert package["external_engine_execution"]["status"] == "external_outputs_unverified_for_physical_readiness"
    assert sum("external_task_id" in row for row in package["work_steps"]) == 2
    assert any("specialist CAD/EDA" in gate["criterion"] for gate in package["acceptance_gates"])
    forged = dict(third_party, release_authorized=True)
    with pytest.raises(ValueError, match="authority"):
        compile_work_package(case, review, external_engine_execution=forged)

def test_preexisting_native_output_is_not_proof_of_current_build(tmp_path, monkeypatch):
    source = tmp_path / "source"
    entry = source / "eda" / "board.ato"
    entry.parent.mkdir(parents=True)
    entry.write_text("test")
    old = source / "eda" / "build" / "board.kicad_pcb"
    old.parent.mkdir(parents=True)
    old.write_text("(kicad_pcb old result)")
    monkeypatch.setattr("hardware_splicer.external_engine_orchestration.shutil.which",
                        lambda name: "/usr/bin/" + name)
    monkeypatch.setattr("hardware_splicer.external_engine_orchestration.subprocess.run",
                        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="success", stderr=""))
    result = run_external_engine_plan(plan(ATO), workspace=source, output_dir=tmp_path / "results",
                                      confirm_execute=True)
    assert result["completed"] == 0
    assert result["tasks"][0]["status"] == "blocked_stale_project_artifact"
    assert not result["fabrication_authorized"]


def test_symlinked_project_input_denied_before_any_tool_launch(tmp_path, monkeypatch):
    source = tmp_path / "source"
    (source / "cad").mkdir(parents=True)
    (source / "cad" / "original.json").write_text('{"commands":[]}')
    (source / "cad" / "envelope.json").symlink_to("original.json")
    with pytest.raises(EnginePlanError, match="symlink"):
        run_external_engine_plan(plan(CAD), workspace=source, output_dir=tmp_path / "results",
                                 confirm_execute=True)


def test_path_symlink_output_cannot_be_used_to_claim_compilation(tmp_path, monkeypatch):
    root = tmp_path / "source"
    source = root / ATO["source"]
    source.parent.mkdir(parents=True)
    source.write_text("test")
    (root / "eda" / "build").symlink_to(source.parent, target_is_directory=True)
    monkeypatch.setattr("hardware_splicer.external_engine_orchestration.shutil.which",
                        lambda name: "/bin/" + name)
    with pytest.raises(EnginePlanError, match="symlink"):
        run_external_engine_plan(plan(ATO), workspace=root, output_dir=tmp_path / "out",
                                 confirm_execute=True)

def test_invalid_tscircuit_json_is_not_accepted_as_electronics_proof(tmp_path, monkeypatch):
    source = tmp_path / "source"
    entry = source / TSCI["source"]
    entry.parent.mkdir(parents=True)
    entry.write_text("// placeholder")
    monkeypatch.setattr("hardware_splicer.external_engine_orchestration.shutil.which",
                        lambda name: "/usr/bin/" + name)
    def fake(cmd, **kw):
        artifact = source / TSCI["artifact_paths"][0]
        artifact.parent.mkdir(parents=True)
        artifact.write_text("[]")
        return SimpleNamespace(returncode=0, stdout="built", stderr="")
    monkeypatch.setattr("hardware_splicer.external_engine_orchestration.subprocess.run", fake)
    report = run_external_engine_plan(plan(TSCI), workspace=source,
                                      output_dir=tmp_path / "run", confirm_execute=True)
    assert report["blocked"] == 1
    assert report["tasks"][0]["status"] == "blocked_circuit_json_interchange"
    assert not report["release_authorized"]


def test_circuit_json_projection_preserves_review_only_identity():
    from hardware_splicer.external_engine_electrical_truth import inspect_native_circuit_json
    doc = Path(__file__).parent / "fixtures" / "upstream_circuit_json.json"
    result = inspect_native_circuit_json(doc, project_id="test-independent-ingestion")
    assert result["canonical_component_count"] == 3
    assert result["canonical_net_count"] == 3
    assert result["source_sha256"].startswith("sha256:")
    assert not result["fabrication_authorized"]

def test_freecad_invalid_shape_is_blocked_even_if_cli_exits_zero(tmp_path, monkeypatch):
    workspace = tmp_path / "inputs"
    (workspace / "part.step").write_bytes(b"ISO-10303-21;\\nEND-ISO-10303-21;")
    job = {"id": "geometry", "engine": "freecad", "operation": "inspect_step",
           "source": "part.step"}
    monkeypatch.setattr("hardware_splicer.external_engine_orchestration.shutil.which",
                        lambda name: "/bin/" + name)
    def fake_run(command, **kwargs):
        worker = Path(command[1])
        (worker.parent / "step_inspection.json").write_text(json.dumps({
            "shape_valid": False, "solid_count": 1, "volume_mm3": 2,
            "bbox_mm": [1, 1, 2]
        }))
        return SimpleNamespace(returncode=0, stdout="run okay", stderr="")
    monkeypatch.setattr("hardware_splicer.external_engine_orchestration.subprocess.run", fake_run)
    report = run_external_engine_plan(plan(job), workspace=workspace,
                                      output_dir=tmp_path / "out", confirm_execute=True)
    assert report["tasks"][0]["status"] == "blocked_invalid_geometry"
    assert report["blocked"] == 1 and report["completed"] == 0
    assert not report["release_authorized"]
