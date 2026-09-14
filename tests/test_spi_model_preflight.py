import hashlib
import sys

import pytest

from hardware_splicer.spi_model_preflight import (
    ModelPreflightError,
    recommended_preflight,
    run_bound_model_preflight,
)


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _manifest(model_id: str, kind: str, filename: str, payload: bytes) -> dict:
    return {
        "schema_version": "hardware_splicer.vendor_model_capture.v1",
        "model_id": model_id,
        "expected_model_kind": kind,
        "capture_status": "captured_hashed_unreviewed",
        "sha256": _sha(payload),
        "size_bytes": len(payload),
        "archive_type": "none",
        "filename": filename,
        "recognized_model_files": [
            {"path": filename, "model_kind": kind, "sha256": _sha(payload)}
        ],
        "recognized_expected_model_file_count": 1,
        "modeled_evidence_only": True,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "authority_effect": "none",
        "physical_authority_granted": False,
    }


def test_recommended_preflight_separates_parser_compile_from_simulation() -> None:
    ibis = recommended_preflight("IBIS")
    verilog = recommended_preflight("Verilog")

    assert ibis["tool_name"] == "IBISCHK7"
    assert ibis["reference_version"] == "7.2.1"
    assert ibis["simulation_engine"] is False
    assert verilog["tool_name"] == "Icarus Verilog"
    assert verilog["reference_version"] == "13.0"
    assert verilog["simulation_engine"] is False


def test_bound_preflight_pass_is_not_model_execution_credit() -> None:
    payload = b"[IBIS Ver] 4.2\n[Component] TXU0304\n"
    manifest = _manifest("txu0304-ibis-scem787", "IBIS", "txu0304.ibs", payload)

    result = run_bound_model_preflight(
        outer_payload=payload,
        capture_manifest=manifest,
        member_path="txu0304.ibs",
        tool_name="synthetic-parser",
        tool_version="0-test",
        argv_template=[sys.executable, "-c", "import pathlib,sys; sys.exit(0 if pathlib.Path(sys.argv[1]).read_bytes() else 2)", "{model}"],
        allowed_executables={sys.executable.split("/")[-1]},
        expected_model_kind="IBIS",
    )

    assert result["status"] == "passed_preflight"
    assert result["preflight_pass"] is True
    assert result["eligible_for_model_execution_credit"] is False
    assert result["eligible_for_vendor_model_campaign_credit"] is False
    assert result["syntax_or_compile_preflight_only"] is True
    assert result["physical_correctness"] == "UNPROVEN"
    assert result["physical_authority_granted"] is False


def test_bound_preflight_nonzero_exit_fails_without_authority_change() -> None:
    payload = b"module W25Q128JW(); endmodule\n"
    manifest = _manifest("w25q128jw-q-verilog-da02-aag072", "Verilog", "w25q.v", payload)

    result = run_bound_model_preflight(
        outer_payload=payload,
        capture_manifest=manifest,
        member_path="w25q.v",
        tool_name="synthetic-compiler",
        tool_version="0-test",
        argv_template=[sys.executable, "-c", "import sys; sys.exit(7)", "{model}"],
        allowed_executables={sys.executable.split("/")[-1]},
        expected_model_kind="Verilog",
    )

    assert result["status"] == "failed_preflight"
    assert result["preflight_pass"] is False
    assert result["process_exit_code"] == 7
    assert result["eligible_for_vendor_model_campaign_credit"] is False
    assert result["physical_authority_granted"] is False


def test_preflight_rejects_wrong_capture_kind() -> None:
    payload = b"module W25Q128JW(); endmodule\n"
    manifest = _manifest("fixture", "Verilog", "model.v", payload)

    with pytest.raises(ModelPreflightError, match="model kind mismatch"):
        run_bound_model_preflight(
            outer_payload=payload,
            capture_manifest=manifest,
            member_path="model.v",
            tool_name="synthetic-parser",
            tool_version="0-test",
            argv_template=[sys.executable, "-c", "import sys; sys.exit(0)", "{model}"],
            allowed_executables={sys.executable.split("/")[-1]},
            expected_model_kind="IBIS",
        )


def test_preflight_rejects_unallowlisted_tool() -> None:
    payload = b"[IBIS Ver] 4.2\n[Component] X\n"
    manifest = _manifest("fixture", "IBIS", "model.ibs", payload)

    with pytest.raises(ModelPreflightError, match="not allowlisted"):
        run_bound_model_preflight(
            outer_payload=payload,
            capture_manifest=manifest,
            member_path="model.ibs",
            tool_name="synthetic-parser",
            tool_version="0-test",
            argv_template=[sys.executable, "-c", "import sys; sys.exit(0)", "{model}"],
            allowed_executables={"not-python"},
            expected_model_kind="IBIS",
        )
