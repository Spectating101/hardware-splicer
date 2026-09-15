"""Materialize one exact model member from a captured vendor payload in memory.

No archive member is written by this layer. The outer payload and requested member must both
match the immutable capture manifest before downstream validation can see the bytes.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import PurePosixPath
from typing import Any, Mapping

SCHEMA_VERSION = "hardware_splicer.captured_model_materialization.v1"
_CAPTURE_SCHEMA_VERSION = "hardware_splicer.vendor_model_capture.v1"


class CapturedModelMaterializationError(ValueError):
    pass


def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def extract_bound_model_member(
    outer_payload: bytes,
    capture_manifest: Mapping[str, Any],
    *,
    member_path: str,
) -> tuple[bytes, dict[str, Any]]:
    """Return an exact captured model member only when outer + inner identities match."""

    if capture_manifest.get("schema_version") != _CAPTURE_SCHEMA_VERSION:
        raise CapturedModelMaterializationError("capture schema mismatch")
    if not isinstance(outer_payload, (bytes, bytearray)) or not outer_payload:
        raise CapturedModelMaterializationError("captured outer payload is empty")

    payload = bytes(outer_payload)
    if _sha256(payload) != capture_manifest.get("sha256"):
        raise CapturedModelMaterializationError("outer payload SHA-256 mismatch")
    if len(payload) != capture_manifest.get("size_bytes"):
        raise CapturedModelMaterializationError("outer payload size mismatch")

    normalized = str(PurePosixPath(str(member_path).replace("\\", "/")))
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise CapturedModelMaterializationError("unsafe member path")

    recognized = capture_manifest.get("recognized_model_files")
    if not isinstance(recognized, list):
        raise CapturedModelMaterializationError("recognized model inventory missing")
    expected_row = next(
        (
            row
            for row in recognized
            if isinstance(row, Mapping) and row.get("path") == normalized
        ),
        None,
    )
    if not isinstance(expected_row, Mapping):
        raise CapturedModelMaterializationError("requested member is not a recognized model file")

    archive_type = capture_manifest.get("archive_type")
    if archive_type == "zip":
        if not zipfile.is_zipfile(io.BytesIO(payload)):
            raise CapturedModelMaterializationError("manifest declares ZIP but payload is not ZIP")
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            try:
                info = archive.getinfo(normalized)
            except KeyError as exc:
                raise CapturedModelMaterializationError("captured ZIP member is missing") from exc
            if info.flag_bits & 0x1:
                raise CapturedModelMaterializationError("captured ZIP member is encrypted")
            member = archive.read(info)
    elif archive_type == "none":
        if normalized != capture_manifest.get("filename"):
            raise CapturedModelMaterializationError("direct capture member path does not match filename")
        member = payload
    else:
        raise CapturedModelMaterializationError("unsupported captured archive type")

    member_sha = _sha256(member)
    if member_sha != expected_row.get("sha256"):
        raise CapturedModelMaterializationError("captured member SHA-256 mismatch")

    return member, {
        "schema_version": SCHEMA_VERSION,
        "model_id": capture_manifest.get("model_id"),
        "model_kind": expected_row.get("model_kind"),
        "member_path": normalized,
        "member_size_bytes": len(member),
        "member_sha256": member_sha,
        "outer_sha256": capture_manifest.get("sha256"),
        "modeled_evidence_only": True,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
    }
