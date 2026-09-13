"""Bound syntax-validation wrappers for captured manufacturer IBIS and Verilog models.

These validators deliberately stop short of signal-integrity or protocol simulation. They prove
that exact captured model bytes are accepted by an explicitly identified parser/compiler. That
is useful modeled-tool evidence, but it never becomes measured or physical authority.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .backends.base import executable_version

SCHEMA_VERSION = "hardware_splicer.vendor_model_validation.v1"
_CAPTURE_SCHEMA_VERSION = "hardware_splicer.vendor_model_capture.v1"


def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _base_result(*, model_id: str, model_kind: str, member_path: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "model_id": model_id,
        "model_kind": model_kind,
        "member_path": member_path,
        "validation_pass": None,
        "modeled_evidence_only": True,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
    }


def _bound_member(
    model_bytes: bytes,
    capture_manifest: Mapping[str, Any],
    *,
    member_path: str,
    expected_kind: str,
) -> tuple[bool, str | None]:
    if capture_manifest.get("schema_version") != _CAPTURE_SCHEMA_VERSION:
        return False, "capture_schema_mismatch"
    if capture_manifest.get("expected_model_kind") != expected_kind:
        return False, "capture_model_kind_mismatch"
    if capture_manifest.get("capture_status") != "captured_hashed_unreviewed":
        return False, "capture_status_invalid"
    if capture_manifest.get("physical_authority_granted") is not False:
        return False, "capture_authority_boundary_invalid"

    normalized = str(PurePosixPath(str(member_path)))
    recognized = capture_manifest.get("recognized_model_files")
    if not isinstance(recognized, list):
        return False, "recognized_model_files_missing"
    expected_sha = None
    for row in recognized:
        if not isinstance(row, Mapping):
            continue
        if row.get("path") == normalized and row.get("model_kind") == expected_kind:
            expected_sha = row.get("sha256")
            break
    if not expected_sha:
        return False, "member_not_recognized_in_capture"
    if _sha256(model_bytes) != expected_sha:
        return False, "member_sha256_mismatch"
    return True, None


def _safe_temp_name(member_path: str, suffix: str) -> str:
    name = PurePosixPath(member_path).name
    stem = Path(name).stem or "vendor_model"
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem)[:80] or "vendor_model"
    return safe_stem + suffix


def _finish_tool_result(
    result: dict[str, Any],
    *,
    executable: str,
    version: str | None,
    command: list[str],
    returncode: int | None,
    stdout: str,
    stderr: str,
    timed_out: bool = False,
) -> dict[str, Any]:
    raw_output = ((stdout or "") + "\n" + (stderr or "")).encode("utf-8", errors="replace")
    result.update(
        {
            "tool": {"executable": executable, "version": version},
            "command_shape": [Path(part).name if index == len(command) - 1 else part for index, part in enumerate(command)],
            "returncode": returncode,
            "timed_out": timed_out,
            "raw_output_sha256": _sha256(raw_output),
            "stdout_tail": (stdout or "")[-4000:],
            "stderr_tail": (stderr or "")[-4000:],
            "validation_pass": returncode == 0 and not timed_out,
            "status": "passed_syntax_validation" if returncode == 0 and not timed_out else "failed_syntax_validation",
        }
    )
    return result


def validate_ibis_model_bytes(
    model_bytes: bytes,
    capture_manifest: Mapping[str, Any],
    *,
    member_path: str,
    parser_executable: str = "ibischk",
    timeout_s: int = 30,
) -> dict[str, Any]:
    """Run a configurable IBIS Golden-Parser-compatible executable on exact captured bytes."""

    result = _base_result(
        model_id=str(capture_manifest.get("model_id") or ""),
        model_kind="IBIS",
        member_path=member_path,
    )
    bound, reason = _bound_member(
        model_bytes, capture_manifest, member_path=member_path, expected_kind="IBIS"
    )
    if not bound:
        result.update({"status": "rejected_capture_binding", "binding_error": reason})
        return result

    executable = shutil.which(parser_executable)
    if not executable:
        result.update({"status": "tool_unavailable", "tool": {"executable": parser_executable, "version": None}})
        return result

    version = executable_version(parser_executable, ("-v",)) or executable_version(parser_executable)
    with tempfile.TemporaryDirectory(prefix="hs-ibis-validate-") as tmp:
        path = Path(tmp) / _safe_temp_name(member_path, ".ibs")
        path.write_bytes(model_bytes)
        command = [executable, str(path)]
        try:
            proc = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=int(timeout_s),
            )
        except subprocess.TimeoutExpired as exc:
            return _finish_tool_result(
                result,
                executable=executable,
                version=version,
                command=command,
                returncode=None,
                stdout=str(exc.stdout or ""),
                stderr=str(exc.stderr or ""),
                timed_out=True,
            )
        except OSError as exc:
            result.update({"status": "tool_execution_error", "tool": {"executable": executable, "version": version}, "error": str(exc)})
            return result

    return _finish_tool_result(
        result,
        executable=executable,
        version=version,
        command=command,
        returncode=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
    )


def _unsafe_verilog_includes(model_bytes: bytes) -> list[str]:
    text = model_bytes.decode("latin-1", errors="ignore")
    unsafe: list[str] = []
    for match in re.finditer(r"(?m)^\s*`include\s+[\"<]([^\">]+)[\">]", text):
        raw = match.group(1).replace("\\", "/")
        path = PurePosixPath(raw)
        if path.is_absolute() or ".." in path.parts or len(path.parts) > 1:
            unsafe.append(raw)
        else:
            # V1 intentionally accepts only self-contained model files. A future manifest can
            # explicitly bind companion include files instead of allowing implicit filesystem reads.
            unsafe.append(raw)
    return sorted(set(unsafe))


def validate_verilog_model_bytes(
    model_bytes: bytes,
    capture_manifest: Mapping[str, Any],
    *,
    member_path: str,
    compiler_executable: str = "iverilog",
    timeout_s: int = 30,
) -> dict[str, Any]:
    """Compile exact captured Verilog bytes with Icarus-compatible syntax-only settings."""

    result = _base_result(
        model_id=str(capture_manifest.get("model_id") or ""),
        model_kind="Verilog",
        member_path=member_path,
    )
    bound, reason = _bound_member(
        model_bytes, capture_manifest, member_path=member_path, expected_kind="Verilog"
    )
    if not bound:
        result.update({"status": "rejected_capture_binding", "binding_error": reason})
        return result

    unsafe_includes = _unsafe_verilog_includes(model_bytes)
    if unsafe_includes:
        result.update(
            {
                "status": "blocked_unbound_include_dependencies",
                "unbound_include_dependencies": unsafe_includes,
            }
        )
        return result

    executable = shutil.which(compiler_executable)
    if not executable:
        result.update({"status": "tool_unavailable", "tool": {"executable": compiler_executable, "version": None}})
        return result

    version = executable_version(compiler_executable, ("-V",)) or executable_version(compiler_executable)
    with tempfile.TemporaryDirectory(prefix="hs-verilog-validate-") as tmp:
        path = Path(tmp) / _safe_temp_name(member_path, ".v")
        path.write_bytes(model_bytes)
        command = [executable, "-tnull", "-g2012", str(path)]
        try:
            proc = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=int(timeout_s),
            )
        except subprocess.TimeoutExpired as exc:
            return _finish_tool_result(
                result,
                executable=executable,
                version=version,
                command=command,
                returncode=None,
                stdout=str(exc.stdout or ""),
                stderr=str(exc.stderr or ""),
                timed_out=True,
            )
        except OSError as exc:
            result.update({"status": "tool_execution_error", "tool": {"executable": executable, "version": version}, "error": str(exc)})
            return result

    return _finish_tool_result(
        result,
        executable=executable,
        version=version,
        command=command,
        returncode=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
    )
