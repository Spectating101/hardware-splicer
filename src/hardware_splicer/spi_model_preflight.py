"""Bound syntax/preflight checks for captured SPI vendor models.

Preflight answers only whether exact captured model bytes can be consumed by a selected parser
or compiler.  It is deliberately below model-execution credit: an IBISCHK or Verilog compile
pass is not a signal-integrity/protocol simulation and cannot satisfy any preregistered modeled
campaign execution.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from .captured_model_materialization import extract_bound_model_member

SCHEMA_VERSION = "hardware_splicer.spi_model_preflight.v1"
_MAX_TIMEOUT_S = 120
_MAX_OUTPUT_BYTES = 2 * 1024 * 1024


class ModelPreflightError(ValueError):
    pass


def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def run_bound_model_preflight(
    *,
    outer_payload: bytes,
    capture_manifest: Mapping[str, Any],
    member_path: str,
    tool_name: str,
    tool_version: str,
    argv_template: Sequence[str],
    allowed_executables: set[str],
    expected_model_kind: str,
    timeout_s: int = 30,
) -> dict[str, Any]:
    """Materialize one hash-bound model member and run a bounded parser/compiler.

    ``argv_template`` must contain the literal token ``{model}``, which is replaced by the
    private temporary path. The executable is allowlisted by basename and is invoked with
    ``shell=False``.  No preflight result receives simulation or physical authority.
    """

    if capture_manifest.get("expected_model_kind") != expected_model_kind:
        raise ModelPreflightError("capture manifest model kind mismatch")
    if not argv_template or "{model}" not in argv_template:
        raise ModelPreflightError("argv_template must contain {model}")
    if not all(isinstance(item, str) and item and "\x00" not in item for item in argv_template):
        raise ModelPreflightError("argv_template contains an invalid argument")
    executable = Path(argv_template[0]).name
    if executable not in set(allowed_executables):
        raise ModelPreflightError(f"preflight executable is not allowlisted: {executable}")
    if not isinstance(timeout_s, int) or isinstance(timeout_s, bool) or not (1 <= timeout_s <= _MAX_TIMEOUT_S):
        raise ModelPreflightError(f"timeout_s must be within 1..{_MAX_TIMEOUT_S}")

    member, materialization = extract_bound_model_member(
        outer_payload,
        capture_manifest,
        member_path=member_path,
    )
    suffix = PurePosixPath(member_path).suffix

    with tempfile.TemporaryDirectory(prefix="hs-model-preflight-") as tmp:
        local_path = Path(tmp) / ("model" + suffix)
        local_path.write_bytes(member)
        try:
            local_path.chmod(0o600)
        except OSError:
            pass
        argv = [str(local_path) if item == "{model}" else item for item in argv_template]
        env = {
            "PATH": os.environ.get("PATH", ""),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        }
        try:
            completed = subprocess.run(
                argv,
                cwd=tmp,
                env=env,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ModelPreflightError(f"preflight timed out after {timeout_s}s") from exc
        except OSError as exc:
            raise ModelPreflightError(f"preflight tool could not be started: {exc}") from exc

    stdout = bytes(completed.stdout or b"")
    stderr = bytes(completed.stderr or b"")
    if len(stdout) + len(stderr) > _MAX_OUTPUT_BYTES:
        raise ModelPreflightError("preflight output exceeds byte ceiling")
    raw = stdout + b"\n--- HS STDERR ---\n" + stderr
    passed = int(completed.returncode) == 0

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "passed_preflight" if passed else "failed_preflight",
        "preflight_pass": passed,
        "model_id": capture_manifest.get("model_id"),
        "model_kind": expected_model_kind,
        "capture_sha256": capture_manifest.get("sha256"),
        "member_path": member_path,
        "member_sha256": materialization["member_sha256"],
        "tool": {
            "name": str(tool_name),
            "version": str(tool_version),
            "executable": executable,
        },
        "process_exit_code": int(completed.returncode),
        "raw_output_sha256": _sha256(raw),
        "stdout_size_bytes": len(stdout),
        "stderr_size_bytes": len(stderr),
        "eligible_for_model_execution_credit": False,
        "eligible_for_vendor_model_campaign_credit": False,
        "syntax_or_compile_preflight_only": True,
        "modeled_evidence_only": True,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "fabrication_ready": False,
        "power_on_ready": False,
        "physical_authority_granted": False,
        "authority_effect": "none",
    }


def recommended_preflight(model_kind: str) -> dict[str, Any]:
    """Describe the selected reproducible preflight role without claiming tool availability."""

    if model_kind == "IBIS":
        return {
            "model_kind": "IBIS",
            "tool_name": "IBISCHK7",
            "reference_version": "7.2.1",
            "argv_template": ["ibischk7_64", "-caution", "-numbered", "{model}"],
            "role": "official_ibis_conformance_parser",
            "simulation_engine": False,
            "note": "Parser conformance is required preflight but does not simulate signal integrity.",
        }
    if model_kind == "Verilog":
        return {
            "model_kind": "Verilog",
            "tool_name": "Icarus Verilog",
            "reference_version": "13.0",
            "argv_template": ["iverilog", "-g2012", "-tnull", "{model}"],
            "role": "verilog_compile_preflight",
            "simulation_engine": False,
            "note": "Compile preflight does not prove the vendor model produces correct protocol behavior.",
        }
    raise ModelPreflightError(f"unsupported model kind for recommended preflight: {model_kind}")
