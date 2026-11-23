"""Immutable receipts for AI proposals that must not advance a review's base.

Native candidate creation already retains the candidate and opens a review.
Saving another project revision merely to record that execution would make the
review stale. These receipts bind execution to the accepted action and its
original source pin, while leaving project revision and review decisions alone.
"""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterator, Mapping

from .artifact_retention import load_artifact_pin, read_pinned_artifact_bytes, read_pinned_artifact_sidecars
from .project_store import ProjectStore, RevisionConflict


RECEIPT_SCHEMA = "hardware_splicer.ai_candidate_execution_receipt.v1"
_ADMIN_FIELDS = {"engineeringAiSessions", "engineeringFindings"}


def content_hash(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


@contextmanager
def candidate_execution_lock(run_dir: Path, *, api: bool = False) -> Iterator[None]:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / ("api_execution.lock" if api else "execution.lock")
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _binding(project_id: str, session: Mapping[str, Any], action: Mapping[str, Any]) -> dict[str, Any]:
    if session.get("project_id") != project_id or action.get("project_id") != project_id:
        raise ValueError("AI candidate execution project identity differs")
    if action.get("session_id") != session.get("session_id"):
        raise ValueError("AI candidate execution session identity differs")
    return {
        "project_id": project_id,
        "session_id": session["session_id"],
        "action_id": action["action_id"],
        "accepted_action_sha256": content_hash(action),
    }


def load_candidate_execution_receipt(
    run_dir: Path, project_id: str, session: Mapping[str, Any], action: Mapping[str, Any]
) -> dict[str, Any] | None:
    path = run_dir / "execution_receipt.json"
    if path.is_symlink():
        raise ValueError("AI execution receipt must not be a symlink")
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != RECEIPT_SCHEMA:
        raise ValueError("invalid AI candidate execution receipt")
    if any(data.get(key) != value for key, value in _binding(project_id, session, action).items()):
        raise ValueError("AI execution receipt does not match the accepted action")
    result = data.get("tool_result")
    if not isinstance(result, dict) or data.get("tool_result_sha256") != content_hash(result):
        raise ValueError("AI execution receipt result integrity failed")
    expected_result_identity = {
        "project_id": project_id,
        "session_id": session["session_id"],
        "action_id": action["action_id"],
        "action_type": action["action_type"],
        "project_revision": data.get("design_revision"),
    }
    if any(result.get(key) != value for key, value in expected_result_identity.items()):
        raise ValueError("AI execution receipt result identity differs")
    if result.get("status") not in {"succeeded", "failed"}:
        raise ValueError("AI execution receipt has an invalid result status")
    artifact = result.get("artifact")
    # A failed attempt may retain its diagnostic entirely in the immutable
    # receipt. It is still bound to the accepted action and result hash above.
    if artifact is None and result["status"] == "failed":
        return data
    if not isinstance(artifact, dict):
        raise ValueError("AI execution receipt requires a bound artifact")
    relative = artifact.get("project_relative_path")
    filename = Path(relative).name if isinstance(relative, str) else ""
    if not filename or relative != f"ai_tool_runs/{session['session_id']}/{action['action_id']}/{filename}":
        raise ValueError("AI execution artifact is not bound to this action")
    artifact_path = run_dir / filename
    if artifact_path.is_symlink() or not artifact_path.is_file():
        raise ValueError("AI execution artifact is missing or is a symlink")
    payload = artifact_path.read_bytes()
    if len(payload) != artifact.get("size_bytes") or hashlib.sha256(payload).hexdigest() != artifact.get("sha256"):
        raise ValueError("AI execution artifact integrity failed")
    return data


def store_candidate_execution_receipt(
    run_dir: Path, project_id: str, session: Mapping[str, Any], action: Mapping[str, Any],
    *, identity: Mapping[str, Any], result: Mapping[str, Any],
) -> dict[str, Any]:
    body = {
        "schema_version": RECEIPT_SCHEMA,
        **_binding(project_id, session, action),
        **dict(identity),
        "tool_result": dict(result),
        "tool_result_sha256": content_hash(result),
    }
    payload = (json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    run_dir.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".execution_receipt.", dir=run_dir)
    temporary = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, run_dir / "execution_receipt.json")
    finally:
        temporary.unlink(missing_ok=True)
    return body


def unchanged_execution_base(
    store: ProjectStore, project_id: str, *, pinned_revision: int,
    expected_revision: int | None, require_native_pin: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Permit administrative revisions only; changed source/design requires a new action."""
    original = store.load(project_id, revision=pinned_revision)
    latest = store.load(project_id)
    if expected_revision is not None and int(latest["revision"]) != expected_revision:
        raise RevisionConflict("project changed before AI source/edit execution")
    before = {key: value for key, value in original["snapshot"].items() if key not in _ADMIN_FIELDS}
    after = {key: value for key, value in latest["snapshot"].items() if key not in _ADMIN_FIELDS}
    if before != after:
        raise RevisionConflict("project source or design changed since the accepted action's pinned revision")
    identity: dict[str, Any] = {
        "design_revision": pinned_revision,
        "review_base_revision": int(latest["revision"]),
        "design_snapshot_sha256": content_hash(before),
        "registered_sources_sha256": content_hash(before.get("engineeringSources") or []),
    }
    if require_native_pin:
        original_pin = load_artifact_pin(store, project_id, pinned_revision)
        latest_pin = load_artifact_pin(store, project_id, int(latest["revision"]))
        if not original_pin or not latest_pin:
            raise ValueError("native editing requires retained artifacts at both the action and review revisions")
        # Include sidecar inventories as well as native files; timestamps and
        # retention bookkeeping do not describe the source design.
        def pin_identity(pin: Mapping[str, Any]) -> dict[str, Any]:
            return {key: value for key, value in pin.items()
                    if key not in {"schema_version", "project_id", "revision", "retained_at", "retention_basis"}}
        if pin_identity(original_pin) != pin_identity(latest_pin):
            raise RevisionConflict("retained source artifacts changed since the accepted action")
        for revision in {pinned_revision, int(latest["revision"])}:
            for kind in ("pcb", "schematic"):
                read_pinned_artifact_bytes(store, project_id, revision, kind)
                read_pinned_artifact_sidecars(store, project_id, revision, kind)
        identity["artifact_pin_sha256"] = content_hash(pin_identity(original_pin))
    return latest, identity
