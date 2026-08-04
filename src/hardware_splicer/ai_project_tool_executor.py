"""Execute explicitly accepted, software-side AI project previews.

This module is deliberately narrower than the AI proposal vocabulary. It can run
only deterministic guided planning and deterministic compose previews. It never
runs arbitrary commands, enables LLM-first compose, touches devices, or elevates
fabrication, flashing, power, motion, operational, or release authority.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Sequence

from .compose_dispatch import compose_dispatch
from .guided_engineering_planner import plan_guided_engineering_project
from .project_store import ProjectStore, validate_project_id

AI_TOOL_EXECUTOR_SCHEMA = "hardware_splicer.ai_project_tool_executor.v1"
AI_TOOL_RESULT_SCHEMA = "hardware_splicer.ai_project_tool_result.v1"
AI_TOOL_EXECUTOR_IDENTITY = "hardware_splicer.ai_project_tool_executor.python.v1"

EXECUTABLE_AI_PREVIEW_ACTIONS = (
    "run_guided_plan",
    "run_compose",
)

_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_MAX_RESULT_JSON_BYTES = 16 * 1024 * 1024
_MAX_SUMMARY_ROWS = 64


class AIProjectToolExecutorError(RuntimeError):
    """Base error for accepted AI preview execution."""


class AIActionNotExecutable(AIProjectToolExecutorError, ValueError):
    pass


class AIActionNotAccepted(AIProjectToolExecutorError, ValueError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(value: Any, label: str) -> str:
    token = str(value or "").strip()
    if not _ID_RE.fullmatch(token):
        raise ValueError(f"{label} has an invalid identifier")
    return token


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> Dict[str, Any]:
    payload = _canonical_json(value)
    if len(payload) > _MAX_RESULT_JSON_BYTES:
        raise ValueError("AI preview result exceeds the bounded JSON artifact ceiling")
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
    return {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def _run_root(
    store: ProjectStore,
    project_id: str,
    session_id: str,
    action_id: str,
) -> tuple[Path, str]:
    safe_project = validate_project_id(project_id)
    safe_session = _safe_id(session_id, "session_id")
    safe_action = _safe_id(action_id, "action_id")
    project_dir = (store.root / safe_project).resolve()
    if project_dir.parent != store.root:
        raise ValueError("project tool directory resolves outside project root")
    run_dir = (
        project_dir / "ai_tool_runs" / safe_session / safe_action
    ).resolve()
    expected_parent = (project_dir / "ai_tool_runs" / safe_session).resolve()
    if run_dir.parent != expected_parent:
        raise ValueError("AI tool run directory resolves outside the session boundary")
    relative = run_dir.relative_to(project_dir).as_posix()
    return run_dir, relative


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[Dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [
        dict(row)
        for row in list(value)[:_MAX_SUMMARY_ROWS]
        if isinstance(row, Mapping)
    ]


def _combined_sources(snapshot: Mapping[str, Any]) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for collection in (
        snapshot.get("engineeringSources"),
        snapshot.get("engineeringParsedSources"),
    ):
        for source in _rows(collection):
            key = (
                str(source.get("source_id") or ""),
                str(source.get("content_hash") or source.get("revision") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            result.append(source)
    return result


def _planner_intake(
    project_id: str,
    snapshot: Mapping[str, Any],
    session: Mapping[str, Any],
    action: Mapping[str, Any],
) -> Dict[str, Any]:
    inputs = _mapping(action.get("inputs"))
    explicit = inputs.get("intake")
    if isinstance(explicit, Mapping):
        intake = dict(explicit)
    else:
        constraints = _mapping(session.get("constraints"))
        intake = {
            "project_id": project_id,
            "name": str(snapshot.get("name") or project_id),
            "goal": str(session.get("mission") or ""),
            "intent": str(session.get("mission") or ""),
            "mode": str(snapshot.get("mode") or constraints.get("mode") or "greenfield"),
            "constraints": constraints,
            "parts": list(
                snapshot.get("parts")
                or snapshot.get("availableParts")
                or constraints.get("parts")
                or []
            ),
            "available_parts": list(
                snapshot.get("available_parts")
                or snapshot.get("availableParts")
                or constraints.get("available_parts")
                or []
            ),
        }
    intake["project_id"] = project_id
    intake.setdefault("goal", str(session.get("mission") or ""))
    intake.setdefault("intent", str(session.get("mission") or ""))
    intake.setdefault("constraints", _mapping(session.get("constraints")))
    return intake


def _plan_summary(plan: Mapping[str, Any]) -> Dict[str, Any]:
    readiness = _mapping(plan.get("engineering_readiness"))
    status = _mapping(plan.get("engineering_status"))
    closure = _mapping(plan.get("manufacturing_closure"))
    execution = _mapping(plan.get("engineering_execution_plan"))
    return {
        "schema_version": str(plan.get("schema_version") or ""),
        "engineering_readiness": readiness,
        "engineering_status": status,
        "manufacturing_closure": {
            "status": closure.get("status"),
            "blocking_check_count": len(_rows(closure.get("blocking_checks"))),
            "warning_check_count": len(_rows(closure.get("warning_checks"))),
        },
        "execution_preview": {
            "check_count": len(_rows(execution.get("checks"))),
            "unresolved_count": len(_rows(execution.get("unresolved"))),
            "automatic_execution": False,
        },
        "missing_info": [str(row) for row in list(plan.get("missing_info") or [])[:64]],
        "ordered_step_count": len(list(plan.get("ordered_steps") or [])),
    }


def _compose_summary(result: Mapping[str, Any]) -> Dict[str, Any]:
    quality_gate = _mapping(result.get("design_quality_gate"))
    failure = _mapping(result.get("failure"))
    return {
        "ok": bool(result.get("ok")),
        "mode": str(result.get("mode") or ""),
        "build_id": result.get("build_id"),
        "module_ids": [str(row) for row in list(result.get("module_ids") or [])[:64]],
        "design_quality_gate": quality_gate,
        "failure": failure,
        "warnings": [str(row) for row in list(result.get("warnings") or [])[:64]],
        "error": result.get("error"),
        "automatic_execution": False,
        "allow_llm_first": False,
        "export_gerber": False,
    }


def execute_ai_project_action_preview(
    store: ProjectStore,
    project_id: str,
    session: Mapping[str, Any],
    action: Mapping[str, Any],
    *,
    guided_planner: Callable[..., Dict[str, Any]] | None = None,
    compose_callable: Callable[..., Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Execute one accepted allowlisted action against its pinned project revision."""

    action_type = str(action.get("action_type") or "")
    if action_type not in EXECUTABLE_AI_PREVIEW_ACTIONS:
        raise AIActionNotExecutable(
            f"AI action type {action_type!r} is not executable in the preview boundary"
        )
    if str(action.get("status") or "") != "accepted":
        raise AIActionNotAccepted("AI action must be explicitly accepted before preview")
    if action.get("tool_result"):
        return dict(action.get("tool_result") or {})

    session_id = _safe_id(session.get("session_id"), "session_id")
    action_id = _safe_id(action.get("action_id"), "action_id")
    pinned_revision = int(
        action.get("project_revision") or session.get("project_revision") or 0
    )
    if pinned_revision < 1:
        raise ValueError("AI action has no valid pinned project revision")
    pinned = store.load(project_id, revision=pinned_revision)
    snapshot = dict(pinned["snapshot"])
    run_dir, relative_run_dir = _run_root(store, project_id, session_id, action_id)
    started_at = _utc_now()

    try:
        if action_type == "run_guided_plan":
            planner = guided_planner or plan_guided_engineering_project
            intake = _planner_intake(project_id, snapshot, session, action)
            plan = planner(
                intake,
                engineering_sources=_combined_sources(snapshot),
                declared_conflicts=[],
                baseline_project=None,
                skip_vision=True,
            )
            artifact_path = run_dir / "guided_plan.json"
            artifact = _atomic_write_json(artifact_path, plan)
            summary = _plan_summary(plan)
            artifact_name = "guided_plan.json"
        elif action_type == "run_compose":
            compose = compose_callable or compose_dispatch
            inputs = _mapping(action.get("inputs"))
            phrase = str(
                inputs.get("phrase")
                or inputs.get("goal")
                or session.get("mission")
                or ""
            ).strip()
            if not phrase:
                raise ValueError("run_compose requires a phrase or session mission")
            constraints = {
                **_mapping(session.get("constraints")),
                **_mapping(inputs.get("constraints")),
            }
            compose_dir = run_dir / "compose"
            result = compose(
                out_dir=compose_dir,
                phrase=phrase,
                module_ids=(
                    [str(row) for row in inputs.get("module_ids")]
                    if isinstance(inputs.get("module_ids"), list)
                    else None
                ),
                constraints=constraints,
                material_mode=(
                    str(inputs.get("material_mode"))
                    if inputs.get("material_mode")
                    else None
                ),
                salvage_mode=bool(inputs.get("salvage_mode", False)),
                export_gerber=False,
                wire_only=bool(inputs.get("wire_only", False)),
                allow_llm_first=False,
                request_id=action_id,
            )
            artifact_path = run_dir / "compose_result.json"
            artifact = _atomic_write_json(artifact_path, result)
            summary = _compose_summary(result)
            artifact_name = "compose_result.json"
        else:
            raise AIActionNotExecutable(action_type)
        status_value = "succeeded"
        error = None
    except Exception as exc:
        status_value = "failed"
        summary = {
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "automatic_execution": False,
        }
        artifact_path = run_dir / "failure.json"
        artifact = _atomic_write_json(artifact_path, summary)
        artifact_name = "failure.json"
        error = {"type": type(exc).__name__, "message": str(exc)}

    completed_at = _utc_now()
    return {
        "schema_version": AI_TOOL_RESULT_SCHEMA,
        "executor_identity": AI_TOOL_EXECUTOR_IDENTITY,
        "project_id": project_id,
        "project_revision": pinned_revision,
        "session_id": session_id,
        "action_id": action_id,
        "action_type": action_type,
        "status": status_value,
        "started_at": started_at,
        "completed_at": completed_at,
        "summary": summary,
        "error": error,
        "artifact": {
            "project_relative_path": f"{relative_run_dir}/{artifact_name}",
            **artifact,
        },
        "automatic_execution": False,
        "physical_authority_unchanged": True,
        "fabrication_authorized": False,
        "firmware_flash_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "operational_authorized": False,
        "release_authorized": False,
    }
