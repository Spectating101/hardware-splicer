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
_MACHINE_SNAPSHOT_KEYS = {"machineProject", "machine_project"}


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


def _json_payload(value: Mapping[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _json_payload(value)
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


def _atomic_create_json(path: Path, value: Mapping[str, Any]) -> None:
    """Create an immutable JSON record without replacing a concurrent writer."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _json_payload(value)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp_path, path)
        except FileExistsError as exc:
            raise ReviewConflict(f"immutable review record already exists: {path.name}") from exc
    finally:
        temp_path.unlink(missing_ok=True)


def _snapshot_changes(base: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[Dict[str, Any]]:
    """Report non-machine top-level changes so project state cannot hide behind ontology diffs."""

    changes: list[Dict[str, Any]] = []
    keys = (set(base) | set(candidate)) - _MACHINE_SNAPSHOT_KEYS
    for key in sorted(keys):
        before = base.get(key)
        after = candidate.get(key)
        if before != after:
            changes.append({"path": key, "before": before, "after": after})
    return changes


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

    def _event_path(self, project_id: str, review_id: str, sequence: int) -> Path:
        return self._review_dir(project_id, review_id) / "events" / f"{int(sequence):08d}.json"

    def _write_event(
        self,
        project_id: str,
        review_id: str,
        sequence: int,
        event: Mapping[str, Any],
    ) -> Dict[str, Any]:
        record = {
            "schema_version": PROJECT_REVIEW_EVENT_SCHEMA,
            "sequence": int(sequence),
            **dict(event),
        }
        _atomic_create_json(self._event_path(project_id, review_id, sequence), record)
        return record

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
        candidate_session_id = candidate_snapshot.get("projectId") or candidate_snapshot.get("project_id")
        if candidate_session_id is not None and str(candidate_session_id) != safe_id:
            raise ValueError("candidate snapshot project identity must match the persistent project")

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
        snapshot_changes = _snapshot_changes(base_snapshot, candidate_snapshot)
        if (
            not semantic_diff.project_changes
            and not semantic_diff.object_changes
            and not snapshot_changes
        ):
            raise ValueError("candidate snapshot contains no reviewable changes")

        snapshot_flags = [
            {
                "code": "snapshot_field_changed",
                "severity": "required",
                "path": change["path"],
                "message": f"project snapshot field {change['path']!r} changed outside the canonical machine object",
            }
            for change in snapshot_changes
        ]
        summary = semantic_diff.summary()
        summary["snapshot_fields_changed"] = len(snapshot_changes)
        summary["review_required"] = bool(summary.get("review_required") or snapshot_flags)

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
            "snapshot_changes": snapshot_changes,
            "review_flags": snapshot_flags,
            "summary": summary,
        }
        _atomic_write_json(review_dir / "proposal.json", proposal)
        return self.get(safe_id, review_id)

    def _events(self, project_id: str, review_id: str) -> list[Dict[str, Any]]:
        events_dir = self._review_dir(project_id, review_id) / "events"
        if not events_dir.is_dir():
            return []
        return [_read_json(path) for path in sorted(events_dir.glob("*.json"))]

    @staticmethod
    def _revision_matches_review(
        envelope: Mapping[str, Any],
        review_id: str,
        candidate_snapshot: Mapping[str, Any],
    ) -> bool:
        metadata = envelope.get("metadata") if isinstance(envelope.get("metadata"), Mapping) else {}
        return bool(
            metadata.get("review_id") == review_id
            and metadata.get("review_decision") == "accepted"
            and envelope.get("snapshot") == candidate_snapshot
        )

    def _complete_acceptance(
        self,
        project_id: str,
        review_id: str,
        proposal: Mapping[str, Any],
        intent: Mapping[str, Any],
        *,
        recovered: bool = False,
    ) -> Dict[str, Any]:
        expected_revision = int(intent["accepted_revision"])
        completion = {
            "event_type": "decision_completed",
            "decision": "accepted",
            "decided_at": _utc_now(),
            "actor": intent.get("actor"),
            "note": intent.get("note") or "",
            "accepted_revision": expected_revision,
            "recovered": bool(recovered),
        }
        return self._write_event(project_id, review_id, int(intent["sequence"]) + 1, completion)

    def _reconcile_accepting(
        self,
        project_id: str,
        review_id: str,
        proposal: Mapping[str, Any],
        events: list[Dict[str, Any]],
    ) -> list[Dict[str, Any]]:
        if not events or events[-1].get("decision") != "accepting":
            return events
        intent = events[-1]
        expected_revision = int(intent.get("accepted_revision") or 0)
        if expected_revision <= 0:
            return events
        try:
            envelope = self.project_store.load(project_id, revision=expected_revision)
        except ProjectNotFound:
            return events
        if not self._revision_matches_review(envelope, review_id, proposal["candidate_snapshot"]):
            return events
        try:
            completion = self._complete_acceptance(
                project_id,
                review_id,
                proposal,
                intent,
                recovered=True,
            )
        except ReviewConflict:
            return self._events(project_id, review_id)
        return [*events, completion]

    def get(self, project_id: str, review_id: str) -> Dict[str, Any]:
        review_dir = self._review_dir(project_id, review_id)
        proposal_path = review_dir / "proposal.json"
        if not proposal_path.is_file():
            raise ReviewNotFound(review_id)
        proposal = _read_json(proposal_path)
        events = self._events(project_id, review_id)
        events = self._reconcile_accepting(project_id, review_id, proposal, events)
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
                        "review_flags",
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

    def _finish_acceptance(
        self,
        project_id: str,
        review_id: str,
        review: Mapping[str, Any],
        intent: Mapping[str, Any],
    ) -> Dict[str, Any]:
        base_revision = int(review["base_revision"])
        expected_revision = int(intent["accepted_revision"])
        try:
            existing = self.project_store.load(project_id, revision=expected_revision)
        except ProjectNotFound:
            latest = self.project_store.load_latest_with_recovery(project_id)
            if int(latest["revision"]) != base_revision:
                raise RevisionConflict(
                    f"review {review_id!r} is based on revision {base_revision}, "
                    f"but project is at revision {latest['revision']}"
                )
            existing = self.project_store.save(
                project_id,
                review["candidate_snapshot"],
                expected_revision=base_revision,
                metadata={
                    "review_id": review_id,
                    "review_decision": "accepted",
                    "review_actor": str(intent.get("actor") or "").strip(),
                },
            )
        if int(existing["revision"]) != expected_revision or not self._revision_matches_review(
            existing,
            review_id,
            review["candidate_snapshot"],
        ):
            raise RevisionConflict(
                f"revision {expected_revision} exists but does not belong to review {review_id!r}"
            )
        self._complete_acceptance(project_id, review_id, review, intent)
        return self.get(project_id, review_id)

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
        actor_value = str(actor or "").strip()
        if not actor_value:
            raise ValueError("actor is required")

        review = self.get(project_id, review_id)
        status = review["status"]
        if status == "accepting":
            if normalized != "accepted":
                raise ReviewConflict(f"review {review_id!r} has an acceptance in progress")
            intent = review["decision"]
            if str(intent.get("actor") or "") != actor_value:
                raise ReviewConflict(
                    f"review {review_id!r} acceptance was started by {intent.get('actor')!r}"
                )
            return self._finish_acceptance(project_id, review_id, review, intent)
        if status != "pending":
            raise ReviewConflict(f"review {review_id!r} is already {status}")

        if normalized == "rejected":
            self._write_event(
                project_id,
                review_id,
                1,
                {
                    "event_type": "decision_completed",
                    "decision": "rejected",
                    "decided_at": _utc_now(),
                    "actor": actor_value,
                    "note": str(note or ""),
                    "accepted_revision": None,
                },
            )
            return self.get(project_id, review_id)

        latest = self.project_store.load_latest_with_recovery(project_id)
        base_revision = int(review["base_revision"])
        if int(latest["revision"]) != base_revision:
            raise RevisionConflict(
                f"review {review_id!r} is based on revision {base_revision}, "
                f"but project is at revision {latest['revision']}"
            )
        intent = self._write_event(
            project_id,
            review_id,
            1,
            {
                "event_type": "decision_intent",
                "decision": "accepting",
                "decided_at": _utc_now(),
                "actor": actor_value,
                "note": str(note or ""),
                "accepted_revision": base_revision + 1,
            },
        )
        return self._finish_acceptance(project_id, review_id, review, intent)
