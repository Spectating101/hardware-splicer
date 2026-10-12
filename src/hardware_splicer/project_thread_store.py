"""Append-only review threads anchored to a project object, finding, or artifact.

Threads are discussion only. They never alter a project snapshot, revision,
staged review, or any authority or release field.

Author identity is self-declared unless a pre-verified operator identity is
supplied. A verified comment is still only a comment.
"""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping

from .operator_identity import OperatorIdentity
from .project_store import InvalidProjectId, ProjectNotFound, ProjectStore, validate_project_id

PROJECT_THREAD_SCHEMA = "hardware_splicer.review_thread.v1"
_AUTHORITY_KEYS = frozenset(
    {"authority", "release", "fabrication", "power_on", "status", "revision_override"}
)
_ANCHOR_KEYS = frozenset({"revision", "object_id", "finding_ref", "artifact", "position"})
_AUTHOR_KEYS = frozenset({"kind", "id"})
_ARTIFACT_KEYS = frozenset({"relative", "kind"})
_POSITION_KEYS = frozenset({"x_mm", "y_mm"})
_ARTIFACT_KINDS = frozenset({"schematic", "pcb"})
_POSITION_ABS_MAX = 1e5
_VERIFIED_BY_OPERATOR_TOKEN = "operator-token"
_AUTHOR_KINDS = frozenset({"human", "agent", "system"})
_EVENT_TYPES = frozenset({"comment", "resolve", "reopen"})
_MAX_LABEL = 200
_MAX_AUTHOR_ID = 120
_MAX_COMMENT = 4000
_MAX_NOTE = 1000
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_BODY_ALLOWED_CONTROLS = frozenset({"\n", "\r", "\t"})


class ProjectThreadError(RuntimeError):
    pass


class ThreadNotFound(ProjectThreadError, FileNotFoundError):
    pass


class ThreadConflict(ProjectThreadError):
    pass


class ThreadStateError(ProjectThreadError):
    pass


