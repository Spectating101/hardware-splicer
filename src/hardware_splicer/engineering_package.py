"""Deterministic, revision-pinned Engineering Package export.

The package is a reproducible ZIP of bounded project truth, AI proposals, human
decisions, software preview evidence, repair lineage, conversation briefings, and
authority state. It never copies registered raw source bytes into the export.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

from .ai_project_orchestrator import _sanitize_value
from .project_store import ProjectStore, validate_project_id

ENGINEERING_PACKAGE_SCHEMA = "hardware_splicer.engineering_package.v1"
ENGINEERING_PACKAGE_MANIFEST_SCHEMA = "hardware_splicer.engineering_package_manifest.v1"
ENGINEERING_PACKAGE_RECORD_SCHEMA = "hardware_splicer.engineering_package_record.v1"
_PACKAGE_ID_RE = re.compile(r"engineering-package-r[0-9]{8}-[a-f0-9]{16}\Z")
_MAX_PACKAGE_BYTES = 64 * 1024 * 1024
_AUTHORITY_FIELDS = (
    "fabrication_authorized",
    "firmware_flash_authorized",
    "flash_authorized",
    "power_on_authorized",
    "motion_authorized",
    "operational_authorized",
    "release_authorized",
)
_SECRET_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "access_token",
    "refresh_token",
}


class EngineeringPackageError(RuntimeError):
    """Base error for deterministic Engineering Package export."""


class InvalidEngineeringPackage(EngineeringPackageError, ValueError):
    pass


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any, *, limit: int = 4096) -> list[Dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(row) for row in list(value)[:limit] if isinstance(row, Mapping)]


def _strings(value: Any, *, limit: int = 4096) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [str(row) for row in list(value)[:limit] if str(row).strip()]


def _clean(value: Any, *, depth: int = 0) -> Any:
    """Sanitize raw-content fields, secrets, binary values, and unbounded objects."""

    value = _sanitize_value(value, depth=depth)
    if isinstance(value, Mapping):
        result: Dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            if key.lower() in _SECRET_KEYS:
                continue
            result[key] = _clean(raw_value, depth=depth + 1)
        return result
    if isinstance(value, list):
        return [_clean(row, depth=depth + 1) for row in value]
    return value


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _session_rows(snapshot: Mapping[str, Any]) -> list[Dict[str, Any]]:
    return _rows(snapshot.get("engineeringAiSessions"))


def _source_rows(snapshot: Mapping[str, Any]) -> tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
    registered = [_clean(row) for row in _rows(snapshot.get("engineeringSources"))]
    parsed = [_clean(row) for row in _rows(snapshot.get("engineeringParsedSources"))]
    return registered, parsed


def _requirements(sessions: Iterable[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for session in sessions:
        session_id = str(session.get("session_id") or "")
        for row in _rows(session.get("requirements")):
            requirement_id = str(row.get("id") or "")
            key = (session_id, requirement_id or hashlib.sha256(_canonical_json_bytes(row)).hexdigest())
            if key in seen:
                continue
            seen.add(key)
            result.append(
                {
                    "session_id": session_id,
                    "session_kind": str(session.get("session_kind") or "project_proposal"),
                    **_clean(row),
                }
            )
    return result


def _candidates(sessions: Iterable[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    for session in sessions:
        session_id = str(session.get("session_id") or "")
        for row in _rows(session.get("architecture_candidates"), limit=256):
            result.append(
                {
                    "session_id": session_id,
                    "session_kind": str(session.get("session_kind") or "project_proposal"),
                    **_clean(row),
                }
            )
    return result


def _actions(sessions: Iterable[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    for session in sessions:
        session_id = str(session.get("session_id") or "")
        for action in _rows(session.get("actions"), limit=4096):
            tool_result = _mapping(action.get("tool_result"))
            result.append(
                {
                    "session_id": session_id,
                    "session_kind": str(session.get("session_kind") or "project_proposal"),
                    "action_id": str(action.get("action_id") or ""),
                    "action_type": str(action.get("action_type") or ""),
                    "title": str(action.get("title") or ""),
                    "rationale": str(action.get("rationale") or ""),
                    "status": str(action.get("status") or ""),
                    "project_revision": action.get("project_revision"),
                    "source_ids": _strings(action.get("source_ids"), limit=64),
                    "origin_turn_id": action.get("origin_turn_id"),
                    "inputs": _clean(action.get("inputs") or {}),
                    "decision": _clean(action.get("decision") or {}),
                    "tool_result_status": tool_result.get("status"),
                    "tool_artifact": _clean(tool_result.get("artifact") or {}),
                    "repair_sessions": _clean(_rows(action.get("repair_sessions"), limit=64)),
                    "automatic_execution": False,
                    "authority_effect": str(action.get("authority_effect") or "none"),
                }
            )
    return result


def _tool_results(sessions: Iterable[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    for session in sessions:
        for action in _rows(session.get("actions"), limit=4096):
            tool_result = _mapping(action.get("tool_result"))
            if not tool_result:
                continue
            result.append(
                {
                    "session_id": str(session.get("session_id") or ""),
                    "action_id": str(action.get("action_id") or ""),
                    "action_type": str(action.get("action_type") or ""),
                    "status": str(tool_result.get("status") or ""),
                    "executor_identity": str(tool_result.get("executor_identity") or ""),
                    "project_revision": tool_result.get("project_revision"),
                    "summary": _clean(tool_result.get("summary") or {}),
                    "error": _clean(tool_result.get("error") or {}),
                    "artifact": _clean(tool_result.get("artifact") or {}),
                    "automatic_execution": False,
                    "physical_authority_unchanged": bool(
                        tool_result.get("physical_authority_unchanged", True)
                    ),
                }
            )
    return result


def _decisions(sessions: Iterable[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    for session in sessions:
        for action in _rows(session.get("actions"), limit=4096):
            decision = _mapping(action.get("decision"))
            if not decision:
                continue
            result.append(
                {
                    "session_id": str(session.get("session_id") or ""),
                    "action_id": str(action.get("action_id") or ""),
                    "action_type": str(action.get("action_type") or ""),
                    "action_status": str(action.get("status") or ""),
                    "decision": _clean(decision),
                }
            )
    return result


def _repairs(sessions: Iterable[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    return [
        {
            "session_id": str(session.get("session_id") or ""),
            "project_revision": session.get("project_revision"),
            "provider": session.get("provider"),
            "model": session.get("model"),
            "repair_of": _clean(session.get("repair_of") or {}),
            "summary": session.get("summary"),
            "candidate_ids": [
                str(row.get("id") or "")
                for row in _rows(session.get("architecture_candidates"), limit=16)
            ],
            "action_ids": [
                str(row.get("action_id") or "")
                for row in _rows(session.get("actions"), limit=64)
            ],
            "automatic_execution": False,
        }
        for session in sessions
        if str(session.get("session_kind") or "") == "failure_repair"
    ]


def _conversation_turns(sessions: Iterable[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    for session in sessions:
        for turn in _rows(session.get("conversationTurns"), limit=4096):
            result.append(
                {
                    "session_id": str(session.get("session_id") or ""),
                    "turn_id": str(turn.get("turn_id") or ""),
                    "project_revision": turn.get("project_revision"),
                    "created_at": turn.get("created_at"),
                    "user_message": turn.get("user_message"),
                    "assistant_answer": turn.get("assistant_answer"),
                    "answer_kind": turn.get("answer_kind"),
                    "evidence_refs": _clean(_rows(turn.get("evidence_refs"), limit=64)),
                    "blockers": _strings(turn.get("blockers"), limit=128),
                    "recommended_action_id": turn.get("recommended_action_id"),
                    "provider": turn.get("provider"),
                    "model": turn.get("model"),
                    "prompt_sha256": turn.get("prompt_sha256"),
                    "context_sha256": turn.get("context_sha256"),
                    "response_sha256": turn.get("response_sha256"),
                    "automatic_execution": False,
                }
            )
    return result


def _source_conflicts(snapshot: Mapping[str, Any]) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    for key in (
        "engineeringSourceConflicts",
        "sourceConflicts",
        "declaredConflicts",
    ):
        result.extend(_clean(_rows(snapshot.get(key), limit=1024)))
    source_graph = _mapping(
        snapshot.get("engineeringSourceGraph")
        or snapshot.get("engineering_source_graph")
    )
    result.extend(_clean(_rows(source_graph.get("conflicts"), limit=1024)))
    return result


def _blockers(
    snapshot: Mapping[str, Any],
    sessions: Iterable[Mapping[str, Any]],
    tool_results: Iterable[Mapping[str, Any]],
) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, message: Any, *, object_id: str = "") -> None:
        text = str(message or "").strip()
        if not text:
            return
        key = (kind, f"{object_id}:{text}")
        if key in seen:
            return
        seen.add(key)
        result.append({"kind": kind, "object_id": object_id, "message": text})

    for key in ("missingInfo", "missing_info", "blockers"):
        for message in _strings(snapshot.get(key), limit=2048):
            add("project", message)
    status = _mapping(snapshot.get("engineeringStatus") or snapshot.get("engineering_status"))
    for row in _rows(status.get("blockers"), limit=2048):
        add(
            "engineering_status",
            row.get("message") or row.get("reason") or row.get("title"),
            object_id=str(row.get("blocker_id") or row.get("object_id") or ""),
        )
    for session in sessions:
        session_id = str(session.get("session_id") or "")
        for question in _strings(session.get("open_questions"), limit=512):
            add("open_question", question, object_id=session_id)
        for turn in _rows(session.get("conversationTurns"), limit=4096):
            turn_id = str(turn.get("turn_id") or "")
            for message in _strings(turn.get("blockers"), limit=512):
                add("conversation", message, object_id=turn_id)
    for result_row in tool_results:
        if str(result_row.get("status") or "") != "failed":
            continue
        error = _mapping(result_row.get("error"))
        summary = _mapping(result_row.get("summary"))
        add(
            "tool_failure",
            error.get("message") or summary.get("error") or "Software preview failed.",
            object_id=str(result_row.get("action_id") or ""),
        )
    return result


def _authority_state(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    values = {field: snapshot.get(field) for field in _AUTHORITY_FIELDS}
    return {
        "schema_version": "hardware_splicer.engineering_package_authority.v1",
        "project_authority": values,
        "package_creation_authority_effect": "none",
        "package_is_software_evidence": True,
        "package_authorizes_physical_action": False,
    }


def _artifact_references(
    registered_sources: Iterable[Mapping[str, Any]],
    parsed_sources: Iterable[Mapping[str, Any]],
    tool_results: Iterable[Mapping[str, Any]],
) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    for kind, collection in (
        ("registered_source", registered_sources),
        ("parsed_source", parsed_sources),
    ):
        for row in collection:
            result.append(
                {
                    "kind": kind,
                    "source_id": row.get("source_id"),
                    "content_hash": row.get("content_hash"),
                    "source_type": row.get("source_type"),
                    "authority_ceiling": row.get("authority_ceiling"),
                    "storage": _clean(row.get("storage") or {}),
                    "metadata": _clean(row.get("metadata") or {}),
                    "raw_bytes_included": False,
                }
            )
    for row in tool_results:
        artifact = _mapping(row.get("artifact"))
        if artifact:
            result.append(
                {
                    "kind": "software_preview_artifact",
                    "session_id": row.get("session_id"),
                    "action_id": row.get("action_id"),
                    "status": row.get("status"),
                    "project_relative_path": artifact.get("project_relative_path"),
                    "sha256": artifact.get("sha256"),
                    "size_bytes": artifact.get("size_bytes"),
                    "bytes_included": False,
                }
            )
    return result


def _readme(
    *,
    project_id: str,
    source_revision: int,
    package_id: str,
    file_names: Sequence[str],
) -> str:
    listing = "\n".join(f"- `{name}`" for name in file_names)
    return f"""# Hardware Splicer Engineering Package

