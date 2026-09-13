"""Capture and inventory manufacturer simulation-model bytes without authority promotion."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import PurePosixPath
from typing import Any, Iterable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

SCHEMA_VERSION = "hardware_splicer.vendor_model_capture.v1"
_DEFAULT_MAX_BYTES = 32 * 1024 * 1024


class VendorModelCaptureError(ValueError):
    """Raised when a model capture violates the bounded acquisition contract."""


def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def validate_vendor_url(url: str, expected_hosts: Iterable[str]) -> str:
    parsed = urlparse(str(url))
    host = (parsed.hostname or "").lower()
    allowed = {str(item).lower() for item in expected_hosts if str(item).strip()}
    if parsed.scheme != "https":
        raise VendorModelCaptureError("vendor model URL must use https")
    if not host or host not in allowed:
        raise VendorModelCaptureError(f"vendor model host {host!r} is not in the expected host set")
    if parsed.username or parsed.password:
        raise VendorModelCaptureError("vendor model URL must not contain userinfo")
    return host


def _looks_like_html(payload: bytes) -> bool:
    prefix = payload[:1024].lstrip().lower()
    return prefix.startswith(b"<!doctype html") or prefix.startswith(b"<html") or b"<html" in prefix[:512]


def _zip_inventory(payload: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for info in archive.infolist():
            name = info.filename.replace("\\", "/")
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts:
                raise VendorModelCaptureError(f"unsafe ZIP member path: {name}")
            if info.flag_bits & 0x1:
                raise VendorModelCaptureError(f"encrypted ZIP member is not accepted: {name}")
            member = archive.read(info)
            rows.append(
                {
                    "path": name,
                    "size_bytes": len(member),
                    "sha256": _sha256(member),
                    "is_directory": info.is_dir(),
                }
            )
    return rows


def inspect_vendor_model_bytes(
    payload: bytes,
    *,
    model_id: str,
    source_url: str,
    expected_hosts: Iterable[str],
    filename: str,
    content_type: str | None = None,
    expected_sha256: str | None = None,
    max_bytes: int = _DEFAULT_MAX_BYTES,
) -> dict[str, Any]:
    """Create a deterministic capture manifest from already acquired model bytes."""

    validate_vendor_url(source_url, expected_hosts)
    if not isinstance(payload, (bytes, bytearray)) or not payload:
        raise VendorModelCaptureError("vendor model payload is empty")
    data = bytes(payload)
    if len(data) > int(max_bytes):
        raise VendorModelCaptureError("vendor model payload exceeds capture byte ceiling")
    if _looks_like_html(data) or (content_type and "html" in content_type.lower()):
        raise VendorModelCaptureError("vendor endpoint returned HTML rather than model bytes")

    digest = _sha256(data)
    if expected_sha256 and digest.lower() != str(expected_sha256).lower():
        raise VendorModelCaptureError("vendor model SHA-256 does not match expected identity")

    is_zip = zipfile.is_zipfile(io.BytesIO(data))
    members = _zip_inventory(data) if is_zip else []
    if is_zip and not members:
        raise VendorModelCaptureError("vendor model ZIP contains no members")

    return {
        "schema_version": SCHEMA_VERSION,
        "model_id": str(model_id),
        "source_url": str(source_url),
        "filename": str(filename),
        "content_type": content_type,
        "size_bytes": len(data),
        "sha256": digest,
        "archive_type": "zip" if is_zip else "none",
        "archive_members": members,
        "capture_status": "captured_hashed_unreviewed",
        "modeled_evidence_only": True,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
    }


def capture_vendor_model_url(
    *,
    model_id: str,
    url: str,
    expected_hosts: Iterable[str],
    filename: str,
    expected_sha256: str | None = None,
    max_bytes: int = _DEFAULT_MAX_BYTES,
    timeout_s: float = 30.0,
) -> tuple[bytes, dict[str, Any]]:
    """Fetch one explicit official-model URL and return bytes plus an immutable manifest.

    No redirect is trusted implicitly: the final response URL must remain on the same expected
    host allowlist.  This function is never needed by unit tests and performs no background work.
    """

    validate_vendor_url(url, expected_hosts)
    request = Request(url, headers={"User-Agent": "hardware-splicer/vendor-model-capture-v1"})
    with urlopen(request, timeout=float(timeout_s)) as response:  # noqa: S310 - host allowlist above
        final_url = response.geturl()
        validate_vendor_url(final_url, expected_hosts)
        content_type = response.headers.get("Content-Type")
        declared_length = response.headers.get("Content-Length")
        if declared_length:
            try:
                if int(declared_length) > int(max_bytes):
                    raise VendorModelCaptureError("declared vendor model size exceeds byte ceiling")
            except ValueError:
                pass
        payload = response.read(int(max_bytes) + 1)

    if len(payload) > int(max_bytes):
        raise VendorModelCaptureError("vendor model payload exceeds capture byte ceiling")
    manifest = inspect_vendor_model_bytes(
        payload,
        model_id=model_id,
        source_url=final_url,
        expected_hosts=expected_hosts,
        filename=filename,
        content_type=content_type,
        expected_sha256=expected_sha256,
        max_bytes=max_bytes,
    )
    manifest["requested_url"] = url
    return payload, manifest


def manifest_json(manifest: dict[str, Any]) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"
