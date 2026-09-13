"""Capture and inventory manufacturer simulation-model bytes without authority promotion."""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from pathlib import PurePosixPath
from typing import Any, Iterable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

SCHEMA_VERSION = "hardware_splicer.vendor_model_capture.v1"
_DEFAULT_MAX_BYTES = 32 * 1024 * 1024
_SUPPORTED_MODEL_KINDS = {"IBIS", "Verilog"}


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


def _detect_model_kind(filename: str, payload: bytes) -> str | None:
    """Recognize bounded textual IBIS/Verilog identities without executing model code."""

    suffix = PurePosixPath(filename.lower()).suffix
    sample = payload[:2 * 1024 * 1024].decode("latin-1", errors="ignore")
    lowered = sample.lower()

    if suffix in {".ibs", ".ibis"} and "[ibis ver]" in lowered and (
        "[component]" in lowered or "[model]" in lowered
    ):
        return "IBIS"

    if suffix in {".v", ".sv"} and re.search(r"(?m)^\s*module\s+[A-Za-z_][A-Za-z0-9_$]*", sample):
        return "Verilog"

    return None


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
            member = b"" if info.is_dir() else archive.read(info)
            rows.append(
                {
                    "path": name,
                    "size_bytes": len(member),
                    "sha256": _sha256(member),
                    "is_directory": info.is_dir(),
                    "detected_model_kind": None if info.is_dir() else _detect_model_kind(name, member),
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
    expected_model_kind: str,
    content_type: str | None = None,
    expected_sha256: str | None = None,
    max_bytes: int = _DEFAULT_MAX_BYTES,
) -> dict[str, Any]:
    """Create a deterministic capture manifest from already acquired model bytes."""

    if expected_model_kind not in _SUPPORTED_MODEL_KINDS:
        raise VendorModelCaptureError(f"unsupported expected model kind: {expected_model_kind}")
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

    if is_zip:
        recognized = [
            {"path": row["path"], "model_kind": row["detected_model_kind"], "sha256": row["sha256"]}
            for row in members
            if row.get("detected_model_kind")
        ]
    else:
        direct_kind = _detect_model_kind(filename, data)
        recognized = (
            [{"path": filename, "model_kind": direct_kind, "sha256": digest}]
            if direct_kind
            else []
        )

    expected_files = [row for row in recognized if row["model_kind"] == expected_model_kind]
    if not expected_files:
        raise VendorModelCaptureError(
            f"captured payload contains no recognized {expected_model_kind} model file"
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "model_id": str(model_id),
        "expected_model_kind": expected_model_kind,
        "source_url": str(source_url),
        "filename": str(filename),
        "content_type": content_type,
        "size_bytes": len(data),
        "sha256": digest,
        "archive_type": "zip" if is_zip else "none",
        "archive_members": members,
        "recognized_model_files": recognized,
        "recognized_expected_model_file_count": len(expected_files),
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
    expected_model_kind: str,
    expected_sha256: str | None = None,
    max_bytes: int = _DEFAULT_MAX_BYTES,
    timeout_s: float = 30.0,
) -> tuple[bytes, dict[str, Any]]:
    """Fetch one explicit official-model URL and return bytes plus an immutable manifest.

    No redirect is trusted implicitly: the final response URL must remain on the same expected
    host allowlist. This function performs no background work and never executes captured code.
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
        expected_model_kind=expected_model_kind,
        content_type=content_type,
        expected_sha256=expected_sha256,
        max_bytes=max_bytes,
    )
    manifest["requested_url"] = url
    return payload, manifest


def manifest_json(manifest: dict[str, Any]) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"
