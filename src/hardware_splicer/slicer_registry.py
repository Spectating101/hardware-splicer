"""Server-owned slicer profile registry.

Agents may choose a profile id that the operator has registered for a printer,
but they never provide or retrieve the profile bytes themselves.  This keeps
printer/material settings inside the trusted server configuration while still
letting the mission reason over safe public descriptors and immutable hashes.
"""

from __future__ import annotations

from typing import Any

from .fabrication_operator import FabricationValidationError
from .slicer_operator import SlicerProfile


class SlicerProfileRegistry:
    def __init__(self, profiles: list[SlicerProfile] | tuple[SlicerProfile, ...]):
        self._profiles: dict[str, SlicerProfile] = {}
        for profile in profiles:
            if not isinstance(profile, SlicerProfile):
                raise FabricationValidationError("slicer registry entries must be SlicerProfile objects")
            if profile.profile_id in self._profiles:
                raise FabricationValidationError(f"duplicate profile_id {profile.profile_id!r}")
            self._profiles[profile.profile_id] = profile

    def list_public(self, *, printer_id: str | None = None) -> list[dict[str, Any]]:
        values = self._profiles.values()
        if printer_id is not None:
            if not isinstance(printer_id, str) or not printer_id.strip():
                raise FabricationValidationError("printer_id must be a non-empty string")
            wanted = printer_id.strip()
            values = [profile for profile in values if profile.printer_id == wanted]
        return [profile.public_descriptor() for profile in sorted(values, key=lambda item: item.profile_id)]

    def get(self, profile_id: str, *, printer_id: str | None = None) -> SlicerProfile:
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise FabricationValidationError("profile_id must be a non-empty string")
        key = profile_id.strip()
        try:
            profile = self._profiles[key]
        except KeyError as exc:
            raise FabricationValidationError(f"unknown configured slicer profile {key!r}") from exc
        if printer_id is not None and profile.printer_id != printer_id:
            raise FabricationValidationError("slicer profile belongs to a different printer")
        return profile
