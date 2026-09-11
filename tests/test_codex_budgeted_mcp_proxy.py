from __future__ import annotations

import json

from hardware_splicer.codex_budgeted_mcp_proxy import (
    ASTRA_MAX_BACKEND_CALLS,
    ASTRA_MAX_MCP_TOOL_CALLS,
    ASTRA_MAX_REQUEST_BYTES,
    ToolBudget,
    classify_client_line,
)


def _call(request_id: int, name: str, arguments: dict | None = None) -> str:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        }
    ) + "\n"


def test_non_tool_protocol_messages_do_not_consume_budget() -> None:
    budget = ToolBudget(max_tool_calls=2, max_backend_calls=1)
    for message in (
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ):
        action, denial = classify_client_line(json.dumps(message) + "\n", budget)
        assert action == "forward"
        assert denial is None
    assert budget.tool_calls == 0
    assert budget.backend_calls == 0


def test_exact_allowed_tool_surface_is_budgeted() -> None:
    budget = ToolBudget(max_tool_calls=4, max_backend_calls=1)
    names = [
        "hs_backend_status",
        "hs_backend_list_operations",
        "hs_backend_describe_operation",
        "hs_backend_call",
    ]
    for index, name in enumerate(names, start=1):
        action, denial = classify_client_line(_call(index, name), budget)
        assert action == "forward"
        assert denial is None
    assert budget.tool_calls == 4
    assert budget.backend_calls == 1


def test_total_tool_budget_denies_next_call_without_incrementing() -> None:
    budget = ToolBudget(max_tool_calls=2, max_backend_calls=2)
    assert classify_client_line(_call(1, "hs_backend_status"), budget)[0] == "forward"
    assert classify_client_line(_call(2, "hs_backend_list_operations"), budget)[0] == "forward"
    action, denial = classify_client_line(_call(3, "hs_backend_describe_operation"), budget)
    assert action == "deny"
    assert denial["id"] == 3
    assert denial["error"]["code"] == -32098
    assert denial["error"]["data"]["tool_calls_used"] == 2
    assert denial["error"]["data"]["tool_calls_limit"] == 2
    assert denial["error"]["data"]["api_fallback"] is False
    assert budget.tool_calls == 2


def test_backend_call_budget_is_independent_and_harder_than_total_limit() -> None:
    budget = ToolBudget(max_tool_calls=10, max_backend_calls=2)
    assert classify_client_line(_call(1, "hs_backend_call"), budget)[0] == "forward"
    assert classify_client_line(_call(2, "hs_backend_status"), budget)[0] == "forward"
    assert classify_client_line(_call(3, "hs_backend_call"), budget)[0] == "forward"
    action, denial = classify_client_line(_call(4, "hs_backend_call"), budget)
    assert action == "deny"
    assert denial["error"]["code"] == -32098
    assert denial["error"]["data"]["backend_calls_used"] == 2
    assert denial["error"]["data"]["backend_calls_limit"] == 2
    assert budget.tool_calls == 3
    assert budget.backend_calls == 2


def test_unknown_tool_is_policy_denial_and_consumes_no_budget() -> None:
    budget = ToolBudget(max_tool_calls=20, max_backend_calls=8)
    action, denial = classify_client_line(_call(1, "read_repo_source"), budget)
    assert action == "deny"
    assert denial["error"]["code"] == -32097
    assert "outside" in denial["error"]["message"]
    assert budget.tool_calls == 0
    assert budget.backend_calls == 0


def test_malformed_tool_call_fails_closed() -> None:
    budget = ToolBudget()
    action, denial = classify_client_line(
        json.dumps({"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": []}),
        budget,
    )
    assert action == "deny"
    assert denial["id"] == 7
    assert denial["error"]["code"] == -32097
    assert budget.tool_calls == 0


def test_malformed_json_fails_closed() -> None:
    budget = ToolBudget()
    action, denial = classify_client_line("{not-json}\n", budget)
    assert action == "deny"
    assert denial["error"]["code"] == -32097
    assert budget.tool_calls == 0


def test_oversized_message_fails_before_json_or_budget_processing() -> None:
    budget = ToolBudget()
    raw = "{" + ("x" * ASTRA_MAX_REQUEST_BYTES) + "}"
    action, denial = classify_client_line(raw, budget)
    assert action == "deny"
    assert "request-size limit" in denial["error"]["message"]
    assert budget.tool_calls == 0


def test_experiment_limits_are_deliberately_small() -> None:
    assert ASTRA_MAX_MCP_TOOL_CALLS == 20
    assert ASTRA_MAX_BACKEND_CALLS == 8
    assert ASTRA_MAX_REQUEST_BYTES == 262_144
