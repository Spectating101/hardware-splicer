"""Project-scoped audit and explicit cleanup for source blobs and upload sessions."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping

from pydantic import BaseModel, ConfigDict, Field

from .project_store import default_project_root, validate_project_id
from .source_upload_session import (
    SourceUploadSession,
    UploadSessionStatus,
    abandon_source_upload_session,
)


SOURCE_STORAGE_OPERATIONS_SCHEMA = "hardware_splicer.source_storage_operations.v1"
DEFAULT_CLEANUP_MINIMUM_AGE_HOURS = 24.0


class SourceStorageModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class SourceBlobAudit(SourceStorageModel):
    blob_ref: str
    path_digest: str | None = None
    size_bytes: int = Field(ge=0)
    modified_at: str
    age_hours: float = Field(ge=0)
    referenced: bool = False
    content_hash_valid: bool = False
    path_shape_valid: bool = False
    symlink: bool = False
    orphan: bool = False
    corrupt: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UploadSessionAudit(SourceStorageModel):
    session_id: str
    status: str
    filename: str | None = None
    total_size_bytes: int = Field(default=0, ge=0)
    received_chunk_count: int = Field(default=0, ge=0)
    chunk_bytes: int = Field(default=0, ge=0)
    expires_at: str | None = None
    expired: bool = False
    manifest_valid: bool = True
    chunk_directory_present: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SourceStorageAuditReport(SourceStorageModel):
    schema_version: str = SOURCE_STORAGE_OPERATIONS_SCHEMA
    project_id: str
    referenced_blob_refs: list[str] = Field(default_factory=list)
    blobs: list[SourceBlobAudit] = Field(default_factory=list)
    sessions: list[UploadSessionAudit] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    automatic_deletion: bool = False


class SourceStorageCleanupRequest(SourceStorageModel):
    dry_run: bool = True
    minimum_age_hours: float = Field(
        default=DEFAULT_CLEANUP_MINIMUM_AGE_HOURS,
        ge=1.0,
        le=24.0 * 365.0,
    )
    delete_orphan_blobs: bool = True
    clean_expired_session_chunks: bool = True
    include_corrupt_orphans: bool = False
    confirm_project_id: str = ""


class SourceStorageCleanupResult(SourceStorageModel):
    schema_version: str = SOURCE_STORAGE_OPERATIONS_SCHEMA
    project_id: str
    dry_run: bool
    deleted_blob_refs: list[str] = Field(default_factory=list)
    candidate_blob_refs: list[str] = Field(default_factory=list)
    cleaned_session_ids: list[str] = Field(default_factory=list)
    candidate_session_ids: list[str] = Field(default_factory=list)
    bytes_reclaimed: int = Field(default=0, ge=0)
    bytes_reclaimable: int = Field(default=0, ge=0)
    project_revision_mutated: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_from_timestamp(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def _age_hours(modified_at: float, now: datetime) -> float:
    return max(0.0, (now.timestamp() - modified_at) / 3600.0)


def _project_dir(project_root: str | Path | None, project_id: str) -> Path:
    root = (
        Path(project_root)
        if project_root is not None
        else default_project_root()
    ).expanduser().resolve()
    unresolved = root / validate_project_id(project_id)
    if unresolved.is_symlink():
        raise ValueError("project storage directory must not be a symlink")
    resolved = unresolved.resolve()
    if resolved.parent != root:
        raise ValueError("project storage directory resolves outside project root")
    if not resolved.is_dir():
        raise FileNotFoundError(project_id)
    return resolved


def _rows(value: Any) -> list[Dict[str, Any]]:
    return [dict(row) for row in value or [] if isinstance(row, Mapping)]


def referenced_blob_refs(snapshot: Mapping[str, Any]) -> list[str]:
    refs: set[str] = set()
    for source in _rows(snapshot.get("engineeringSources")):
        metadata = source.get("metadata")
        if isinstance(metadata, Mapping) and metadata.get("blob_ref"):
            refs.add(str(metadata["blob_ref"]))
    for upload in _rows(snapshot.get("engineeringSourceUploads")):
        if upload.get("blob_ref"):
            refs.add(str(upload["blob_ref"]))
        metadata = upload.get("metadata")
        if isinstance(metadata, Mapping) and metadata.get("blob_ref"):
            refs.add(str(metadata["blob_ref"]))
    return sorted(refs)


def _audit_blob(
    project_dir: Path,
    path: Path,
    references: set[str],
    now: datetime,
) -> SourceBlobAudit:
    symlink = path.is_symlink()
    stat = path.lstat() if symlink else path.stat()
    blob_ref = path.relative_to(project_dir).as_posix()
    parts = Path(blob_ref).parts
    path_digest: str | None = None
    path_shape_valid = False
    if len(parts) == 4 and parts[:2] == ("sources", "sha256"):
        prefix, candidate = parts[2], parts[3]
        if (
            len(prefix) == 2
            and len(candidate) == 64
            and prefix == candidate[:2]
            and all(character in "0123456789abcdef" for character in candidate)
        ):
            path_digest = candidate
            path_shape_valid = True
    content_hash_valid = False
    actual_digest: str | None = None
    read_error: str | None = None
    if path.is_file() and not symlink:
        try:
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            actual_digest = digest.hexdigest()
            content_hash_valid = bool(path_digest and actual_digest == path_digest)
        except OSError as exc:
            read_error = str(exc)
    referenced = blob_ref in references
    corrupt = symlink or not path_shape_valid or not content_hash_valid
    return SourceBlobAudit(
        blob_ref=blob_ref,
        path_digest=path_digest,
        size_bytes=stat.st_size if path.is_file() and not symlink else 0,
        modified_at=_iso_from_timestamp(stat.st_mtime),
        age_hours=_age_hours(stat.st_mtime, now),
        referenced=referenced,
        content_hash_valid=content_hash_valid,
        path_shape_valid=path_shape_valid,
        symlink=symlink,
        orphan=not referenced,
        corrupt=corrupt,
        metadata={
            "actual_digest": actual_digest,
            "read_error": read_error,
        },
    )


def _audit_blobs(
    project_dir: Path,
    references: set[str],
    now: datetime,
) -> list[SourceBlobAudit]:
    root = project_dir / "sources" / "sha256"
    if not root.exists():
        return []
    if root.is_symlink():
        stat = root.lstat()
        return [
            SourceBlobAudit(
                blob_ref="sources/sha256",
                size_bytes=0,
                modified_at=_iso_from_timestamp(stat.st_mtime),
                age_hours=_age_hours(stat.st_mtime, now),
                symlink=True,
                orphan=True,
                corrupt=True,
                metadata={"unsafe_root": True},
            )
        ]
    blobs: list[SourceBlobAudit] = []
    for prefix in sorted(root.iterdir()):
        if prefix.is_symlink():
            blobs.append(_audit_blob(project_dir, prefix, references, now))
            continue
        if not prefix.is_dir():
            blobs.append(_audit_blob(project_dir, prefix, references, now))
            continue
        for path in sorted(prefix.iterdir()):
            blobs.append(_audit_blob(project_dir, path, references, now))
    return blobs


def _parse_expiry(value: str | None, now: datetime) -> bool:
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed <= now


def _audit_sessions(project_dir: Path, now: datetime) -> list[UploadSessionAudit]:
    root = project_dir / "source_upload_sessions"
    if not root.exists() or root.is_symlink():
        return []
    rows: list[UploadSessionAudit] = []
    for session_dir in sorted(root.iterdir()):
        if not session_dir.is_dir() or session_dir.is_symlink():
            continue
        manifest = session_dir / "session.json"
        chunks = session_dir / "chunks"
        chunk_bytes = 0
        if chunks.is_dir() and not chunks.is_symlink():
            for path in chunks.iterdir():
                if path.is_file() and not path.is_symlink():
                    chunk_bytes += path.stat().st_size
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            session = SourceUploadSession.model_validate(payload)
            rows.append(
                UploadSessionAudit(
                    session_id=session.session_id,
                    status=session.status.value,
                    filename=session.filename,
                    total_size_bytes=session.total_size_bytes,
                    received_chunk_count=len(session.received_chunks),
                    chunk_bytes=chunk_bytes,
                    expires_at=session.expires_at,
                    expired=_parse_expiry(session.expires_at, now),
                    manifest_valid=True,
                    chunk_directory_present=chunks.is_dir(),
                    metadata={
                        "expected_revision": session.expected_revision,
                        "chunk_count": session.chunk_count,
                        "complete": session.complete,
                        "finalized_revision": session.finalized_revision,
                    },
                )
            )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            rows.append(
                UploadSessionAudit(
                    session_id=session_dir.name,
                    status="corrupt",
                    chunk_bytes=chunk_bytes,
                    manifest_valid=False,
                    chunk_directory_present=chunks.is_dir(),
                    metadata={"manifest_error": str(exc)},
                )
            )
    return rows


def audit_project_source_storage(
    project_id: str,
    snapshot: Mapping[str, Any],
    *,
    project_root: str | Path | None = None,
    now: datetime | None = None,
) -> SourceStorageAuditReport:
    project_dir = _project_dir(project_root, project_id)
    resolved_now = now or _utc_now()
    references = set(referenced_blob_refs(snapshot))
    blobs = _audit_blobs(project_dir, references, resolved_now)
    sessions = _audit_sessions(project_dir, resolved_now)
    return SourceStorageAuditReport(
        project_id=project_id,
        referenced_blob_refs=sorted(references),
        blobs=blobs,
        sessions=sessions,
        summary={
            "referenced_blob_count": len(references),
            "stored_blob_count": len(blobs),
            "orphan_blob_count": sum(row.orphan for row in blobs),
            "corrupt_blob_count": sum(row.corrupt for row in blobs),
            "stored_blob_bytes": sum(row.size_bytes for row in blobs),
            "orphan_blob_bytes": sum(
                row.size_bytes for row in blobs if row.orphan
            ),
            "session_count": len(sessions),
            "open_session_count": sum(row.status == "open" for row in sessions),
            "expired_session_count": sum(row.expired for row in sessions),
            "temporary_chunk_bytes": sum(row.chunk_bytes for row in sessions),
            "automatic_deletion": False,
        },
        automatic_deletion=False,
    )


def cleanup_project_source_storage(
    project_id: str,
    snapshot: Mapping[str, Any],
    request: SourceStorageCleanupRequest | Mapping[str, Any],
    *,
    project_root: str | Path | None = None,
    now: datetime | None = None,
) -> SourceStorageCleanupResult:
    resolved = (
        request
        if isinstance(request, SourceStorageCleanupRequest)
        else SourceStorageCleanupRequest.model_validate(request)
    )
    if not resolved.dry_run and resolved.confirm_project_id != project_id:
        raise ValueError(
            "confirm_project_id must exactly match project_id for destructive cleanup"
        )
    project_dir = _project_dir(project_root, project_id)
    report = audit_project_source_storage(
        project_id,
        snapshot,
        project_root=project_root,
        now=now,
    )
    blob_candidates = [
        row
        for row in report.blobs
        if resolved.delete_orphan_blobs
        and row.orphan
        and row.age_hours >= resolved.minimum_age_hours
        and not row.symlink
        and (row.content_hash_valid or resolved.include_corrupt_orphans)
    ]
    session_candidates = [
        row
        for row in report.sessions
        if resolved.clean_expired_session_chunks
        and row.expired
        and row.status in {
            UploadSessionStatus.OPEN.value,
            UploadSessionStatus.ABANDONED.value,
        }
        and row.manifest_valid
        and row.chunk_directory_present
    ]
    deleted: list[str] = []
    cleaned_sessions: list[str] = []
    reclaimed = 0
    if not resolved.dry_run:
        for row in blob_candidates:
            target = (project_dir / row.blob_ref).resolve()
            if project_dir not in target.parents or not target.is_file():
                raise ValueError(
                    f"cleanup candidate resolves outside project or is not a file: {row.blob_ref}"
                )
            if target.is_symlink():
                raise ValueError(
                    f"cleanup refuses symlink candidate: {row.blob_ref}"
                )
            target.unlink()
            deleted.append(row.blob_ref)
            reclaimed += row.size_bytes
            parent = target.parent
            if parent != project_dir and parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
        for row in session_candidates:
            if row.status == UploadSessionStatus.OPEN.value:
                abandon_source_upload_session(
                    project_id,
                    row.session_id,
                    project_root=project_root,
                )
            else:
                chunks = (
                    project_dir
                    / "source_upload_sessions"
                    / row.session_id
                    / "chunks"
                )
                if chunks.is_dir() and not chunks.is_symlink():
                    shutil.rmtree(chunks)
            cleaned_sessions.append(row.session_id)
            reclaimed += row.chunk_bytes
    return SourceStorageCleanupResult(
        project_id=project_id,
        dry_run=resolved.dry_run,
        deleted_blob_refs=deleted,
        candidate_blob_refs=[row.blob_ref for row in blob_candidates],
        cleaned_session_ids=cleaned_sessions,
        candidate_session_ids=[row.session_id for row in session_candidates],
        bytes_reclaimed=reclaimed,
        bytes_reclaimable=(
            sum(row.size_bytes for row in blob_candidates)
            + sum(row.chunk_bytes for row in session_candidates)
        ),
        project_revision_mutated=False,
        metadata={
            "minimum_age_hours": resolved.minimum_age_hours,
            "delete_orphan_blobs": resolved.delete_orphan_blobs,
            "clean_expired_session_chunks": (
                resolved.clean_expired_session_chunks
            ),
            "include_corrupt_orphans": resolved.include_corrupt_orphans,
            "referenced_blobs_never_candidates": True,
            "automatic_deletion": False,
        },
    )
