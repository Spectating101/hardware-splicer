"""Read-only projection of how persisted findings were established.

Provenance is never guessed or flattering. If stored fields do not say how a
finding was established, the kind is ``unknown``. This module does not write,
does not execute tools, and never upgrades authority. Every finding carries
``authority_ceiling: observed`` and cannot imply a stronger engineering claim.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Sequence

from pydantic import ValidationError

from .ai_project_orchestrator import ALLOWED_AI_ACTION_TYPES
from .ai_project_tool_executor import EXECUTABLE_AI_PREVIEW_ACTIONS
from .engineering_review_identity import AUTHORITY_CEILING
from .machine_project import MachineProject, TraceabilityIssue, traceability_issues

_CATEGORY_ORDER = ("failed_check", "object_blocker", "traceability_issue")
_MACHINE_PROJECT_INVALID_PREFIX = "Stored machine project fails validation: "
_MACHINE_PROJECT_INVALID_SOURCE = "machine_project_invalid"
_MACHINE_PROJECT_INVALID_BASIS = (
    "MachineProject validation rejected the stored machine project"
)
_VALIDATION_TEXT_LIMIT = 500
_PYDANTIC_URL_RE = re.compile(r"https?://\S+")
# ``physical`` is reserved: no persisted field yet links a blocker or failed
# check to a specific bench measurement.
_PROVENANCE_KINDS = frozenset(
    {"deterministic", "model_derived", "physical", "human", "unknown"}
)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(row) for row in value if isinstance(row, Mapping)]


def _strings(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [_text(row) for row in value if _text(row)]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _finding_id(
    category: str, object_id: str | None, text: str, source_ref: str | None
) -> str:
    payload = [category, object_id or "", text, source_ref or ""]
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return "finding-" + digest[:16]


def _provenance(
    kind: str,
    basis: str,
    source_ref: str | None,
) -> dict[str, Any]:
    if kind not in _PROVENANCE_KINDS:
        kind = "unknown"
    return {
        "kind": kind,
        "basis": basis,
        "source_ref": source_ref,
        "authority_ceiling": AUTHORITY_CEILING,
    }


def _finding(
    category: str,
    object_id: str | None,
    text: str,
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    source_ref = provenance.get("source_ref")
    source_ref = _text(source_ref) or None
    return {
        "finding_id": _finding_id(category, object_id, text, source_ref),
        "category": category,
        "object_id": object_id,
        "text": text,
        "provenance": dict(provenance),
    }


def _sessions(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    return _rows(snapshot.get("engineeringAiSessions"))


def _session_output_texts(session: Mapping[str, Any]) -> set[str]:
    texts: set[str] = set()
    for key in ("blockers", "open_questions", "risks"):
        texts.update(_strings(session.get(key)))
    for turn in _rows(session.get("conversationTurns")):
        for key in ("blockers", "open_questions", "risks"):
            texts.update(_strings(turn.get(key)))
    return texts


def _session_has_model_identity(session: Mapping[str, Any]) -> bool:
    return bool(_text(session.get("provider")) and _text(session.get("model")))


def _recorded_action_types(action: Mapping[str, Any]) -> list[str]:
    tool_result = _mapping(action.get("tool_result"))
    seen: set[str] = set()
    values: list[str] = []
    for raw in (
        action.get("action_type"),
        action.get("tool"),
        tool_result.get("action_type"),
        tool_result.get("tool"),
    ):
        token = _text(raw)
        if token and token not in seen:
            seen.add(token)
            values.append(token)
    return values


def _failed_action_text(action: Mapping[str, Any]) -> str:
    tool_result = _mapping(action.get("tool_result"))
    error = _mapping(tool_result.get("error"))
    summary = _mapping(tool_result.get("summary"))
    return _text(
        error.get("message")
        or summary.get("message")
        or action.get("title")
        or action.get("rationale")
    )


def _action_never_executed(action: Mapping[str, Any]) -> bool:
    return action.get("tool_result") is None


def _failed_check_provenance(action: Mapping[str, Any]) -> dict[str, Any]:
    source_ref = _text(action.get("action_id")) or None
    recorded = _recorded_action_types(action)
    if len(recorded) > 1:
        return _provenance(
            "unknown",
            "recorded action_type/tool fields disagree",
            source_ref,
        )
    action_type = recorded[0] if recorded else ""
    if action_type in EXECUTABLE_AI_PREVIEW_ACTIONS and not _action_never_executed(action):
        return _provenance(
            "deterministic",
            "failed action executed by the deterministic tool executor",
            source_ref,
        )
    if action_type in ALLOWED_AI_ACTION_TYPES and _action_never_executed(action):
        return _provenance(
            "model_derived",
            "failed model proposal that was never executed deterministically",
            source_ref,
        )
    return _provenance(
        "unknown",
        "stored fields do not establish how this failed check was produced",
        source_ref,
    )


def _collect_failed_checks(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for session in _sessions(snapshot):
        for action in _rows(session.get("actions")):
            if _text(action.get("status")).lower() != "failed":
                continue
            text = _failed_action_text(action)
            if not text:
                continue
            object_id = _text(action.get("object_id")) or None
            findings.append(
                _finding(
                    "failed_check",
                    object_id,
                    text,
                    _failed_check_provenance(action),
                )
            )
    return findings


def _graph_nodes(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    graph = _mapping(snapshot.get("engineeringSystemGraph"))
    return _rows(graph.get("nodes"))


def _object_id(row: Mapping[str, Any]) -> str | None:
    return _text(row.get("object_id") or row.get("id") or row.get("node_id")) or None


def _machine_mapping(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    raw = snapshot.get("machineProject")
    if not isinstance(raw, Mapping):
        raw = snapshot.get("machine_project")
    return _mapping(raw)


def _human_decision_ref(snapshot: Mapping[str, Any], text: str) -> str | None:
    for session in _sessions(snapshot):
        for action in _rows(session.get("actions")):
            decision = _mapping(action.get("decision"))
            if not decision:
                continue
            reviewer = _text(decision.get("reviewer") or decision.get("actor"))
            if not reviewer:
                continue
            carried = {
                _text(decision.get("note")),
                _text(decision.get("message")),
                _text(decision.get("text")),
            }
            if text in carried:
                return _text(action.get("action_id")) or None
    return None


def _model_session_ref(snapshot: Mapping[str, Any], text: str) -> str | None:
    for session in _sessions(snapshot):
        if not _session_has_model_identity(session):
            continue
        if text in _session_output_texts(session):
            return _text(session.get("session_id")) or None
    return None


def _object_blocker_provenance(
    text: str,
    snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    human_ref = _human_decision_ref(snapshot, text)
    if human_ref is not None:
        return _provenance(
            "human",
            "recorded human review or decision entry carries this blocker",
            human_ref,
        )
    session_ref = _model_session_ref(snapshot, text)
    if session_ref is not None:
        return _provenance(
            "model_derived",
            "blocker text recorded in an AI session with provider and model",
            session_ref,
        )
    return _provenance(
        "unknown",
        "stored fields do not establish how this object blocker was produced",
        None,
    )


def _collect_object_blockers(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for node in _graph_nodes(snapshot):
        object_id = _object_id(node)
        for text in _strings(node.get("blockers")):
            findings.append(
                _finding(
                    "object_blocker",
                    object_id,
                    text,
                    _object_blocker_provenance(text, snapshot),
                )
            )
    return findings


def _validation_messages(exc: BaseException) -> str:
    parts: list[str] = []
    if isinstance(exc, ValidationError):
        for error in exc.errors():
            message = _text(error.get("msg"))
            if message:
                parts.append(message)
    else:
        message = _text(exc)
        if message:
            parts.append(message)
    joined = _PYDANTIC_URL_RE.sub("", "; ".join(parts) or _text(exc)).strip()
    joined = re.sub(r"\s+", " ", joined)
    text = f"{_MACHINE_PROJECT_INVALID_PREFIX}{joined}"
    return text[:_VALIDATION_TEXT_LIMIT]


def _invalid_machine_project_finding(exc: BaseException) -> dict[str, Any]:
    return _finding(
        "traceability_issue",
        None,
        _validation_messages(exc),
        _provenance(
            "deterministic",
            _MACHINE_PROJECT_INVALID_BASIS,
            _MACHINE_PROJECT_INVALID_SOURCE,
        ),
    )


def _parse_machine_project(snapshot: Mapping[str, Any]) -> MachineProject | None:
    raw = _machine_mapping(snapshot)
    if not raw:
        return None
    return MachineProject.model_validate(raw)


def _traceability_provenance(issue: TraceabilityIssue) -> dict[str, Any]:
    return _provenance(
        "deterministic",
        "computed by traceability_issues() over the stored machine project",
        _text(issue.code) or None,
    )


def _collect_traceability_issues(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = _machine_mapping(snapshot)
    if not raw:
        return []
    try:
        project = _parse_machine_project(snapshot)
    except (ValidationError, TypeError, ValueError) as exc:
        return [_invalid_machine_project_finding(exc)]
    if project is None:
        return []
    findings: list[dict[str, Any]] = []
    for issue in traceability_issues(project):
        text = _text(issue.message)
        if not text:
            continue
        object_id = _text(issue.object_id) or None
        findings.append(
            _finding(
                "traceability_issue",
                object_id,
                text,
                _traceability_provenance(issue),
            )
        )
    return findings


def _dedupe(findings: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for row in findings:
        key = (
            _text(row.get("category")),
            _text(row.get("object_id")),
            _text(row.get("text")),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(dict(row))
    return result


def _sort_key(row: Mapping[str, Any]) -> tuple[int, str, str]:
    category = _text(row.get("category"))
    try:
        category_index = _CATEGORY_ORDER.index(category)
    except ValueError:
        category_index = len(_CATEGORY_ORDER)
    return (category_index, _text(row.get("object_id")), _text(row.get("text")))


def project_findings(snapshot: Mapping[str, Any], revision: int) -> list[dict[str, Any]]:
    """Project findings and their stored establishment provenance.

    ``revision`` is accepted so callers can bind the projection to a loaded
    revision. It is not an authority signal and is not written back.
    """

    del revision
    body = _mapping(snapshot)
    collected = [
        *_collect_failed_checks(body),
        *_collect_object_blockers(body),
        *_collect_traceability_issues(body),
    ]
    unique = _dedupe(collected)
    unique.sort(key=_sort_key)
    return unique
