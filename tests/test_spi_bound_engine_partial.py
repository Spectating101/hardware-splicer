import hashlib
import json
import sys

import pytest

from hardware_splicer.spi_bound_engine_runner import (
    ENGINE_REPORT_SCHEMA_VERSION,
    BoundEngineRunError,
    run_bound_spi_model_engine,
)
from hardware_splicer.spi_model_execution_contract import required_checks_for_execution
from hardware_splicer.spi_virtual_model_campaign import build_spi_virtual_model_campaign


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _capture(model_id: str, filename: str, payload: bytes) -> dict:
    return {
        "schema_version": "hardware_splicer.vendor_model_capture.v1",
        "model_id": model_id,
        "expected_model_kind": "IBIS",
        "recognized_expected_model_file_count": 1,
        "capture_status": "captured_hashed_unreviewed",
        "sha256": _sha(payload),
        "size_bytes": len(payload),
        "archive_type": "none",
        "filename": filename,
        "recognized_model_files": [
            {"path": filename, "model_kind": "IBIS", "sha256": _sha(payload)}
        ],
        "modeled_evidence_only": True,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "authority_effect": "none",
        "physical_authority_granted": False,
    }


def _engine_argv(execution_id: str) -> list[str]:
    report = {
        "schema_version": ENGINE_REPORT_SCHEMA_VERSION,
        "execution_id": execution_id,
        "checks": [
            {"check_id": check_id, "status": "pass", "evidence": {"synthetic": True}}
            for check_id in sorted(required_checks_for_execution(execution_id))
        ],
        "metrics": {"synthetic_metric": 1.0},
    }
    return [
        sys.executable,
        "-c",
        "import json; print(json.dumps(%r, sort_keys=True))" % report,
    ]


def test_runner_executes_ready_txu_only_case_in_partial_campaign() -> None:
    payload = b"[IBIS Ver] 4.2\n[File Name] txu0304.ibs\n"
    manifest = _capture("txu0304-ibis-scem787", "txu0304.ibs", payload)
    campaign = build_spi_virtual_model_campaign([manifest])
    execution_id = "ibis-dut-rail-absent"

    result = run_bound_spi_model_engine(
        campaign,
        execution_id=execution_id,
        engine_name="synthetic-test-engine",
        engine_version="0-test",
        argv=_engine_argv(execution_id),
        allowed_executables={sys.executable.split("/")[-1]},
        model_inputs={
            "txu0304-ibis-scem787": {
                "outer_payload": payload,
                "capture_manifest": manifest,
                "member_path": "txu0304.ibs",
            }
        },
    )

    assert campaign["status"] == "partial_model_execution_ready"
    assert result["campaign_status"] == "partial_model_execution_ready"
    assert result["execution_ready"] is True
    assert result["status"] == "accepted_modeled_result"
    assert result["audit"]["audit_pass"] is True
    assert result["physical_correctness"] == "UNPROVEN"
    assert result["physical_authority_granted"] is False


def test_runner_rejects_nonready_case_in_same_partial_campaign() -> None:
    payload = b"[IBIS Ver] 4.2\n[File Name] txu0304.ibs\n"
    manifest = _capture("txu0304-ibis-scem787", "txu0304.ibs", payload)
    campaign = build_spi_virtual_model_campaign([manifest])

    with pytest.raises(BoundEngineRunError, match="execution is not ready"):
        run_bound_spi_model_engine(
            campaign,
            execution_id="ibis-nominal-3v3-to-1v8",
            engine_name="synthetic-test-engine",
            engine_version="0-test",
            argv=_engine_argv("ibis-nominal-3v3-to-1v8"),
            allowed_executables={sys.executable.split("/")[-1]},
            model_inputs={
                "txu0304-ibis-scem787": {
                    "outer_payload": payload,
                    "capture_manifest": manifest,
                    "member_path": "txu0304.ibs",
                }
            },
        )
