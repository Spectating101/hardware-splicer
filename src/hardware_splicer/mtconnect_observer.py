"""Read-only MTConnect observer for manufacturing equipment.

MTConnect is used as an observation protocol only. The adapter supports the
standard probe/current/sample GET flows, retains exact XML bytes in the physical
observation store, and exposes a small parsed summary. It has no command or
write path and therefore cannot control the observed equipment.
"""

from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import httpx

from .fabrication_operator import FabricationValidationError
from .physical_observation_store import PhysicalObservationStore

_MAX_XML_BYTES = 16 * 1024 * 1024


class MtconnectExecutionError(RuntimeError):
    pass


class MtconnectObserver:
    def __init__(
        self,
        *,
        source_id: str,
        base_url: str,
        observations: PhysicalObservationStore,
        headers: Mapping[str, str] | None = None,
        client: httpx.Client | None = None,
        timeout_seconds: float = 5.0,
    ):
        if not isinstance(source_id, str) or not source_id.strip() or len(source_id.strip()) > 128:
            raise FabricationValidationError("MTConnect source_id must be bounded text")
        if any(ord(ch) < 32 for ch in source_id):
            raise FabricationValidationError("MTConnect source_id must be printable text")
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
            raise FabricationValidationError("MTConnect base_url must be server-configured http(s) without credentials")
        if parsed.query or parsed.fragment:
            raise FabricationValidationError("MTConnect base_url must not contain query or fragment")
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or not 0.1 <= float(timeout_seconds) <= 30:
            raise FabricationValidationError("MTConnect timeout must be between 0.1 and 30 seconds")
        clean_headers: dict[str, str] = {}
        for key, value in dict(headers or {}).items():
            if not isinstance(key, str) or not isinstance(value, str) or any(ch in key + value for ch in "\r\n\x00"):
                raise FabricationValidationError("MTConnect headers must be server-configured text")
            clean_headers[key] = value
        self.source_id = source_id.strip()
        self.base_url = base_url.rstrip("/")
        self.observations = observations
        self.timeout_seconds = float(timeout_seconds)
        self._owns_client = client is None
        self.client = client or httpx.Client(
            headers=clean_headers,
            timeout=self.timeout_seconds,
            follow_redirects=False,
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def probe(self) -> dict[str, Any]:
        return self._capture("probe", "/probe", params=None, kind="machine_telemetry")

    def current(self) -> dict[str, Any]:
        return self._capture("current", "/current", params=None, kind="machine_telemetry")

    def sample(self, *, from_sequence: int, count: int = 1000) -> dict[str, Any]:
        if type(from_sequence) is not int or from_sequence < 1:
            raise FabricationValidationError("MTConnect from_sequence must be a positive integer")
        if type(count) is not int or not 1 <= count <= 10000:
            raise FabricationValidationError("MTConnect sample count must be 1..10000")
        return self._capture(
            "sample",
            "/sample",
            params={"from": str(from_sequence), "count": str(count)},
            kind="machine_telemetry",
        )

    def _capture(
        self,
        operation: str,
        path: str,
        *,
        params: Mapping[str, str] | None,
        kind: str,
    ) -> dict[str, Any]:
        chunks: list[bytes] = []
        total = 0
        try:
            with self.client.stream(
                "GET",
                f"{self.base_url}{path}",
                params=dict(params or {}),
            ) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "application/xml").split(";", 1)[0].strip()
                if "xml" not in content_type.lower():
                    raise MtconnectExecutionError("MTConnect response is not XML")
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > _MAX_XML_BYTES:
                        raise MtconnectExecutionError("MTConnect response exceeded configured size limit")
                    chunks.append(chunk)
                status_code = response.status_code
        except MtconnectExecutionError:
            raise
        except httpx.HTTPError as exc:
            raise MtconnectExecutionError(f"MTConnect {operation} failed") from exc
        data = b"".join(chunks)
        if not data:
            raise MtconnectExecutionError("MTConnect response is empty")
        summary = _xml_summary(data)
        record = self.observations.put(
            kind=kind,
            source_id=self.source_id,
            media_type=content_type or "application/xml",
            data=data,
            metadata={
                "protocol": "mtconnect",
                "operation": operation,
                "http_status": status_code,
                "root_element": summary["root_element"],
                "header": summary["header"],
                "device_count": summary["device_count"],
                "data_item_count": summary["data_item_count"],
                "stream_value_count": summary["stream_value_count"],
            },
        )
        return {
            "schema": "hardware_splicer.mtconnect_observation.v1",
            "source_id": self.source_id,
            "operation": operation,
            "summary": summary,
            "observation": record.public_dict(),
            "read_only": True,
            "physical_correctness": "UNPROVEN",
        }


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _xml_summary(data: bytes) -> dict[str, Any]:
    prefix = data[:8192].upper()
    if b"<!DOCTYPE" in prefix or b"<!ENTITY" in prefix:
        raise MtconnectExecutionError("MTConnect XML must not contain DTD/entity declarations")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise MtconnectExecutionError("MTConnect XML is malformed") from exc
    header: dict[str, str] = {}
    device_count = 0
    data_item_count = 0
    stream_value_count = 0
    for element in root.iter():
        name = _local(element.tag)
        if name == "Header" and not header:
            for key in ("instanceId", "nextSequence", "firstSequence", "lastSequence", "version", "creationTime"):
                if key in element.attrib:
                    header[key] = element.attrib[key]
        elif name == "Device":
            device_count += 1
        elif name == "DataItem":
            data_item_count += 1
        elif name not in {
            "MTConnectDevices", "MTConnectStreams", "MTConnectError", "Header",
            "Devices", "Device", "Components", "Component", "DataItems", "DataItem",
            "Streams", "DeviceStream", "ComponentStream", "Samples", "Events", "Condition",
        } and ("sequence" in element.attrib or "dataItemId" in element.attrib):
            stream_value_count += 1
    return {
        "root_element": _local(root.tag),
        "header": header,
        "device_count": device_count,
        "data_item_count": data_item_count,
        "stream_value_count": stream_value_count,
    }
