"""Observation-only camera adapter for the physical feedback plane.

The camera source is server configuration.  Agents may request a bounded capture
through the generic operator contract, but they cannot choose arbitrary URLs or
promote the resulting image to a passing physical test.  Exact image bytes are
retained in :mod:`physical_observation_store` and the operator returns only a
content-addressed observation reference plus validated image metadata.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol
from urllib.parse import urlsplit

import httpx
from PIL import Image, UnidentifiedImageError

from .fabrication_operator import FabricationValidationError
from .physical_observation_store import PhysicalObservationStore
from .physical_operator import PhysicalExecutionPlan

_ALLOWED_MEDIA = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}
_MAX_FRAME_BYTES = 20 * 1024 * 1024
_MAX_PIXELS = 40_000_000


class CameraCaptureError(RuntimeError):
    pass


class CameraSnapshotSource(Protocol):
    source_id: str

    def capture(self) -> tuple[bytes, str, Mapping[str, Any]]: ...


def _validate_url(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FabricationValidationError("camera snapshot URL is required")
    cleaned = value.strip()
    parsed = urlsplit(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise FabricationValidationError("camera snapshot URL must be absolute http(s)")
    if parsed.username is not None or parsed.password is not None or parsed.fragment:
        raise FabricationValidationError("camera snapshot URL must not contain credentials or fragment")
    return cleaned


class HttpSnapshotSource:
    """Server-owned HTTP snapshot source with no discovery or redirect following."""

    def __init__(
        self,
        *,
        source_id: str,
        url: str,
        headers: Mapping[str, str] | None = None,
        timeout_seconds: float = 10.0,
        max_frame_bytes: int = _MAX_FRAME_BYTES,
        client: httpx.Client | None = None,
    ):
        if not isinstance(source_id, str) or not source_id.strip() or len(source_id.strip()) > 128:
            raise FabricationValidationError("camera source_id must be a bounded string")
        if type(timeout_seconds) not in {int, float} or not 0.1 <= float(timeout_seconds) <= 120:
            raise FabricationValidationError("camera timeout must be between 0.1 and 120 seconds")
        if type(max_frame_bytes) is not int or not 1 <= max_frame_bytes <= _MAX_FRAME_BYTES:
            raise FabricationValidationError("camera max_frame_bytes is out of range")
        clean_headers: dict[str, str] = {}
        for key, value in (headers or {}).items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise FabricationValidationError("camera headers must be strings")
            if not key.strip() or any(ch in key + value for ch in "\r\n\x00"):
                raise FabricationValidationError("camera headers contain invalid characters")
            clean_headers[key.strip()] = value
        self.source_id = source_id.strip()
        self.url = _validate_url(url)
        self.headers = clean_headers
        self.timeout_seconds = float(timeout_seconds)
        self.max_frame_bytes = max_frame_bytes
        self._owns_client = client is None
        self.client = client or httpx.Client(follow_redirects=False)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def capture(self) -> tuple[bytes, str, Mapping[str, Any]]:
        try:
            response = self.client.get(
                self.url,
                headers=self.headers,
                timeout=self.timeout_seconds,
                follow_redirects=False,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise CameraCaptureError("camera snapshot request failed") from exc
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type not in _ALLOWED_MEDIA:
            raise CameraCaptureError("camera returned unsupported image media type")
        data = bytes(response.content)
        if not data or len(data) > self.max_frame_bytes:
            raise CameraCaptureError("camera snapshot is empty or exceeds size limit")
        metadata = inspect_image(data, expected_format=_ALLOWED_MEDIA[content_type])
        return data, content_type, metadata


def inspect_image(data: bytes, *, expected_format: str | None = None) -> dict[str, Any]:
    """Validate one image without treating visual content as engineering evidence."""

    if not isinstance(data, bytes) or not data:
        raise FabricationValidationError("camera frame must be non-empty bytes")
    try:
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            image_format = str(image.format or "").upper()
            mode = str(image.mode)
            if width <= 0 or height <= 0 or width * height > _MAX_PIXELS:
                raise CameraCaptureError("camera image dimensions exceed safety limits")
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise CameraCaptureError("camera payload is not a valid supported image") from exc
    if expected_format is not None and image_format != expected_format.upper():
        raise CameraCaptureError("camera content type does not match image bytes")
    if image_format not in set(_ALLOWED_MEDIA.values()):
        raise CameraCaptureError("camera image format is unsupported")
    return {
        "width": int(width),
        "height": int(height),
        "format": image_format,
        "mode": mode,
    }


class CameraObservationHandle:
    """Private handle for an observation-only camera operator."""

    def __init__(
        self,
        *,
        operator_id: str,
        source: CameraSnapshotSource,
        observations: PhysicalObservationStore,
    ):
        if not isinstance(operator_id, str) or not operator_id.strip():
            raise FabricationValidationError("camera operator_id is required")
        self.operator_id = operator_id.strip()
        self.source = source
        self.observations = observations

    def execute(self, plan: PhysicalExecutionPlan) -> Mapping[str, Any]:
        if not isinstance(plan, PhysicalExecutionPlan):
            raise FabricationValidationError("camera handle requires a physical execution plan")
        if plan.operator_id != self.operator_id or plan.operator_kind != "instrument":
            raise FabricationValidationError("camera execution plan targets a different operator")
        if plan.action == "status":
            return {
                "schema": "hardware_splicer.camera_status.v1",
                "source_id": self.source.source_id,
                "available": True,
                "physical_correctness": "UNPROVEN",
            }
        if plan.action != "capture":
            raise FabricationValidationError(f"unsupported camera action {plan.action!r}")
        data, media_type, metadata = self.source.capture()
        record = self.observations.put(
            kind="image",
            source_id=self.source.source_id,
            media_type=media_type,
            data=data,
            metadata={
                **dict(metadata),
                "operator_id": self.operator_id,
                "capture_requested_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {
            "schema": "hardware_splicer.camera_observation.v1",
            "operator_id": self.operator_id,
            "source_id": self.source.source_id,
            "observation": record.public_dict(),
            "physical_correctness": "UNPROVEN",
            "interpretation_performed": False,
        }