Project: `{project_id}`  
Source revision: `{source_revision}`  
Package: `{package_id}`

This package is a deterministic, reviewable export of project evidence and engineering history. It contains source descriptors and hashes, not registered raw source bytes.

The package records AI proposals, human decisions, software previews, failures, repairs, conversation briefings, blockers, and the current authority state. None of these records grants fabrication, flashing, power-on, motion, operational, or release authority.

## Files

{listing}

`MANIFEST.json` identifies every included file by SHA-256 and byte count. The manifest intentionally excludes a self-hash. The ZIP itself is identified by the package record returned by the Hardware Splicer API.
"""


def package_payloads(
    project_id: str,
    source_revision: int,
    snapshot: Mapping[str, Any],
    *,
    source_saved_at: str = "",
) -> tuple[str, Dict[str, bytes], Dict[str, Any]]:
    """Build deterministic package file payloads without touching the filesystem."""

    clean_snapshot = _clean(snapshot)
    snapshot_bytes = _canonical_json_bytes(clean_snapshot)
    snapshot_sha256 = _sha256(snapshot_bytes)
    package_id = (
        f"engineering-package-r{int(source_revision):08d}-{snapshot_sha256[:16]}"
    )
    sessions = _session_rows(snapshot)
    registered_sources, parsed_sources = _source_rows(snapshot)
    requirements = _requirements(sessions)
    candidates = _candidates(sessions)
    actions = _actions(sessions)
    tool_results = _tool_results(sessions)
    decisions = _decisions(sessions)
    repairs = _repairs(sessions)
    turns = _conversation_turns(sessions)
    blockers = _blockers(snapshot, sessions, tool_results)
    source_conflicts = _source_conflicts(snapshot)
    artifacts = _artifact_references(registered_sources, parsed_sources, tool_results)
    latest_session = sessions[-1] if sessions else {}

    project_brief = {
        "schema_version": ENGINEERING_PACKAGE_SCHEMA,
        "project_id": project_id,
        "source_revision": int(source_revision),
        "source_saved_at": str(source_saved_at or ""),
        "snapshot_sha256": snapshot_sha256,
        "name": snapshot.get("name") or snapshot.get("projectName") or project_id,
        "mode": snapshot.get("mode"),
        "current_stage": snapshot.get("currentStage") or snapshot.get("current_stage"),
        "mission": latest_session.get("mission") or snapshot.get("mission"),
        "latest_ai_session_id": latest_session.get("session_id"),
        "source_count": len(registered_sources),
        "parsed_source_count": len(parsed_sources),
        "requirement_count": len(requirements),
        "candidate_count": len(candidates),
        "action_count": len(actions),
        "tool_result_count": len(tool_results),
        "conversation_turn_count": len(turns),
        "blocker_count": len(blockers),
    }

    json_values: Dict[str, Any] = {
        "PROJECT_BRIEF.json": project_brief,
        "REQUIREMENTS.json": {
            "schema_version": "hardware_splicer.engineering_package_requirements.v1",
            "requirements": requirements,
        },
        "SOURCE_MANIFEST.json": {
            "schema_version": "hardware_splicer.engineering_package_sources.v1",
            "registered_sources": registered_sources,
            "parsed_sources": parsed_sources,
            "raw_source_bytes_included": False,
        },
        "SOURCE_CONFLICTS.json": {
            "schema_version": "hardware_splicer.engineering_package_source_conflicts.v1",
            "conflicts": source_conflicts,
        },
        "ARCHITECTURE_CANDIDATES.json": {
            "schema_version": "hardware_splicer.engineering_package_candidates.v1",
            "candidates": candidates,
        },
        "DECISIONS.json": {
            "schema_version": "hardware_splicer.engineering_package_decisions.v1",
            "decisions": decisions,
        },
        "ACTION_TRACE.json": {
            "schema_version": "hardware_splicer.engineering_package_actions.v1",
            "actions": actions,
        },
        "TOOL_RESULTS.json": {
            "schema_version": "hardware_splicer.engineering_package_tool_results.v1",
            "tool_results": tool_results,
            "software_evidence_only": True,
        },
        "REPAIR_LINEAGE.json": {
            "schema_version": "hardware_splicer.engineering_package_repairs.v1",
            "repairs": repairs,
        },
        "CONVERSATION_BRIEFINGS.json": {
            "schema_version": "hardware_splicer.engineering_package_conversations.v1",
            "conversation_is_project_truth": False,
            "turns": turns,
        },
        "BLOCKERS.json": {
            "schema_version": "hardware_splicer.engineering_package_blockers.v1",
            "blockers": blockers,
        },
        "AUTHORITY_STATE.json": _authority_state(snapshot),
        "ARTIFACT_REFERENCES.json": {
            "schema_version": "hardware_splicer.engineering_package_artifacts.v1",
            "artifacts": artifacts,
            "referenced_artifact_bytes_included": False,
        },
    }
    payloads = {
        name: _canonical_json_bytes(value) for name, value in json_values.items()
    }
    readme_names = [*sorted(payloads), "MANIFEST.json", "README.md"]
    payloads["README.md"] = _readme(
        project_id=project_id,
        source_revision=source_revision,
        package_id=package_id,
        file_names=readme_names,
    ).encode("utf-8")

    file_manifest = [
        {
            "path": name,
            "sha256": _sha256(payload),
            "size_bytes": len(payload),
        }
        for name, payload in sorted(payloads.items())
    ]
    manifest = {
        "schema_version": ENGINEERING_PACKAGE_MANIFEST_SCHEMA,
        "package_id": package_id,
        "project_id": project_id,
        "source_revision": int(source_revision),
        "source_saved_at": str(source_saved_at or ""),
        "snapshot_sha256": snapshot_sha256,
        "raw_source_bytes_included": False,
        "package_authority_effect": "none",
        "manifest_self_hash_excluded": True,
        "files": file_manifest,
    }
    payloads["MANIFEST.json"] = _canonical_json_bytes(manifest)
    total_bytes = sum(len(payload) for payload in payloads.values())
    if total_bytes > _MAX_PACKAGE_BYTES:
        raise InvalidEngineeringPackage(
            f"Engineering Package payload is {total_bytes} bytes, maximum is {_MAX_PACKAGE_BYTES}"
        )
    return package_id, payloads, manifest


def _zip_bytes(payloads: Mapping[str, bytes]) -> bytes:
    fd, temp_name = tempfile.mkstemp(prefix=".engineering-package.", suffix=".zip")
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_STORED) as archive:
            for name, payload in sorted(payloads.items()):
                info = zipfile.ZipInfo(
                    filename=f"ENGINEERING_PACKAGE/{name}",
                    date_time=(1980, 1, 1, 0, 0, 0),
                )
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_STORED
                archive.writestr(info, payload)
        return temp_path.read_bytes()
    finally:
        temp_path.unlink(missing_ok=True)


def build_engineering_package(
    store: ProjectStore,
    project_id: str,
    source_revision: int,
    snapshot: Mapping[str, Any],
    *,
    source_saved_at: str = "",
) -> Dict[str, Any]:
    """Write one content-addressed package directory and deterministic ZIP."""

    safe_project = validate_project_id(project_id)
    package_id, payloads, manifest = package_payloads(
        safe_project,
        source_revision,
        snapshot,
        source_saved_at=source_saved_at,
    )
    if not _PACKAGE_ID_RE.fullmatch(package_id):
        raise InvalidEngineeringPackage("generated package identity is invalid")
    project_dir = (store.root / safe_project).resolve()
    if project_dir.parent != store.root:
        raise InvalidEngineeringPackage("project package path escapes project root")
    packages_dir = (project_dir / "engineering_packages").resolve()
    if packages_dir.parent != project_dir:
        raise InvalidEngineeringPackage("package root escapes project boundary")
    output_dir = (packages_dir / package_id).resolve()
    zip_path = (packages_dir / f"{package_id}.zip").resolve()
    if output_dir.parent != packages_dir or zip_path.parent != packages_dir:
        raise InvalidEngineeringPackage("package output escapes package root")

    manifest_payload = payloads["MANIFEST.json"]
    zip_payload = _zip_bytes(payloads)
    packages_dir.mkdir(parents=True, exist_ok=True)

    if output_dir.exists():
        existing_manifest = output_dir / "MANIFEST.json"
        if not existing_manifest.is_file() or existing_manifest.read_bytes() != manifest_payload:
            raise InvalidEngineeringPackage(
                f"existing package directory does not match {package_id}"
            )
    else:
        temp_dir = Path(
            tempfile.mkdtemp(prefix=f".{package_id}.", dir=packages_dir)
        )
        try:
            for name, payload in payloads.items():
                _atomic_write_bytes(temp_dir / name, payload)
            os.replace(temp_dir, output_dir)
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    if zip_path.exists() and zip_path.read_bytes() != zip_payload:
        raise InvalidEngineeringPackage(f"existing package ZIP does not match {package_id}")
    if not zip_path.exists():
        _atomic_write_bytes(zip_path, zip_payload)

    relative_dir = output_dir.relative_to(project_dir).as_posix()
    relative_zip = zip_path.relative_to(project_dir).as_posix()
    return {
        "schema_version": ENGINEERING_PACKAGE_RECORD_SCHEMA,
        "package_id": package_id,
        "project_id": safe_project,
        "source_revision": int(source_revision),
        "source_saved_at": str(source_saved_at or ""),
        "snapshot_sha256": manifest["snapshot_sha256"],
        "manifest_sha256": _sha256(manifest_payload),
        "manifest_size_bytes": len(manifest_payload),
        "zip_sha256": _sha256(zip_payload),
        "zip_size_bytes": len(zip_payload),
        "project_relative_directory": relative_dir,
        "project_relative_zip": relative_zip,
        "file_count": len(payloads),
        "raw_source_bytes_included": False,
        "package_authority_effect": "none",
        "physical_authority_unchanged": True,
    }


def validate_package_id(package_id: str) -> str:
    value = str(package_id or "").strip()
    if not _PACKAGE_ID_RE.fullmatch(value):
        raise InvalidEngineeringPackage("invalid Engineering Package identity")
    return value
