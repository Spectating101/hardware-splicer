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


def _capture(model_id: str, kind: str, filename: str, payload: bytes) -> dict:
    return {
        "schema_version": "hardware_splicer.vendor_model_capture.v1",
        "model_id": model_id,
        "expected_model_kind": kind,
        "recognized_expected_model_file_count": 1,
        "capture_status": "captured_hashed_unreviewed",
        "sha256": _sha(payload),
        "size_bytes": len(payload),
        "archive_type": "none",
        "filename": filename,
        "recognized_model_files": [
            {
                "path": filename,
                "model_kind": kind,
                "sha256": _sha(payload),
            }
        ],
        "modeled_evidence_only": True,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "authority_effect": "none",
        "physical_authority_granted": False,
    }


def _ready_fixture():
    txu = b"[IBIS Ver] 4.2\n[File Name] txu0304.ibs\n"
    dut = b"[IBIS Ver] 4.2\n[File Name] w25q128jwsiq.ibs\n"
    rtl = b"module W25Q128JW(); endmodule\n"
    manifests = {
        "txu0304-ibis-scem787": _capture("txu0304-ibis-scem787", "IBIS", "txu0304.ibs", txu),
        "w25q128jwsiq-ibis-da03-aag072": _capture(
            "w25q128jwsiq-ibis-da03-aag072", "IBIS", "w25q128jwsiq.ibs", dut
        ),
        "w25q128jw-q-verilog-da02-aag072": _capture(
            "w25q128jw-q-verilog-da02-aag072", "Verilog", "w25q128jw.v", rtl
        ),
    }
    payloads = {
        "txu0304-ibis-scem787": txu,
        "w25q128jwsiq-ibis-da03-aag072": dut,
        "w25q128jw-q-verilog-da02-aag072": rtl,
    }
    campaign = build_spi_virtual_model_campaign(manifests.values())
    assert campaign["status"] == "ready_for_model_execution"
    return campaign, manifests, payloads


def _nominal_inputs(manifests, payloads):
    return {
        "txu0304-ibis-scem787": {
            "outer_payload": payloads["txu0304-ibis-scem787"],
            "capture_manifest": manifests["txu0304-ibis-scem787"],
            "member_path": "txu0304.ibs",
        },
        "w25q128jwsiq-ibis-da03-aag072": {
            "outer_payload": payloads["w25q128jwsiq-ibis-da03-aag072"],
            "capture_manifest": manifests["w25q128jwsiq-ibis-da03-aag072"],
            "member_path": "w25q128jwsiq.ibs",
        },
    }


def _engine_argv(execution_id: str, *, extra_field: bool = False, exit_code: int = 0):
    required = sorted(required_checks_for_execution(execution_id))
    report = {
        "schema_version": ENGINE_REPORT_SCHEMA_VERSION,
        "execution_id": execution_id,
        "checks": [
            {"check_id": check_id, "status": "pass", "evidence": {"synthetic": True}}
            for check_id in required
        ],
        "metrics": {"synthetic_margin_v": 0.25},
    }
    if extra_field:
        report["physical_authority_granted"] = True
    code = (
        "import json,sys; "
        f"print(json.dumps({report!r}, sort_keys=True)); "
        f"sys.exit({int(exit_code)})"
    )
    return [sys.executable, "-c", code]


def test_runner_materializes_exact_models_and_accepts_audited_modeled_result() -> None:
    campaign, manifests, payloads = _ready_fixture()
    execution_id = "ibis-nominal-3v3-to-1v8"

    result = run_bound_spi_model_engine(
        campaign,
        execution_id=execution_id,
        engine_name="synthetic-test-engine",
        engine_version="0.0-test",
        argv=_engine_argv(execution_id),
        allowed_executables={sys.executable.split("/")[-1]},
        model_inputs=_nominal_inputs(manifests, payloads),
    )

    assert result["status"] == "accepted_modeled_result"
    assert result["audit"]["audit_pass"] is True
    assert result["process_exit_code"] == 0
    assert set(result["materializations"]) == {
        "txu0304-ibis-scem787",
        "w25q128jwsiq-ibis-da03-aag072",
    }
    assert all(row["member_sha256"].startswith("sha256:") for row in result["materializations"].values())
    assert result["network_isolation_asserted"] is False
    assert result["physical_correctness"] == "UNPROVEN"
    assert result["physical_authority_granted"] is False


