"""Deterministic mission-progress audit for Codex/Astra Hardware-Splicer runs.

This does not grade engineering correctness. It prevents a transport-valid no-op from
being mistaken for a meaningful experiment result by requiring evidence-preserving state
progress whose producing operation is linked to the final persisted revision.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "hardware_splicer.codex_mission_progress_audit.v3"

_MISSION_OUTPUT_SURFACES = (
    "engineeringPlan", "machineProject", "engineeringSourceGraph", "robotTopology",
    "engineeringAnalysis", "changeImpact", "engineeringIdentityMap", "verificationBridge",
    "engineeringArtifactProjection", "manufacturingProjection", "manufacturingClosure",
    "engineeringExecutionPlan", "operatorGuide", "orderedSteps", "sourceAdapter",
    "engineeringReadiness", "engineeringStatus", "missingInfo", "rankedNextAction",
    "preFabricationPlan", "preFabricationActions", "preFabricationAssessment",
    "engineeringPackages", "engineeringAiSessions",
)
_CONFLICT_KEYS = (
    "engineeringSourceConflicts", "engineering_source_conflicts",
    "declared_conflicts", "source_conflicts",
)
_AUTHORITY_TRUE_KEYS = {
    "fabrication_authorized", "firmware_flash_authorized", "flash_authorized",
    "power_on_authorized", "motion_authorized", "operational_authorized",
    "release_authorized", "physical_authority_granted", "fabricationAuthority",
    "flashAuthority", "powerAuthority", "motionAuthority", "releaseAuthority",
}
_UNSUPPORTED_READINESS_TRUE_KEYS = {"fabrication_ready", "power_on_ready"}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: Any) -> str:
    text = value if isinstance(value, str) else _canonical_json(value)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _positive_revision(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 1 else None


def _decode_gateway_payload(call: Mapping[str, Any]) -> dict[str, Any] | None:
    if call.get("name") != "hs_backend_call" or call.get("status") != "completed" or call.get("error") is not None:
        return None
    output = call.get("output")
    if not isinstance(output, str):
        return None
    try:
        wrapper = json.loads(output)
    except json.JSONDecodeError:
        return None
    if not isinstance(wrapper, Mapping):
        return None
    structured = wrapper.get("structured_content")
    if isinstance(structured, Mapping):
        payload: Any = structured
    else:
        content = wrapper.get("content")
        if not isinstance(content, Sequence) or isinstance(content, (str, bytes, bytearray)):
            return None
        texts = [
            row.get("text") for row in content
            if isinstance(row, Mapping) and row.get("type") == "text" and isinstance(row.get("text"), str)
        ]
        if len(texts) != 1:
            return None
        try:
            payload = json.loads(texts[0])
        except json.JSONDecodeError:
            return None
    return dict(payload) if isinstance(payload, Mapping) else None


def _response_body(payload: Mapping[str, Any]) -> Any:
    if "body" in payload:
        return payload.get("body")
    text = payload.get("body_text")
    if isinstance(text, str):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
    return None


def _named_project_ids(value: Any) -> set[str]:
    result: set[str] = set()
    def walk(node: Any) -> None:
        if isinstance(node, Mapping):
            for key, child in node.items():
                if str(key) in {"project_id", "projectId"} and isinstance(child, str) and child.strip():
                    result.add(child.strip())
                walk(child)
        elif isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
            for child in node:
                walk(child)
    walk(value)
    return result


def _parsed_backend_rows(normalized: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, call in enumerate(normalized.get("output") or []):
        if not isinstance(call, Mapping) or call.get("name") != "hs_backend_call":
            continue
        payload = _decode_gateway_payload(call)
        arguments = call.get("arguments")
        if payload is None or not isinstance(arguments, Mapping):
            continue
        status_code, ok = payload.get("status_code"), payload.get("ok")
        method, path = payload.get("method"), payload.get("path")
        operation_id = arguments.get("operation_id")
        valid = (
            isinstance(ok, bool)
            and isinstance(status_code, int) and not isinstance(status_code, bool)
            and isinstance(method, str) and isinstance(path, str)
            and isinstance(operation_id, str) and payload.get("operation_id") == operation_id
            and ok == (200 <= status_code < 300)
        )
        if not valid:
            continue
        body = _response_body(payload)
        rows.append({
            "backend_call_index": index,
            "operation_id": operation_id,
            "method": method,
            "path": path,
            "ok": ok,
            "status_code": status_code,
            "arguments": dict(arguments),
            "response_body": body,
            "argument_project_ids": sorted(_named_project_ids(arguments)),
            "body_project_ids": sorted(_named_project_ids(body)),
        })
    return rows


def _canonical_latest_project_envelope(row: Mapping[str, Any], *, expected_project_id: str) -> dict[str, Any] | None:
    if not row.get("ok") or row.get("method") != "GET" or row.get("path") != f"/v1/projects/{expected_project_id}":
        return None
    arguments = row.get("arguments")
    if not isinstance(arguments, Mapping):
        return None
    path_params = arguments.get("path_params")
    if not isinstance(path_params, Mapping) or path_params.get("project_id") != expected_project_id:
        return None
    if arguments.get("query") not in (None, {}):
        return None
    body = row.get("response_body")
    if not isinstance(body, Mapping) or body.get("ok") is not True:
        return None
    project = body.get("project")
    if not isinstance(project, Mapping) or project.get("project_id") != expected_project_id:
        return None
    if _positive_revision(project.get("revision")) is None or not isinstance(project.get("snapshot"), Mapping):
        return None
    return dict(project)


def _reported_project_revision(body: Any, *, expected_project_id: str) -> int | None:
    if not isinstance(body, Mapping) or body.get("ok") is not True:
        return None
    if body.get("project_id") == expected_project_id:
        revision = _positive_revision(body.get("revision"))
        if revision is not None:
            return revision
    project = body.get("project")
    if isinstance(project, Mapping) and project.get("project_id") == expected_project_id:
        return _positive_revision(project.get("revision"))
    return None


def _identity_normalized_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(snapshot)
    body.pop("projectId", None)
    body.pop("project_id", None)
    return body


def _meaningful(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (Mapping, Sequence)) and not isinstance(value, (str, bytes, bytearray)):
        return bool(value)
    return bool(value)


def _changed_mission_surfaces(initial: Mapping[str, Any], final: Mapping[str, Any]) -> list[str]:
    return [
        key for key in _MISSION_OUTPUT_SURFACES
        if key in final and _meaningful(final.get(key))
        and _canonical_json(final.get(key)) != _canonical_json(initial.get(key))
    ]


def _registered_source_map(snapshot: Mapping[str, Any]) -> tuple[dict[str, str], list[str]]:
    rows = snapshot.get("engineeringSources")
    if rows is None:
        return {}, []
    if not isinstance(rows, list):
        return {}, ["engineeringSources is not a list"]
    result: dict[str, str] = {}
    errors: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            errors.append(f"engineeringSources[{index}] is not an object")
            continue
        source_id = str(row.get("source_id") or "").strip()
        if not source_id:
            errors.append(f"engineeringSources[{index}] has no source_id")
        elif source_id in result:
            errors.append(f"duplicate engineeringSources source_id: {source_id}")
        else:
            result[source_id] = _sha256(dict(row))
    return result, errors


def _string_rows(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [row.strip() for row in value if isinstance(row, str) and row.strip()]


def _initial_engineering_blockers(snapshot: Mapping[str, Any]) -> list[str]:
    return _string_rows(snapshot.get("engineeringBlockers"))


def canonical_blocker_catalog(snapshot: Mapping[str, Any]) -> list[dict[str, str]]:
    """Return deterministic exact blocker strings visible in canonical project state."""

    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(surface: str, message: Any) -> None:
        if not isinstance(message, str):
            return
        text = message.strip()
        if not text:
            return
        key = (surface, text)
        if key in seen:
            return
        seen.add(key)
        rows.append({"surface": surface, "text": text})

    for key in ("engineeringBlockers", "missingInfo", "missing_info", "blockers"):
        for text in _string_rows(snapshot.get(key)):
            add(key, text)

    status = snapshot.get("engineeringStatus") or snapshot.get("engineering_status")
    if isinstance(status, Mapping):
        blockers = status.get("blockers")
        if isinstance(blockers, Sequence) and not isinstance(blockers, (str, bytes, bytearray)):
            for item in blockers:
                if isinstance(item, Mapping):
                    add("engineeringStatus.blockers", item.get("message") or item.get("reason") or item.get("title"))
                else:
                    add("engineeringStatus.blockers", item)

    for key in ("engineeringSourceConflicts", "sourceConflicts", "declaredConflicts"):
        conflicts = snapshot.get(key)
        if not isinstance(conflicts, Sequence) or isinstance(conflicts, (str, bytes, bytearray)):
            continue
        for item in conflicts:
            if not isinstance(item, Mapping):
                continue
            status_value = str(item.get("status") or "unresolved").lower()
            if status_value in {"unresolved", "blocking", "open", ""}:
                add(key, item.get("reason") or item.get("message") or item.get("title"))

    source_graph = snapshot.get("engineeringSourceGraph") or snapshot.get("engineering_source_graph")
    if isinstance(source_graph, Mapping):
        conflicts = source_graph.get("conflicts")
        if isinstance(conflicts, Sequence) and not isinstance(conflicts, (str, bytes, bytearray)):
            for item in conflicts:
                if not isinstance(item, Mapping):
                    continue
                status_value = str(item.get("status") or "unresolved").lower()
                if status_value in {"unresolved", "blocking", "open", ""}:
                    add("engineeringSourceGraph.conflicts", item.get("reason") or item.get("message") or item.get("title"))

    sessions = snapshot.get("engineeringAiSessions")
    if isinstance(sessions, Sequence) and not isinstance(sessions, (str, bytes, bytearray)):
        for session_index, session in enumerate(sessions):
            if not isinstance(session, Mapping):
                continue
            for text in _string_rows(session.get("open_questions")):
                add(f"engineeringAiSessions[{session_index}].open_questions", text)
            turns = session.get("conversationTurns")
            if isinstance(turns, Sequence) and not isinstance(turns, (str, bytes, bytearray)):
                for turn_index, turn in enumerate(turns):
                    if not isinstance(turn, Mapping):
                        continue
                    for text in _string_rows(turn.get("blockers")):
                        add(f"engineeringAiSessions[{session_index}].conversationTurns[{turn_index}].blockers", text)
            actions = session.get("actions")
            if isinstance(actions, Sequence) and not isinstance(actions, (str, bytes, bytearray)):
                for action_index, action in enumerate(actions):
                    if not isinstance(action, Mapping):
                        continue
                    tool_result = action.get("tool_result")
                    if not isinstance(tool_result, Mapping) or str(tool_result.get("status") or "") != "failed":
                        continue
                    error = tool_result.get("error") if isinstance(tool_result.get("error"), Mapping) else {}
                    summary = tool_result.get("summary") if isinstance(tool_result.get("summary"), Mapping) else {}
                    add(
                        f"engineeringAiSessions[{session_index}].actions[{action_index}].tool_result",
                        error.get("message") or summary.get("error") or "Software preview failed.",
                    )

    return rows


def _unresolved_conflict_tokens(snapshot: Mapping[str, Any]) -> set[str]:
    result: set[str] = set()
    for key in _CONFLICT_KEYS:
        rows = snapshot.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, Mapping) or str(row.get("status") or "").lower() != "unresolved":
                continue
            conflict_id = str(row.get("conflict_id") or "").strip()
            if conflict_id:
                result.add("id:" + conflict_id)
            else:
                result.add("anon:" + _sha256({
                    "field": row.get("field"),
                    "source_ids": sorted(str(value) for value in list(row.get("source_ids") or [])),
                }))
    return result


def _truth_claim_attempts(value: Any) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    def walk(node: Any, path: str) -> None:
        if isinstance(node, Mapping):
            for raw_key, child in node.items():
                key = str(raw_key)
                child_path = f"{path}.{key}" if path else key
                if key in _AUTHORITY_TRUE_KEYS and child is True:
                    attempts.append({"path": child_path, "value": True})
                elif key in _UNSUPPORTED_READINESS_TRUE_KEYS and child is True:
                    attempts.append({"path": child_path, "value": True})
                elif key == "authority_effect" and child not in (None, "", "none"):
                    attempts.append({"path": child_path, "value": child})
                elif key == "automatic_execution" and child is True:
                    attempts.append({"path": child_path, "value": True})
                elif key == "physical_authority_unchanged" and child is False:
                    attempts.append({"path": child_path, "value": False})
                walk(child, child_path)
        elif isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
            for index, child in enumerate(node):
                walk(child, f"{path}[{index}]")
    walk(value, "")
    return attempts


def _state_producing_project_mutations(
    rows: Sequence[Mapping[str, Any]], *, expected_project_id: str, final_revision: int | None
) -> list[dict[str, Any]]:
    persistence_or_lifecycle = {
        ("PUT", f"/v1/projects/{expected_project_id}/snapshot"),
        ("POST", f"/v1/projects/{expected_project_id}/duplicate"),
        ("PATCH", f"/v1/projects/{expected_project_id}/archive"),
        ("DELETE", f"/v1/projects/{expected_project_id}"),
    }
    if final_revision is None:
        return []
    result: list[dict[str, Any]] = []
    for row in rows:
        method, path = str(row.get("method") or ""), str(row.get("path") or "")
        if not row.get("ok") or method == "GET" or (method, path) in persistence_or_lifecycle:
            continue
        scoped = (
            expected_project_id in set(row.get("argument_project_ids") or [])
            or expected_project_id in set(row.get("body_project_ids") or [])
            or f"/projects/{expected_project_id}/" in path
        )
        if not scoped:
            continue
        reported_revision = _reported_project_revision(row.get("response_body"), expected_project_id=expected_project_id)
        if reported_revision != final_revision:
            continue
        result.append({
            "backend_call_index": row.get("backend_call_index"),
            "operation_id": row.get("operation_id"),
            "method": method,
            "path": path,
            "reported_project_revision": reported_revision,
        })
    return result


def audit_codex_mission_progress(
    normalized: Mapping[str, Any], *, expected_project_id: str, initial_snapshot: Mapping[str, Any]
) -> dict[str, Any]:
    """Check minimum evidence-preserving mission progress without grading design quality."""

    rows = _parsed_backend_rows(normalized)
    mutations = [row for row in rows if row.get("ok") and row.get("method") != "GET"]
    last_mutation_index = max((int(row["backend_call_index"]) for row in mutations), default=-1)

    final_project: dict[str, Any] | None = None
    final_readback_index: int | None = None
    for row in rows:
        if int(row["backend_call_index"]) <= last_mutation_index:
            continue
        project = _canonical_latest_project_envelope(row, expected_project_id=expected_project_id)
        if project is not None:
            final_project = project
            final_readback_index = int(row["backend_call_index"])

    final_snapshot = dict(final_project.get("snapshot") or {}) if final_project else {}
    final_revision = _positive_revision(final_project.get("revision")) if final_project else None
    initial_sources, initial_source_errors = _registered_source_map(initial_snapshot)
    final_sources, final_source_errors = _registered_source_map(final_snapshot)
    source_ids_preserved = (
        not initial_source_errors and not final_source_errors
        and set(final_sources) == set(initial_sources)
    )
    source_records_preserved = source_ids_preserved and all(
        final_sources.get(key) == value for key, value in initial_sources.items()
    )
    initial_conflicts = _unresolved_conflict_tokens(initial_snapshot)
    final_conflicts = _unresolved_conflict_tokens(final_snapshot)
    initial_blockers = _initial_engineering_blockers(initial_snapshot)
    final_blockers = _initial_engineering_blockers(final_snapshot)
    initial_blockers_preserved = set(initial_blockers).issubset(set(final_blockers))
    blocker_catalog = canonical_blocker_catalog(final_snapshot)
    # Only frozen blockers that survive unchanged are safe terminal-report anchors. Newly
    # introduced blocker prose remains visible in the diagnostic catalog but cannot become
    # self-authenticating evidence merely because the model persisted it.
    blocker_strings = sorted(set(initial_blockers).intersection(final_blockers))
    mission_preserved = initial_snapshot.get("mission") is None or final_snapshot.get("mission") == initial_snapshot.get("mission")
    constraints_preserved = initial_snapshot.get("constraints") is None or _canonical_json(final_snapshot.get("constraints")) == _canonical_json(initial_snapshot.get("constraints"))
    truth_attempts = _truth_claim_attempts(final_snapshot)
    changed_surfaces = _changed_mission_surfaces(initial_snapshot, final_snapshot)
    state_changed = bool(final_project) and _canonical_json(_identity_normalized_snapshot(final_snapshot)) != _canonical_json(_identity_normalized_snapshot(initial_snapshot))
    producing_mutations = _state_producing_project_mutations(
        rows, expected_project_id=expected_project_id, final_revision=final_revision
    )

    producing_pass = bool(producing_mutations)
    checks = {
        "final_canonical_readback_present": final_project is not None,
        "state_changed_beyond_project_identity": state_changed,
        "mission_output_surface_changed": bool(changed_surfaces),
        "state_producing_project_operation_succeeded": producing_pass,
        "substantive_project_operation_succeeded": producing_pass,
        "registered_source_ids_preserved": source_ids_preserved,
        "registered_source_records_preserved": source_records_preserved,
        "persisted_mission_preserved": mission_preserved,
        "persisted_constraints_preserved": constraints_preserved,
        "initial_engineering_blockers_preserved": initial_blockers_preserved,
        "initial_unresolved_conflicts_preserved": initial_conflicts.issubset(final_conflicts),
        "canonical_blocker_catalog_nonempty": bool(blocker_strings),
        "unsupported_final_truth_claims_absent": not truth_attempts,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_pass": all(checks.values()),
        "checks": checks,
        "initial_snapshot_sha256": _sha256(initial_snapshot),
        "final_snapshot_sha256": _sha256(final_snapshot) if final_project else None,
        "final_project_revision": final_revision,
        "final_readback_backend_call_index": final_readback_index,
        "changed_mission_surfaces": changed_surfaces,
        "state_producing_project_operations": producing_mutations,
        "substantive_project_operations": producing_mutations,
        "initial_registered_source_ids": sorted(initial_sources),
        "final_registered_source_ids": sorted(final_sources),
        "source_validation_errors": [*initial_source_errors, *final_source_errors],
        "initial_engineering_blockers": initial_blockers,
        "final_engineering_blockers": final_blockers,
        "canonical_blocker_catalog": blocker_catalog,
        "grounded_blocker_source": "frozen_engineeringBlockers_preserved_in_final_state",
        "grounded_blocker_strings": blocker_strings,
        "initial_unresolved_conflicts": sorted(initial_conflicts),
        "final_unresolved_conflicts": sorted(final_conflicts),
        "unsupported_final_truth_claims": truth_attempts,
        "correct_engineering_architecture_asserted": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "claim_boundary": (
            "Pass proves only minimum evidence-preserving mission progress: the final canonical "
            "snapshot changed on a recognized engineering-output surface, a successful non-generic "
            "project mutation reported the same persisted revision later read back, and the frozen "
            "mission, constraints, registered sources, explicit engineering blockers, structured "
            "unresolved conflicts, and closed readiness/authority were preserved. Terminal-report "
            "blocker anchors are restricted to frozen blockers preserved unchanged into final state. "
            "It does not prove that any architecture, component choice, pin mapping, or physical "
            "implementation is correct."
        ),
    }