class ThreadValidationError(ProjectThreadError, ValueError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reject_symlink(path: Path, *, label: str) -> None:
    if path.is_symlink():
        raise ProjectThreadError(f"{label} must not be a symlink")


def _path_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _read_json(path: Path) -> Dict[str, Any]:
    _reject_symlink(path, label=path.name)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectThreadError(f"cannot read thread JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ProjectThreadError(f"thread JSON must be an object: {path}")
    return value


def _json_payload(value: Mapping[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    _reject_symlink(path, label=path.name)
    _reject_symlink(path.parent, label=path.parent.name)
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

    _reject_symlink(path, label=path.name)
    _reject_symlink(path.parent, label=path.parent.name)
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
            raise ThreadConflict(f"immutable thread record already exists: {path.name}") from exc
    finally:
        temp_path.unlink(missing_ok=True)


def _is_forbidden_key(key: Any) -> bool:
    raw = str(key)
    lowered = raw.lower()
    return "authoriz" in lowered or lowered in _AUTHORITY_KEYS


def reject_authority_keys(value: Mapping[str, Any], *, label: str) -> None:
    for key, nested in value.items():
        if _is_forbidden_key(key):
            raise ThreadValidationError(f"{label} must not contain authority field {key!r}")
        if isinstance(nested, Mapping):
            reject_authority_keys(nested, label=f"{label}.{key}")


def _has_control_chars(value: str) -> bool:
    return any(unicodedata.category(ch).startswith("C") for ch in value)


def _has_disallowed_body_controls(value: str) -> bool:
    for ch in value:
        if ch in _BODY_ALLOWED_CONTROLS:
            continue
        if unicodedata.category(ch).startswith("C"):
            return True
    return False


def _is_absolute_artifact_path(relative: str) -> bool:
    if os.path.isabs(relative) or relative.startswith("/") or relative.startswith("\\"):
        return True
    return _WINDOWS_DRIVE_RE.match(relative) is not None


def _require_mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ThreadValidationError(f"{label} must be an object")
    return value


def _clean_label(value: Any, *, field: str, max_len: int = _MAX_LABEL) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ThreadValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > max_len:
        raise ThreadValidationError(f"{field} must be at most {max_len} characters")
    if _has_control_chars(cleaned):
        raise ThreadValidationError(f"{field} must not contain control characters")
    return cleaned


def _normalize_artifact(value: Any) -> Dict[str, str] | None:
    if value is None:
        return None
    artifact = _require_mapping(value, label="anchor.artifact")
    reject_authority_keys(artifact, label="anchor.artifact")
    extra = set(artifact) - _ARTIFACT_KEYS
    if extra:
        raise ThreadValidationError(f"anchor.artifact contains unknown fields: {sorted(extra)}")
    relative = _clean_label(artifact.get("relative"), field="artifact.relative")
    if relative is None:
        raise ThreadValidationError("artifact.relative is required")
    if _is_absolute_artifact_path(relative):
        raise ThreadValidationError("artifact.relative must not be an absolute path")
    segments = [part for part in relative.replace("\\", "/").split("/") if part]
    if ".." in segments:
        raise ThreadValidationError("artifact.relative must not contain '..' segments")
    kind = artifact.get("kind")
    if not isinstance(kind, str) or kind.strip() not in _ARTIFACT_KINDS:
        raise ThreadValidationError("artifact.kind must be 'schematic' or 'pcb'")
    return {"relative": relative, "kind": kind.strip()}


def _finite_millimetre(value: Any, *, field: str) -> float:
    range_message = f"{field} must be a finite number within +-100000 mm"
    if type(value) is bool:
        raise ThreadValidationError(f"{field} must be a finite number")
    if type(value) is int:
        if abs(value) > _POSITION_ABS_MAX:
            raise ThreadValidationError(range_message)
        return round(float(value), 3)
    if type(value) is not float:
        raise ThreadValidationError(f"{field} must be a finite number")
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise ThreadValidationError(range_message) from exc
    if not math.isfinite(number) or abs(number) > _POSITION_ABS_MAX:
        raise ThreadValidationError(range_message)
    return round(number, 3)


def _normalize_position(value: Any) -> Dict[str, float] | None:
    if value is None:
        return None
    position = _require_mapping(value, label="anchor.position")
    reject_authority_keys(position, label="anchor.position")
    extra = set(position) - _POSITION_KEYS
    if extra:
        raise ThreadValidationError(f"anchor.position contains unknown fields: {sorted(extra)}")
    if "x_mm" not in position or "y_mm" not in position:
        raise ThreadValidationError("anchor.position requires x_mm and y_mm")
    return {
        "x_mm": _finite_millimetre(position.get("x_mm"), field="position.x_mm"),
        "y_mm": _finite_millimetre(position.get("y_mm"), field="position.y_mm"),
    }


def _normalize_anchor(anchor: Any, *, latest_revision: int | None = None) -> Dict[str, Any]:
    raw = _require_mapping(anchor, label="anchor")
    reject_authority_keys(raw, label="anchor")
    extra = set(raw) - _ANCHOR_KEYS
    if extra:
        raise ThreadValidationError(f"anchor contains unknown fields: {sorted(extra)}")
    revision = raw.get("revision")
    if type(revision) is not int:
        raise ThreadValidationError("anchor.revision must be an integer")
    if revision < 1:
        raise ThreadValidationError("anchor.revision must be at least 1")
    if latest_revision is not None and revision > latest_revision:
        raise ThreadValidationError(
            f"anchor.revision {revision} is above latest revision {latest_revision}"
        )
    object_id = _clean_label(raw.get("object_id"), field="object_id")
    finding_ref = _clean_label(raw.get("finding_ref"), field="finding_ref")
    artifact = _normalize_artifact(raw.get("artifact"))
    position = _normalize_position(raw.get("position"))
    if position is not None and artifact is None:
        raise ThreadValidationError("position requires artifact")
    if object_id is None and finding_ref is None and artifact is None:
        raise ThreadValidationError("anchor must include object_id, finding_ref, or artifact")
    return {
        "revision": revision,
        "object_id": object_id,
        "finding_ref": finding_ref,
        "artifact": artifact,
        "position": position,
    }


def _normalize_author(author: Any) -> Dict[str, str]:
    raw = _require_mapping(author, label="author")
    reject_authority_keys(raw, label="author")
    extra = set(raw) - _AUTHOR_KEYS
    if extra:
        raise ThreadValidationError(f"author contains unknown fields: {sorted(extra)}")
    kind = raw.get("kind")
    if not isinstance(kind, str) or kind.strip() not in _AUTHOR_KINDS:
        raise ThreadValidationError("author.kind must be 'human', 'agent', or 'system'")
    kind = kind.strip()
    author_id = raw.get("id")
    if not isinstance(author_id, str):
        raise ThreadValidationError("author.id is required")
    author_id = author_id.strip()
    if not author_id:
        if kind == "agent":
            raise ThreadValidationError("agent authors must have a non-empty id naming the agent/model")
        raise ThreadValidationError("author.id is required")
    if len(author_id) > _MAX_AUTHOR_ID:
        raise ThreadValidationError(f"author.id must be at most {_MAX_AUTHOR_ID} characters")
    return {"kind": kind, "id": author_id}


def _resolve_event_author(
    author: Mapping[str, Any] | None,
    verified_operator: OperatorIdentity | None,
) -> tuple[Dict[str, str], bool]:
    if verified_operator is None:
        return _normalize_author(author), False
    return _normalize_author({"kind": verified_operator.kind, "id": verified_operator.id}), True


def _normalize_body(body: Any, *, event_type: str) -> str:
    if body is None:
        text = ""
    elif isinstance(body, str):
        text = body.strip()
    else:
        raise ThreadValidationError("body must be a string")
    if event_type == "comment":
        if not text:
            raise ThreadValidationError("comment body is required")
        if len(text) > _MAX_COMMENT:
            raise ThreadValidationError(f"comment body must be at most {_MAX_COMMENT} characters")
    elif len(text) > _MAX_NOTE:
        raise ThreadValidationError(f"{event_type} body must be at most {_MAX_NOTE} characters")
    if _has_disallowed_body_controls(text):
        raise ThreadValidationError("body must not contain control characters other than newline, carriage return, or tab")
    return text


def _derived_status(events: list[Mapping[str, Any]]) -> str:
    status = "open"
    for event in events:
        event_type = event.get("type")
        if event_type == "resolve":
            status = "resolved"
        elif event_type == "reopen":
            status = "open"
    return status


def _comment_count(events: list[Mapping[str, Any]]) -> int:
    return sum(1 for event in events if event.get("type") == "comment")


def _validate_stored_anchor(anchor: Any) -> None:
    try:
        _normalize_anchor(anchor)
    except ThreadValidationError as exc:
        raise ProjectThreadError("thread anchor is structurally corrupt") from exc


def _validate_thread_record(
    value: Mapping[str, Any],
    *,
    project_id: str,
    thread_id: str,
) -> Dict[str, Any]:
    try:
        if value.get("schema_version") != PROJECT_THREAD_SCHEMA:
            raise ProjectThreadError("thread schema_version is missing or unsupported")
        stored_thread = value.get("thread_id")
        if not isinstance(stored_thread, str) or stored_thread != thread_id:
            raise ProjectThreadError("thread_id does not match the thread directory")
        stored_project = value.get("project_id")
        if not isinstance(stored_project, str) or stored_project != project_id:
            raise ProjectThreadError("project_id does not match the project directory")
        anchor = value.get("anchor")
        if not isinstance(anchor, Mapping):
            raise ProjectThreadError("thread anchor must be an object")
        _validate_stored_anchor(anchor)
        if not isinstance(value.get("created_at"), str):
            raise ProjectThreadError("thread created_at must be a string")
    except ProjectThreadError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise ProjectThreadError("thread record is structurally corrupt") from exc
    return dict(value)


def _validate_event_record(value: Mapping[str, Any], *, sequence: int) -> Dict[str, Any]:
    try:
        seq = value.get("seq")
        if seq.__class__ is not int or seq != sequence:
            raise ProjectThreadError(f"event seq must equal file number {sequence}")
        if value.get("type") not in _EVENT_TYPES:
            raise ProjectThreadError("event type is missing or unsupported")
        author = value.get("author")
        if not isinstance(author, Mapping):
            raise ProjectThreadError("event author must be an object")
        if author.get("kind") not in _AUTHOR_KINDS:
            raise ProjectThreadError("event author.kind is missing or unsupported")
        author_id = author.get("id")
        if not isinstance(author_id, str) or not author_id:
            raise ProjectThreadError("event author.id must be a non-empty string")
        author_verified = value.get("author_verified")
        if author_verified is True:
            if value.get("verified_by") != _VERIFIED_BY_OPERATOR_TOKEN:
                raise ProjectThreadError(
                    "event author_verified true requires verified_by 'operator-token'"
                )
        elif author_verified is False:
            if "verified_by" in value:
                raise ProjectThreadError("event author_verified false must omit verified_by")
        else:
            raise ProjectThreadError("event author_verified must be exactly true or false")
        if not isinstance(value.get("body"), str):
            raise ProjectThreadError("event body must be a string")
        if not isinstance(value.get("created_at"), str):
            raise ProjectThreadError("event created_at must be a string")
    except ProjectThreadError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise ProjectThreadError("event record is structurally corrupt") from exc
    return dict(value)


class ProjectThreadStore:
    """Store discussion threads beside a project tree without touching authority."""

    def __init__(self, root: str | Path | ProjectStore | None = None) -> None:
        if isinstance(root, ProjectStore):
            self.project_store = root
        else:
            self.project_store = ProjectStore(root)

    def _project_dir(self, project_id: str) -> Path:
        safe_id = validate_project_id(project_id)
        path = (self.project_store.root / safe_id).resolve()
        if path.parent != self.project_store.root:
            raise InvalidProjectId("project_id resolves outside project root")
        if not path.is_dir():
            raise ProjectNotFound(safe_id)
        return path

    def _assert_inside_project(self, path: Path, project_dir: Path, *, label: str) -> None:
        _reject_symlink(path, label=label)
        if path.exists() and not _path_inside(path, project_dir):
            raise ProjectThreadError(f"{label} resolves outside the project directory")

    def _assert_threads_tree_has_no_symlinks(self, threads_root: Path) -> None:
        _reject_symlink(threads_root, label="threads directory")
        if not threads_root.exists():
            return
        if not threads_root.is_dir():
            raise ProjectThreadError("threads path is not a directory")
        for thread_dir in threads_root.iterdir():
            _reject_symlink(thread_dir, label="thread directory")
            if not thread_dir.is_dir():
                continue
            _reject_symlink(thread_dir / "thread.json", label="thread.json")
            events_dir = thread_dir / "events"
            _reject_symlink(events_dir, label="events directory")
            if events_dir.is_dir():
                for event_path in events_dir.iterdir():
                    _reject_symlink(event_path, label="event file")

    def _thread_root(self, project_id: str) -> Path:
        project_dir = self._project_dir(project_id)
        threads = project_dir / "threads"
        self._assert_inside_project(threads, project_dir, label="threads directory")
        if threads.exists():
            self._assert_threads_tree_has_no_symlinks(threads)
        return threads

    def _thread_dir(self, project_id: str, thread_id: str) -> Path:
        safe_thread = validate_project_id(thread_id)
        project_dir = self._project_dir(project_id)
        path = self._thread_root(project_id) / safe_thread
        self._assert_inside_project(path, project_dir, label="thread directory")
        return path

    def _events_dir(self, project_id: str, thread_id: str) -> Path:
        project_dir = self._project_dir(project_id)
        events_dir = self._thread_dir(project_id, thread_id) / "events"
        self._assert_inside_project(events_dir, project_dir, label="events directory")
        return events_dir

    def _event_path(self, project_id: str, thread_id: str, sequence: int) -> Path:
        path = self._events_dir(project_id, thread_id) / f"{int(sequence):08d}.json"
        _reject_symlink(path, label="event file")
        return path

    def _events(self, project_id: str, thread_id: str) -> list[Dict[str, Any]]:
        events_dir = self._events_dir(project_id, thread_id)
        if not events_dir.is_dir():
            return []
        events: list[Dict[str, Any]] = []
        file_seqs: list[int] = []
        for path in sorted(events_dir.glob("*.json")):
            _reject_symlink(path, label="event file")
            if not path.stem.isdigit():
                raise ProjectThreadError(f"event file name is not a sequence: {path.name}")
            sequence = int(path.stem)
            events.append(_validate_event_record(_read_json(path), sequence=sequence))
            file_seqs.append(sequence)
        if file_seqs != list(range(1, len(file_seqs) + 1)):
            raise ProjectThreadError("event sequence must be contiguous from 1")
        return events

    def _latest_revision(self, project_id: str) -> int:
        return int(self.project_store.load(project_id)["revision"])

    def _write_event(
        self,
        project_id: str,
        thread_id: str,
        sequence: int,
        event_type: str,
        author: Mapping[str, str],
        body: str,
        *,
        verified: bool = False,
    ) -> Dict[str, Any]:
        record: Dict[str, Any] = {
            "seq": int(sequence),
            "type": event_type,
            "author": dict(author),
            "author_verified": bool(verified),
            "body": body,
            "created_at": _utc_now(),
        }
        if verified:
            record["verified_by"] = _VERIFIED_BY_OPERATOR_TOKEN
        _atomic_create_json(self._event_path(project_id, thread_id, sequence), record)
        return record

    def _thread_view(
        self,
        project_id: str,
        thread_id: str,
        *,
        include_events: bool,
    ) -> Dict[str, Any]:
        thread_path = self._thread_dir(project_id, thread_id) / "thread.json"
        _reject_symlink(thread_path, label="thread.json")
        if not thread_path.is_file():
            raise ThreadNotFound(thread_id)
        try:
            meta = _validate_thread_record(
                _read_json(thread_path),
                project_id=project_id,
                thread_id=thread_id,
            )
            events = self._events(project_id, thread_id)
            if not events or events[0].get("seq") != 1:
                raise ProjectThreadError("committed thread is missing event 1")
            last_event_at = events[-1]["created_at"]
        except ProjectThreadError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectThreadError(f"thread {thread_id!r} is structurally corrupt") from exc
        view = {
            **meta,
            "status": _derived_status(events),
            "comment_count": _comment_count(events),
            "last_event_at": last_event_at,
        }
        if include_events:
            view["events"] = events
        return view

    def create_thread(
        self,
        project_id: str,
        anchor: Mapping[str, Any],
        author: Mapping[str, Any] | None,
        body: str,
        verified_operator: OperatorIdentity | None = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if kwargs:
            reject_authority_keys(kwargs, label="thread")
        safe_id = validate_project_id(project_id)
        latest_revision = self._latest_revision(safe_id)
        normalized_anchor = _normalize_anchor(anchor, latest_revision=latest_revision)
        normalized_author, verified = _resolve_event_author(author, verified_operator)
        comment_body = _normalize_body(body, event_type="comment")

        thread_id = f"thread-{uuid.uuid4().hex[:16]}"
        thread_dir = self._thread_dir(safe_id, thread_id)
        if thread_dir.exists():
            raise ThreadConflict(f"thread already exists: {thread_id}")
        record = {
            "schema_version": PROJECT_THREAD_SCHEMA,
            "thread_id": thread_id,
            "project_id": safe_id,
            "anchor": normalized_anchor,
            "created_at": _utc_now(),
        }
        self._write_event(
            safe_id,
            thread_id,
            1,
            "comment",
            normalized_author,
            comment_body,
            verified=verified,
        )
        _atomic_write_json(thread_dir / "thread.json", record)
        return self.get_thread(safe_id, thread_id)

    def list_threads(
        self,
        project_id: str,
        object_id: str | None = None,
        status: str | None = None,
        **kwargs: Any,
    ) -> list[Dict[str, Any]]:
        if kwargs:
            reject_authority_keys(kwargs, label="list")
        if status is not None and status not in {"open", "resolved"}:
            raise ThreadValidationError("status must be 'open' or 'resolved'")
        threads_root = self._thread_root(project_id)
        if not threads_root.is_dir():
            return []
        object_filter = object_id.strip() if isinstance(object_id, str) and object_id.strip() else None
        rows: list[Dict[str, Any]] = []
        for directory in threads_root.iterdir():
            _reject_symlink(directory, label="thread directory")
            if not directory.is_dir():
                continue
            thread_path = directory / "thread.json"
            _reject_symlink(thread_path, label="thread.json")
            if not thread_path.is_file():
                continue
            row = self._thread_view(project_id, directory.name, include_events=False)
            if object_filter is not None and row.get("anchor", {}).get("object_id") != object_filter:
                continue
            if status is not None and row.get("status") != status:
                continue
            rows.append(row)
        rows.sort(key=lambda row: str(row.get("last_event_at") or ""), reverse=True)
        return rows

    def get_thread(self, project_id: str, thread_id: str) -> Dict[str, Any]:
        return self._thread_view(project_id, thread_id, include_events=True)

    def append_event(
        self,
        project_id: str,
        thread_id: str,
        type: str,
        author: Mapping[str, Any] | None,
        body: str = "",
        expected_event_seq: int | None = None,
        verified_operator: OperatorIdentity | None = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if kwargs:
            reject_authority_keys(kwargs, label="event")
        current = self.get_thread(project_id, thread_id)
        events = current["events"]
        last_seq = int(events[-1]["seq"]) if events else 0
        if expected_event_seq is not None:
            if expected_event_seq.__class__ is not int:
                raise ThreadValidationError("expected_event_seq must be an integer")
            if expected_event_seq != last_seq:
                raise ThreadConflict(
                    f"thread {thread_id!r} is at event {last_seq}, expected {expected_event_seq}"
                )
        event_type = str(type or "").strip()
        if event_type not in _EVENT_TYPES:
            raise ThreadValidationError("event type must be 'comment', 'resolve', or 'reopen'")
        status = current["status"]
        if event_type == "resolve" and status != "open":
            raise ThreadStateError(f"thread {thread_id!r} is {status} and cannot be resolved")
        if event_type == "reopen" and status != "resolved":
            raise ThreadStateError(f"thread {thread_id!r} is {status} and cannot be reopened")
        normalized_author, verified = _resolve_event_author(author, verified_operator)
        note = _normalize_body(body, event_type=event_type)
        return self._write_event(
            project_id,
            thread_id,
            last_seq + 1,
            event_type,
            normalized_author,
            note,
            verified=verified,
        )
