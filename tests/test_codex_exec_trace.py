from __future__ import annotations

import json

import pytest

from hardware_splicer.codex_exec_trace import (
    audit_codex_exec_trace,
    normalize_codex_exec_events,
    parse_codex_jsonl,
)


def _project_body(project_id: str = "exp-1", revision: int = 1) -> dict:
    return {
        "ok": True,
        "project": {
            "schema_version": "hardware_splicer.project_snapshot.v1",
            "project_id": project_id,
            "revision": revision,
            "saved_at": "2026-09-10T00:00:00+00:00",
            "snapshot": {"mission": "synthetic"},
            "metadata": {},
        },
    }


def _gateway_payload(
    *,
    operation_id: str,
    method: str = "GET",
    ok: bool = True,
    status_code: int = 200,
    project_id: str = "exp-1",
) -> dict:
    return {
        "ok": ok,
        "status_code": status_code,
        "content_type": "application/json",
        "byte_length": 2,
        "sha256": "0" * 64,
        "headers": {"content-type": "application/json"},
        "body": (
            _project_body(project_id)
            if ok and method == "GET"
            else {"detail": "blocked"}
        ),
        "operation_id": operation_id,
        "method": method,
        "path": f"/v1/projects/{project_id}",
    }


def _mcp(
    item_id: str,
    tool: str,
    arguments: dict,
    *,
    status: str = "completed",
    server: str = "hardware-splicer-backend",
    gateway_payload: dict | None = None,
) -> dict:
    if gateway_payload is None and tool == "hs_backend_call":
        gateway_payload = _gateway_payload(
            operation_id=str(arguments.get("operation_id") or "unknown")
        )
    text = json.dumps(gateway_payload) if tool == "hs_backend_call" else "{}"
    result = {
        "content": [{"type": "text", "text": text}],
        "structured_content": None,
    }
    return {
        "type": "item.completed",
        "item": {
            "id": item_id,
            "type": "mcp_tool_call",
            "server": server,
            "tool": tool,
            "arguments": arguments,
            "result": result if status == "completed" else None,
            "error": None if status == "completed" else {"message": "boom"},
            "status": status,
        },
    }


def _valid_events() -> list[dict]:
    project = "exp-1"
    return [
        {"type": "thread.started", "thread_id": "thread-1"},
        {"type": "turn.started"},
        _mcp("1", "hs_backend_status", {}),
        _mcp("2", "hs_backend_list_operations", {"text": "project"}),
        _mcp("3", "hs_backend_describe_operation", {"operation_id": "get_project"}),
        _mcp(
            "4",
            "hs_backend_call",
            {
                "operation_id": "get_project",
                "path_params": {"project_id": project},
            },
        ),
        {
            "type": "item.completed",
            "item": {"id": "5", "type": "agent_message", "text": "done"},
        },
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 100,
                "cached_input_tokens": 20,
                "cache_write_input_tokens": 0,
                "output_tokens": 30,
                "reasoning_output_tokens": 10,
            },
        },
    ]


def _audit(events: list[dict]) -> dict:
    return audit_codex_exec_trace(
        events,
        model="gpt-6-astra",
        expected_project_id="exp-1",
        known_source_ids=set(),
    )


def test_parse_jsonl_rejects_malformed_line() -> None:
    with pytest.raises(ValueError, match="line 2"):
        parse_codex_jsonl('{"type":"turn.started"}\nnot-json\n')


def test_valid_trace_normalizes_and_audits() -> None:
    events = _valid_events()
    normalized = normalize_codex_exec_events(events, model="gpt-6-astra")
    assert normalized["status"] == "completed"
    assert normalized["id"] == "thread-1"
    assert len(normalized["output"]) == 4
    assert normalized["codex_trace"]["cleanroom_contract_pass"] is True
    assert normalized["usage"]["reasoning_output_tokens"] == 10

    audit = _audit(events)
    assert audit["hard_truth_contract_pass"] is True
    assert audit["codex_cleanroom_contract_pass"] is True
    assert audit["backend_result_parse_pass"] is True
    assert audit["final_project_readback_pass"] is True
    assert audit["codex_hard_truth_contract_pass"] is True


@pytest.mark.parametrize(
    "item_type",
    ["command_execution", "file_change", "web_search", "collab_tool_call"],
)
def test_non_mcp_tool_activity_fails_cleanroom_contract(item_type: str) -> None:
    events = _valid_events()
    events.insert(
        -1,
        {
            "type": "item.completed",
            "item": {"id": "x", "type": item_type, "status": "completed"},
        },
    )
    audit = _audit(events)
    assert audit["hard_truth_contract_pass"] is True
    assert audit["codex_cleanroom_contract_pass"] is False
    assert audit["codex_hard_truth_contract_pass"] is False


def test_foreign_mcp_server_fails_cleanroom() -> None:
    events = _valid_events()
    events[2] = _mcp("1", "hs_backend_status", {}, server="other-server")
    audit = _audit(events)
    assert audit["codex_foreign_mcp_servers"] == ["other-server"]
    assert audit["codex_hard_truth_contract_pass"] is False


def test_unexpected_mcp_tool_fails_cleanroom_and_gateway() -> None:
    events = _valid_events()
    events[2] = _mcp("1", "read_repo_source", {})
    audit = _audit(events)
    assert audit["codex_unexpected_mcp_tools"] == ["read_repo_source"]
    assert audit["hard_truth_contract_pass"] is False
    assert audit["codex_hard_truth_contract_pass"] is False


