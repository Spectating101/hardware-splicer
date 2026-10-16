"""Deterministic cross-tool handoff bundles for a fabrication revision.

The bundle is a transport/provenance object, not an authorization. It can carry
EDA exports, firmware, geometry, CAM/machine jobs, assembly instructions and
validation procedures while hashing every retained byte. ZIP metadata is fixed
so identical inputs produce identical package bytes.
"""
from __future__ import annotations

import hashlib
import io
import json
import posixpath
import re
import zipfile
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .fabrication_operator import FabricationValidationError

_PATH_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,127}$")


@dataclass(frozen=True)
class HandoffArtifact:
    path: str
    content: bytes
    role: str
    producer: str
    media_type: str = "application/octet-stream"
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class FabricationHandoffBundle:
    manifest: Mapping[str, Any]
    zip_bytes: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.zip_bytes).hexdigest()


class FabricationHandoffBuilder:
    def build(
        self,
        *,
        project_id: str,
        mission_id: str,
        revision_id: str,
        artifacts: Iterable[HandoffArtifact],
        provenance: Iterable[Mapping[str, Any]] = (),
    ) -> FabricationHandoffBundle:
        ids = {
            "project_id": _id(project_id, "project_id"),
            "mission_id": _id(mission_id, "mission_id"),
            "revision_id": _id(revision_id, "revision_id"),
        }
        rows: list[tuple[HandoffArtifact, str, dict[str, Any]]] = []
        seen: set[str] = set()
        for artifact in artifacts:
            if not isinstance(artifact, HandoffArtifact):
                raise FabricationValidationError("handoff artifacts must use HandoffArtifact")
            path = _safe_path(artifact.path)
            if path in seen or path == "HANDOFF_MANIFEST.json":
                raise FabricationValidationError("handoff artifact paths must be unique")
            seen.add(path)
            if not isinstance(artifact.content, (bytes, bytearray)) or not artifact.content:
                raise FabricationValidationError("handoff artifact content must be non-empty bytes")
            role = _id(artifact.role, "artifact role")
            producer = _id(artifact.producer, "artifact producer")
            media_type = _text(artifact.media_type, "media_type", maximum=128)
            metadata = _canonical(dict(artifact.metadata or {}))
            content = bytes(artifact.content)
            rows.append((artifact, path, {
                "path": path,
                "role": role,
                "producer": producer,
                "media_type": media_type,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
                "metadata": metadata,
            }))
        if not rows:
            raise FabricationValidationError("handoff bundle requires at least one artifact")
        provenance_rows = [_canonical(dict(item)) for item in provenance]
        manifest = {
            "schema": "hardware_splicer.fabrication_handoff_manifest.v1",
            **ids,
            "artifacts": [row for _artifact, _path, row in sorted(rows, key=lambda item: item[1])],
            "provenance": provenance_rows,
            "physical_correctness": "UNPROVEN",
            "fabrication_authorized": False,
            "flash_authorized": False,
            "motion_authorized": False,
            "automatic_execution": False,
        }
        manifest_bytes = (json.dumps(
            manifest,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ) + "\n").encode("utf-8")
        output = io.BytesIO()
        with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            _write(archive, "HANDOFF_MANIFEST.json", manifest_bytes)
            for artifact, path, _row in sorted(rows, key=lambda item: item[1]):
                _write(archive, path, bytes(artifact.content))
        return FabricationHandoffBundle(manifest=manifest, zip_bytes=output.getvalue())


def _write(archive: zipfile.ZipFile, path: str, content: bytes) -> None:
    info = zipfile.ZipInfo(path)
    info.date_time = (1980, 1, 1, 0, 0, 0)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, content)


def _safe_path(value: Any) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError("handoff path must be a string")
    normalized = value.replace("\\", "/").strip("/")
    if not normalized or normalized.startswith(".") or len(normalized) > 512:
        raise FabricationValidationError("handoff path is invalid")
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} or _PATH_SEGMENT_RE.fullmatch(part) is None for part in parts):
        raise FabricationValidationError("handoff path contains an invalid segment")
    final = posixpath.normpath(normalized)
    if final.startswith("../") or final == "..":
        raise FabricationValidationError("handoff path escapes package root")
    return final


def _canonical(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise FabricationValidationError("handoff metadata/provenance must be canonical JSON") from exc


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 128 or any(not (ch.isalnum() or ch in "._:-") for ch in cleaned):
        raise FabricationValidationError(f"{field} must be a bounded identifier")
    return cleaned


def _text(value: Any, field: str, *, maximum: int) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > maximum or any(ord(ch) < 32 for ch in cleaned):
        raise FabricationValidationError(f"{field} must be bounded printable text")
    return cleaned