def test_runner_rejects_tampered_captured_bytes_before_engine_execution() -> None:
    campaign, manifests, payloads = _ready_fixture()
    inputs = _nominal_inputs(manifests, payloads)
    inputs["txu0304-ibis-scem787"]["outer_payload"] = b"tampered"

    with pytest.raises(ValueError, match="outer payload SHA-256 mismatch"):
        run_bound_spi_model_engine(
            campaign,
            execution_id="ibis-nominal-3v3-to-1v8",
            engine_name="synthetic-test-engine",
            engine_version="0.0-test",
            argv=_engine_argv("ibis-nominal-3v3-to-1v8"),
            allowed_executables={sys.executable.split("/")[-1]},
            model_inputs=inputs,
        )


def test_runner_requires_exact_preregistered_model_set() -> None:
    campaign, manifests, payloads = _ready_fixture()
    inputs = _nominal_inputs(manifests, payloads)
    inputs.pop("w25q128jwsiq-ibis-da03-aag072")

    with pytest.raises(BoundEngineRunError, match="exactly match"):
        run_bound_spi_model_engine(
            campaign,
            execution_id="ibis-nominal-3v3-to-1v8",
            engine_name="synthetic-test-engine",
            engine_version="0.0-test",
            argv=_engine_argv("ibis-nominal-3v3-to-1v8"),
            allowed_executables={sys.executable.split("/")[-1]},
            model_inputs=inputs,
        )


def test_runner_rejects_unallowlisted_executable() -> None:
    campaign, manifests, payloads = _ready_fixture()

    with pytest.raises(BoundEngineRunError, match="not allowlisted"):
        run_bound_spi_model_engine(
            campaign,
            execution_id="ibis-nominal-3v3-to-1v8",
            engine_name="synthetic-test-engine",
            engine_version="0.0-test",
            argv=_engine_argv("ibis-nominal-3v3-to-1v8"),
            allowed_executables={"definitely-not-python"},
            model_inputs=_nominal_inputs(manifests, payloads),
        )


def test_engine_report_cannot_smuggle_authority_fields() -> None:
    campaign, manifests, payloads = _ready_fixture()

    with pytest.raises(BoundEngineRunError, match="unsupported fields"):
        run_bound_spi_model_engine(
            campaign,
            execution_id="ibis-nominal-3v3-to-1v8",
            engine_name="synthetic-test-engine",
            engine_version="0.0-test",
            argv=_engine_argv("ibis-nominal-3v3-to-1v8", extra_field=True),
            allowed_executables={sys.executable.split("/")[-1]},
            model_inputs=_nominal_inputs(manifests, payloads),
        )


def test_nonzero_engine_exit_is_sealed_then_rejected_by_contract() -> None:
    campaign, manifests, payloads = _ready_fixture()
    execution_id = "ibis-nominal-3v3-to-1v8"

    result = run_bound_spi_model_engine(
        campaign,
        execution_id=execution_id,
        engine_name="synthetic-test-engine",
        engine_version="0.0-test",
        argv=_engine_argv(execution_id, exit_code=7),
        allowed_executables={sys.executable.split("/")[-1]},
        model_inputs=_nominal_inputs(manifests, payloads),
    )

    assert result["process_exit_code"] == 7
    assert result["status"] == "rejected_contract"
    assert result["audit"]["checks"]["successful_process_exit"] is False
    assert result["audit"]["audit_pass"] is False