def test_started_mcp_without_terminal_result_fails_closed() -> None:
    events = _valid_events()
    events[2] = {
        "type": "item.started",
        "item": {
            "id": "1",
            "type": "mcp_tool_call",
            "server": "hardware-splicer-backend",
            "tool": "hs_backend_status",
            "arguments": {},
            "result": None,
            "error": None,
            "status": "in_progress",
        },
    }
    normalized = normalize_codex_exec_events(events, model="gpt-6-astra")
    assert normalized["status"] == "failed"
    assert normalized["output"][0]["status"] == "failed"
    assert "before terminal" in normalized["output"][0]["error"]


def test_turn_failure_fails_response_completion() -> None:
    events = _valid_events()[:-1]
    events.append({"type": "turn.failed", "error": {"message": "model unavailable"}})
    normalized = normalize_codex_exec_events(events, model="gpt-6-astra")
    assert normalized["status"] == "failed"
    assert normalized["error"] == "model unavailable"


def test_error_item_fails_response_completion() -> None:
    events = _valid_events()
    events.insert(
        -1,
        {
            "type": "item.completed",
            "item": {"id": "err", "type": "error", "message": "nonfatal"},
        },
    )
    normalized = normalize_codex_exec_events(events, model="gpt-6-astra")
    assert normalized["status"] == "failed"
    assert "nonfatal" in normalized["error"]


def test_unknown_item_type_fails_cleanroom_contract() -> None:
    events = _valid_events()
    events.insert(
        -1,
        {"type": "item.completed", "item": {"id": "new", "type": "future_tool"}},
    )
    audit = _audit(events)
    assert audit["codex_unknown_item_types"] == ["future_tool"]
    assert audit["codex_hard_truth_contract_pass"] is False


def test_arguments_and_result_are_preserved() -> None:
    normalized = normalize_codex_exec_events(_valid_events(), model="gpt-6-astra")
    call = normalized["output"][-1]
    assert call["arguments"]["path_params"]["project_id"] == "exp-1"
    result = json.loads(call["output"])
    payload = json.loads(result["content"][0]["text"])
    assert payload["operation_id"] == "get_project"


def test_intermediate_backend_failure_is_evidence_not_automatic_case_failure() -> None:
    events = _valid_events()
    events.insert(
        5,
        _mcp(
            "3b",
            "hs_backend_call",
            {
                "operation_id": "update_project",
                "path_params": {"project_id": "exp-1"},
            },
            gateway_payload=_gateway_payload(
                operation_id="update_project",
                method="PATCH",
                ok=False,
                status_code=422,
            ),
        ),
    )
    audit = _audit(events)
    assert audit["backend_application_failure_count"] == 1
    assert audit["backend_result_parse_pass"] is True
    assert audit["final_project_readback_pass"] is True
    assert audit["codex_hard_truth_contract_pass"] is True


def test_successful_mutation_requires_later_project_readback() -> None:
    events = _valid_events()
    events.insert(
        -2,
        _mcp(
            "4b",
            "hs_backend_call",
            {
                "operation_id": "update_project",
                "path_params": {"project_id": "exp-1"},
            },
            gateway_payload=_gateway_payload(
                operation_id="update_project",
                method="PATCH",
                ok=True,
                status_code=200,
            ),
        ),
    )
    audit = _audit(events)
    assert audit["backend_result_parse_pass"] is True
    assert audit["final_project_readback_pass"] is False
    assert audit["codex_hard_truth_contract_pass"] is False


def test_successful_readback_after_mutation_passes() -> None:
    events = _valid_events()
    events.pop(5)
    mutation = _mcp(
        "4a",
        "hs_backend_call",
        {
            "operation_id": "update_project",
            "path_params": {"project_id": "exp-1"},
        },
        gateway_payload=_gateway_payload(
            operation_id="update_project", method="PATCH", ok=True, status_code=200
        ),
    )
    readback = _mcp(
        "4b",
        "hs_backend_call",
        {"operation_id": "get_project", "path_params": {"project_id": "exp-1"}},
        gateway_payload=_gateway_payload(operation_id="get_project"),
    )
    events.insert(5, mutation)
    events.insert(6, readback)
    audit = _audit(events)
    assert audit["codex_backend_result_audit"]["successful_mutation_count"] == 1
    assert audit["final_project_readback_pass"] is True
    assert audit["codex_hard_truth_contract_pass"] is True


def test_unparseable_backend_result_fails_semantic_contract() -> None:
    events = _valid_events()
    events[5]["item"]["result"]["content"][0]["text"] = "not-json"
    audit = _audit(events)
    assert audit["backend_result_parse_pass"] is False
    assert audit["codex_hard_truth_contract_pass"] is False


def test_readback_of_wrong_project_fails_semantic_contract() -> None:
    events = _valid_events()
    events[5] = _mcp(
        "4",
        "hs_backend_call",
        {"operation_id": "get_project", "path_params": {"project_id": "exp-1"}},
        gateway_payload=_gateway_payload(
            operation_id="get_project", project_id="other-project"
        ),
    )
    audit = _audit(events)
    assert audit["final_project_readback_pass"] is False
    assert audit["codex_hard_truth_contract_pass"] is False
