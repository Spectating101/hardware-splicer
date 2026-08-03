"""Bounded execution for software-only engineering checks.

This module intentionally supports no flashing, device access, power control, or
physical motion.  Commands are generated from named operations; callers cannot submit
an arbitrary shell string. Execution is disabled unless explicitly enabled by the
host and every workspace/target remains inside the configured execution root.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator


ENGINEERING_EXECUTION_SCHEMA = "hardware_splicer.engineering_execution.v1"
MAX_OUTPUT_CHARS = 40_000


class ExecutionBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ExecutionOperation(str, Enum):
    ARTIFACT_HASH = "artifact_hash"
    PYTHON_COMPILE = "python_compile"
    PYTEST = "pytest"
    KICAD_ERC = "kicad_erc"
    KICAD_DRC = "kicad_drc"
    NGSPICE = "ngspice"
    PLATFORMIO_BUILD = "platformio_build"
    COLCON_BUILD = "colcon_build"
    COLCON_TEST = "colcon_test"
    ROS2_DOCTOR = "ros2_doctor"
    URDF_CHECK = "urdf_check"


class ExecutionStatus(str, Enum):
    PLANNED = "planned"
    BLOCKED = "blocked"
    UNAVAILABLE = "unavailable"
    PASSED = "passed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ERROR = "error"


class ExecutionRequest(ExecutionBase):
    execution_id: str = Field(min_length=1)
    operation: ExecutionOperation
    workspace: str = "."
    target: str | None = None
    timeout_s: int = Field(default=60, ge=1, le=900)
    options: Dict[str, Any] = Field(default_factory=dict)
    expected_outputs: list[str] = Field(default_factory=list)
    execute: bool = False

    @model_validator(mode="after")
    def operation_requires_target(self) -> "ExecutionRequest":
        operations = {
            ExecutionOperation.ARTIFACT_HASH,
            ExecutionOperation.PYTHON_COMPILE,
            ExecutionOperation.KICAD_ERC,
            ExecutionOperation.KICAD_DRC,
            ExecutionOperation.NGSPICE,
            ExecutionOperation.URDF_CHECK,
        }
        if self.operation in operations and not self.target:
            raise ValueError(f"operation {self.operation.value} requires target")
        return self


class ExecutionResult(ExecutionBase):
    schema_version: str = ENGINEERING_EXECUTION_SCHEMA
    execution_id: str
    operation: ExecutionOperation
    status: ExecutionStatus
    argv: list[str] = Field(default_factory=list)
    workspace: str
    target: str | None = None
    tool: str | None = None
    tool_available: bool = False
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_s: float = 0.0
    output_hashes: Dict[str, str] = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutionPolicyError(ValueError):
    pass


def default_execution_root() -> Path:
    configured = os.getenv("HARDWARE_SPLICER_EXECUTION_ROOT", "").strip()
    root = Path(configured).expanduser() if configured else Path.cwd()
    return root.resolve()


def execution_enabled() -> bool:
    return os.getenv("HARDWARE_SPLICER_EXECUTION_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def _within(root: Path, value: str | Path) -> Path:
    path = (root / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    if path != root and root not in path.parents:
        raise ExecutionPolicyError(f"path resolves outside execution root: {value}")
    return path


def _safe_pytest_targets(value: Any) -> list[str]:
    targets = value if isinstance(value, list) else []
    result: list[str] = []
    for item in targets:
        token = str(item)
        if token.startswith("-") or "::" in token and token.startswith("-"):
            raise ExecutionPolicyError("pytest target cannot be an option")
        result.append(token)
    return result


def _argv(request: ExecutionRequest, workspace: Path, target: Path | None) -> tuple[list[str], str | None]:
    operation = request.operation
    if operation == ExecutionOperation.ARTIFACT_HASH:
        return [], None
    if operation == ExecutionOperation.PYTHON_COMPILE:
        return [sys.executable, "-m", "compileall", "-q", str(target)], sys.executable
    if operation == ExecutionOperation.PYTEST:
        targets = _safe_pytest_targets(request.options.get("targets")) or ["tests"]
        return [sys.executable, "-m", "pytest", "-q", *targets], sys.executable
    if operation == ExecutionOperation.KICAD_ERC:
        return ["kicad-cli", "sch", "erc", str(target)], shutil.which("kicad-cli")
    if operation == ExecutionOperation.KICAD_DRC:
        return ["kicad-cli", "pcb", "drc", str(target)], shutil.which("kicad-cli")
    if operation == ExecutionOperation.NGSPICE:
        return ["ngspice", "-b", str(target)], shutil.which("ngspice")
    if operation == ExecutionOperation.PLATFORMIO_BUILD:
        return ["pio", "run", "--project-dir", str(workspace)], shutil.which("pio")
    if operation == ExecutionOperation.COLCON_BUILD:
        return ["colcon", "build", "--event-handlers", "console_direct+"], shutil.which("colcon")
    if operation == ExecutionOperation.COLCON_TEST:
        return ["colcon", "test", "--event-handlers", "console_direct+"], shutil.which("colcon")
    if operation == ExecutionOperation.ROS2_DOCTOR:
        return ["ros2", "doctor", "--report"], shutil.which("ros2")
    if operation == ExecutionOperation.URDF_CHECK:
        return ["check_urdf", str(target)], shutil.which("check_urdf")
    raise ExecutionPolicyError(f"unsupported operation: {operation.value}")


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _output_hashes(workspace: Path, paths: list[str]) -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    for value in paths:
        path = _within(workspace, value)
        if path.is_file():
            hashes[str(path.relative_to(workspace))] = _hash_file(path)
    return hashes


def preview_engineering_execution(
    request: ExecutionRequest,
    *,
    root: Path | None = None,
) -> ExecutionResult:
    execution_root = (root or default_execution_root()).resolve()
    workspace = _within(execution_root, request.workspace)
    target = _within(workspace, request.target) if request.target else None
    argv, tool = _argv(request, workspace, target)
    available = request.operation == ExecutionOperation.ARTIFACT_HASH or bool(tool)
    blockers: list[str] = []
    if not workspace.is_dir():
        blockers.append("workspace does not exist or is not a directory")
    if target is not None and not target.exists():
        blockers.append("target does not exist")
    if not available:
        blockers.append(f"required tool is unavailable for {request.operation.value}")
    if request.execute and not execution_enabled():
        blockers.append("execution is disabled by host policy")
    status = ExecutionStatus.BLOCKED if blockers else ExecutionStatus.PLANNED
    return ExecutionResult(
        execution_id=request.execution_id,
        operation=request.operation,
        status=status,
        argv=argv,
        workspace=str(workspace),
        target=str(target) if target else None,
        tool=tool,
        tool_available=available,
        blockers=blockers,
        metadata={
            "execute_requested": request.execute,
            "execution_enabled": execution_enabled(),
            "shell": False,
            "network_authorized": False,
            "device_access_authorized": False,
            "flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
        },
    )


def run_engineering_execution(
    request: ExecutionRequest,
    *,
    root: Path | None = None,
) -> ExecutionResult:
    preview = preview_engineering_execution(request, root=root)
    if preview.blockers or not request.execute:
        return preview

    workspace = Path(preview.workspace)
    target = Path(preview.target) if preview.target else None
    started = time.monotonic()
    if request.operation == ExecutionOperation.ARTIFACT_HASH:
        hashes = {str(target.relative_to(workspace)): _hash_file(target)} if target and target.is_file() else {}
        status = ExecutionStatus.PASSED if hashes else ExecutionStatus.FAILED
        return preview.model_copy(
            update={
                "status": status,
                "duration_s": round(time.monotonic() - started, 6),
                "output_hashes": hashes,
            },
            deep=True,
        )

    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", str(workspace)),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
        "PYTHONUNBUFFERED": "1",
        "HARDWARE_SPLICER_EXECUTION_SANDBOX": "1",
    }
    try:
        proc = subprocess.run(
            preview.argv,
            cwd=workspace,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=request.timeout_s,
            check=False,
            shell=False,
            start_new_session=True,
        )
        status = ExecutionStatus.PASSED if proc.returncode == 0 else ExecutionStatus.FAILED
        return preview.model_copy(
            update={
                "status": status,
                "returncode": proc.returncode,
                "stdout": (proc.stdout or "")[-MAX_OUTPUT_CHARS:],
                "stderr": (proc.stderr or "")[-MAX_OUTPUT_CHARS:],
                "duration_s": round(time.monotonic() - started, 6),
                "output_hashes": _output_hashes(workspace, request.expected_outputs),
            },
            deep=True,
        )
    except subprocess.TimeoutExpired as exc:
        return preview.model_copy(
            update={
                "status": ExecutionStatus.TIMEOUT,
                "stdout": str(exc.stdout or "")[-MAX_OUTPUT_CHARS:],
                "stderr": str(exc.stderr or "")[-MAX_OUTPUT_CHARS:],
                "duration_s": round(time.monotonic() - started, 6),
                "blockers": [f"operation exceeded timeout of {request.timeout_s}s"],
            },
            deep=True,
        )
    except OSError as exc:
        return preview.model_copy(
            update={
                "status": ExecutionStatus.ERROR,
                "duration_s": round(time.monotonic() - started, 6),
                "blockers": [str(exc)],
            },
            deep=True,
        )


def execution_manifest(result: ExecutionResult) -> Dict[str, Any]:
    payload = result.model_dump(mode="json")
    payload["manifest_hash"] = f"sha256:{hashlib.sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()}"
    return payload
