"""Generic OpenOCD programmer backend behind HS physical authority.

Unlike the RP-specific picotool adapter, this covers server-configured OpenOCD
targets. Agents never provide config paths, Tcl commands, target addresses or
firmware paths. A firmware artifact must be registered, staged, and then bound
to an exact PhysicalExecutionPlan whose actuation grant is consumed by the
existing dispatcher before this handle is called.

The adapter deliberately does not auto-run/reset the newly programmed target.
"""
from __future__ import annotations

import hashlib
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from .fabrication_operator import FabricationValidationError
from .physical_artifact import PhysicalArtifactRegistry
from .physical_operator import PhysicalExecutionPlan


class OpenOcdExecutionError(RuntimeError):
    pass


class OpenOcdRunner(Protocol):
    def __call__(self, argv: Sequence[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[bytes]: ...


def _default_runner(argv: Sequence[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        list(argv),
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=timeout,
        shell=False,
    )


@dataclass(frozen=True)
class OpenOcdTarget:
    target_id: str
    config_files: tuple[Path, ...]
    binary_flash_address: int | None = None


class OpenOcdTargetRegistry:
    def __init__(self) -> None:
        self._targets: dict[str, OpenOcdTarget] = {}

    def register(
        self,
        *,
        target_id: str,
        config_files: Sequence[str | Path],
        binary_flash_address: int | None = None,
    ) -> None:
        tid = _id(target_id, "target_id")
        if tid in self._targets:
            raise FabricationValidationError("OpenOCD target id is already registered")
        if not config_files:
            raise FabricationValidationError("OpenOCD target requires server-owned config files")
        resolved: list[Path] = []
        for raw in config_files:
            literal = Path(raw)
            if literal.is_symlink():
                raise FabricationValidationError("OpenOCD config files must not be symlinks")
            path = literal.resolve()
            if not path.is_file() or path.suffix.lower() not in {".cfg", ".tcl"}:
                raise FabricationValidationError("OpenOCD config must be an existing .cfg/.tcl file")
            resolved.append(path)
        if binary_flash_address is not None:
            if type(binary_flash_address) is not int or not 0 <= binary_flash_address <= 0xFFFFFFFFFFFFFFFF:
                raise FabricationValidationError("OpenOCD binary flash address must be a non-negative integer")
        self._targets[tid] = OpenOcdTarget(tid, tuple(resolved), binary_flash_address)

    def get(self, target_id: str) -> OpenOcdTarget:
        try:
            return self._targets[target_id]
        except KeyError as exc:
            raise FabricationValidationError("unknown OpenOCD target id") from exc

    def public_descriptor(self, target_id: str) -> dict[str, Any]:
        target = self.get(target_id)
        return {
            "target_id": target.target_id,
            "config_sha256": [_sha(path.read_bytes()) for path in target.config_files],
            "binary_flash_address_configured": target.binary_flash_address is not None,
            "live_probe_performed": False,
        }


class OpenOcdRunnerBackend:
    def __init__(
        self,
        *,
        targets: OpenOcdTargetRegistry,
        executable: str = "openocd",
        runner: OpenOcdRunner | None = None,
        timeout_seconds: int = 180,
    ):
        if not isinstance(executable, str) or not executable.strip() or any(ch in executable for ch in "\r\n\x00"):
            raise FabricationValidationError("OpenOCD executable must be server-configured text")
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 1200:
            raise FabricationValidationError("OpenOCD timeout must be 1..1200 seconds")
        self.targets = targets
        self.executable = executable.strip()
        self.runner = runner or _default_runner
        self.timeout_seconds = timeout_seconds

    def program_and_verify(self, target_id: str, firmware: bytes, *, firmware_format: str) -> dict[str, Any]:
        target = self.targets.get(target_id)
        fmt = _format(firmware_format)
        if not isinstance(firmware, (bytes, bytearray)) or not firmware:
            raise FabricationValidationError("OpenOCD firmware must be non-empty bytes")
        if fmt == "bin" and target.binary_flash_address is None:
            raise FabricationValidationError("binary firmware requires a server-configured flash address")
        suffix = {"elf": ".elf", "hex": ".hex", "s19": ".s19", "bin": ".bin"}[fmt]
        with tempfile.TemporaryDirectory(prefix="hs-openocd-") as temp_dir:
            root = Path(temp_dir)
            firmware_name = f"firmware{suffix}"
            (root / firmware_name).write_bytes(bytes(firmware))
            # The Tcl command contains only a constant basename and an optional
            # server-owned integer address; no model/user text is interpolated.
            command = f"program {firmware_name} verify exit"
            if fmt == "bin":
                command += f" 0x{target.binary_flash_address:x}"
            argv = [self.executable]
            for config in target.config_files:
                argv.extend(["-f", str(config)])
            argv.extend(["-c", command])
            try:
                completed = self.runner(argv, cwd=root, timeout=self.timeout_seconds)
            except (OSError, subprocess.SubprocessError) as exc:
                raise OpenOcdExecutionError("OpenOCD programming failed") from exc
            stdout = bytes(completed.stdout or b"")
            stderr = bytes(completed.stderr or b"")
            if completed.returncode != 0:
                message = (stderr or stdout).decode("utf-8", errors="replace")[-1000:]
                raise OpenOcdExecutionError(f"OpenOCD exited with {completed.returncode}: {message}")
            return {
                "returncode": int(completed.returncode),
                "stdout_sha256": _sha(stdout),
                "stderr_sha256": _sha(stderr),
                "verify_requested": True,
                "auto_reset_run": False,
                "firmware_format": fmt,
            }


class OpenOcdProgrammerHandle:
    """Private OpenOCD handle consumed only by the generic physical dispatcher."""

    def __init__(
        self,
        *,
        operator_id: str,
        target_id: str,
        artifacts: PhysicalArtifactRegistry,
        backend: OpenOcdRunnerBackend,
    ):
        self.operator_id = _id(operator_id, "operator_id")
        self.target_id = _id(target_id, "target_id")
        backend.targets.get(self.target_id)
        self.artifacts = artifacts
        self.backend = backend
        self._staged_sha256: str | None = None

    def execute(self, plan: PhysicalExecutionPlan) -> Mapping[str, Any]:
        if not isinstance(plan, PhysicalExecutionPlan) or plan.operator_kind != "programmer":
            raise FabricationValidationError("OpenOCD handle requires a programmer execution plan")
        if plan.operator_id != self.operator_id:
            raise FabricationValidationError("OpenOCD plan targets a different operator")
        if plan.action == "inspect_target":
            return {
                "schema": "hardware_splicer.programmer_observation.v1",
                "backend": "openocd",
                **self.backend.targets.public_descriptor(self.target_id),
                "physical_correctness": "UNPROVEN",
            }
        if plan.action == "stage_firmware":
            artifact = self._artifact(plan.payload)
            self._staged_sha256 = artifact["sha256"]
            return {
                "schema": "hardware_splicer.programmer_stage.v1",
                "backend": "openocd",
                "target_id": self.target_id,
                "artifact_id": artifact["artifact_id"],
                "artifact_sha256": artifact["sha256"],
            }
        if plan.action == "flash":
            artifact = self.artifacts.verify_plan_artifact(plan)
            bindings = plan.payload.get("bindings") if isinstance(plan.payload, Mapping) else None
            if not isinstance(bindings, Mapping) or bindings.get("target_id") != self.target_id:
                raise FabricationValidationError("OpenOCD flash plan is not bound to configured target identity")
            if self._staged_sha256 != artifact.sha256:
                raise FabricationValidationError("firmware must be staged before OpenOCD flash")
            fmt = artifact.metadata.get("format") if isinstance(artifact.metadata, Mapping) else None
            result = self.backend.program_and_verify(
                self.target_id,
                self.artifacts.bytes(artifact.artifact_id),
                firmware_format=fmt,
            )
            return {
                "schema": "hardware_splicer.programmer_flash_receipt.v1",
                "backend": "openocd",
                "target_id": self.target_id,
                "artifact_id": artifact.artifact_id,
                "artifact_sha256": artifact.sha256,
                "verified": True,
                "auto_execute": False,
                "auto_reboot": False,
                "result": result,
                "physical_correctness": "UNPROVEN",
            }
        if plan.action == "abort":
            raise FabricationValidationError("OpenOCD v0 does not expose a generic asynchronous abort")
        raise FabricationValidationError(f"unsupported OpenOCD programmer action {plan.action!r}")

    def _artifact(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if not isinstance(payload, Mapping) or not isinstance(payload.get("artifact_id"), str):
            raise FabricationValidationError("OpenOCD stage requires artifact_id")
        artifact = self.artifacts.describe(payload["artifact_id"])
        if artifact.get("kind") != "firmware":
            raise FabricationValidationError("OpenOCD stage requires a firmware artifact")
        _format((artifact.get("metadata") or {}).get("format"))
        return artifact


def _format(value: Any) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError("firmware metadata.format is required for OpenOCD")
    normalized = value.strip().lower()
    aliases = {"ihex": "hex", "intel_hex": "hex", "srec": "s19"}
    normalized = aliases.get(normalized, normalized)
    if normalized not in {"elf", "hex", "s19", "bin"}:
        raise FabricationValidationError("OpenOCD firmware format must be elf, hex, s19, or bin")
    return normalized


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 128 or any(not (ch.isalnum() or ch in "._:-") for ch in cleaned):
        raise FabricationValidationError(f"{field} must be a bounded identifier")
    return cleaned


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
