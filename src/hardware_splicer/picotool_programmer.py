"""RP-series programmer adapter for the generic physical control plane.

Uses Raspberry Pi's ``picotool`` through a fixed argv/no-shell runner.  Target
selection is server configuration, never agent input.  Firmware must already be
a registered immutable artifact and must be staged before flash.  Flash runs
``load -v`` followed by an independent ``verify``; it deliberately does not use
``-x`` or reboot/execute the target automatically.

Reference command contract: https://github.com/raspberrypi/picotool
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from .fabrication_operator import FabricationValidationError
from .physical_artifact import PhysicalArtifactRegistry
from .physical_operator import PhysicalExecutionPlan


class PicotoolExecutionError(RuntimeError):
    pass


class CommandRunner(Protocol):
    def __call__(self, argv: Sequence[str], *, timeout: int) -> subprocess.CompletedProcess[bytes]: ...


def _default_runner(argv: Sequence[str], *, timeout: int) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        list(argv),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=timeout,
        shell=False,
    )


class PicotoolRunner:
    def __init__(
        self,
        executable: str = "picotool",
        *,
        device_selector: Sequence[str] = (),
        timeout_seconds: int = 120,
        runner: CommandRunner | None = None,
    ):
        if not isinstance(executable, str) or not executable.strip():
            raise FabricationValidationError("picotool executable is required")
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 600:
            raise FabricationValidationError("picotool timeout must be an integer from 1 to 600 seconds")
        clean_selector = []
        for item in device_selector:
            if not isinstance(item, str) or not item or any(ch in item for ch in "\r\n\x00"):
                raise FabricationValidationError("picotool device selector contains invalid text")
            clean_selector.append(item)
        self.executable = executable.strip()
        self.device_selector = tuple(clean_selector)
        self.timeout_seconds = timeout_seconds
        self._runner = runner or _default_runner

    def _run(self, argv: Sequence[str]) -> dict[str, Any]:
        try:
            completed = self._runner(tuple(argv), timeout=self.timeout_seconds)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PicotoolExecutionError("picotool execution failed") from exc
        stdout = completed.stdout.decode("utf-8", errors="replace")[-8000:]
        stderr = completed.stderr.decode("utf-8", errors="replace")[-8000:]
        if completed.returncode != 0:
            raise PicotoolExecutionError(
                f"picotool exited with {completed.returncode}: {stderr or stdout}"
            )
        return {"returncode": completed.returncode, "stdout": stdout, "stderr": stderr}

    def info(self) -> dict[str, Any]:
        return self._run([self.executable, "info", "-a", *self.device_selector])

    def flash_and_verify(self, firmware: bytes, *, suffix: str = ".uf2") -> dict[str, Any]:
        if not isinstance(firmware, (bytes, bytearray)) or not firmware:
            raise FabricationValidationError("firmware must be non-empty bytes")
        if suffix not in {".uf2", ".elf", ".bin"}:
            raise FabricationValidationError("picotool firmware suffix must be .uf2, .elf or .bin")
        with tempfile.TemporaryDirectory(prefix="hs-picotool-") as temp_dir:
            path = Path(temp_dir) / f"firmware{suffix}"
            path.write_bytes(bytes(firmware))
            load = self._run(
                [self.executable, "load", "-v", str(path), *self.device_selector]
            )
            verify = self._run(
                [self.executable, "verify", str(path), *self.device_selector]
            )
        return {
            "load": load,
            "verify": verify,
            "auto_execute": False,
            "auto_reboot": False,
        }


class PicotoolProgrammerHandle:
    """Private physical handle used only behind PhysicalDispatcher."""

    def __init__(
        self,
        *,
        operator_id: str,
        target_id: str,
        artifacts: PhysicalArtifactRegistry,
        picotool: PicotoolRunner,
        firmware_suffix: str = ".uf2",
    ):
        if not isinstance(operator_id, str) or not operator_id.strip():
            raise FabricationValidationError("programmer operator_id is required")
        if not isinstance(target_id, str) or not target_id.strip():
            raise FabricationValidationError("programmer target_id is required")
        if firmware_suffix not in {".uf2", ".elf", ".bin"}:
            raise FabricationValidationError("unsupported programmer firmware suffix")
        self.operator_id = operator_id.strip()
        self.target_id = target_id.strip()
        self.artifacts = artifacts
        self.picotool = picotool
        self.firmware_suffix = firmware_suffix
        self._staged_sha256: str | None = None

    def execute(self, plan: PhysicalExecutionPlan) -> Mapping[str, Any]:
        if not isinstance(plan, PhysicalExecutionPlan) or plan.operator_kind != "programmer":
            raise FabricationValidationError("picotool handle requires a programmer execution plan")
        if plan.operator_id != self.operator_id:
            raise FabricationValidationError("programmer execution plan targets a different operator")

        if plan.action == "inspect_target":
            result = self.picotool.info()
            return {
                "schema": "hardware_splicer.programmer_observation.v1",
                "target_id": self.target_id,
                "backend": "picotool",
                "result": result,
            }
        if plan.action == "stage_firmware":
            artifact = self._artifact(plan.payload)
            if artifact["kind"] != "firmware":
                raise FabricationValidationError("programmer stage requires a firmware artifact")
            self._staged_sha256 = artifact["sha256"]
            return {
                "schema": "hardware_splicer.programmer_stage.v1",
                "target_id": self.target_id,
                "artifact_id": artifact["artifact_id"],
                "artifact_sha256": artifact["sha256"],
            }
        if plan.action == "flash":
            artifact = self.artifacts.verify_plan_artifact(plan)
            bindings = plan.payload.get("bindings") if isinstance(plan.payload, Mapping) else None
            if not isinstance(bindings, Mapping) or bindings.get("target_id") != self.target_id:
                raise FabricationValidationError("flash plan is not bound to the configured target identity")
            if self._staged_sha256 != artifact.sha256:
                raise FabricationValidationError("firmware must be staged before flash")
            result = self.picotool.flash_and_verify(
                self.artifacts.bytes(artifact.artifact_id),
                suffix=self.firmware_suffix,
            )
            return {
                "schema": "hardware_splicer.programmer_flash_receipt.v1",
                "target_id": self.target_id,
                "artifact_id": artifact.artifact_id,
                "artifact_sha256": artifact.sha256,
                "verified": True,
                "auto_execute": False,
                "auto_reboot": False,
                "backend": "picotool",
                "result": result,
            }
        if plan.action == "abort":
            raise FabricationValidationError("picotool synchronous backend has no safe generic abort operation")
        raise FabricationValidationError(f"unsupported picotool programmer action {plan.action!r}")

    def _artifact(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if not isinstance(payload, Mapping) or not isinstance(payload.get("artifact_id"), str):
            raise FabricationValidationError("programmer stage requires artifact_id")
        return self.artifacts.describe(payload["artifact_id"])
