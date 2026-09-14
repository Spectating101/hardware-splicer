"""Fail-closed execution boundary for captured SPI vendor models.

This runner closes the gap between immutable capture manifests and the existing model-result
audit contract.  It materializes only hash-bound model members into a private temporary
workspace, exposes those paths to one explicitly allowlisted subprocess, captures the raw
process output, seals the engine report, and immediately audits the result.

It does *not* claim network isolation, simulator correctness, measured evidence, physical
correctness, fabrication readiness, power-on readiness, or physical authority.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from .captured_model_materialization import extract_bound_model_member
from .spi_model_execution_contract import (
    audit_spi_model_execution_result,
    seal_spi_model_execution_result,
)

SCHEMA_VERSION = "hardware_splicer.spi_bound_engine_run.v1"
ENGINE_REPORT_SCHEMA_VERSION = "hardware_splicer.spi_engine_report.v1"
_DEFAULT_TIMEOUT_S = 60
_MAX_TIMEOUT_S = 300
_DEFAULT_MAX_OUTPUT_BYTES = 5 * 1024 * 1024
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9]+")


class BoundEngineRunError(ValueError):
    """Raised when execution prerequisites or the engine-report boundary are invalid."""


def _safe_env_key(model_id: str) -> str:
    token = _SAFE_ID_RE.sub("_", str(model_id)).strip("_").upper()
    if not token:
        raise BoundEngineRunError("model id cannot be converted to an environment key")
    return "HS_MODEL_" + token


def _planned_execution(campaign: Mapping[str, Any], execution_id: str) -> Mapping[str, Any]:
    for row in campaign.get("planned_executions", []):
        if isinstance(row, Mapping) and row.get("execution_id") == execution_id:
            return row
    raise BoundEngineRunError(f"execution is not preregistered: {execution_id}")


def _parse_engine_report(stdout: bytes, *, execution_id: str) -> Mapping[str, Any]:
    try:
        report = json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BoundEngineRunError("engine stdout is not one UTF-8 JSON report") from exc
    if not isinstance(report, Mapping):
        raise BoundEngineRunError("engine report must be a JSON object")
    allowed = {"schema_version", "execution_id", "checks", "metrics"}
    extras = sorted(set(report) - allowed)
    if extras:
        raise BoundEngineRunError(f"engine report contains unsupported fields: {extras}")
    if report.get("schema_version") != ENGINE_REPORT_SCHEMA_VERSION:
        raise BoundEngineRunError("engine report schema mismatch")
    if report.get("execution_id") != execution_id:
        raise BoundEngineRunError("engine report execution id mismatch")
    if not isinstance(report.get("checks"), list):
        raise BoundEngineRunError("engine report checks must be a list")
    if not isinstance(report.get("metrics", {}), Mapping):
        raise BoundEngineRunError("engine report metrics must be an object")
    return report


def run_bound_spi_model_engine(
    campaign: Mapping[str, Any],
    *,
    execution_id: str,
    engine_name: str,
    engine_version: str,
    argv: Sequence[str],
    allowed_executables: set[str],
    model_inputs: Mapping[str, Mapping[str, Any]],
    timeout_s: int = _DEFAULT_TIMEOUT_S,
    max_output_bytes: int = _DEFAULT_MAX_OUTPUT_BYTES,
) -> dict[str, Any]:
    """Execute one preregistered model case against exact captured model bytes.

    ``model_inputs`` must contain exactly the preregistered model IDs for the execution. Each
    value contains ``outer_payload`` (bytes), ``capture_manifest`` (mapping), and
    ``member_path`` (the recognized model member to materialize).

    The subprocess receives model paths only through ``HS_MODEL_<MODEL_ID>`` environment
    variables plus ``HS_EXECUTION_ID`` and ``HS_EXECUTION_CONDITIONS_JSON``.  The subprocess
    must emit exactly one JSON report on stdout using ``ENGINE_REPORT_SCHEMA_VERSION``.
    """

    if campaign.get("status") != "ready_for_model_execution" or campaign.get("execution_ready") is not True:
        raise BoundEngineRunError("campaign is not ready for model execution")

    planned = _planned_execution(campaign, execution_id)
    required_models = {str(model_id) for model_id in planned.get("required_models", [])}
    supplied_models = {str(model_id) for model_id in model_inputs}
    if not required_models or supplied_models != required_models:
        raise BoundEngineRunError(
            "model input set must exactly match preregistered required models: "
            f"required={sorted(required_models)} supplied={sorted(supplied_models)}"
        )

    if not argv or not all(isinstance(item, str) and item and "\x00" not in item for item in argv):
        raise BoundEngineRunError("argv must be a non-empty sequence of valid strings")
    executable = Path(argv[0]).name
    if executable not in set(allowed_executables):
        raise BoundEngineRunError(f"engine executable is not allowlisted: {executable}")
    if not isinstance(timeout_s, int) or isinstance(timeout_s, bool) or timeout_s <= 0 or timeout_s > _MAX_TIMEOUT_S:
        raise BoundEngineRunError(f"timeout_s must be within 1..{_MAX_TIMEOUT_S}")
    if not isinstance(max_output_bytes, int) or isinstance(max_output_bytes, bool) or max_output_bytes <= 0:
        raise BoundEngineRunError("max_output_bytes must be a positive integer")

    campaign_models = campaign.get("model_captures")
    if not isinstance(campaign_models, Mapping):
        raise BoundEngineRunError("campaign model-capture map is missing")

    materializations: dict[str, Any] = {}
    model_hashes: dict[str, str] = {}
    env_keys: set[str] = set()

    with tempfile.TemporaryDirectory(prefix="hs-spi-model-") as tmp:
        workdir = Path(tmp)
        env: dict[str, str] = {
            "PATH": os.environ.get("PATH", ""),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "HS_EXECUTION_ID": execution_id,
            "HS_EXECUTION_CONDITIONS_JSON": json.dumps(
                planned.get("conditions", {}), sort_keys=True, separators=(",", ":")
            ),
        }

        for model_id in sorted(required_models):
            row = model_inputs.get(model_id)
            if not isinstance(row, Mapping):
                raise BoundEngineRunError(f"model input must be an object: {model_id}")
            outer_payload = row.get("outer_payload")
            manifest = row.get("capture_manifest")
            member_path = row.get("member_path")
            if not isinstance(outer_payload, (bytes, bytearray)):
                raise BoundEngineRunError(f"outer_payload must be bytes: {model_id}")
            if not isinstance(manifest, Mapping):
                raise BoundEngineRunError(f"capture_manifest must be an object: {model_id}")
            if manifest.get("model_id") != model_id:
                raise BoundEngineRunError(f"capture manifest model id mismatch: {model_id}")
            expected_outer_hash = campaign_models.get(model_id, {}).get("capture_sha256") if isinstance(campaign_models.get(model_id), Mapping) else None
            if manifest.get("sha256") != expected_outer_hash:
                raise BoundEngineRunError(f"capture manifest does not match ready campaign: {model_id}")

            member, materialization = extract_bound_model_member(
                bytes(outer_payload), manifest, member_path=str(member_path or "")
            )
            suffix = PurePosixPath(str(member_path or "")).suffix
            local_name = _SAFE_ID_RE.sub("-", model_id).strip("-") + suffix
            local_path = workdir / local_name
            local_path.write_bytes(member)
            try:
                local_path.chmod(0o600)
            except OSError:
                pass

            env_key = _safe_env_key(model_id)
            if env_key in env_keys:
                raise BoundEngineRunError("model ids collide after environment-key normalization")
            env_keys.add(env_key)
            env[env_key] = str(local_path)
            materializations[model_id] = {
                **materialization,
                "workspace_filename": local_name,
            }
            model_hashes[model_id] = str(manifest.get("sha256"))

        try:
            completed = subprocess.run(
                list(argv),
                cwd=workdir,
                env=env,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise BoundEngineRunError(f"engine timed out after {timeout_s}s") from exc
        except OSError as exc:
            raise BoundEngineRunError(f"engine could not be started: {exc}") from exc

    stdout = bytes(completed.stdout or b"")
    stderr = bytes(completed.stderr or b"")
    if len(stdout) + len(stderr) > max_output_bytes:
        raise BoundEngineRunError("engine output exceeds configured byte ceiling")

    report = _parse_engine_report(stdout, execution_id=execution_id)
    raw_output = stdout + b"\n--- HS STDERR ---\n" + stderr
    sealed = seal_spi_model_execution_result(
        campaign,
        execution_id=execution_id,
        engine_name=engine_name,
        engine_version=engine_version,
        exit_code=int(completed.returncode),
        raw_output=raw_output,
        model_hashes=model_hashes,
        checks=report["checks"],
        metrics=report.get("metrics", {}),
    )
    audit = audit_spi_model_execution_result(campaign, sealed)

    return {
        "schema_version": SCHEMA_VERSION,
        "status": audit["status"],
        "execution_id": execution_id,
        "target_candidate_id": campaign.get("target_candidate_id"),
        "engine": {"name": engine_name, "version": engine_version, "executable": executable},
        "process_exit_code": int(completed.returncode),
        "stdout_size_bytes": len(stdout),
        "stderr_size_bytes": len(stderr),
        "materializations": materializations,
        "sealed_result": sealed,
        "audit": audit,
        "network_isolation_asserted": False,
        "model_inference_used": False,
        "modeled_evidence_only": True,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "fabrication_ready": False,
        "power_on_ready": False,
        "physical_authority_granted": False,
        "authority_effect": "none",
    }
