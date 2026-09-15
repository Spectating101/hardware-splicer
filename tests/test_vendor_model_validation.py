import hashlib
from types import SimpleNamespace

from hardware_splicer import vendor_model_validation as validation


def _capture(model_id: str, kind: str, member_path: str, payload: bytes) -> dict:
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    return {
        "schema_version": "hardware_splicer.vendor_model_capture.v1",
        "model_id": model_id,
        "expected_model_kind": kind,
        "capture_status": "captured_hashed_unreviewed",
        "recognized_model_files": [
            {"path": member_path, "model_kind": kind, "sha256": digest}
        ],
        "recognized_expected_model_file_count": 1,
        "modeled_evidence_only": True,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
    }


def test_ibis_binding_mismatch_rejects_before_tool_lookup(monkeypatch) -> None:
    payload = b"[IBIS Ver] 4.2\n[Component] X\n"
    capture = _capture("ibis", "IBIS", "x.ibs", payload)
    looked_up = []
    monkeypatch.setattr(validation.shutil, "which", lambda executable: looked_up.append(executable))

    result = validation.validate_ibis_model_bytes(
        payload + b"changed", capture, member_path="x.ibs"
    )

    assert result["status"] == "rejected_capture_binding"
    assert result["binding_error"] == "member_sha256_mismatch"
    assert looked_up == []
    assert result["physical_authority_granted"] is False


def test_ibis_missing_parser_is_clean_blocker(monkeypatch) -> None:
    payload = b"[IBIS Ver] 4.2\n[Component] X\n"
    capture = _capture("ibis", "IBIS", "x.ibs", payload)
    monkeypatch.setattr(validation.shutil, "which", lambda executable: None)

    result = validation.validate_ibis_model_bytes(payload, capture, member_path="x.ibs")

    assert result["status"] == "tool_unavailable"
    assert result["validation_pass"] is None
    assert result["measured_evidence_present"] is False


def test_ibis_parser_success_is_only_syntax_validation(monkeypatch) -> None:
    payload = b"[IBIS Ver] 4.2\n[Component] X\n"
    capture = _capture("ibis", "IBIS", "x.ibs", payload)
    monkeypatch.setattr(validation.shutil, "which", lambda executable: "/usr/bin/ibischk")
    monkeypatch.setattr(validation, "executable_version", lambda *args, **kwargs: "ibischk test")
    monkeypatch.setattr(
        validation.subprocess,
        "run",
        lambda command, **kwargs: SimpleNamespace(returncode=0, stdout="IBIS OK", stderr=""),
    )

    result = validation.validate_ibis_model_bytes(payload, capture, member_path="x.ibs")

    assert result["status"] == "passed_syntax_validation"
    assert result["validation_pass"] is True
    assert result["tool"]["version"] == "ibischk test"
    assert result["raw_output_sha256"].startswith("sha256:")
    assert result["physical_correctness"] == "UNPROVEN"


def test_verilog_unbound_include_is_rejected_before_compiler(monkeypatch) -> None:
    payload = b'`include "support.vh"\nmodule W25Q(); endmodule\n'
    capture = _capture("verilog", "Verilog", "w25q.v", payload)
    looked_up = []
    monkeypatch.setattr(validation.shutil, "which", lambda executable: looked_up.append(executable))

    result = validation.validate_verilog_model_bytes(payload, capture, member_path="w25q.v")

    assert result["status"] == "blocked_unbound_include_dependencies"
    assert result["unbound_include_dependencies"] == ["support.vh"]
    assert looked_up == []


def test_verilog_compile_failure_is_not_a_pass(monkeypatch) -> None:
    payload = b"module W25Q(input CSn); endmodule\n"
    capture = _capture("verilog", "Verilog", "w25q.v", payload)
    monkeypatch.setattr(validation.shutil, "which", lambda executable: "/usr/bin/iverilog")
    monkeypatch.setattr(validation, "executable_version", lambda *args, **kwargs: "Icarus 13 test")
    monkeypatch.setattr(
        validation.subprocess,
        "run",
        lambda command, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="syntax error"),
    )

    result = validation.validate_verilog_model_bytes(payload, capture, member_path="w25q.v")

    assert result["status"] == "failed_syntax_validation"
    assert result["validation_pass"] is False
    assert "syntax error" in result["stderr_tail"]
    assert result["authority_effect"] == "none"


def test_verilog_compile_success_remains_modeled_only(monkeypatch) -> None:
    payload = b"module W25Q(input CSn); endmodule\n"
    capture = _capture("verilog", "Verilog", "w25q.v", payload)
    monkeypatch.setattr(validation.shutil, "which", lambda executable: "/usr/bin/iverilog")
    monkeypatch.setattr(validation, "executable_version", lambda *args, **kwargs: "Icarus 13 test")
    seen = []

    def _run(command, **kwargs):
        seen.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(validation.subprocess, "run", _run)

    result = validation.validate_verilog_model_bytes(payload, capture, member_path="w25q.v")

    assert result["status"] == "passed_syntax_validation"
    assert result["validation_pass"] is True
    assert seen and seen[0][1:3] == ["-tnull", "-g2012"]
    assert result["modeled_evidence_only"] is True
    assert result["measured_evidence_present"] is False
    assert result["physical_authority_granted"] is False
