"""Immutable raw observations captured from the physical world.

A camera frame, serial transcript, instrument trace, or machine-telemetry blob is
useful evidence input, but capture alone must not turn it into engineering truth.
This store therefore retains exact bytes and bounded metadata under a content
hash while explicitly keeping ``physical_correctness`` UNPROVEN.

Promotion into :class:`PhysicalEvidenceRecord` is a separate operation that must
supply procedure, acceptance criteria, target identity and (where applicable)
calibration information.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .fabrication_operator import FabricationValidationError

_SCHEMA = "hardware_splicer.physical_observation_artifact.v1"
_KINDS = frozenset({"image", "serial_log", "instrument_trace", "machine_telemetry", "other"})
_ID_RE = re.compile(r"^oa-[0-9a-f]{32}$")
_MAX_BYTES = 64 * 1024 * 1024
_FORBIDDEN_METADATA_KEYS = frozenset(
    {
        "authority",
        "authorization",
        "authorized",
        "physical_correctness",
        "passed",
        "verified",
        "fabrication_authorized",
        "flash_authorized",
        "power_on_authorized",
        "motion_authorized",
        "release_authorized",
    }
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _bounded_text(value: Any, *, field: str, maximum: int = 256) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > maximum or any(ord(ch) < 32 for ch in cleaned):
        raise FabricationValidationError(f"{field} must be bounded printable text")
    return cleaned


def _reject_truth_metadata(value: Any, *, path: str = "metadata") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            lowered = str(key).strip().lower()
            if lowered in _FORBIDDEN_METADATA_KEYS or "authoriz" in lowered:
                raise FabricationValidationError(
                    f"{path} must not claim engineering authority through field {key!r}"
                )
            _reject_truth_metadata(nested, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _reject_truth_metadata(nested, path=f"{path}[{index}]")


def _metadata(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise FabricationValidationError("observation metadata must be an object")
    _reject_truth_metadata(value)
    try:
        encoded = json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        normalized = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise FabricationValidationError("observation metadata must be canonical JSON") from exc
    return normalized


@dataclass(frozen=True)
class PhysicalObservationArtifact:
    schema: str
    observation_id: str
    kind: str
    source_id: str
    captured_at: str
    media_type: str
    sha256: str
    size_bytes: int
    metadata: Mapping[str, Any]
    physical_correctness: str = "UNPROVEN"

    def public_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["metadata"] = json.loads(json.dumps(dict(self.metadata)))
        return value


class PhysicalObservationStore:
    """Append-only retained raw physical observations.

    Each observation is one atomically published directory containing ``record.json``
    and ``payload.bin``.  The public surface exposes metadata and hashes, never raw
    bytes.  Raw reads are intended for trusted server-side evidence processing only.
    """

    def __init__(self, root: str | Path, *, max_bytes: int = _MAX_BYTES):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        if type(max_bytes) is not int or not 1 <= max_bytes <= _MAX_BYTES:
            raise FabricationValidationError(f"max_bytes must be an integer from 1 to {_MAX_BYTES}")
        self.max_bytes = max_bytes

    def put(
        self,
        *,
        kind: str,
        source_id: str,
        media_type: str,
        data: bytes | bytearray,
        metadata: Mapping[str, Any] | None = None,
        captured_at: str | None = None,
    ) -> PhysicalObservationArtifact:
        if kind not in _KINDS:
            raise FabricationValidationError(f"observation kind must be one of {', '.join(sorted(_KINDS))}")
        source = _bounded_text(source_id, field="source_id", maximum=128)
        media = _bounded_text(media_type, field="media_type", maximum=128)
        if not isinstance(data, (bytes, bytearray)) or not data:
            raise FabricationValidationError("observation payload must be non-empty bytes")
        payload = bytes(data)
        if len(payload) > self.max_bytes:
            raise FabricationValidationError("observation payload exceeds configured size limit")
        stamp = _bounded_text(captured_at or _now(), field="captured_at", maximum=128)
        record = PhysicalObservationArtifact(
            schema=_SCHEMA,
            observation_id=f"oa-{uuid.uuid4().hex}",
            kind=kind,
            source_id=source,
            captured_at=stamp,
            media_type=media,
            sha256=_sha256(payload),
            size_bytes=len(payload),
            metadata=_metadata(metadata),
        )
        self._publish(record, payload)
        return record

    def describe(self, observation_id: str) -> PhysicalObservationArtifact:
        directory = self._directory(observation_id)
        path = directory / "record.json"
        if not path.is_file() or path.is_symlink():
            raise FabricationValidationError("physical observation does not exist")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FabricationValidationError("physical observation record cannot be read") from exc
        try:
            record = PhysicalObservationArtifact(**value)
        except (TypeError, ValueError) as exc:
            raise FabricationValidationError("physical observation record is invalid") from exc
        payload = self.read_bytes(observation_id)
        if record.sha256 != _sha256(payload) or record.size_bytes != len(payload):
            raise FabricationValidationError("physical observation payload no longer matches its record")
        if record.schema != _SCHEMA or record.physical_correctness != "UNPROVEN":
            raise FabricationValidationError("physical observation record has invalid authority semantics")
        return record

    def read_bytes(self, observation_id: str) -> bytes:
        path = self._directory(observation_id) / "payload.bin"
        if not path.is_file() or path.is_symlink():
            raise FabricationValidationError("physical observation payload does not exist")
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise FabricationValidationError("physical observation payload cannot be read") from exc
        if not data or len(data) > self.max_bytes:
            raise FabricationValidationError("physical observation payload is invalid")
        return data

    def list_public(self, *, kind: str | None = None) -> list[dict[str, Any]]:
        if kind is not None and kind not in _KINDS:
            raise FabricationValidationError("unsupported physical observation kind")
        values: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("oa-*")):
            if not path.is_dir() or path.is_symlink() or _ID_RE.fullmatch(path.name) is None:
                continue
            try:
                record = self.describe(path.name)
            except FabricationValidationError:
                continue
            if kind is None or record.kind == kind:
                values.append(record.public_dict())
        return values

    def _publish(self, record: PhysicalObservationArtifact, payload: bytes) -> None:
        final = self._directory(record.observation_id)
        if final.exists():
            raise FabricationValidationError("physical observation id collision")
        temp = Path(tempfile.mkdtemp(prefix=".observation-", dir=self.root))
        try:
            (temp / "payload.bin").write_bytes(payload)
            record_text = json.dumps(record.public_dict(), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
            (temp / "record.json").write_text(record_text, encoding="utf-8")
            for child in (temp / "payload.bin", temp / "record.json"):
                with child.open("rb") as handle:
                    os.fsync(handle.fileno())
            os.rename(temp, final)
        except FileExistsError as exc:
            raise FabricationValidationError("physical observation id collision") from exc
        finally:
            if temp.exists():
                shutil.rmtree(temp, ignore_errors=True)

    def _directory(self, observation_id: str) -> Path:
        if not isinstance(observation_id, str) or _ID_RE.fullmatch(observation_id) is None:
            raise FabricationValidationError("physical observation id is invalid")
        path = self.root / observation_id
        if path.resolve().parent != self.root.resolve():
            raise FabricationValidationError("physical observation path escapes configured root")
        return path
