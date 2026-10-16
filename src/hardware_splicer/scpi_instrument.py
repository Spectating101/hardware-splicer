"""Read-first SCPI bench-instrument adapter.

The language model selects a server-declared measurement id, never raw SCPI.
This first adapter intentionally supports observation only.  Output/configuration
writes remain disabled until a bounded recipe executor is separately reviewed.
A socket transport is provided for lab instruments that expose SCPI-over-TCP;
host/port and query mappings are server configuration, not mission input.
"""

from __future__ import annotations

import socket
from typing import Any, Mapping, Protocol

from .fabrication_operator import FabricationValidationError
from .physical_operator import PhysicalExecutionPlan


class ScpiExecutionError(RuntimeError):
    pass


class ScpiQueryTransport(Protocol):
    def query(self, command: str) -> str: ...


class SocketScpiTransport:
    def __init__(
        self,
        host: str,
        *,
        port: int = 5025,
        timeout_seconds: float = 3.0,
        max_response_bytes: int = 65536,
    ):
        if not isinstance(host, str) or not host.strip() or any(ch in host for ch in "\r\n\x00"):
            raise FabricationValidationError("SCPI host must be server-configured text")
        if type(port) is not int or not 1 <= port <= 65535:
            raise FabricationValidationError("SCPI port must be 1..65535")
        if type(timeout_seconds) not in {int, float} or not 0.1 <= float(timeout_seconds) <= 30:
            raise FabricationValidationError("SCPI timeout must be between 0.1 and 30 seconds")
        if type(max_response_bytes) is not int or not 1 <= max_response_bytes <= 1024 * 1024:
            raise FabricationValidationError("SCPI response limit is invalid")
        self.host = host.strip()
        self.port = port
        self.timeout_seconds = float(timeout_seconds)
        self.max_response_bytes = max_response_bytes

    def query(self, command: str) -> str:
        if not isinstance(command, str) or not command or any(ch in command for ch in "\r\n\x00"):
            raise FabricationValidationError("SCPI query command is invalid")
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout_seconds) as sock:
                sock.settimeout(self.timeout_seconds)
                sock.sendall(command.encode("ascii") + b"\n")
                chunks: list[bytes] = []
                total = 0
                while True:
                    chunk = sock.recv(min(4096, self.max_response_bytes - total))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                    if b"\n" in chunk:
                        break
                    if total >= self.max_response_bytes:
                        raise ScpiExecutionError("SCPI response exceeded configured limit")
        except (OSError, UnicodeEncodeError) as exc:
            raise ScpiExecutionError("SCPI query failed") from exc
        data = b"".join(chunks)
        try:
            return data.decode("utf-8", errors="replace").strip()
        except Exception as exc:  # pragma: no cover
            raise ScpiExecutionError("SCPI response could not be decoded") from exc


class ScpiReadOnlyHandle:
    """Private physical handle exposing configured observation ids only."""

    def __init__(
        self,
        *,
        operator_id: str,
        transport: ScpiQueryTransport,
        measurements: Mapping[str, str],
        identity_query: str = "*IDN?",
    ):
        if not isinstance(operator_id, str) or not operator_id.strip():
            raise FabricationValidationError("instrument operator_id is required")
        if not isinstance(measurements, Mapping) or not measurements:
            raise FabricationValidationError("SCPI measurements must be a non-empty mapping")
        clean: dict[str, str] = {}
        for key, command in measurements.items():
            if not isinstance(key, str) or not key.strip() or any(ch.isspace() for ch in key.strip()):
                raise FabricationValidationError("SCPI measurement ids must be bounded identifiers")
            if not isinstance(command, str) or not command or any(ch in command for ch in "\r\n\x00"):
                raise FabricationValidationError("SCPI configured queries contain invalid text")
            clean[key.strip()] = command
        if not isinstance(identity_query, str) or not identity_query or any(ch in identity_query for ch in "\r\n\x00"):
            raise FabricationValidationError("SCPI identity query is invalid")
        self.operator_id = operator_id.strip()
        self.transport = transport
        self.measurements = clean
        self.identity_query = identity_query

    def execute(self, plan: PhysicalExecutionPlan) -> Mapping[str, Any]:
        if not isinstance(plan, PhysicalExecutionPlan) or plan.operator_kind != "instrument":
            raise FabricationValidationError("SCPI handle requires an instrument execution plan")
        if plan.operator_id != self.operator_id:
            raise FabricationValidationError("instrument execution plan targets a different operator")
        if plan.action == "status":
            return {
                "schema": "hardware_splicer.instrument_observation.v1",
                "operator_id": self.operator_id,
                "measurement_id": "identity",
                "value": self.transport.query(self.identity_query),
                "physical_correctness": "UNPROVEN",
            }
        if plan.action == "read":
            measurement_id = plan.payload.get("measurement_id") if isinstance(plan.payload, Mapping) else None
            if not isinstance(measurement_id, str) or measurement_id not in self.measurements:
                raise FabricationValidationError("unknown configured SCPI measurement_id")
            return {
                "schema": "hardware_splicer.instrument_observation.v1",
                "operator_id": self.operator_id,
                "measurement_id": measurement_id,
                "value": self.transport.query(self.measurements[measurement_id]),
                "physical_correctness": "UNPROVEN",
            }
        if plan.action in {"configure", "enable_output", "disable_output"}:
            raise FabricationValidationError("read-only SCPI adapter does not permit instrument writes")
        raise FabricationValidationError(f"unsupported SCPI instrument action {plan.action!r}")
