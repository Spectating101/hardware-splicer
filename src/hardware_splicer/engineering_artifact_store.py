"""Immutable store for non-executable engineering/fabrication artifacts.

Executable machine inputs belong in ``PhysicalArtifactRegistry``. This store is
for geometry, EDA/manufacturing bundles, BOMs, PCB-fab request packages,
handoff bundles and similar provenance-bearing bytes that must be retained and
referenced without becoming directly executable physical commands.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .fabrication_operator import FabricationValidationError

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ALLOWED_KINDS = frozenset({
    "geometry",
    "eda_bundle",
    "manufacturing_bundle",
    "bom",
    "pcb_fab_request",
    "handoff_bundle",
    "simulation_output",
    "inspection_document",
    "other",
})


@dataclass(frozen=True)
class EngineeringArtifact:
    schema: str
    artifact_id: str
    kind: str
    sha256: str
    size_bytes: int
    media_type: str
    producer: str
    metadata: Mapping[str, Any]
    executable: bool = False
    physical_correctness: str = "UNPROVEN"

    def public_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["metadata"] = json.loads(json.dumps(dict(self.metadata)))
        return value


class EngineeringArtifactStore:
    def __init__(self, root: str | Path, *, max_bytes: int = 256 * 1024 * 1024) -> None:
        literal = Path(root)
        if literal.exists() and literal.is_symlink():
            raise FabricationValidationError("engineering artifact root must not be a symlink")
        self.root = literal.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if type(max_bytes) is not int or not 1 <= max_bytes <= 1024 * 1024 * 1024:
            raise FabricationValidationError("engineering artifact max_bytes is invalid")
        self.max_bytes = max_bytes

    def put(
        self,
        *,
        artifact_id: str,
        kind: str,
        content: bytes | bytearray,
        media_type: str,
        producer: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> EngineeringArtifact:
        aid = _id(artifact_id, "artifact_id")
        if kind not in _ALLOWED_KINDS:
            raise FabricationValidationError("unsupported engineering artifact kind")
        if not isinstance(content, (bytes, bytearray)) or not content:
            raise FabricationValidationError("engineering artifact content must be non-empty bytes")
        payload = bytes(content)
        if len(payload) > self.max_bytes:
            raise FabricationValidationError("engineering artifact exceeds configured size limit")
        media = _text(media_type, "media_type", 128)
        producer_id = _id(producer, "producer")
        meta = _canonical(dict(metadata or {}))
        record = EngineeringArtifact(
            schema="hardware_splicer.engineering_artifact.v1",
            artifact_id=aid,
            kind=kind,
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
            media_type=media,
            producer=producer_id,
            metadata=meta,
        )
        self._publish(record, payload)
        return record

    def describe(self, artifact_id: str) -> EngineeringArtifact:
        directory = self._directory(artifact_id)
        record_path = directory / "record.json"
        payload_path = directory / "payload.bin"
        if not record_path.is_file() or record_path.is_symlink() or not payload_path.is_file() or payload_path.is_symlink():
            raise FabricationValidationError("engineering artifact does not exist")
        try:
            value = json.loads(record_path.read_text(encoding="utf-8"))
            record = EngineeringArtifact(**value)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise FabricationValidationError("engineering artifact record is invalid") from exc
        payload = payload_path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != record.sha256 or len(payload) != record.size_bytes:
            raise FabricationValidationError("engineering artifact payload no longer matches record")
        if record.executable is not False or record.physical_correctness != "UNPROVEN":
            raise FabricationValidationError("engineering artifact authority semantics are invalid")
        return record

    def bytes(self, artifact_id: str) -> bytes:
        record = self.describe(artifact_id)
        data = (self._directory(record.artifact_id) / "payload.bin").read_bytes()
        return bytes(data)

    def list_public(self, *, kind: str | None = None) -> list[dict[str, Any]]:
        if kind is not None and kind not in _ALLOWED_KINDS:
            raise FabricationValidationError("unsupported engineering artifact kind")
        result: list[dict[str, Any]] = []
        for directory in sorted(self.root.iterdir()):
            if not directory.is_dir() or directory.is_symlink() or _ID_RE.fullmatch(directory.name) is None:
                continue
            try:
                record = self.describe(directory.name)
            except FabricationValidationError:
                continue
            if kind is None or record.kind == kind:
                result.append(record.public_dict())
        return result

    def _publish(self, record: EngineeringArtifact, payload: bytes) -> None:
        final = self._directory(record.artifact_id)
        if final.exists():
            raise FabricationValidationError("engineering artifact id already exists")
        temp = Path(tempfile.mkdtemp(prefix=".artifact-", dir=self.root))
        try:
            (temp / "payload.bin").write_bytes(payload)
            (temp / "record.json").write_text(
                json.dumps(record.public_dict(), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
                encoding="utf-8",
            )
            for child in (temp / "payload.bin", temp / "record.json"):
                with child.open("rb") as handle:
                    os.fsync(handle.fileno())
            os.rename(temp, final)
        except FileExistsError as exc:
            raise FabricationValidationError("engineering artifact id already exists") from exc
        finally:
            if temp.exists():
                shutil.rmtree(temp, ignore_errors=True)

    def _directory(self, artifact_id: str) -> Path:
        aid = _id(artifact_id, "artifact_id")
        path = self.root / aid
        if path.resolve().parent != self.root.resolve():
            raise FabricationValidationError("engineering artifact path escapes configured root")
        return path


def _canonical(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise FabricationValidationError("engineering artifact metadata must be canonical JSON") from exc


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str) or _ID_RE.fullmatch(value.strip()) is None:
        raise FabricationValidationError(f"{field} must be a bounded identifier")
    return value.strip()


def _text(value: Any, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > maximum or any(ord(ch) < 32 for ch in cleaned):
        raise FabricationValidationError(f"{field} must be bounded printable text")
    return cleaned
