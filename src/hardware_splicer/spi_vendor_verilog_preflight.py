"""Hash-bound Icarus preflight for captured SPI vendor Verilog.

The preflight establishes only that the exact captured source is structurally eligible for the
later preregistered JEDEC-ID execution. It does not drive the SPI interface, does not observe a
JEDEC response, and grants no model-result, measured, fabrication, power-on, or physical credit.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .captured_model_materialization import extract_bound_model_member
from .spi_winbond_verilog_capability import audit_winbond_verilog_capabilities

SCHEMA_VERSION = "hardware_splicer.spi_vendor_verilog_preflight.v1"
_MODEL_ID = "w25q128jw-q-verilog-da02-aag072"
_DEFAULT_TIMEOUT_S = 30
_MAX_TIMEOUT_S = 120
_DEFAULT_MAX_OUTPUT_BYTES = 2 * 1024 * 1024


class VendorVerilogPreflightError(ValueError):
    pass


def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _recognized_verilog_paths(manifest: Mapping[str, Any]) -> list[str]:
    rows = manifest.get("recognized_model_files")
    if not isinstance(rows, list):
        return []
    return sorted(
        str(row.get("path"))
        for row in rows
        if isinstance(row, Mapping)
        and row.get("model_kind") == "Verilog"
        and isinstance(row.get("path"), str)
        and row.get("path")
    )


def preflight_winbond_verilog_model(
    outer_payload: bytes,
    manifest: Mapping[str, Any],
    *,
    timeout_s: int = _DEFAULT_TIMEOUT_S,
    max_output_bytes: int = _DEFAULT_MAX_OUTPUT_BYTES,
    iverilog_path: str | None = None,
) -> dict[str, Any]:
    """Compile-check exact captured Winbond model members with Icarus Verilog.

    Passing this gate means only that the hash-bound source both contains the frozen static
    0x9F/JEDEC-ID candidate structures and compiles as Verilog under the recorded Icarus engine.
    A later exact testbench still has to drive the model and satisfy the campaign's required
    behavioral checks before modeled execution credit is possible.
    """

    if manifest.get("model_id") != _MODEL_ID:
        raise VendorVerilogPreflightError("unexpected model id for Winbond Verilog preflight")
    if not isinstance(timeout_s, int) or isinstance(timeout_s, bool) or not 1 <= timeout_s <= _MAX_TIMEOUT_S:
        raise VendorVerilogPreflightError(f"timeout_s must be within 1..{_MAX_TIMEOUT_S}")
    if not isinstance(max_output_bytes, int) or isinstance(max_output_bytes, bool) or max_output_bytes <= 0:
        raise VendorVerilogPreflightError("max_output_bytes must be a positive integer")

    static_audit = audit_winbond_verilog_capabilities(outer_payload, manifest)
    member_paths = _recognized_verilog_paths(manifest)
    if not member_paths:
        raise VendorVerilogPreflightError("capture contains no recognized Verilog model members")

    executable = iverilog_path or shutil.which("iverilog")
    base: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "model_id": _MODEL_ID,
        "capture_sha256": manifest.get("sha256"),
        "static_audit_schema_version": static_audit.get("schema_version"),
        "static_source_candidate": static_audit.get("jedec_id_read_9f_source_candidate") is True,
        "module_names": list(static_audit.get("module_names", [])),
        "recognized_verilog_member_paths": member_paths,
        "compile_engine": "iverilog",
        "compile_pass": False,
        "jedec_id_read_9f_supported": False,
        "execution_credit_granted": False,
        "modeled_evidence_only": True,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "fabrication_ready": False,
        "power_on_ready": False,
        "physical_authority_granted": False,
        "authority_effect": "none",
    }
    if not executable:
        return {
            **base,
            "status": "tool_unavailable",
            "engine_version_output_sha256": None,
            "compile_exit_code": None,
            "compile_output_sha256": None,
        }

    try:
        version_run = subprocess.run(
            [executable, "-V"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_s,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VendorVerilogPreflightError(f"Icarus version probe failed: {exc}") from exc
    version_raw = bytes(version_run.stdout or b"") + bytes(version_run.stderr or b"")
    if len(version_raw) > max_output_bytes:
        raise VendorVerilogPreflightError("Icarus version output exceeds byte ceiling")

    materializations: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="hs-winbond-verilog-preflight-") as tmp:
        workspace = Path(tmp)
        local_paths: list[Path] = []
        used_names: set[str] = set()
        for index, member_path in enumerate(member_paths):
            member, materialization = extract_bound_model_member(
                outer_payload,
                manifest,
                member_path=member_path,
            )
            basename = PurePosixPath(member_path).name or f"model-{index}.v"
            local_name = basename
            if local_name in used_names:
                local_name = f"{index}-{basename}"
            used_names.add(local_name)
            local_path = workspace / local_name
            local_path.write_bytes(member)
            try:
                local_path.chmod(0o600)
            except OSError:
                pass
            local_paths.append(local_path)
            materializations.append({**materialization, "workspace_filename": local_name})

        command = [executable, "-g2012", "-tnull", *[str(path) for path in local_paths]]
        try:
            compile_run = subprocess.run(
                command,
                cwd=workspace,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise VendorVerilogPreflightError(f"Icarus compile preflight timed out after {timeout_s}s") from exc
        except OSError as exc:
            raise VendorVerilogPreflightError(f"Icarus compile preflight could not start: {exc}") from exc

    compile_raw = bytes(compile_run.stdout or b"") + bytes(compile_run.stderr or b"")
    if len(compile_raw) > max_output_bytes:
        raise VendorVerilogPreflightError("Icarus compile output exceeds byte ceiling")

    compile_pass = compile_run.returncode == 0
    source_candidate = static_audit.get("jedec_id_read_9f_source_candidate") is True
    execution_eligible = bool(compile_pass and source_candidate)
    if not compile_pass:
        status = "compile_failed"
    elif not source_candidate:
        status = "compiled_source_not_jedec_candidate"
    else:
        status = "eligible_for_bound_jedec_testbench"

    return {
        **base,
        "status": status,
        "compile_engine_executable": Path(executable).name,
        "engine_version_exit_code": int(version_run.returncode),
        "engine_version_output_sha256": _sha256(version_raw),
        "compile_exit_code": int(compile_run.returncode),
        "compile_output_sha256": _sha256(compile_raw),
        "compile_pass": compile_pass,
        "materializations": materializations,
        # This is the semantic-capability field consumed by #97's fail-closed campaign gate.
        # It means execution-eligible, not execution-passed.
        "jedec_id_read_9f_supported": execution_eligible,
        "execution_credit_granted": False,
        "required_next_step": (
            "Bind an exact testbench to the captured model interface, drive 0x9F at the frozen clock, "
            "observe EF6018, prove no write/erase side effect, then seal and audit the result."
        ),
        "nonclaims": [
            "Compile preflight is not a JEDEC-ID behavioral execution.",
            "Execution eligibility is not a passing manufacturer-model result.",
            "A passing manufacturer-model result would still be modeled-only evidence.",
        ],
    }
