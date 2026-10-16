"""Read-only OPC UA observation adapter.

The agent chooses bounded measurement ids; server configuration owns the OPC UA
endpoint, credentials/security and node ids. Values are captured as canonical
JSON into the immutable physical observation store and remain UNPROVEN until a
separate physical-evidence procedure promotes them.

A small backend protocol keeps tests dependency-free. ``AsyncUaReadBackend`` is
an optional live implementation loaded lazily when ``asyncua`` is installed.
No write/call/subscription-control surface is exposed here.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from .fabrication_operator import FabricationValidationError
from .physical_observation_store import PhysicalObservationStore


class OpcUaExecutionError(RuntimeError):
    pass


class OpcUaReadBackend(Protocol):
    def read_values(self, node_ids: Sequence[str]) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class OpcUaMeasurement:
    measurement_id: str
    node_id: str
    unit: str | None = None


class OpcUaMeasurementRegistry:
    def __init__(self) -> None:
        self._rows: dict[str, OpcUaMeasurement] = {}

    def register(self, *, measurement_id: str, node_id: str, unit: str | None = None) -> None:
        mid = _id(measurement_id, "measurement_id")
        if mid in self._rows:
            raise FabricationValidationError("OPC UA measurement id is already registered")
        if not isinstance(node_id, str) or not node_id.strip() or len(node_id.strip()) > 512:
            raise FabricationValidationError("OPC UA node id must be bounded server-owned text")
        if any(ch in node_id for ch in "\r\n\x00"):
            raise FabricationValidationError("OPC UA node id contains control characters")
        if unit is not None and (not isinstance(unit, str) or not unit.strip() or len(unit.strip()) > 64):
            raise FabricationValidationError("OPC UA unit must be bounded text")
        self._rows[mid] = OpcUaMeasurement(mid, node_id.strip(), unit.strip() if unit else None)

    def get(self, measurement_id: str) -> OpcUaMeasurement:
        try:
            return self._rows[measurement_id]
        except KeyError as exc:
            raise FabricationValidationError("unknown OPC UA measurement id") from exc

    def list_public(self) -> list[dict[str, Any]]:
        return [
            {"measurement_id": row.measurement_id, "unit": row.unit}
            for row in sorted(self._rows.values(), key=lambda item: item.measurement_id)
        ]


class AsyncUaReadBackend:
    """Optional live backend using FreeOpcUa/asyncua.

    Endpoint/security credentials are constructor inputs supplied only by server
    configuration. The public fabricator API never accepts them.
    """

    def __init__(self, *, endpoint: str, timeout_seconds: float = 5.0) -> None:
        if not isinstance(endpoint, str) or not endpoint.startswith("opc.tcp://") or any(ch in endpoint for ch in "\r\n\x00"):
            raise FabricationValidationError("OPC UA endpoint must be a server-configured opc.tcp URL")
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or not 0.1 <= float(timeout_seconds) <= 30:
            raise FabricationValidationError("OPC UA timeout must be between 0.1 and 30 seconds")
        self.endpoint = endpoint
        self.timeout_seconds = float(timeout_seconds)

    def read_values(self, node_ids: Sequence[str]) -> Mapping[str, Any]:
        try:
            return asyncio.run(self._read(node_ids))
        except RuntimeError as exc:
            raise OpcUaExecutionError("OPC UA read requires a synchronous worker context") from exc

    async def _read(self, node_ids: Sequence[str]) -> Mapping[str, Any]:
        try:
            from asyncua import Client  # type: ignore
        except ImportError as exc:
            raise OpcUaExecutionError("live OPC UA support requires the optional asyncua package") from exc
        try:
            async with Client(url=self.endpoint, timeout=self.timeout_seconds) as client:
                values: dict[str, Any] = {}
                for node_id in node_ids:
                    values[node_id] = await client.get_node(node_id).read_value()
                return values
        except Exception as exc:
            if isinstance(exc, OpcUaExecutionError):
                raise
            raise OpcUaExecutionError("OPC UA read failed") from exc


class OpcUaObserver:
    def __init__(
        self,
        *,
        source_id: str,
        measurements: OpcUaMeasurementRegistry,
        backend: OpcUaReadBackend,
        observations: PhysicalObservationStore,
    ) -> None:
        self.source_id = _id(source_id, "source_id")
        self.measurements = measurements
        self.backend = backend
        self.observations = observations

    def read(self, measurement_ids: Sequence[str]) -> dict[str, Any]:
        if isinstance(measurement_ids, (str, bytes, bytearray)) or not isinstance(measurement_ids, Sequence):
            raise FabricationValidationError("OPC UA measurement_ids must be a list")
        if not measurement_ids or len(measurement_ids) > 64:
            raise FabricationValidationError("OPC UA read requires 1..64 measurement ids")
        rows = [self.measurements.get(_id(value, "measurement_id")) for value in measurement_ids]
        if len({row.measurement_id for row in rows}) != len(rows):
            raise FabricationValidationError("OPC UA measurement ids must be unique")
        node_values = self.backend.read_values([row.node_id for row in rows])
        if not isinstance(node_values, Mapping):
            raise OpcUaExecutionError("OPC UA backend returned invalid data")
        values: list[dict[str, Any]] = []
        for row in rows:
            if row.node_id not in node_values:
                raise OpcUaExecutionError("OPC UA backend omitted a requested node")
            value = _json_value(node_values[row.node_id])
            values.append({
                "measurement_id": row.measurement_id,
                "value": value,
                "unit": row.unit,
            })
        payload = json.dumps(
            {"schema": "hardware_splicer.opcua_capture.v1", "source_id": self.source_id, "values": values},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        record = self.observations.put(
            kind="machine_telemetry",
            source_id=self.source_id,
            media_type="application/json",
            data=payload,
            metadata={
                "protocol": "opcua",
                "measurement_ids": [row.measurement_id for row in rows],
                "read_only": True,
            },
        )
        return {
            "schema": "hardware_splicer.opcua_observation.v1",
            "source_id": self.source_id,
            "values": values,
            "observation": record.public_dict(),
            "read_only": True,
            "physical_correctness": "UNPROVEN",
        }


def _json_value(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, default=str))
    except (TypeError, ValueError) as exc:
        raise OpcUaExecutionError("OPC UA value cannot be represented as bounded JSON") from exc


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 128 or any(not (ch.isalnum() or ch in "._:-") for ch in cleaned):
        raise FabricationValidationError(f"{field} must be a bounded identifier")
    return cleaned
