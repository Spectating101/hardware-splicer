from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from hardware_splicer import HardwareCompileSpec, compile_hardware_bundle
from hardware_splicer.api import create_app
from hardware_splicer.jobs import JobStore


def _minimal_spec(use_3d_splicer: bool = False) -> HardwareCompileSpec:
    return HardwareCompileSpec.from_dict(
        {
            "project_name": "compiler_unit",
            "simulation_fidelity": "starter",
            "use_3d_splicer": use_3d_splicer,
            "machine": {
                "machine_name": "CompilerUnit",
                "boards": [
                    {
                        "board_id": "main_ctrl",
                        "pcb_outline_mm": [80, 50, 1.6],
                        "capabilities": {"pwm_channels": 2, "actuation_current_budget_a": 0.8},
                    }
                ],
            },
            "mechanism": {
                "project_name": "compiler_unit_mech",
                "pan_tilt": {"name": "pt", "pan_servo": "sg90", "tilt_servo": "sg90"},
            },
        }
    )


def test_compile_spec_rejects_bad_fidelity():
    with pytest.raises(ValueError, match="simulation_fidelity"):
        HardwareCompileSpec.from_dict({"machine": {}, "simulation_fidelity": "expensive"})


def test_compile_spec_resolves_json_relative_board_files(tmp_path):
    netlist = tmp_path / "controller.net"
    netlist.write_text("(export (version \"E\"))\n", encoding="utf-8")
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(
        json.dumps(
            {
                "project_name": "relative_files",
                "machine": {"boards": [{"board_id": "main_ctrl"}]},
                "board_design_files": {"main_ctrl": {"path": netlist.name, "kind": "netlist"}},
            }
        ),
        encoding="utf-8",
    )

    spec = HardwareCompileSpec.from_json_file(spec_file)

    assert spec.board_design_files["main_ctrl"]["path"] == str(netlist.resolve())


def test_compile_hardware_bundle_without_3d_service(tmp_path):
    result = compile_hardware_bundle(_minimal_spec(use_3d_splicer=False), out_dir=tmp_path)

    assert result.ok is True
    assert result.request_id
    assert Path(result.bundle_file).exists()
    assert Path(result.report_file).exists()
    assert Path(result.summary_file).exists()
    assert Path(result.manifest_file).exists()
    assert Path(result.metadata_file).exists()
    assert Path(result.artifacts["mechanical_authority"]).exists()
    assert Path(result.artifacts["robotics_actuation"]).exists()
    assert Path(result.artifacts["robotics_simulation"]).exists()
    assert Path(result.artifacts["robotics_platform_authority"]).exists()
    assert Path(result.artifacts["mechatronics_authority"]).exists()
    assert Path(result.artifacts["casefile"]).exists()
    assert Path(result.artifacts["project_log"]).exists()
    assert Path(result.artifacts["hardware_review"]).exists()
    assert result.mecha_bundle_dir
    assert (Path(result.mecha_bundle_dir) / "mecha_splicer.bundle.json").exists()
    assert result.mechanical_authority["schema_version"] == "hardware_splicer.mechanical_authority.v1"
    assert result.mechanical_authority["production_authorized"] is False
    assert result.robotics_actuation["schema_version"] == "hardware_splicer.robotics_actuation.v1"
    assert result.robotics_actuation["production_authorized"] is False
    assert result.robotics_simulation["schema_version"] == "hardware_splicer.robotics_simulation.v1"
    assert result.robotics_platform_authority["schema_version"] == "hardware_splicer.robotics_platform_authority.v1"
    assert result.robotics_platform_authority["production_authorized"] is False
    assert result.mechatronics_authority["schema_version"] == "hardware_splicer.mechatronics_authority.v1"
    assert result.mechatronics_authority["production_authorized"] is False

    bundle = json.loads(Path(result.bundle_file).read_text(encoding="utf-8"))
    assert bundle["schema"] == "hardware_splicer.bundle.v1"
    assert bundle["input"]["use_3d_splicer"] is False
    assert bundle["casefile"]["schema_version"] == "hardware_splicer.casefile.v1"
    assert bundle["project_log"]["schema_version"] == "hardware_splicer.project_log.v1"
    assert bundle["mechanical_authority"]["current_authority_level"] in {"reference_geometry", "measured_geometry", "fit_load_simulation"}
    assert bundle["robotics_actuation"]["actuation_profile"]["actuator_count"] == 2
    assert bundle["robotics_simulation"]["schema_version"] == "hardware_splicer.robotics_simulation.v1"
    assert bundle["robotics_platform_authority"]["schema_version"] == "hardware_splicer.robotics_platform_authority.v1"
    assert bundle["mechatronics_authority"]["current_authority_level"] in {"electrical_circuit_authority", "system_intake"}

    casefile = json.loads(Path(result.artifacts["casefile"]).read_text(encoding="utf-8"))
    assert casefile["schema_version"] == "hardware_splicer.casefile.v1"
    assert [row["source"] for row in casefile["inspiration_patterns"]] == ["CNX Software", "Hackaday.io", "Hackster.io"]
    assert casefile["bench_and_release"]["hardware_splicer_authority_level"] == result.mechatronics_authority["current_authority_level"]
    assert casefile["hardware_overview"]["actuators"]
    assert casefile["artifact_index"]["hardware_review"] == result.artifacts["hardware_review"]

    project_log = json.loads(Path(result.artifacts["project_log"]).read_text(encoding="utf-8"))
    assert project_log["schema_version"] == "hardware_splicer.project_log.v1"
    phases = {row["phase"] for row in project_log["events"]}
    assert {"intake", "circuit_engineering", "mechanical_generation", "robotics_actuation", "robotics_simulation", "packaging", "bench_release"} <= phases

    hardware_review = Path(result.artifacts["hardware_review"]).read_text(encoding="utf-8")
    assert "## Hardware Overview" in hardware_review
    assert "## Circuit Evaluation" in hardware_review
    assert "## Mechanical Evaluation" in hardware_review
    assert "## Issues and Resolutions" in hardware_review
    assert "## Final Observations" in hardware_review

    manifest = json.loads(Path(result.manifest_file).read_text(encoding="utf-8"))
    assert manifest["schema"] == "hardware_splicer.manifest.v1"
    assert manifest["request_id"] == result.request_id
    assert any(row["path"] == "hardware_splicer.bundle.json" for row in manifest["files"])
    assert any(row["path"] == "BUILD_METADATA.json" for row in manifest["files"])
    assert any(row["path"] == "CASEFILE.json" for row in manifest["files"])
    assert any(row["path"] == "PROJECT_LOG.json" for row in manifest["files"])
    assert any(row["path"] == "HARDWARE_REVIEW.md" for row in manifest["files"])
    assert any(row["path"] == "ROBOTICS_SIMULATION.json" for row in manifest["files"])
    assert any(row["path"] == "ROBOTICS_PLATFORM_AUTHORITY.json" for row in manifest["files"])

    metadata = json.loads(Path(result.metadata_file).read_text(encoding="utf-8"))
    assert metadata["schema"] == "hardware_splicer.build_metadata.v1"
    assert metadata["request_id"] == result.request_id
    assert metadata["runtime"]["ok"] is True
    assert metadata["mechanical_authority"]["schema_version"] == "hardware_splicer.mechanical_authority.v1"
    assert metadata["robotics_actuation"]["schema_version"] == "hardware_splicer.robotics_actuation.v1"
    assert metadata["robotics_simulation"]["schema_version"] == "hardware_splicer.robotics_simulation.v1"
    assert metadata["robotics_platform_authority"]["schema_version"] == "hardware_splicer.robotics_platform_authority.v1"
    assert metadata["mechatronics_authority"]["schema_version"] == "hardware_splicer.mechatronics_authority.v1"


