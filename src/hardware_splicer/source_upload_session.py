"""Project-scoped resumable upload sessions for bounded engineering sources."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import secrets
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .engineering_source_ingestion import (
    MAX_ENGINEERING_SOURCE_BYTES,
    MAX_SOURCE_FILENAME_CHARACTERS,
)
from .machine_project import AuthorityState
from .project_store import default_project_root, validate_project_id


SOURCE_UPLOAD_SESSION_SCHEMA = "hardware_splicer.source_upload_session.v1"
SOURCE_UPLOAD_CHUNK_BYTES = 1024 * 1024
SOURCE_UPLOAD_SESSION_TTL_HOURS = 24
MAX_SOURCE_UPLOAD_CHUNKS = math.ceil(
    MAX_ENGINEERING_SOURCE_BYTES / SOURCE_UPLOAD_CHUNK_BYTES
)
_SESSION_ID_RE = re.compile(r"[A-Za-z0-9_-]{16,96}\Z")


class UploadSessionStatus(str, Enum):
    OPEN = "open"
    FINALIZED = "finalized"
    ABANDONED = "abandoned"


class SourceUploadSessionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class SourceUploadSessionCreate(SourceUploadSessionModel):
    project_id: str = Field(min_length=1, max_length=96)
    filename: str = Field(min_length=1, max_length=MAX_SOURCE_FILENAME_CHARACTERS)
    total_size_bytes: int = Field(ge=1, le=MAX_ENGINEERING_SOURCE_BYTES)
    expected_revision: int = Field(ge=1)
    declared_media_type: str | None = Field(default=None, max_length=255)
    authority_ceiling: AuthorityState = AuthorityState.DECLARED
    expected_content_hash: str | None = Field(default=None, max_length=71)
    captured_at: str | None = Field(default=None, max_length=128)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("project_id")
    @classmethod
    def validate_project_identifier(cls, value: str) -> str:
        return validate_project_id(value)

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        resolved = value.strip()
        if not resolved:
            raise ValueError("filename must not be blank")
        if "\x00" in resolved:
            raise ValueError("filename must not contain NUL")
        return resolved

    @field_validator("authority_ceiling")
    @classmethod
    def keep_authority_fail_closed(cls, value: AuthorityState) -> AuthorityState:
        if value not in {
            AuthorityState.UNKNOWN,
            AuthorityState.PROPOSED,
            AuthorityState.DECLARED,
        }:
            raise ValueError(
                "resumable uploaded files cannot enter above declared authority"
            )
        return value

    @field_validator("expected_content_hash")
    @classmethod
    def validate_expected_hash(cls, value: str | None) -> str | None:
        if value in (None, ""):
            return None
        resolved = str(value).lower()
        if (
            not resolved.startswith("sha256:")
            or len(resolved) != 71
            or any(character not in "0123456789abcdef" for character in resolved[7:])
        ):
            raise ValueError("expected_content_hash must be canonical sha256:<hex>")
        return resolved


class UploadChunkRecord(SourceUploadSessionModel):
    chunk_index: int = Field(ge=0)
    size_bytes: int = Field(ge=1, le=SOURCE_UPLOAD_CHUNK_BYTES)
    content_hash: str = Field(min_length=71, max_length=71)
    stored_at: str


class SourceUploadSession(SourceUploadSessionModel):
    schema_version: str = SOURCE_UPLOAD_SESSION_SCHEMA
    session_id: str
    project_id: str
    filename: str
    total_size_bytes: int
    expected_revision: int
    declared_media_type: str | None = None
    authority_ceiling: AuthorityState
    expected_content_hash: str | None = None
    captured_at: str | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    chunk_size_bytes: int = SOURCE_UPLOAD_CHUNK_BYTES
    chunk_count: int = Field(ge=1, le=MAX_SOURCE_UPLOAD_CHUNKS)
    received_chunks: list[UploadChunkRecord] = Field(default_factory=list)
    status: UploadSessionStatus = UploadSessionStatus.OPEN
    created_at: str
    expires_at: str
    finalized_at: str | None = None
    finalized_revision: int | None = None
    ingestion: Dict[str, Any] = Field(default_factory=dict)
    automatic_authorization: bool = False

    @property
    def received_indexes(self) -> set[int]:
        return {row.chunk_index for row in self.received_chunks}

    @property
    def complete(self) -> bool:
        return self.received_indexes == set(range(self.chunk_count))


class SourceUploadSessionError(RuntimeError):
    pass


class SourceUploadSessionNotFound(SourceUploadSessionError, FileNotFoundError):
    pass


class SourceUploadSessionConflict(SourceUploadSessionError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat()


def validate_session_id(value: str) -> str:
    resolved = str(value or "").strip()
    if not _SESSION_ID_RE.fullmatch(resolved):
        raise ValueError("invalid source upload session identifier")
    return resolved


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _session_root(project_root: str | Path | None, project_id: str) -> Path:
    root = (
        Path(project_root)
        if project_root is not None
        else default_project_root()
    ).expanduser().resolve()
    project_dir = root / validate_project_id(project_id)
    if project_dir.is_symlink():
        raise ValueError("project upload-session directory must not be a symlink")
    resolved_project = project_dir.resolve()
    if resolved_project.parent != root:
        raise ValueError("project upload-session directory resolves outside root")
    session_root = resolved_project / "source_upload_sessions"
    current = root
    for part in session_root.relative_to(root).parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise ValueError("upload-session path contains a symlink")
    session_root.mkdir(parents=True, exist_ok=True)
    return session_root


def _session_dir(
    project_root: str | Path | None,
    project_id: str,
    session_id: str,
) -> Path:
    root = _session_root(project_root, project_id)
    path = root / validate_session_id(session_id)
    if path.is_symlink():
        raise ValueError("upload session directory must not be a symlink")
    resolved = path.resolve()
    if resolved.parent != root:
        raise ValueError("upload session resolves outside session root")
    return resolved


def _manifest_path(
    project_root: str | Path | None,
    project_id: str,
    session_id: str,
) -> Path:
    return _session_dir(project_root, project_id, session_id) / "session.json"


def _chunk_path(
    project_root: str | Path | None,
    project_id: str,
    session_id: str,
    chunk_index: int,
) -> Path:
    session_dir = _session_dir(project_root, project_id, session_id)
    chunks = session_dir / "chunks"
    if chunks.is_symlink():
        raise ValueError("upload session chunk directory must not be a symlink")
    chunks.mkdir(parents=True, exist_ok=True)
    target = chunks / f"{chunk_index:08d}.part"
    if target.is_symlink():
        raise ValueError("upload session chunk path must not be a symlink")
    return target


def _load_manifest(path: Path) -> SourceUploadSession:
    if not path.is_file():
        raise SourceUploadSessionNotFound(str(path))
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceUploadSessionError(
            f"cannot read valid upload session manifest: {path}"
        ) from exc
    return SourceUploadSession.model_validate(payload)


def create_source_upload_session(
    request: SourceUploadSessionCreate | Mapping[str, Any],
    *,
    project_root: str | Path | None = None,
) -> SourceUploadSession:
    resolved = (
        request
        if isinstance(request, SourceUploadSessionCreate)
        else SourceUploadSessionCreate.model_validate(request)
    )
    root = _session_root(project_root, resolved.project_id)
    for _ in range(8):
        session_id = secrets.token_urlsafe(24).replace("-", "_")
        path = root / session_id
        try:
            path.mkdir(mode=0o700)
            break
        except FileExistsError:
            continue
    else:
        raise SourceUploadSessionConflict("could not allocate unique upload session")

    now = _utc_now()
    session = SourceUploadSession(
        session_id=session_id,
        project_id=resolved.project_id,
        filename=resolved.filename,
        total_size_bytes=resolved.total_size_bytes,
        expected_revision=resolved.expected_revision,
        declared_media_type=resolved.declared_media_type,
        authority_ceiling=resolved.authority_ceiling,
        expected_content_hash=resolved.expected_content_hash,
        captured_at=resolved.captured_at,
        metadata=resolved.metadata,
        chunk_count=math.ceil(
            resolved.total_size_bytes / SOURCE_UPLOAD_CHUNK_BYTES
        ),
        created_at=_iso(now),
        expires_at=_iso(now + timedelta(hours=SOURCE_UPLOAD_SESSION_TTL_HOURS)),
    )
    _atomic_write_json(path / "session.json", session.model_dump(mode="json"))
    return session


def load_source_upload_session(
    project_id: str,
    session_id: str,
    *,
    project_root: str | Path | None = None,
) -> SourceUploadSession:
    return _load_manifest(
        _manifest_path(project_root, project_id, session_id)
    )


def expected_chunk_size(session: SourceUploadSession, chunk_index: int) -> int:
    if chunk_index < 0 or chunk_index >= session.chunk_count:
        raise ValueError("chunk_index is outside the upload session")
    if chunk_index < session.chunk_count - 1:
        return session.chunk_size_bytes
    consumed = session.chunk_size_bytes * (session.chunk_count - 1)
    return session.total_size_bytes - consumed


def store_source_upload_chunk(
    project_id: str,
    session_id: str,
    chunk_index: int,
    content: bytes,
    *,
    expected_content_hash: str | None = None,
    project_root: str | Path | None = None,
) -> tuple[SourceUploadSession, UploadChunkRecord, bool]:
    session = load_source_upload_session(
        project_id,
        session_id,
        project_root=project_root,
    )
    if session.status != UploadSessionStatus.OPEN:
        raise SourceUploadSessionConflict(
            f"upload session is {session.status.value}, not open"
        )
    required_size = expected_chunk_size(session, chunk_index)
    if len(content) != required_size:
        raise ValueError(
            f"chunk {chunk_index} must contain exactly {required_size} bytes"
        )
    digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
    if expected_content_hash and digest != expected_content_hash.lower():
        raise ValueError("chunk content hash does not match X-Chunk-SHA256")

    target = _chunk_path(
        project_root,
        project_id,
        session_id,
        chunk_index,
    )
    existing = next(
        (
            row
            for row in session.received_chunks
            if row.chunk_index == chunk_index
        ),
        None,
    )
    if existing is not None or target.exists():
        if not target.is_file():
            raise SourceUploadSessionConflict(
                f"chunk path exists but is not a file: {target}"
            )
        current = target.read_bytes()
        current_hash = f"sha256:{hashlib.sha256(current).hexdigest()}"
        if current_hash != digest or len(current) != len(content):
            raise SourceUploadSessionConflict(
                f"chunk {chunk_index} is already stored with different content"
            )
        record = existing or UploadChunkRecord(
            chunk_index=chunk_index,
            size_bytes=len(content),
            content_hash=digest,
            stored_at=_iso(_utc_now()),
        )
        return session, record, False

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{chunk_index:08d}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if hashlib.sha256(temp_path.read_bytes()).hexdigest() != digest[7:]:
            raise ValueError("temporary upload chunk failed hash verification")
        os.replace(temp_path, target)
    finally:
        temp_path.unlink(missing_ok=True)

    record = UploadChunkRecord(
        chunk_index=chunk_index,
        size_bytes=len(content),
        content_hash=digest,
        stored_at=_iso(_utc_now()),
    )
    session.received_chunks = sorted(
        [*session.received_chunks, record],
        key=lambda row: row.chunk_index,
    )
    _atomic_write_json(
        _manifest_path(project_root, project_id, session_id),
        session.model_dump(mode="json"),
    )
    return session, record, True


def assemble_source_upload_session(
    project_id: str,
    session_id: str,
    *,
    project_root: str | Path | None = None,
) -> tuple[SourceUploadSession, bytes, str]:
    session = load_source_upload_session(
        project_id,
        session_id,
        project_root=project_root,
    )
    if session.status != UploadSessionStatus.OPEN:
        raise SourceUploadSessionConflict(
            f"upload session is {session.status.value}, not open"
        )
    if not session.complete:
        missing = sorted(set(range(session.chunk_count)) - session.received_indexes)
        raise SourceUploadSessionConflict(
            f"upload session is incomplete; missing chunks: {missing}"
        )
    content = bytearray()
    for index in range(session.chunk_count):
        target = _chunk_path(
            project_root,
            project_id,
            session_id,
            index,
        )
        if not target.is_file():
            raise SourceUploadSessionConflict(f"chunk {index} is missing")
        chunk = target.read_bytes()
        record = next(
            row for row in session.received_chunks if row.chunk_index == index
        )
        digest = f"sha256:{hashlib.sha256(chunk).hexdigest()}"
        if len(chunk) != record.size_bytes or digest != record.content_hash:
            raise SourceUploadSessionConflict(
                f"chunk {index} no longer matches its manifest"
            )
        content.extend(chunk)
        if len(content) > session.total_size_bytes:
            raise SourceUploadSessionConflict(
                "assembled upload exceeds declared total size"
            )
    if len(content) != session.total_size_bytes:
        raise SourceUploadSessionConflict(
            "assembled upload does not match declared total size"
        )
    content_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"
    if (
        session.expected_content_hash
        and content_hash != session.expected_content_hash
    ):
        raise SourceUploadSessionConflict(
            "assembled upload does not match expected_content_hash"
        )
    return session, bytes(content), content_hash


def finalize_source_upload_session_manifest(
    project_id: str,
    session_id: str,
    *,
    revision: int,
    ingestion: Mapping[str, Any],
    project_root: str | Path | None = None,
) -> SourceUploadSession:
    session = load_source_upload_session(
        project_id,
        session_id,
        project_root=project_root,
    )
    session.status = UploadSessionStatus.FINALIZED
    session.finalized_at = _iso(_utc_now())
    session.finalized_revision = revision
    session.ingestion = dict(ingestion)
    _atomic_write_json(
        _manifest_path(project_root, project_id, session_id),
        session.model_dump(mode="json"),
    )
    chunks = _session_dir(project_root, project_id, session_id) / "chunks"
    if chunks.exists() and not chunks.is_symlink():
        shutil.rmtree(chunks)
    return session


def abandon_source_upload_session(
    project_id: str,
    session_id: str,
    *,
    project_root: str | Path | None = None,
) -> SourceUploadSession:
    session = load_source_upload_session(
        project_id,
        session_id,
        project_root=project_root,
    )
    if session.status == UploadSessionStatus.FINALIZED:
        raise SourceUploadSessionConflict("finalized upload session cannot be abandoned")
    session.status = UploadSessionStatus.ABANDONED
    _atomic_write_json(
        _manifest_path(project_root, project_id, session_id),
        session.model_dump(mode="json"),
    )
    chunks = _session_dir(project_root, project_id, session_id) / "chunks"
    if chunks.exists() and not chunks.is_symlink():
        shutil.rmtree(chunks)
    return session
