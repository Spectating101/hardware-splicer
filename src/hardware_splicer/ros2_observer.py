"""Read-only ROS 2 graph introspection for future workcell integration.

This adapter intentionally stops at graph observation. It can list nodes and
topics/types through fixed ``ros2`` CLI argv, retains the exact output as a raw
physical observation, and exposes no publish/service/action/motion operation.
A future live robot bridge must remain behind HS physical authority.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Protocol, Sequence

from .fabrication_operator import FabricationValidationError
from .physical_observation_store import PhysicalObservationStore


class Ros2ExecutionError(RuntimeError):
    pass


class Ros2Runner(Protocol):
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


class Ros2GraphObserver:
    def __init__(
        self,
        *,
        source_id: str,
        observations: PhysicalObservationStore,
        executable: str = "ros2",
        runner: Ros2Runner | None = None,
        timeout_seconds: int = 15,
    ) -> None:
        self.source_id = _id(source_id, "source_id")
        if not isinstance(executable, str) or not executable.strip() or any(ch in executable for ch in "\r\n\x00"):
            raise FabricationValidationError("ROS 2 executable must be server-configured text")
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 120:
            raise FabricationValidationError("ROS 2 timeout must be 1..120 seconds")
        self.observations = observations
        self.executable = executable.strip()
        self.runner = runner or _default_runner
        self.timeout_seconds = timeout_seconds

    def capture_graph(self) -> dict[str, Any]:
        nodes = self._run([self.executable, "node", "list"])
        topics = self._run([self.executable, "topic", "list", "-t"])
        value = {
            "schema": "hardware_splicer.ros2_graph_capture.v1",
            "source_id": self.source_id,
            "nodes": _lines(nodes["stdout"]),
            "topics": _lines(topics["stdout"]),
            "commands": [
                {"argv_shape": ["ros2", "node", "list"], "stdout_sha256": nodes["stdout_sha256"]},
                {"argv_shape": ["ros2", "topic", "list", "-t"], "stdout_sha256": topics["stdout_sha256"]},
            ],
            "read_only": True,
        }
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        record = self.observations.put(
            kind="machine_telemetry",
            source_id=self.source_id,
            media_type="application/json",
            data=payload,
            metadata={"protocol": "ros2", "read_only": True},
        )
        return {
            "schema": "hardware_splicer.ros2_graph_observation.v1",
            "source_id": self.source_id,
            "graph": value,
            "observation": record.public_dict(),
            "read_only": True,
            "physical_correctness": "UNPROVEN",
        }

    def _run(self, argv: list[str]) -> dict[str, Any]:
        try:
            completed = self.runner(argv, timeout=self.timeout_seconds)
        except (OSError, subprocess.SubprocessError) as exc:
            raise Ros2ExecutionError("ROS 2 graph introspection failed") from exc
        stdout = bytes(completed.stdout or b"")
        stderr = bytes(completed.stderr or b"")
        if completed.returncode != 0:
            message = (stderr or stdout).decode("utf-8", errors="replace")[-1000:]
            raise Ros2ExecutionError(f"ROS 2 CLI exited with {completed.returncode}: {message}")
        return {
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        }


def _lines(value: str) -> list[str]:
    rows = [line.strip() for line in value.splitlines() if line.strip()]
    if len(rows) > 10000:
        raise Ros2ExecutionError("ROS 2 graph output exceeded bounded row count")
    return rows


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 128 or any(not (ch.isalnum() or ch in "._:-") for ch in cleaned):
        raise FabricationValidationError(f"{field} must be a bounded identifier")
    return cleaned