def test_compile_hardware_bundle_rejects_missing_board_design_file(tmp_path):
    spec = HardwareCompileSpec.from_dict(
        {
            "project_name": "bad_file",
            "machine": {"boards": [{"board_id": "main_ctrl"}]},
            "board_design_files": {"main_ctrl": {"path": str(tmp_path / "missing.net"), "kind": "netlist"}},
            "run_mechanism_sim": False,
        }
    )

    with pytest.raises(ValueError, match="Board design file does not exist"):
        compile_hardware_bundle(spec, out_dir=tmp_path / "out")


def test_compiler_api_compile_without_3d_service(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    client = TestClient(create_app())
    payload = _minimal_spec(use_3d_splicer=False).to_dict()

    response = client.post(
        "/v1/compile",
        json={"spec": payload, "out_dir": "api_bundle", "request_id": "unit-api", "start_splicer": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["request_id"] == "unit-api"
    assert Path(data["bundle_file"]).exists()
    assert Path(data["manifest_file"]).exists()
    assert Path(data["metadata_file"]).exists()


def test_compiler_api_rejects_out_dir_outside_output_root(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    output_root = tmp_path / "allowed"
    outside = tmp_path / "outside"
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(output_root))
    monkeypatch.delenv("HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR", raising=False)
    client = TestClient(create_app())
    payload = _minimal_spec(use_3d_splicer=False).to_dict()

    response = client.post(
        "/v1/compile",
        json={"spec": payload, "out_dir": str(outside), "start_splicer": False},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]["error"]
    assert detail["type"] == "validation_error"
    assert "HARDWARE_SPLICER_OUTPUT_ROOT" in detail["message"]


def test_compiler_api_status_reports_runtime():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    response = client.get("/v1/status")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["app_roots"]["circuit_ai"]["exists"] is True


def test_compiler_api_validate_reports_spec_errors(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    payload = {
        "project_name": "validate_bad",
        "machine": {"boards": [{"board_id": "main_ctrl"}]},
        "board_design_files": {"main_ctrl": {"path": str(tmp_path / "missing.net"), "kind": "netlist"}},
        "run_mechanism_sim": False,
    }

    response = client.post("/v1/validate", json={"spec": payload})

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert any(issue["code"] == "board_design_file_missing" for issue in data["issues"])


def test_compiler_api_async_job_lifecycle(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path / "outputs"))
    monkeypatch.setenv("HARDWARE_SPLICER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("HARDWARE_SPLICER_JOB_WORKERS", "1")

    with TestClient(create_app()) as client:
        payload = _minimal_spec(use_3d_splicer=False).to_dict()
        response = client.post(
            "/v1/jobs",
            json={"spec": payload, "request_id": "async-unit", "out_dir": "async-unit", "start_splicer": False},
        )

        assert response.status_code in {200, 202}
        submitted = response.json()
        assert submitted["job_id"] == "async-unit"
        assert submitted["status"] in {"queued", "running", "succeeded"}

        deadline = time.monotonic() + 20
        job = {}
        while time.monotonic() < deadline:
            status_response = client.get("/v1/jobs/async-unit")
            assert status_response.status_code == 200
            job = status_response.json()
            if job["status"] == "succeeded":
                break
            time.sleep(0.1)

        assert job["status"] == "succeeded"

        result_response = client.get("/v1/jobs/async-unit/result")
        assert result_response.status_code == 200
        result = result_response.json()
        assert result["ok"] is True
        assert result["result"]["ok"] is True
        assert Path(result["result"]["manifest_file"]).exists()

        artifacts_response = client.get("/v1/jobs/async-unit/artifacts")
        assert artifacts_response.status_code == 200
        artifacts = artifacts_response.json()
        assert artifacts["schema"] == "hardware_splicer.manifest.v1"
        assert artifacts["request_id"] == "async-unit"

        bundle_response = client.get("/v1/jobs/async-unit/bundle")
        assert bundle_response.status_code == 200
        assert bundle_response.content.startswith(b"PK")
        assert "application/zip" in bundle_response.headers["content-type"]

        listed = client.get("/v1/jobs", params={"status": "succeeded"}).json()
        assert any(row["job_id"] == "async-unit" for row in listed["jobs"])


def test_compiler_api_async_jobs_are_idempotent_by_request_id(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path / "outputs"))
    monkeypatch.setenv("HARDWARE_SPLICER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("HARDWARE_SPLICER_JOB_WORKERS", "0")

    with TestClient(create_app()) as client:
        payload = _minimal_spec(use_3d_splicer=False).to_dict()
        first = client.post("/v1/jobs", json={"spec": payload, "request_id": "same-job", "start_splicer": False})
        second = client.post("/v1/jobs", json={"spec": payload, "request_id": "same-job", "start_splicer": False})

        assert first.status_code == 202
        assert second.status_code in {200, 202}
        assert first.json()["job_id"] == second.json()["job_id"] == "same-job"

        cancel = client.post("/v1/jobs/same-job/cancel")
        assert cancel.status_code == 200
        assert cancel.json()["ok"] is True
        assert cancel.json()["job"]["status"] == "cancelled"

        retry = client.post("/v1/jobs/same-job/retry")
        assert retry.status_code == 200
        assert retry.json()["ok"] is True
        assert retry.json()["job"]["status"] == "queued"


def test_compiler_api_async_submit_rejects_invalid_spec(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path / "outputs"))
    monkeypatch.setenv("HARDWARE_SPLICER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("HARDWARE_SPLICER_JOB_WORKERS", "0")

    with TestClient(create_app()) as client:
        payload = {
            "project_name": "bad_async",
            "machine": {"boards": [{"board_id": "main_ctrl"}]},
            "board_design_files": {"main_ctrl": {"path": str(tmp_path / "missing.net"), "kind": "netlist"}},
            "run_mechanism_sim": False,
        }
        response = client.post("/v1/jobs", json={"spec": payload, "request_id": "bad-async"})

        assert response.status_code == 422
        assert "Board design file does not exist" in response.json()["detail"]["error"]["message"]


def test_job_store_recovers_interrupted_running_jobs(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    spec = _minimal_spec(use_3d_splicer=False).to_dict()
    store.create_job(
        job_id="recover-me",
        request_id="recover-me",
        project_name="recover",
        output_dir=str(tmp_path / "out"),
        spec=spec,
        options={"start_splicer": False, "splicer_port": 0},
    )
    claimed = store.claim_next()
    assert claimed is not None
    assert claimed.status == "running"

    recovered = store.recover_interrupted_running()

    assert recovered == 1
    job = store.get_job("recover-me")
    assert job is not None
    assert job.status == "failed"
    assert job.error["type"] == "WorkerInterrupted"
