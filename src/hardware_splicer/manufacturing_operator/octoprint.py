"""Local OctoPrint manufacturing adapter — stage-only, never auto-start.

This is a real adapter for a desktop agent's constrained tool surface, not
proof of fabrication. It intentionally exposes no arbitrary G-code commands,
heater control, motor movement, or print-start operation.
"""
from __future__ import annotations

import hashlib
import ipaddress
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx

MAX_GCODE_BYTES = 32 * 1024 * 1024


class ManufacturingRefusal(ValueError):
    """A potentially unsafe machine operation was not attempted."""


def validate_local_printer_url(base_url: str) -> str:
    parsed = urlsplit(base_url)
    if parsed.scheme != "http" or not parsed.hostname:
        raise ManufacturingRefusal("v0 only supports locally hosted HTTP printer controllers")
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise ManufacturingRefusal("Printer endpoint must be an origin, not a credentialed URL or path")
    if parsed.hostname != "localhost":
        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError as exc:
            raise ManufacturingRefusal("Use localhost or a numeric private/loopback/LAN IP address") from exc
        if not (address.is_private or address.is_loopback or address.is_link_local):
            raise ManufacturingRefusal("Public printer endpoints are not allowed")
        if address.is_multicast or address.is_unspecified or address.is_reserved:
            raise ManufacturingRefusal("Unusable printer endpoint")
    if parsed.port is not None and not (1 <= parsed.port <= 65535):
        raise ManufacturingRefusal("Invalid local printer port")
    return base_url.rstrip("/")


@dataclass(frozen=True)
class StagedPrintReceipt:
    schema_version: str
    printer_endpoint: str
    filename: str
    gcode_sha256: str
    gcode_bytes: int
    printer_state_before_upload: str
    staged_only: bool = True
    start_requested: bool = False
    human_start_approval_obtained: bool = False
    fabricated_object_verified: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


class OctoPrintOperator:
    """A deliberately limited, single-printer machine interface.

    The API key must come from the desktop's local credential store, not from
    LLM-generated configuration. Never expose this class's HTTP client as an
    arbitrary-URL or arbitrary-command agent tool.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        origin = validate_local_printer_url(base_url)
        if not api_key or api_key.isspace():
            raise ManufacturingRefusal("A locally configured OctoPrint API key is required")
        self.endpoint = origin
        self._http = httpx.Client(
            base_url=origin,
            headers={"X-Api-Key": api_key},
            timeout=httpx.Timeout(10.0, connect=3.0),
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "OctoPrintOperator":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def printer_status(self) -> dict:
        """Read machine state; do not cause motion, extrusion or heating."""
        response = self._http.get("/api/printer")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("state"), dict):
            raise ManufacturingRefusal("Printer did not supply a recognized state")
        return payload

    def stage_gcode(self, gcode: Path) -> StagedPrintReceipt:
        """Upload without selecting or starting; requires a separate trusted UI to start.

        A successful stage does NOT mean that the G-code is safe or printable.
        """
        path = Path(gcode)
        if not path.is_file() or path.suffix.lower() not in (".gcode", ".gco"):
            raise ManufacturingRefusal("A pre-sliced local G-code file is required")
        length = path.stat().st_size
        if not (0 < length <= MAX_GCODE_BYTES):
            raise ManufacturingRefusal("G-code must be nonempty and within the v0 32 MiB limit")
        payload = path.read_bytes()
        if len(payload) != length:
            raise ManufacturingRefusal("G-code changed while reading")
        before = hashlib.sha256(payload).hexdigest()
        status = self.printer_status()
        state = status["state"]
        flags = state.get("flags") or {}
        if not isinstance(flags, dict) or (
            not flags.get("operational")
            or flags.get("printing") or flags.get("paused") or flags.get("error")
            or flags.get("closedOrError")
        ):
            raise ManufacturingRefusal("Printer is not idle and operational; upload refused")
        response = self._http.post(
            "/api/files/local",
            data={"select": "false", "print": "false"},
            files={"file": (path.name, payload, "application/octet-stream")},
        )
        if response.status_code != 201:
            raise ManufacturingRefusal(f"OctoPrint refused staging (HTTP {response.status_code})")
        if hashlib.sha256(path.read_bytes()).hexdigest() != before:
            raise ManufacturingRefusal("Local G-code changed during upload; invalidate staged file")
        return StagedPrintReceipt(
            schema_version="hardware_splicer.octoprint_staging.v0",
            printer_endpoint=self.endpoint,
            filename=path.name,
            gcode_sha256=before,
            gcode_bytes=length,
            printer_state_before_upload=str(state.get("text", "unknown")),
        )
