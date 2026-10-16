"""Normalized 3D-printer operator with explicit physical authority boundaries.

The operator deliberately separates preparing a print from making a machine
move or heat. Staging G-code and reading printer status need no physical grant.
Starting or resuming a job consumes a one-shot human grant bound to the exact
G-code hash and printer. Pause and cancel are safety-reducing actions and do
not mint or escalate authority.

Backends describe OctoPrint and Moonraker request shapes behind an injected
transport. Tests use an in-memory transport; importing this module never opens
a socket or contacts a printer.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Protocol
from urllib.parse import quote

from .fabrication_operator import FabricationGrantStore, FabricationValidationError


class PrinterTransport(Protocol):
    """Small transport seam so printer control is testable without a device."""

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]: ...

    def upload(
        self,
        path: str,
        *,
        filename: str,
        data: bytes,
        fields: Mapping[str, str],
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class PreparedPrint:
    schema: str
    printer_id: str
    backend: str
    artifact_sha256: str
    remote_path: str
    size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PrintRun:
    schema: str
    project_id: str
    mission_id: str
    printer_id: str
    backend: str
    artifact_sha256: str
    remote_path: str
    started_with_grant_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PrinterBackend(Protocol):
    name: str

    def stage(self, transport: PrinterTransport, *, filename: str, data: bytes) -> str: ...
    def status(self, transport: PrinterTransport) -> Mapping[str, Any]: ...
    def start(self, transport: PrinterTransport, prepared: PreparedPrint) -> Mapping[str, Any]: ...
    def pause(self, transport: PrinterTransport) -> Mapping[str, Any]: ...
    def resume(self, transport: PrinterTransport) -> Mapping[str, Any]: ...
    def cancel(self, transport: PrinterTransport) -> Mapping[str, Any]: ...


def _filename(value: str) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError("filename must be a string")
    cleaned = value.strip().replace("\\", "/").split("/")[-1]
    if not cleaned or cleaned in {".", ".."} or len(cleaned) > 180:
        raise FabricationValidationError("filename must be a bounded basename")
    if not cleaned.lower().endswith((".gcode", ".gco", ".g")):
        raise FabricationValidationError("printer operator stages G-code only")
    if any(ord(ch) < 32 for ch in cleaned):
        raise FabricationValidationError("filename must not contain control characters")
    return cleaned


def _bytes(value: bytes | bytearray) -> bytes:
    if not isinstance(value, (bytes, bytearray)) or not value:
        raise FabricationValidationError("G-code payload must be non-empty bytes")
    return bytes(value)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


class OctoPrintBackend:
    """OctoPrint REST request mapping.

    Upload explicitly selects but does not print the file. The later `/api/job`
    start command is the physical boundary guarded by a human grant.
    """

    name = "octoprint"

    def stage(self, transport: PrinterTransport, *, filename: str, data: bytes) -> str:
        response = transport.upload(
            "/api/files/local",
            filename=filename,
            data=data,
            fields={"select": "true", "print": "false"},
        )
        files = _mapping(response.get("files"))
        local = _mapping(files.get("local"))
        remote = local.get("path") or local.get("name") or filename
        return str(remote)

    def status(self, transport: PrinterTransport) -> Mapping[str, Any]:
        return {
            "backend": self.name,
            "job": dict(transport.request("GET", "/api/job")),
            "printer": dict(transport.request("GET", "/api/printer")),
        }

    def start(self, transport: PrinterTransport, prepared: PreparedPrint) -> Mapping[str, Any]:
        return transport.request("POST", "/api/job", json_body={"command": "start"})

    def pause(self, transport: PrinterTransport) -> Mapping[str, Any]:
        return transport.request("POST", "/api/job", json_body={"command": "pause", "action": "pause"})

    def resume(self, transport: PrinterTransport) -> Mapping[str, Any]:
        return transport.request("POST", "/api/job", json_body={"command": "pause", "action": "resume"})

    def cancel(self, transport: PrinterTransport) -> Mapping[str, Any]:
        return transport.request("POST", "/api/job", json_body={"command": "cancel"})


class MoonrakerBackend:
    """Moonraker/Klipper request mapping."""

    name = "moonraker"

    def stage(self, transport: PrinterTransport, *, filename: str, data: bytes) -> str:
        response = transport.upload(
            "/server/files/upload",
            filename=filename,
            data=data,
            fields={"root": "gcodes", "path": "", "print": "false"},
        )
        item = _mapping(response.get("item"))
        remote = item.get("path") or item.get("filename") or filename
        return str(remote)

    def status(self, transport: PrinterTransport) -> Mapping[str, Any]:
        path = "/printer/objects/query?print_stats&virtual_sdcard&extruder&heater_bed"
        return {"backend": self.name, "printer": dict(transport.request("GET", path))}

    def start(self, transport: PrinterTransport, prepared: PreparedPrint) -> Mapping[str, Any]:
        remote = quote(prepared.remote_path, safe="/")
        return transport.request("POST", f"/printer/print/start?filename={remote}")

    def pause(self, transport: PrinterTransport) -> Mapping[str, Any]:
        return transport.request("POST", "/printer/print/pause")

    def resume(self, transport: PrinterTransport) -> Mapping[str, Any]:
        return transport.request("POST", "/printer/print/resume")

    def cancel(self, transport: PrinterTransport) -> Mapping[str, Any]:
        return transport.request("POST", "/printer/print/cancel")


class FabricationPrinter:
    """One normalized printer endpoint controlled by explicit human grants."""

    def __init__(
        self,
        *,
        printer_id: str,
        backend: PrinterBackend,
        transport: PrinterTransport,
        grants: FabricationGrantStore,
    ):
        if not isinstance(printer_id, str) or not printer_id.strip():
            raise FabricationValidationError("printer_id is required")
        self.printer_id = printer_id.strip()
        self.backend = backend
        self.transport = transport
        self.grants = grants

    def stage_gcode(self, *, filename: str, data: bytes | bytearray) -> PreparedPrint:
        """Upload/select G-code without starting physical fabrication."""

        safe_name = _filename(filename)
        payload = _bytes(data)
        digest = hashlib.sha256(payload).hexdigest()
        remote = self.backend.stage(self.transport, filename=safe_name, data=payload)
        return PreparedPrint(
            schema="hardware_splicer.prepared_print.v1",
            printer_id=self.printer_id,
            backend=self.backend.name,
            artifact_sha256=digest,
            remote_path=remote,
            size_bytes=len(payload),
        )

    def status(self) -> dict[str, Any]:
        """Read machine/job state. Reading state grants no physical authority."""

        return {
            "schema": "hardware_splicer.printer_observation.v1",
            "printer_id": self.printer_id,
            "physical_correctness": "UNPROVEN",
            "observation": json.loads(json.dumps(self.backend.status(self.transport))),
        }

    def start(
        self,
        prepared: PreparedPrint,
        *,
        project_id: str,
        mission_id: str,
        grant_id: str,
    ) -> PrintRun:
        self._prepared_for_this_printer(prepared)
        # Consume before sending the command. Ambiguous transport failure cannot
        # be retried without a fresh human approval.
        self.grants.consume(
            grant_id,
            project_id=project_id,
            mission_id=mission_id,
            operator_id=self.printer_id,
            action="start",
            artifact_sha256=prepared.artifact_sha256,
        )
        self.backend.start(self.transport, prepared)
        return PrintRun(
            schema="hardware_splicer.print_run.v1",
            project_id=project_id,
            mission_id=mission_id,
            printer_id=self.printer_id,
            backend=self.backend.name,
            artifact_sha256=prepared.artifact_sha256,
            remote_path=prepared.remote_path,
            started_with_grant_id=grant_id,
        )

    def pause(self, run: PrintRun) -> Mapping[str, Any]:
        self._run_for_this_printer(run)
        return self.backend.pause(self.transport)

    def cancel(self, run: PrintRun) -> Mapping[str, Any]:
        self._run_for_this_printer(run)
        return self.backend.cancel(self.transport)

    def resume(self, run: PrintRun, *, grant_id: str) -> Mapping[str, Any]:
        self._run_for_this_printer(run)
        self.grants.consume(
            grant_id,
            project_id=run.project_id,
            mission_id=run.mission_id,
            operator_id=self.printer_id,
            action="resume",
            artifact_sha256=run.artifact_sha256,
        )
        return self.backend.resume(self.transport)

    def _prepared_for_this_printer(self, prepared: PreparedPrint) -> None:
        if not isinstance(prepared, PreparedPrint):
            raise FabricationValidationError("start requires a server-created PreparedPrint")
        if prepared.printer_id != self.printer_id or prepared.backend != self.backend.name:
            raise FabricationValidationError("prepared print belongs to a different printer/backend")

    def _run_for_this_printer(self, run: PrintRun) -> None:
        if not isinstance(run, PrintRun):
            raise FabricationValidationError("operation requires a server-created PrintRun")
        if run.printer_id != self.printer_id or run.backend != self.backend.name:
            raise FabricationValidationError("print run belongs to a different printer/backend")
