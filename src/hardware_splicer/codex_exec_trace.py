"""Normalize Codex exec JSONL into Hardware-Splicer's external MCP audit shape."""

from __future__ import annotations

import json
from collections import OrderedDict
from typing import Any, Mapping, Sequence

from .external_mcp_trace_audit import audit_response_trace

CODEX_TRACE_SCHEMA = "hardware_splicer.codex_exec_trace.v2"
DEFAULT_MCP_SERVER = "hardware-splicer-backend"
HS_MCP_TOOLS = {
    "hs_backend_status",
    "hs_backend_list_operations",
    "hs_backend_describe_operation",
    "hs_backend_call",
}
_ALLOWED_NON_TOOL_ITEMS = {"agent_message", "reasoning", "todo_list"}
_FORBIDDEN_ITEM_TYPES = {"command_execution", "file_change", "web_search", "collab_tool_call"}


def parse_codex_jsonl(text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid Codex JSONL at line {line_number}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"Codex JSONL line {line_number} is not a JSON object")
        events.append(value)
    if not events:
        raise ValueError("Codex JSONL contains no events")
    return events


def _json_text(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _item(event: Mapping[str, Any]) -> Mapping[str, Any] | None:
    value = event.get("item")
    return value if isinstance(value, Mapping) else None


def _normalize_mcp_item(item: Mapping[str, Any], *, terminal: bool) -> dict[str, Any]:
    status = str(item.get("status") or "")
    error = item.get("error")
    result = item.get("result")
    arguments = item.get("arguments")
    if not isinstance(arguments, Mapping):
        arguments = arguments if arguments is not None else {}
    completed = (
        terminal
        and status == "completed"
        and error in (None, {})
        and result is not None
    )
    if completed:
        normalized_status = "completed"
        normalized_error = None
    else:
        normalized_status = "failed"
        if isinstance(error, Mapping):
            normalized_error = str(error.get("message") or _json_text(error))
        elif error:
            normalized_error = str(error)
        elif not terminal:
            normalized_error = "Codex JSONL ended before terminal MCP event"
        elif status != "completed":
            normalized_error = f"Codex MCP status is {status or 'missing'}"
        else:
            normalized_error = "Codex MCP completed without a result payload"
    return {
        "type": "mcp_call",
        "name": item.get("tool"),
        "arguments": arguments,
        "status": normalized_status,
        "error": normalized_error,
        "output": None if result is None else _json_text(result),
        "codex_server": item.get("server"),
        "codex_item_id": item.get("id"),
    }


def normalize_codex_exec_events(
    events: Sequence[Mapping[str, Any]],
    *,
    model: str,
    expected_mcp_server: str = DEFAULT_MCP_SERVER,
) -> dict[str, Any]:
    if not events:
        raise ValueError("Codex trace has no events")

    thread_ids: list[str] = []
    turn_started = 0
    turn_completed: list[Mapping[str, Any]] = []
    failures: list[str] = []
    item_states: OrderedDict[str, tuple[Mapping[str, Any], bool]] = OrderedDict()
    forbidden_items: list[dict[str, Any]] = []
    unknown_item_types: list[str] = []
    foreign_mcp_servers: set[str] = set()
    unexpected_mcp_tools: set[str] = set()

    for event_index, event in enumerate(events):
        event_type = str(event.get("type") or "")
        if event_type == "thread.started":
            thread_id = str(event.get("thread_id") or "").strip()
            if thread_id:
                thread_ids.append(thread_id)
            continue
        if event_type == "turn.started":
            turn_started += 1
            continue
        if event_type == "turn.completed":
            turn_completed.append(event)
            continue
        if event_type == "turn.failed":
            error = event.get("error")
            if isinstance(error, Mapping):
                failures.append(str(error.get("message") or _json_text(error)))
            else:
                failures.append(str(error or "Codex turn failed"))
            continue
        if event_type == "error":
            failures.append(str(event.get("message") or "Codex event-stream error"))
            continue
        if event_type not in {"item.started", "item.updated", "item.completed"}:
            failures.append(f"Unknown Codex event type: {event_type or '<missing>'}")
            continue

        item = _item(event)
        if item is None:
            failures.append(f"Codex {event_type} event has no item object")
            continue
        item_id = str(item.get("id") or "").strip()
        item_type = str(item.get("type") or "").strip()
        if not item_id:
            failures.append(f"Codex {event_type} item has no id")
            continue
        terminal = event_type == "item.completed"
        item_states[item_id] = (item, terminal)

        if item_type == "mcp_tool_call":
            server = str(item.get("server") or "")
            tool = str(item.get("tool") or "")
            if server != expected_mcp_server:
                foreign_mcp_servers.add(server or "<missing>")
            if tool not in HS_MCP_TOOLS:
                unexpected_mcp_tools.add(tool or "<missing>")
        elif item_type in _FORBIDDEN_ITEM_TYPES:
            forbidden_items.append(
                {"event_index": event_index, "item_id": item_id, "item_type": item_type}
            )
        elif item_type == "error":
            failures.append(str(item.get("message") or "Codex error item"))
        elif item_type not in _ALLOWED_NON_TOOL_ITEMS:
            unknown_item_types.append(item_type or "<missing>")

    mcp_calls: list[dict[str, Any]] = []
    for item, terminal in item_states.values():
        if item.get("type") == "mcp_tool_call":
            mcp_calls.append(_normalize_mcp_item(item, terminal=terminal))

    unique_threads = list(dict.fromkeys(thread_ids))
    usage = turn_completed[-1].get("usage") if turn_completed else None
    exactly_one_turn = turn_started == 1 and len(turn_completed) == 1
    cleanroom_pass = not (
        forbidden_items
        or unknown_item_types
        or foreign_mcp_servers
        or unexpected_mcp_tools
    )
    response_completed = (
        exactly_one_turn
        and not failures
        and len(unique_threads) == 1
        and all(call.get("status") == "completed" for call in mcp_calls)
    )
    response_error = None if not failures else "; ".join(dict.fromkeys(failures))

    return {
        "id": unique_threads[0] if len(unique_threads) == 1 else None,
        "model": model,
        "status": "completed" if response_completed else "failed",
        "error": response_error,
        "incomplete_details": None
        if response_completed
        else {
            "turn_started_count": turn_started,
            "turn_completed_count": len(turn_completed),
            "thread_ids": unique_threads,
        },
        "output": mcp_calls,
        "usage": usage,
        "codex_trace": {
            "schema_version": CODEX_TRACE_SCHEMA,
            "event_count": len(events),
            "thread_ids": unique_threads,
            "turn_started_count": turn_started,
            "turn_completed_count": len(turn_completed),
            "forbidden_non_mcp_items": forbidden_items,
            "unknown_item_types": sorted(set(unknown_item_types)),
            "foreign_mcp_servers": sorted(foreign_mcp_servers),
            "unexpected_mcp_tools": sorted(unexpected_mcp_tools),
            "cleanroom_contract_pass": cleanroom_pass,
            "raw_reasoning_persisted": False,
        },
    }


def normalize_codex_jsonl(
    text: str,
    *,
    model: str,
    expected_mcp_server: str = DEFAULT_MCP_SERVER,
) -> dict[str, Any]:
    return normalize_codex_exec_events(
        parse_codex_jsonl(text),
        model=model,
        expected_mcp_server=expected_mcp_server,
    )


def _decode_gateway_payload(
    call: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    if call.get("name") != "hs_backend_call":
        return None, "not a backend call"
    if call.get("status") != "completed" or call.get("error") is not None:
        return None, "MCP backend call did not complete successfully"
    output = call.get("output")
    if not isinstance(output, str):
        return None, "Codex MCP result is not inspectable JSON text"
    try:
        wrapper = json.loads(output)
    except json.JSONDecodeError:
        return None, "Codex MCP result wrapper is not valid JSON"
    if not isinstance(wrapper, Mapping):
        return None, "Codex MCP result wrapper is not a JSON object"

    structured = wrapper.get("structured_content")
    if isinstance(structured, Mapping):
        payload: Any = structured
    else:
        content = wrapper.get("content")
        if not isinstance(content, Sequence) or isinstance(
            content, (str, bytes, bytearray)
        ):
            return None, "Codex MCP result has no content blocks"
        texts = [
            row.get("text")
            for row in content
            if isinstance(row, Mapping)
            and row.get("type") == "text"
            and isinstance(row.get("text"), str)
        ]
        if len(texts) != 1:
            return None, "HS MCP result must contain exactly one text payload"
        try:
            payload = json.loads(texts[0])
        except json.JSONDecodeError:
            return None, "HS MCP text payload is not valid JSON"
    if not isinstance(payload, Mapping):
        return None, "HS MCP payload is not a JSON object"
    return dict(payload), None


def _named_project_ids(value: Any) -> set[str]:
    result: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, Mapping):
            for key, child in node.items():
                if str(key) == "project_id" and isinstance(child, str) and child.strip():
                    result.add(child.strip())
                walk(child)
        elif isinstance(node, Sequence) and not isinstance(
            node, (str, bytes, bytearray)
        ):
            for child in node:
                walk(child)

    walk(value)
    return result


def _response_body(payload: Mapping[str, Any]) -> Any:
    if "body" in payload:
        return payload.get("body")
    body_text = payload.get("body_text")
    if isinstance(body_text, str):
        try:
            return json.loads(body_text)
        except json.JSONDecodeError:
            return None
    return None


def _canonical_latest_project_readback(
    row: Mapping[str, Any],
    *,
    expected_project_id: str,
) -> tuple[bool, str | None]:
    """Require the canonical latest-state project load, not a project-related GET."""

    if not row.get("ok") or row.get("method") != "GET":
        return False, "not a successful GET"
    if row.get("path") != f"/v1/projects/{expected_project_id}":
        return False, "not the canonical project-load path"

    arguments = row.get("arguments")
    if not isinstance(arguments, Mapping):
        return False, "backend-call arguments are not an object"
    path_params = arguments.get("path_params")
    if not isinstance(path_params, Mapping) or path_params.get("project_id") != expected_project_id:
        return False, "canonical load does not bind the expected project id"
    query = arguments.get("query")
    if query not in (None, {}):
        if isinstance(query, Mapping) and "revision" in query:
            return False, "historical revision readback cannot certify latest state"
        return False, "canonical latest readback must not include query parameters"
    if expected_project_id not in row.get("body_project_ids", []):
        return False, "canonical load response does not confirm the expected project id"
    return True, None


def audit_codex_backend_results(
    normalized: Mapping[str, Any],
    *,
    expected_project_id: str,
) -> dict[str, Any]:
    calls = [
        row
        for row in normalized.get("output", [])
        if isinstance(row, Mapping) and row.get("name") == "hs_backend_call"
    ]
    parsed_rows: list[dict[str, Any]] = []
    invalid_rows: list[dict[str, Any]] = []
    application_failures: list[dict[str, Any]] = []

    for index, call in enumerate(calls):
        payload, parse_error = _decode_gateway_payload(call)
        arguments = call.get("arguments")
        operation_id = (
            arguments.get("operation_id") if isinstance(arguments, Mapping) else None
        )
        if payload is None:
            invalid_rows.append(
                {
                    "backend_call_index": index,
                    "operation_id": operation_id,
                    "reason": parse_error,
                }
            )
            continue

        status_code = payload.get("status_code")
        ok = payload.get("ok")
        method = payload.get("method")
        path = payload.get("path")
        payload_operation_id = payload.get("operation_id")
        envelope_valid = (
            isinstance(ok, bool)
            and isinstance(status_code, int)
            and not isinstance(status_code, bool)
            and 100 <= status_code <= 599
            and isinstance(method, str)
            and method in {"GET", "POST", "PUT", "PATCH", "DELETE"}
            and isinstance(path, str)
            and bool(path)
            and isinstance(payload_operation_id, str)
            and bool(payload_operation_id)
            and payload_operation_id == operation_id
            and ok == (200 <= status_code < 300)
        )
        if not envelope_valid:
            invalid_rows.append(
                {
                    "backend_call_index": index,
                    "operation_id": operation_id,
                    "reason": "backend result is not a canonical dispatch envelope",
                }
            )
            continue

        body = _response_body(payload)
        row = {
            "backend_call_index": index,
            "operation_id": operation_id,
            "method": method,
            "path": path,
            "ok": ok,
            "status_code": status_code,
            "arguments": dict(arguments) if isinstance(arguments, Mapping) else arguments,
            "argument_project_ids": sorted(_named_project_ids(arguments)),
            "body_project_ids": sorted(_named_project_ids(body)),
        }
        parsed_rows.append(row)
        if not ok:
            application_failures.append(
                {
                    "backend_call_index": index,
                    "operation_id": operation_id,
                    "method": method,
                    "status_code": status_code,
                }
            )

    successful_mutations = [
        row for row in parsed_rows if row["ok"] and row["method"] != "GET"
    ]
    last_mutation_index = (
        max(row["backend_call_index"] for row in successful_mutations)
        if successful_mutations
        else -1
    )

    canonical_readbacks: list[dict[str, Any]] = []
    rejected_readback_candidates: list[dict[str, Any]] = []
    for row in parsed_rows:
        if not row["ok"] or row["method"] != "GET":
            continue
        mentions_project = (
            expected_project_id in row["argument_project_ids"]
            or expected_project_id in row["body_project_ids"]
        )
        if not mentions_project:
            continue
        passed, reason = _canonical_latest_project_readback(
            row,
            expected_project_id=expected_project_id,
        )
        if passed:
            canonical_readbacks.append(row)
        else:
            rejected_readback_candidates.append(
                {
                    "backend_call_index": row["backend_call_index"],
                    "operation_id": row["operation_id"],
                    "method": row["method"],
                    "path": row["path"],
                    "reason": reason,
                }
            )

    final_readbacks = [
        row
        for row in canonical_readbacks
        if row["backend_call_index"] > last_mutation_index
    ]
    final_readback = final_readbacks[-1] if final_readbacks else None
    parse_pass = bool(calls) and not invalid_rows
    final_readback_pass = final_readback is not None

    summarized_final = None
    if final_readback is not None:
        summarized_final = {
            "backend_call_index": final_readback["backend_call_index"],
            "operation_id": final_readback["operation_id"],
            "method": final_readback["method"],
            "path": final_readback["path"],
            "project_id": expected_project_id,
        }

    return {
        "schema_version": "hardware_splicer.codex_backend_result_audit.v2",
        "backend_call_count": len(calls),
        "backend_result_parse_pass": parse_pass,
        "invalid_backend_results": invalid_rows,
        "backend_application_failure_count": len(application_failures),
        "backend_application_failures": application_failures,
        "successful_mutation_count": len(successful_mutations),
        "last_successful_mutation_index": (
            last_mutation_index if successful_mutations else None
        ),
        "successful_project_readback_count": len(canonical_readbacks),
        "rejected_project_readback_candidates": rejected_readback_candidates,
        "final_project_readback_pass": final_readback_pass,
        "final_project_readback": summarized_final,
        "final_project_readback_contract": {
            "method": "GET",
            "path": f"/v1/projects/{expected_project_id}",
            "historical_revision_allowed": False,
            "requires_expected_project_id_in_response": True,
        },
        "backend_result_contract_pass": bool(parse_pass and final_readback_pass),
        "intermediate_application_failures_are_permitted": True,
        "physical_authority_granted": False,
    }


def audit_codex_exec_trace(
    events: Sequence[Mapping[str, Any]],
    *,
    model: str,
    expected_project_id: str,
    known_source_ids: set[str],
    expected_mcp_server: str = DEFAULT_MCP_SERVER,
) -> dict[str, Any]:
    normalized = normalize_codex_exec_events(
        events,
        model=model,
        expected_mcp_server=expected_mcp_server,
    )
    audit = audit_response_trace(
        normalized,
        expected_project_id=expected_project_id,
        known_source_ids=known_source_ids,
    )
    codex = dict(normalized["codex_trace"])
    backend = audit_codex_backend_results(
        normalized,
        expected_project_id=expected_project_id,
    )
    audit["codex_trace_schema_version"] = codex["schema_version"]
    audit["codex_cleanroom_contract_pass"] = codex["cleanroom_contract_pass"]
    audit["codex_forbidden_non_mcp_items"] = codex["forbidden_non_mcp_items"]
    audit["codex_unknown_item_types"] = codex["unknown_item_types"]
    audit["codex_foreign_mcp_servers"] = codex["foreign_mcp_servers"]
    audit["codex_unexpected_mcp_tools"] = codex["unexpected_mcp_tools"]
    audit["codex_backend_result_audit"] = backend
    audit["backend_result_parse_pass"] = backend["backend_result_parse_pass"]
    audit["backend_application_failure_count"] = backend[
        "backend_application_failure_count"
    ]
    audit["final_project_readback_pass"] = backend["final_project_readback_pass"]
    audit["codex_hard_truth_contract_pass"] = bool(
        audit.get("hard_truth_contract_pass")
        and codex["cleanroom_contract_pass"]
        and backend["backend_result_contract_pass"]
    )
    audit["codex_usage"] = normalized.get("usage")
    audit["physical_authority_granted"] = False
    return audit
