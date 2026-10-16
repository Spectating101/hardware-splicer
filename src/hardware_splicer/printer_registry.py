"""Server-side registry for physical printer operators.

Agents and missions refer to a stable ``printer_id``.  Network locations,
credentials and transport details remain server configuration and are never
returned by the public descriptor surface.  This prevents an agent from
turning the fabrication operator into an arbitrary HTTP client or selecting a
machine outside the operator-approved registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import httpx

from .fabrication_operator import FabricationGrantStore, FabricationValidationError
from .printer_operator import FabricationPrinter, MoonrakerBackend, OctoPrintBackend
from .printer_transport import HttpxPrinterTransport

_BACKENDS = {
    "octoprint": OctoPrintBackend,
    "moonraker": MoonrakerBackend,
}


def _identifier(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 128 or any(ch.isspace() for ch in cleaned):
        raise FabricationValidationError(f"{field} must be a bounded identifier")
    return cleaned


@dataclass(frozen=True)
class PrinterRegistryEntry:
    printer_id: str
    backend: str
    base_url: str
    headers: Mapping[str, str]
    display_name: str | None = None
    timeout_seconds: float = 10.0

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "PrinterRegistryEntry":
        if not isinstance(value, Mapping):
            raise FabricationValidationError("printer registry entry must be an object")
        printer_id = _identifier(value.get("printer_id"), field="printer_id")
        backend = _identifier(value.get("backend"), field="backend").lower()
        if backend not in _BACKENDS:
            raise FabricationValidationError(f"unsupported printer backend {backend!r}")
        base_url = value.get("base_url")
        if not isinstance(base_url, str) or not base_url.strip():
            raise FabricationValidationError("printer base_url is required")
        headers = value.get("headers") or {}
        if not isinstance(headers, Mapping):
            raise FabricationValidationError("printer headers must be an object")
        clean_headers: dict[str, str] = {}
        for key, item in headers.items():
            if not isinstance(key, str) or not isinstance(item, str):
                raise FabricationValidationError("printer headers must contain string keys and values")
            if not key.strip() or "\n" in key or "\r" in key or "\n" in item or "\r" in item:
                raise FabricationValidationError("printer headers contain invalid characters")
            clean_headers[key.strip()] = item
        display_name = value.get("display_name")
        if display_name is not None:
            if not isinstance(display_name, str) or not display_name.strip() or len(display_name.strip()) > 120:
                raise FabricationValidationError("display_name must be a bounded string")
            display_name = display_name.strip()
        timeout = value.get("timeout_seconds", 10.0)
        if type(timeout) not in {int, float} or not 0.1 <= float(timeout) <= 120.0:
            raise FabricationValidationError("printer timeout must be between 0.1 and 120 seconds")
        # HttpxPrinterTransport performs the authoritative URL validation.
        HttpxPrinterTransport(base_url.strip(), headers=clean_headers, timeout_seconds=float(timeout)).close()
        return cls(
            printer_id=printer_id,
            backend=backend,
            base_url=base_url.strip().rstrip("/"),
            headers=clean_headers,
            display_name=display_name,
            timeout_seconds=float(timeout),
        )

    def public_descriptor(self) -> dict[str, Any]:
        return {
            "printer_id": self.printer_id,
            "display_name": self.display_name,
            "backend": self.backend,
            "capabilities": ["stage", "status", "start", "pause", "resume", "cancel"],
        }


class PrinterRegistry:
    """Maps stable printer ids to operator-owned connection configuration."""

    def __init__(self, entries: list[PrinterRegistryEntry] | tuple[PrinterRegistryEntry, ...]):
        self._entries: dict[str, PrinterRegistryEntry] = {}
        for entry in entries:
            if not isinstance(entry, PrinterRegistryEntry):
                raise FabricationValidationError("registry entries must be PrinterRegistryEntry objects")
            if entry.printer_id in self._entries:
                raise FabricationValidationError(f"duplicate printer_id {entry.printer_id!r}")
            self._entries[entry.printer_id] = entry

    @classmethod
    def from_mapping(cls, values: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...]) -> "PrinterRegistry":
        if not isinstance(values, (list, tuple)):
            raise FabricationValidationError("printer registry configuration must be a list")
        return cls(tuple(PrinterRegistryEntry.from_mapping(value) for value in values))

    def list_public(self) -> list[dict[str, Any]]:
        return [self._entries[key].public_descriptor() for key in sorted(self._entries)]

    def describe(self, printer_id: str) -> dict[str, Any]:
        return self._entry(printer_id).public_descriptor()

    def build_printer(
        self,
        printer_id: str,
        *,
        grants: FabricationGrantStore,
        client: httpx.Client | None = None,
    ) -> FabricationPrinter:
        entry = self._entry(printer_id)
        transport = HttpxPrinterTransport(
            entry.base_url,
            headers=entry.headers,
            timeout_seconds=entry.timeout_seconds,
            client=client,
        )
        backend = _BACKENDS[entry.backend]()
        return FabricationPrinter(
            printer_id=entry.printer_id,
            backend=backend,
            transport=transport,
            grants=grants,
        )

    def _entry(self, printer_id: str) -> PrinterRegistryEntry:
        key = _identifier(printer_id, field="printer_id")
        try:
            return self._entries[key]
        except KeyError as exc:
            raise FabricationValidationError(f"unknown configured printer {key!r}") from exc
