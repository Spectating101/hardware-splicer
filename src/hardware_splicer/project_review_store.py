"""Staged, append-only review workflow for persistent project revisions.

Candidate snapshots are stored outside revision history until explicitly accepted.
A review decision never upgrades engineering authority; it only controls whether the
candidate snapshot may become the next durable project revision.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping

from .machine_project import MachineProject
from .machine_project_diff import diff_machine_projects
from .project_store import ProjectNotFound, ProjectStore, RevisionConflict, validate_project_id

PROJECT_REVIEW_SCHEMA = "hardware_splicer.project_review.v1"
PROJECT_REVIEW_EVENT_SCHEMA = "hardware_splicer.project_review_event.v1"
_REVIEW_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")


class ProjectReviewError(RuntimeError):
    pass


class InvalidReviewId(ProjectReviewError, ValueError):
    pass


class ReviewNotFound(ProjectReviewError, FileNotFoundError):
    pass


class ReviewConflict(ProjectReviewError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_review_id(review_id: str) -> str:
    raw = str(review_id or "")
    value = raw.strip()
    if raw != value or not _REVIEW_ID_RE.fullmatch(value) or value in {".", ".."}:
        raise InvalidReviewId("review_id contains unsupported characters")
    return value


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectReviewError(f"cannot read review JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ProjectReviewError(f"review JSON must be an object: {path}")
    return value


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


class ProjectReviewStore:
    """Store immutable proposals and append-only decisions beside project revisions."""

    def __init__(self, project_store: ProjectStore) -> None:
        self.project_store = project_store

    def _project_dir(self, project_id: str) -> Path:
        safe_id = validate_project_id(project_id)
        path = (self.project_store.root / safe_id).resolve()
        if path.parent != self.project_store.root:
            raise ValueError("project_id resolves outside project root")
        if not path.is_dir():
            raise ProjectNotFound(safe_id)
        return path

    def _review_dir(self, project_id: str, review_id: str) -> Path:
        safe_review = validate_review_id(review_id)
        root = (self._project_dir(project_id) / "reviews").resolve()
        path = (root / safe_review).resolve()
        if path.parent != root:
            raise InvalidReviewId("review_id resolves outside review root")
        return path

    @staticmethod
    def _machine(snapshot: Mapping[str, Any]) -> MachineProject:
        raw = snapshot.get("machineProject") or snapshot.get("machine_project")
        if not isinstance(raw, Mapping):
            raise ValueError("project snapshot must contain a canonical machineProject")
        return MachineProject.model_validate(raw)

    def create(
        self,
        project_id: str,
        candidate_snapshot: Mapping[str, Any],
        *,
        base_revision: int | None = None,
        created_by: str,
        note: str = "",
        include_metadata: bool = False,
    ) -> Dict[str, Any]:
        safe_id = validate_project_id(project_id)
        if not str(created_by or "").strip():
            raise ValueError("created_by is required")
        if not isinstance(candidate_snapshot, Mapping):
            raise TypeError("candidate_snapshot must be a mapping")
        json.dumps(candidate_snapshot, ensure_ascii=False)

        base = (
            self.project_store.load(safe_id, revision=base_revision)
            if base_revision is not None
            else self.project_store.load_latest_with_recovery(safe_id)
        )
        base_snapshot = base["snapshot"]
        base_machine = self._machine(base_snapshot)
        candidate_machine = self._machine(candidate_snapshot)
        if base_machine.project_id != candidate_machine.project_id:
            raise ValueError("candidate machine project identity must match the base revision")

        semantic_diff = diff_machine_projects(
            base_machine,
            candidate_machine,
            include_metadata=include_metadata,
        )
        if not semantic_diff.project_changes and not semantic_diff.object_changes:
            raise ValueError("candidate snapshot contains no semantic machine changes")

        review_id = f"review-{uuid.uuid4().hex[:16]}"
        review_dir = self._review_dir(safe_id, review_id)
        if review_dir.exists():
            raise ReviewConflict(f"review already exists: {review_id}")
        proposal = {
            "schema_version": PROJECT_REVIEW_SCHEMA,
            "review_id": review_id,
            "project_id": safe_id,
            "base_revision": int(base["revision"]),
            "created_at": _utc_now(),
            "created_by": str(created_by).strip(),
            "note": str(note or ""),
            "include_metadata": bool(include_metadata),
            "candidate_snapshot": dict(candidate_snapshot),
            "diff": semantic_diff.model_dump(mode="json"),
            "summary": semantic_diff.summary(),
        }
        _atomic_write_json(review_dir / "proposal.json", proposal)
        return self.get(safe_id, review_id)

    def _events(self, project_id: str, review_id: str) -> list[Dict[str, Any]]:
        events_dir = self._review_dir(project_id, review_id) / "events"
        if not events_dir.is_dir():
            return []
        return [_read_json(path) for path in sorted(events_dir.glob("*.json"))]

    def get(self, project_id: str, review_id: str) -> Dict[str, Any]:
        review_dir = self._review_dir(project_id, review_id)
        proposal_path = review_dir / "proposal.json"
        if not proposal_path.is_file():
            raise ReviewNotFound(review_id)
        proposal = _read_json(proposal_path)
        events = self._events(project_id, review_id)
        decision = events[-1] if events else None
        return {
            **proposal,
            "status": str(decision.get("decision")) if decision else "pending",
            "decision": decision,
            "events": events,
        }

    def list(self, project_id: str) -> list[Dict[str, Any]]:
        reviews_root = self._project_dir(project_id) / "reviews"
        if not reviews_root.is_dir():
            return []
        reviews: list[Dict[str, Any]] = []
        for directory in reviews_root.iterdir():
            if not directory.is_dir():
                continue
            try:
                review = self.get(project_id, directory.name)
            except ProjectReviewError:
                continue
            reviews.append(
                {
                    key: review.get(key)
                    for key in (
                        "review_id",
                        "project_id",
                        "base_revision",
                        "created_at",
                        "created_by",
                        "note",
                        "summary",
                        "status",
                        "decision",
                    )
                }
            )
        reviews.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
        return reviews

    def list_revisions(self, project_id: str) -> list[Dict[str, Any]]:
        revisions_dir = self._project_dir(project_id) / "revisions"
        rows: list[Dict[str, Any]] = []
        if not revisions_dir.is_dir():
            return rows
        for path in sorted(revisions_dir.glob("*.json"), reverse=True):
            if not path.stem.isdigit():
                continue
            try:
                envelope = self.project_store.load(project_id, revision=int(path.stem))
            except Exception:
                continue
            snapshot = envelope.get("snapshot") or {}
            metadata = envelope.get("metadata") or {}
            rows.append(
                {
                    "revision": int(envelope["revision"]),
                    "saved_at": envelope.get("saved_at"),
                    "name": snapshot.get("projectName") or snapshot.get("project_name") or "Untitled project",
                    "current_stage": snapshot.get("currentStage") or snapshot.get("current_stage") or "intake",
                    "review_id": metadata.get("review_id"),
                    "review_actor": metadata.get("review_actor"),
                }
            )
        return rows

    def decide(
        self,
        project_id: str,
        review_id: str,
        *,
        decision: str,
        actor: str,
        note: str = "",
    ) -> Dict[str, Any]:
        normalized = str(decision or "").strip().lower()
        if normalized not in {"accepted", "rejected"}:
            raise ValueError("decision must be accepted or rejected")
        if not str(actor or "").strip():
            raise ValueError("actor is required")

        review = self.get(project_id, review_id)
        if review["status"] != "pending":
            raise ReviewConflict(f"review {review_id!r} is already {review['status']}")

        accepted_revision: int | None = None
        if normalized == "accepted":
            latest = self.project_store.load_latest_with_recovery(project_id)
            base_revision = int(review["base_revision"])
            if int(latest["revision"]) != base_revision:
                raise RevisionConflict(
                    f"review {review_id!r} is based on revision {base_revision}, "
                    f"but project is at revision {latest['revision']}"
                )
            envelope = self.project_store.save(
                project_id,
                review["candidate_snapshot"],
                expected_revision=base_revision,
                metadata={
                    "review_id": review_id,
                    "review_decision": normalized,
                    "review_actor": str(actor).strip(),
                },
            )
            accepted_revision = int(envelope["revision"])

        event = {
            "schema_version": PROJECT_REVIEW_EVENT_SCHEMA,
            "sequence": 1,
            "decision": normalized,
            "decided_at": _utc_now(),
            "actor": str(actor).strip(),
            "note": str(note or ""),
            "accepted_revision": accepted_revision,
        }
        event_path = self._review_dir(project_id, review_id) / "events" / "00000001.json"
        if event_path.exists():
            raise ReviewConflict(f"review {review_id!r} already has a decision")
        _atomic_write_json(event_path, event)
        return self.get(project_id, review_id)
