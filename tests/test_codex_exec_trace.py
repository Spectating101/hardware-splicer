from __future__ import annotations

import json

import pytest

from hardware_splicer.codex_exec_trace import (
    audit_codex_exec_trace,
    normalize_codex_exec_events,
    parse_codex_jsonl,
)


def _mcp(
    item_id: str,
    tool: str,
    arguments: dict,
    *,
    status: str = "completed",
    server: str = "hardware-splicer-backend",
) -> dict:
    result = {
        "content": [{"type": "text", "text": "{}"}],
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
            {"operation_id": "get_project", "json_body": {"project_id": project}},
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

    audit = audit_codex_exec_trace(
        events,
        model="gpt-6-astra",
        expected_project_id="exp-1",
        known_source_ids=set(),
    )
    assert audit["hard_truth_contract_pass"] is True
    assert audit["codex_cleanroom_contract_pass"] is True
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
    audit = audit_codex_exec_trace(
        events,
        model="gpt-6-astra",
        expected_project_id="exp-1",
        known_source_ids=set(),
    )
    assert audit["hard_truth_contract_pass"] is True
    assert audit["codex_cleanroom_contract_pass"] is False
    assert audit["codex_hard_truth_contract_pass"] is False


def test_foreign_mcp_server_fails_cleanroom() -> None:
    events = _valid_events()
    events[2] = _mcp("1", "hs_backend_status", {}, server="other-server")
    audit = audit_codex_exec_trace(
        events,
        model="gpt-6-astra",
        expected_project_id="exp-1",
        known_source_ids=set(),
    )
    assert audit["codex_foreign_mcp_servers"] == ["other-server"]
    assert audit["codex_hard_truth_contract_pass"] is False


def test_unexpected_mcp_tool_fails_cleanroom_and_gateway() -> None:
    events = _valid_events()
    events[2] = _mcp("1", "read_repo_source", {})
    audit = audit_codex_exec_trace(
        events,
        model="gpt-6-astra",
        expected_project_id="exp-1",
        known_source_ids=set(),
    )
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
    audit = audit_codex_exec_trace(
        events,
        model="gpt-6-astra",
        expected_project_id="exp-1",
        known_source_ids=set(),
    )
    assert audit["codex_unknown_item_types"] == ["future_tool"]
    assert audit["codex_hard_truth_contract_pass"] is False


def test_arguments_and_result_are_preserved() -> None:
    events = _valid_events()
    normalized = normalize_codex_exec_events(events, model="gpt-6-astra")
    call = normalized["output"][-1]
    assert call["arguments"]["json_body"]["project_id"] == "exp-1"
    result = json.loads(call["output"])
    assert result["content"][0]["text"] == "{}"
