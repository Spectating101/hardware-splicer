from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from hardware_splicer.frontier_operator_experiment import (
    HS_MCP_TOOLS,
    LIVE_CONFIRMATION,
    build_anthropic_request_template,
    build_openai_request_template,
    estimate_experiment_cost_usd,
    normalize_anthropic_mcp_response,
    planning_manifest,
    validate_live_policy,
)


def test_cost_envelope_for_full_frontier_corpus() -> None:
    assert estimate_experiment_cost_usd(
        model="gpt-6-astra",
        case_count=10,
        estimated_input_tokens_per_case=40_000,
        max_output_tokens_per_case=8_000,
    ) == 8.0


def test_openai_request_is_bounded_and_nonpersistent() -> None:
    payload = build_openai_request_template(
        model="gpt-6-astra",
        instructions="rules",
        input_text="mission",
    )
    assert payload["model"] == "gpt-6-astra"
    assert payload["reasoning"]["effort"] == "low"
    assert payload["store"] is False
    assert payload["max_output_tokens"] == 8000
    tool = payload["tools"][0]
    assert tuple(tool["allowed_tools"]) == HS_MCP_TOOLS
    assert tool["require_approval"] == "never"


def test_anthropic_request_allowlists_only_hs_gateway() -> None:
    payload = build_anthropic_request_template(
        model="claude-fable-5",
        instructions="rules",
        input_text="mission",
    )
    assert payload["model"] == "claude-fable-5"
    assert payload["output_config"] == {"effort": "low"}
    assert payload["betas"] == ["mcp-client-2025-11-20"]
    toolset = payload["tools"][0]
    assert toolset["default_config"] == {"enabled": False}
    assert set(toolset["configs"]) == set(HS_MCP_TOOLS)
    assert all(row == {"enabled": True} for row in toolset["configs"].values())


def test_live_policy_requires_charge_confirmation() -> None:
    with pytest.raises(ValueError, match=LIVE_CONFIRMATION):
        validate_live_policy(
            model="gpt-6-astra",
            case_count=1,
            estimated_input_tokens_per_case=40_000,
            max_output_tokens_per_case=8_000,
            max_usd=1.0,
            confirmation=None,
            allow_multi_case=False,
        )


def test_live_policy_rejects_multi_case_by_default() -> None:
    with pytest.raises(ValueError, match="multi-case"):
        validate_live_policy(
            model="claude-fable-5",
            case_count=2,
            estimated_input_tokens_per_case=40_000,
            max_output_tokens_per_case=8_000,
            max_usd=2.0,
            confirmation=LIVE_CONFIRMATION,
            allow_multi_case=False,
        )


def test_live_policy_rejects_cost_envelope_above_budget() -> None:
    with pytest.raises(ValueError, match="exceeds"):
        validate_live_policy(
            model="gpt-6-astra",
            case_count=10,
            estimated_input_tokens_per_case=40_000,
            max_output_tokens_per_case=8_000,
            max_usd=2.0,
            confirmation=LIVE_CONFIRMATION,
            allow_multi_case=True,
        )


def test_anthropic_normalization_preserves_calls_and_failures() -> None:
    response = {
        "id": "msg_1",
        "model": "claude-fable-5",
        "stop_reason": "end_turn",
        "content": [
            {
                "type": "mcp_tool_use",
                "id": "use_1",
                "name": "hs_backend_status",
                "server_name": "hardware-splicer",
                "input": {},
            },
            {
                "type": "mcp_tool_result",
                "tool_use_id": "use_1",
                "is_error": False,
                "content": [{"type": "text", "text": "{}"}],
            },
            {
                "type": "mcp_tool_use",
                "id": "use_2",
                "name": "hs_backend_call",
                "server_name": "hardware-splicer",
                "input": {"operation_id": "save_project"},
            },
        ],
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }
    normalized = normalize_anthropic_mcp_response(response)
    assert normalized["status"] == "completed"
    assert normalized["output"][0]["status"] == "completed"
    assert normalized["output"][1]["status"] == "failed"
    assert normalized["output"][1]["error"] == "missing MCP tool result"


def test_max_tokens_response_is_incomplete() -> None:
    normalized = normalize_anthropic_mcp_response(
        {
            "id": "msg_2",
            "model": "claude-fable-5",
            "stop_reason": "max_tokens",
            "content": [],
        }
    )
    assert normalized["status"] == "incomplete"


def test_manifest_is_explicitly_nonlive() -> None:
    manifest = planning_manifest(
        model="claude-fable-5",
        case_ids=["a", "b"],
        estimated_input_tokens_per_case=40_000,
        max_output_tokens_per_case=8_000,
    )
    assert manifest["planned_live_execution"] is False
    assert manifest["network_io_performed"] is False
    assert manifest["physical_authority_granted"] is False
    assert manifest["estimated_text_token_envelope_usd"] == 1.6


def _planner_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)
    env.pop("ANTHROPIC_API_KEY", None)
    return env


def test_planner_cli_needs_no_provider_credentials() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/plan_frontier_operator_experiment.py",
            "--model",
            "gpt-6-astra",
            "--case-id",
            "spi-flash-adapter-baseline",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=_planner_env(),
    )
    payload = json.loads(completed.stdout)
    assert payload["case_count"] == 1
    assert payload["provider_credentials_read"] is False
    assert payload["network_io_performed"] is False
    assert payload["live_execution_performed"] is False
    assert payload["armed_for_live_runner"] is False


def test_planner_cli_cannot_arm_without_budget_and_acknowledgement() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/plan_frontier_operator_experiment.py",
            "--model",
            "claude-fable-5",
            "--case-id",
            "spi-flash-adapter-baseline",
            "--arm-live",
        ],
        capture_output=True,
        text=True,
        env=_planner_env(),
    )
    assert completed.returncode != 0
    assert "max_usd" in completed.stderr or "max_usd" in completed.stdout
