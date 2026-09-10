"""Operation-to-state provenance for Codex/Astra mission-progress claims.

A project-scoped mutation sharing the final revision is not enough: an administrative
mutation could otherwise take credit for engineering-looking state inserted earlier by a
generic save. This audit requires an exact structural payload match between the credited
operation response and a changed final engineering surface.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "hardware_splicer.codex_progress_provenance_audit.v1"

_NONCREDITABLE_SURFACES = {"engineeringPackages", "engineeringAiSessions"}
_RESPONSE_METADATA_KEYS = {
    "ok",
    "project_id",
    "projectId",
    "revision",
    "saved_at",
    "created_at",
    "updated_at",
    "status",
    "message",
    "operation_id",
    "method",
    "path",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _positive_revision(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value


def _decode_gateway_payload(call: Mapping[str, Any]) -> Mapping[str, Any] | None:
    if (
        call.get("name") != "hs_backend_call"
        or call.get("status") != "completed"
        or call.get("error") is not None
    ):
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
        return structured
    content = wrapper.get("content")
    if not isinstance(content, Sequence) or isinstance(content, (str, bytes, bytearray)):
        return None
    texts = [
        row.get("text")
        for row in content
        if isinstance(row, Mapping)
        and row.get("type") == "text"
        and isinstance(row.get("text"), str)
    ]
    if len(texts) != 1:
        return None
    try:
        payload = json.loads(texts[0])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, Mapping) else None


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


def _project_ids(value: Any) -> set[str]:
    result: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, Mapping):
            for key, child in node.items():
                if str(key) in {"project_id", "projectId"} and isinstance(child, str):
                    token = child.strip()
                    if token:
                        result.add(token)
                walk(child)
        elif isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
            for child in node:
                walk(child)

    walk(value)
    return result


def _reported_project_revision(body: Any, expected_project_id: str) -> int | None:
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


def _operation_rows(normalized: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, call in enumerate(normalized.get("output") or []):
        if not isinstance(call, Mapping):
            continue
        payload = _decode_gateway_payload(call)
        arguments = call.get("arguments")
        if payload is None or not isinstance(arguments, Mapping):
            continue
        operation_id = arguments.get("operation_id")
        method = payload.get("method")
        path = payload.get("path")
        status_code = payload.get("status_code")
        ok = payload.get("ok")
        if (
            not isinstance(operation_id, str)
            or payload.get("operation_id") != operation_id
            or not isinstance(method, str)
            or not isinstance(path, str)
            or not isinstance(ok, bool)
            or isinstance(status_code, bool)
            or not isinstance(status_code, int)
            or ok != (200 <= status_code < 300)
        ):
            continue
        body = _response_body(payload)
        rows.append(
            {
                "backend_call_index": index,
                "operation_id": operation_id,
                "method": method,
                "path": path,
                "ok": ok,
                "arguments": dict(arguments),
                "response_body": body,
                "argument_project_ids": sorted(_project_ids(arguments)),
                "body_project_ids": sorted(_project_ids(body)),
            }
        )
    return rows


def _final_snapshot(
    rows: Sequence[Mapping[str, Any]],
    expected_project_id: str,
) -> tuple[dict[str, Any], int | None]:
    mutations = [
        row for row in rows if row.get("ok") and row.get("method") != "GET"
    ]
    last_mutation = max(
        (int(row["backend_call_index"]) for row in mutations),
        default=-1,
    )
    for row in reversed(rows):
        if int(row["backend_call_index"]) <= last_mutation:
            continue
        if (
            row.get("ok") is not True
            or row.get("method") != "GET"
            or row.get("path") != f"/v1/projects/{expected_project_id}"
        ):
            continue
        arguments = row.get("arguments")
        if not isinstance(arguments, Mapping) or arguments.get("query") not in (None, {}):
            continue
        path_params = arguments.get("path_params")
        if not isinstance(path_params, Mapping) or path_params.get("project_id") != expected_project_id:
            continue
        body = row.get("response_body")
        project = body.get("project") if isinstance(body, Mapping) and body.get("ok") is True else None
        if not isinstance(project, Mapping) or project.get("project_id") != expected_project_id:
            continue
        revision = _positive_revision(project.get("revision"))
        snapshot = project.get("snapshot")
        if revision is not None and isinstance(snapshot, Mapping):
            return dict(snapshot), revision
    return {}, None


def _changed_surface_values(
    initial_snapshot: Mapping[str, Any],
    final_snapshot: Mapping[str, Any],
    changed_surfaces: Sequence[str],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for raw_name in changed_surfaces:
        name = str(raw_name)
        if name in _NONCREDITABLE_SURFACES:
            continue
        if name not in final_snapshot:
            continue
        value = final_snapshot.get(name)
        if not isinstance(value, (Mapping, list)) or not value:
            continue
        if _canonical_json(value) == _canonical_json(initial_snapshot.get(name)):
            continue
        result[name] = value
    return result


def _payload_objects(value: Any, path: str = "$") -> list[tuple[str, Any]]:
    """Collect nonempty structural values, excluding generic response metadata."""

    result: list[tuple[str, Any]] = []
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            if key in _RESPONSE_METADATA_KEYS:
                continue
            child_path = f"{path}.{key}"
            if isinstance(child, (Mapping, list)) and child:
                result.append((child_path, child))
                result.extend(_payload_objects(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{path}[{index}]"
            if isinstance(child, (Mapping, list)) and child:
                result.append((child_path, child))
                result.extend(_payload_objects(child, child_path))
    return result


def _is_generic_project_mutation(method: str, path: str, project_id: str) -> bool:
    exact = {
        ("PUT", f"/v1/projects/{project_id}/snapshot"),
        ("POST", f"/v1/projects/{project_id}/duplicate"),
        ("PATCH", f"/v1/projects/{project_id}/archive"),
        ("DELETE", f"/v1/projects/{project_id}"),
    }
    return (method, path) in exact


def audit_codex_progress_provenance(
    normalized: Mapping[str, Any],
    *,
    expected_project_id: str,
    initial_snapshot: Mapping[str, Any],
    mission_progress: Mapping[str, Any],
) -> dict[str, Any]:
    """Require exact operation-output provenance for at least one changed engineering surface."""

    rows = _operation_rows(normalized)
    final_snapshot, final_revision = _final_snapshot(rows, expected_project_id)
    changed = _changed_surface_values(
        initial_snapshot,
        final_snapshot,
        list(mission_progress.get("changed_mission_surfaces") or []),
    )
    changed_fingerprints = {
        _fingerprint(value): surface for surface, value in changed.items()
    }

    revision_candidates: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    for row in rows:
        method = str(row.get("method") or "")
        path = str(row.get("path") or "")
        if not row.get("ok") or method == "GET":
            continue
        if _is_generic_project_mutation(method, path, expected_project_id):
            continue
        # Scope must be established by the request itself or the canonical project path.
        # A response that merely echoes/asserts the experiment id cannot self-authenticate.
        scoped = (
            expected_project_id in set(row.get("argument_project_ids") or [])
            or f"/projects/{expected_project_id}/" in path
        )
        if not scoped:
            continue
        reported_revision = _reported_project_revision(
            row.get("response_body"), expected_project_id
        )
        if reported_revision != final_revision or final_revision is None:
            continue
        candidate = {
            "backend_call_index": row.get("backend_call_index"),
            "operation_id": row.get("operation_id"),
            "method": method,
            "path": path,
            "reported_project_revision": reported_revision,
        }
        revision_candidates.append(candidate)
        for payload_path, payload_value in _payload_objects(row.get("response_body")):
            fp = _fingerprint(payload_value)
            surface = changed_fingerprints.get(fp)
            if surface is None:
                continue
            matches.append(
                {
                    **candidate,
                    "final_surface": surface,
                    "response_payload_path": payload_path,
                    "payload_sha256": fp,
                }
            )

    checks = {
        "mission_progress_contract_pass": mission_progress.get("contract_pass") is True,
        "final_revision_available": final_revision is not None,
        "creditable_changed_engineering_surface_present": bool(changed),
        "revision_linked_project_mutation_present": bool(revision_candidates),
        "operation_payload_matches_changed_final_surface": bool(matches),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_pass": all(checks.values()),
        "checks": checks,
        "final_project_revision": final_revision,
        "creditable_changed_surfaces": sorted(changed),
        "noncreditable_surfaces": sorted(_NONCREDITABLE_SURFACES),
        "revision_linked_candidates": revision_candidates,
        "operation_surface_links": matches,
        "correct_engineering_architecture_asserted": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "claim_boundary": (
            "Pass proves only that at least one changed final engineering surface is an "
            "exact structural value returned by a request-scoped, non-generic HS mutation "
            "that reports the same persisted revision later read back canonically. It does "
            "not prove the returned engineering content is correct, complete, or physically valid."
        ),
    }
