"""Read-only serial/console log capture for physical feedback.

The first live transport is a server-configured TCP serial bridge (for example a
lab-side ser2net-style endpoint).  Agents cannot choose host/port and this module
never writes bytes to the target.  Captured transcripts are retained in the
immutable PhysicalObservationStore and remain UNPROVEN until explicitly promoted
under a concrete test procedure and acceptance criteria.
"""

from __future__ import annotations

import socket
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol

from .fabrication_operator import FabricationValidationError
from .physical_observation_store import PhysicalObservationStore
from .physical_operator import PhysicalExecutionPlan

_MAX_CAPTURE_BYTES = 1024 * 1024


class SerialCaptureError(RuntimeError):
    pass


class SerialLogSource(Protocol):
    source_id: str

    def capture(self) -> tuple[bytes, Mapping[str, Any]]: ...


class TcpSerialLogSource:
    """Server-owned read-only TCP console source."""

    def __init__(
        self,
        *,
        source_id: str,
        host: str,
        port: int,
        idle_timeout_seconds: float = 1.0,
        max_capture_bytes: int = 64 * 1024,
    ):
        if not isinstance(source_id, str) or not source_id.strip() or len(source_id.strip()) > 128:
            raise FabricationValidationError("serial source_id must be a bounded string")
        if not isinstance(host, str) or not host.strip() or any(ch in host for ch in "\r\n\x00"):
            raise FabricationValidationError("serial host must be server-configured text")
        if type(port) is not int or not 1 <= port <= 65535:
            raise FabricationValidationError("serial port must be 1..65535")
        if type(idle_timeout_seconds) not in {int, float} or not 0.05 <= float(idle_timeout_seconds) <= 30:
            raise FabricationValidationError("serial idle timeout must be between 0.05 and 30 seconds")
        if type(max_capture_bytes) is not int or not 1 <= max_capture_bytes <= _MAX_CAPTURE_BYTES:
            raise FabricationValidationError("serial capture limit is invalid")
        self.source_id = source_id.strip()
        self.host = host.strip()
        self.port = port
        self.idle_timeout_seconds = float(idle_timeout_seconds)
        self.max_capture_bytes = max_capture_bytes

    def capture(self) -> tuple[bytes, Mapping[str, Any]]:
        chunks: list[bytes] = []
        total = 0
        try:
            with socket.create_connection((self.host, self.port), timeout=self.idle_timeout_seconds) as sock:
                sock.settimeout(self.idle_timeout_seconds)
                while total < self.max_capture_bytes:
                    try:
                        chunk = sock.recv(min(4096, self.max_capture_bytes - total))
                    except socket.timeout:
                        break
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
        except OSError as exc:
            raise SerialCaptureError("serial log capture failed") from exc
        data = b"".join(chunks)
        if not data:
            raise SerialCaptureError("serial log capture returned no bytes")
        return data, {
            "transport": "tcp_serial_bridge",
            "byte_count": len(data),
            "truncated": len(data) >= self.max_capture_bytes,
            "text_preview": data[:4096].decode("utf-8", errors="replace"),
        }


class SerialObservationHandle:
    """Private generic-operator handle that can only observe serial output."""

    def __init__(
        self,
        *,
        operator_id: str,
        source: SerialLogSource,
        observations: PhysicalObservationStore,
    ):
        if not isinstance(operator_id, str) or not operator_id.strip():
            raise FabricationValidationError("serial observer operator_id is required")
        self.operator_id = operator_id.strip()
        self.source = source
        self.observations = observations

    def execute(self, plan: PhysicalExecutionPlan) -> Mapping[str, Any]:
        if not isinstance(plan, PhysicalExecutionPlan):
            raise FabricationValidationError("serial observer requires a physical execution plan")
        if plan.operator_id != self.operator_id or plan.operator_kind != "instrument":
            raise FabricationValidationError("serial execution plan targets a different operator")
        if plan.action == "status":
            return {
                "schema": "hardware_splicer.serial_status.v1",
                "source_id": self.source.source_id,
                "available": True,
                "physical_correctness": "UNPROVEN",
            }
        if plan.action != "capture_log":
            raise FabricationValidationError(f"unsupported serial observer action {plan.action!r}")
        data, metadata = self.source.capture()
        record = self.observations.put(
            kind="serial_log",
            source_id=self.source.source_id,
            media_type="text/plain; charset=utf-8",
            data=data,
            metadata={
                **dict(metadata),
                "operator_id": self.operator_id,
                "capture_requested_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {
            "schema": "hardware_splicer.serial_observation.v1",
            "operator_id": self.operator_id,
            "source_id": self.source.source_id,
            "observation": record.public_dict(),
            "physical_correctness": "UNPROVEN",
            "interpretation_performed": False,
        }
