"""Capability-driven selection for fabrication and lab operators.

This registry is intentionally descriptive.  It does not contain credentials,
network endpoints, raw commands or authorization.  Agents may ask for a
capability envelope; server configuration decides which concrete operator ids
exist and whether they are available.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from .fabrication_operator import FabricationValidationError

_ALLOWED_KINDS = frozenset({
    "printer", "cnc", "laser", "programmer", "instrument", "camera",
    "serial", "pick_and_place", "robot", "eda", "simulator", "other",
})


@dataclass(frozen=True)
class FabricationCapabilityDescriptor:
    operator_id: str
    kind: str
    display_name: str
    capabilities: tuple[str, ...]
    limits: Mapping[str, float | int | str | bool]
    available: bool = True
    simulated_only: bool = False

    def public_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["limits"] = json.loads(json.dumps(dict(self.limits)))
        return value


class FabricationCapabilityRegistry:
    """Server-owned capability graph for selecting registered operators."""

    def __init__(self) -> None:
        self._descriptors: dict[str, FabricationCapabilityDescriptor] = {}

    def register(self, descriptor: FabricationCapabilityDescriptor) -> None:
        if not isinstance(descriptor, FabricationCapabilityDescriptor):
            raise FabricationValidationError("capability registry requires a descriptor")
        operator_id = self._identifier(descriptor.operator_id, "operator_id")
        if descriptor.kind not in _ALLOWED_KINDS:
            raise FabricationValidationError("unsupported capability kind")
        if operator_id in self._descriptors:
            raise FabricationValidationError(f"operator {operator_id!r} is already registered")
        if not descriptor.capabilities:
            raise FabricationValidationError("operator must expose at least one capability")
        capabilities = tuple(sorted({self._identifier(item, "capability") for item in descriptor.capabilities}))
        limits = self._limits(descriptor.limits)
        self._descriptors[operator_id] = FabricationCapabilityDescriptor(
            operator_id=operator_id,
            kind=descriptor.kind,
            display_name=self._text(descriptor.display_name, "display_name"),
            capabilities=capabilities,
            limits=limits,
            available=bool(descriptor.available),
            simulated_only=bool(descriptor.simulated_only),
        )

    def describe(self, operator_id: str) -> dict[str, Any]:
        try:
            return self._descriptors[operator_id].public_dict()
        except KeyError as exc:
            raise FabricationValidationError("unknown fabrication capability operator") from exc

    def list_public(self, *, kind: str | None = None) -> list[dict[str, Any]]:
        if kind is not None and kind not in _ALLOWED_KINDS:
            raise FabricationValidationError("unsupported capability kind")
        values = [
            descriptor.public_dict()
            for descriptor in self._descriptors.values()
            if kind is None or descriptor.kind == kind
        ]
        values.sort(key=lambda value: (str(value["kind"]), str(value["operator_id"])))
        return values

    def match(
        self,
        *,
        required_capabilities: Iterable[str],
        kind: str | None = None,
        numeric_minimums: Mapping[str, float | int] | None = None,
        allow_simulated: bool = True,
    ) -> list[dict[str, Any]]:
        required = {self._identifier(item, "required capability") for item in required_capabilities}
        if not required:
            raise FabricationValidationError("at least one required capability is needed")
        if kind is not None and kind not in _ALLOWED_KINDS:
            raise FabricationValidationError("unsupported capability kind")
        minimums = self._numeric_minimums(numeric_minimums or {})
        matches: list[FabricationCapabilityDescriptor] = []
        for descriptor in self._descriptors.values():
            if not descriptor.available:
                continue
            if kind is not None and descriptor.kind != kind:
                continue
            if descriptor.simulated_only and not allow_simulated:
                continue
            if not required.issubset(set(descriptor.capabilities)):
                continue
            if any(
                not isinstance(descriptor.limits.get(key), (int, float))
                or isinstance(descriptor.limits.get(key), bool)
                or float(descriptor.limits[key]) < float(value)
                for key, value in minimums.items()
            ):
                continue
            matches.append(descriptor)
        matches.sort(
            key=lambda descriptor: (
                descriptor.simulated_only,
                descriptor.kind,
                descriptor.operator_id,
            )
        )
        return [descriptor.public_dict() for descriptor in matches]

    @staticmethod
    def _identifier(value: Any, field: str) -> str:
        if not isinstance(value, str):
            raise FabricationValidationError(f"{field} must be a string")
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 128 or any(not (ch.isalnum() or ch in "._:-") for ch in cleaned):
            raise FabricationValidationError(f"{field} must be a bounded identifier")
        return cleaned

    @staticmethod
    def _text(value: Any, field: str) -> str:
        if not isinstance(value, str):
            raise FabricationValidationError(f"{field} must be a string")
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 200 or any(ord(ch) < 32 for ch in cleaned):
            raise FabricationValidationError(f"{field} must be bounded printable text")
        return cleaned

    @classmethod
    def _limits(cls, value: Mapping[str, Any]) -> dict[str, float | int | str | bool]:
        if not isinstance(value, Mapping):
            raise FabricationValidationError("capability limits must be an object")
        result: dict[str, float | int | str | bool] = {}
        for key, raw in value.items():
            name = cls._identifier(key, "limit key")
            if not isinstance(raw, (str, int, float, bool)) or (isinstance(raw, float) and raw != raw):
                raise FabricationValidationError("capability limits must be scalar JSON values")
            result[name] = raw
        return result

    @classmethod
    def _numeric_minimums(cls, value: Mapping[str, Any]) -> dict[str, float | int]:
        result: dict[str, float | int] = {}
        for key, raw in value.items():
            name = cls._identifier(key, "numeric minimum key")
            if not isinstance(raw, (int, float)) or isinstance(raw, bool) or float(raw) != float(raw):
                raise FabricationValidationError("numeric minimums must be finite numbers")
            result[name] = raw
        return result
