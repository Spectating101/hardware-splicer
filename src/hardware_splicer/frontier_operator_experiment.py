"""Provider-neutral frontier-model experiment support for Hardware-Splicer.

This module deliberately performs no network I/O. It constructs provider request
templates, estimates text-token cost envelopes, validates explicit paid-API policy,
and normalizes provider MCP traces into the existing external truth-audit shape.

For the current experiment, GPT-6 Astra is intended to run through ChatGPT-authenticated
Codex allowance. The OpenAI API template is compatibility/protocol staging only. Fable
remains a dormant adapter with no planned live run.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

HS_MCP_TOOLS = (
    "hs_backend_status",
    "hs_backend_list_operations",
    "hs_backend_describe_operation",
    "hs_backend_call",
)

LIVE_CONFIRMATION = "I_ACCEPT_PROVIDER_CHARGES"


@dataclass(frozen=True)
class FrontierModelSpec:
    provider: str
    model: str
    input_usd_per_mtok: float
    output_usd_per_mtok: float
    default_effort: str
    remote_mcp: bool
    image_input: bool
    experiment_live_path: str
    notes: str = ""


MODEL_SPECS: dict[str, FrontierModelSpec] = {
    "gpt-6-astra": FrontierModelSpec(
        provider="openai",
        model="gpt-6-astra",
        input_usd_per_mtok=10.0,
        output_usd_per_mtok=50.0,
        default_effort="low",
        remote_mcp=True,
        image_input=True,
        experiment_live_path="codex_chatgpt_allowance",
        notes=(
            "Sole planned live frontier operator. Run through ChatGPT-authenticated "
            "Codex; do not silently fall back to API billing."
        ),
    ),
    "claude-fable-5": FrontierModelSpec(
        provider="anthropic",
        model="claude-fable-5",
        input_usd_per_mtok=10.0,
        output_usd_per_mtok=50.0,
        default_effort="low",
        remote_mcp=True,
        image_input=True,
        experiment_live_path="disabled_no_budget",
        notes=(
            "Dormant compatibility adapter only. No planned live Anthropic run or "
            "credential requirement."
        ),
    ),
}


def get_model_spec(model: str) -> FrontierModelSpec:
    try:
        return MODEL_SPECS[model]
    except KeyError as exc:
        raise ValueError(f"unsupported frontier model: {model!r}") from exc


def estimate_text_cost_usd(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Conservative uncached API text-token estimate for one provider request.

    This estimate is a tripwire for accidental paid API use. It does not describe
    ChatGPT/Codex allowance consumption.
    """

    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("token counts must be non-negative")
    spec = get_model_spec(model)
    total = (
        input_tokens * spec.input_usd_per_mtok
        + output_tokens * spec.output_usd_per_mtok
    ) / 1_000_000
    return round(total, 6)


def estimate_experiment_cost_usd(
    *,
    model: str,
    case_count: int,
    estimated_input_tokens_per_case: int,
    max_output_tokens_per_case: int,
) -> float:
    if case_count < 1:
        raise ValueError("case_count must be positive")
    per_case = estimate_text_cost_usd(
        model=model,
        input_tokens=estimated_input_tokens_per_case,
        output_tokens=max_output_tokens_per_case,
    )
    return round(per_case * case_count, 6)


def validate_live_policy(
    *,
    model: str,
    case_count: int,
    estimated_input_tokens_per_case: int,
    max_output_tokens_per_case: int,
    max_usd: float | None,
    confirmation: str | None,
    allow_multi_case: bool,
) -> dict[str, Any]:
    """Fail closed before any caller is allowed to perform paid provider API I/O."""

    spec = get_model_spec(model)
    if spec.experiment_live_path == "disabled_no_budget":
        raise ValueError(f"live execution is disabled for {model}: no experiment budget")
    if case_count < 1:
        raise ValueError("case_count must be positive")
    if max_usd is None or not math.isfinite(max_usd) or max_usd <= 0:
        raise ValueError("live execution requires a positive finite max_usd")
    if confirmation != LIVE_CONFIRMATION:
        raise ValueError(
            f"live execution requires confirmation={LIVE_CONFIRMATION!r}"
        )
    if case_count > 1 and not allow_multi_case:
        raise ValueError(
            "multi-case live execution is disabled unless allow_multi_case=True"
        )

    estimated = estimate_experiment_cost_usd(
        model=model,
        case_count=case_count,
        estimated_input_tokens_per_case=estimated_input_tokens_per_case,
        max_output_tokens_per_case=max_output_tokens_per_case,
    )
    if estimated > max_usd:
        raise ValueError(
            f"estimated API text-token envelope ${estimated:.4f} exceeds max_usd ${max_usd:.4f}"
        )
    return {
        "model": model,
        "case_count": case_count,
        "experiment_live_path": spec.experiment_live_path,
        "estimated_api_text_token_envelope_usd": estimated,
        "max_usd": max_usd,
        "confirmation_matched": True,
        "multi_case_explicitly_allowed": case_count == 1 or allow_multi_case,
        "warning": (
            "This policy covers paid API execution only. The intended Astra experiment "
            "uses ChatGPT-authenticated Codex allowance and must not auto-fallback here."
        ),
    }


def _openai_mcp_tool(*, server_url: str) -> dict[str, Any]:
    return {
        "type": "mcp",
        "server_label": "hardware_splicer",
        "server_description": (
            "Canonical Hardware-Splicer backend gateway. Engineering truth and "
            "physical authority remain in the backend."
        ),
        "server_url": server_url,
        "allowed_tools": list(HS_MCP_TOOLS),
        "require_approval": "never",
    }


def build_openai_request_template(
    *,
    model: str,
    instructions: str,
    input_text: str,
    server_url: str = "${HS_MCP_SERVER_URL}",
    max_output_tokens: int = 8000,
    effort: str | None = None,
) -> dict[str, Any]:
    spec = get_model_spec(model)
    if spec.provider != "openai":
        raise ValueError(f"{model} is not an OpenAI model")
    if max_output_tokens < 1:
        raise ValueError("max_output_tokens must be positive")
    return {
        "model": spec.model,
        "instructions": instructions,
        "input": input_text,
        "reasoning": {"effort": effort or spec.default_effort},
        "tools": [_openai_mcp_tool(server_url=server_url)],
        "tool_choice": "required",
        "max_output_tokens": max_output_tokens,
        "store": False,
    }


def build_anthropic_request_template(
    *,
    model: str,
    instructions: str,
    input_text: str,
    server_url: str = "${HS_MCP_SERVER_URL}",
    max_output_tokens: int = 8000,
    effort: str | None = None,
) -> dict[str, Any]:
    spec = get_model_spec(model)
    if spec.provider != "anthropic":
        raise ValueError(f"{model} is not an Anthropic model")
    if max_output_tokens < 1:
        raise ValueError("max_output_tokens must be positive")
    return {
        "model": spec.model,
        "max_tokens": max_output_tokens,
        "system": instructions,
        "output_config": {"effort": effort or spec.default_effort},
        "messages": [{"role": "user", "content": input_text}],
        "mcp_servers": [
            {
                "type": "url",
                "url": server_url,
                "name": "hardware-splicer",
            }
        ],
        "tools": [
            {
                "type": "mcp_toolset",
                "mcp_server_name": "hardware-splicer",
                "default_config": {"enabled": False},
                "configs": {
                    name: {"enabled": True}
                    for name in HS_MCP_TOOLS
                },
            }
        ],
        "betas": ["mcp-client-2025-11-20"],
    }


def build_provider_request_template(
    *,
    model: str,
    instructions: str,
    input_text: str,
    server_url: str = "${HS_MCP_SERVER_URL}",
    max_output_tokens: int = 8000,
    effort: str | None = None,
) -> dict[str, Any]:
    spec = get_model_spec(model)
    builder = (
        build_openai_request_template
        if spec.provider == "openai"
        else build_anthropic_request_template
    )
    return builder(
        model=model,
        instructions=instructions,
        input_text=input_text,
        server_url=server_url,
        max_output_tokens=max_output_tokens,
        effort=effort,
    )


def _anthropic_content_blocks(response: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    content = response.get("content")
    if not isinstance(content, Sequence) or isinstance(content, (str, bytes, bytearray)):
        return []
    return [row for row in content if isinstance(row, Mapping)]


def normalize_anthropic_mcp_response(
    response: Mapping[str, Any],
) -> dict[str, Any]:
    """Normalize dormant Anthropic MCP blocks into the existing trace-audit shape."""

    blocks = _anthropic_content_blocks(response)
    uses = {
        str(row.get("id")): row
        for row in blocks
        if row.get("type") == "mcp_tool_use" and row.get("id")
    }
    results = {
        str(row.get("tool_use_id")): row
        for row in blocks
        if row.get("type") == "mcp_tool_result" and row.get("tool_use_id")
    }

    calls: list[dict[str, Any]] = []
    for tool_use_id, row in uses.items():
        result = results.get(tool_use_id)
        is_error = result is None or result.get("is_error") is True
        calls.append(
            {
                "type": "mcp_call",
                "name": row.get("name"),
                "arguments": row.get("input") if isinstance(row.get("input"), Mapping) else {},
                "status": "failed" if is_error else "completed",
                "error": (
                    "missing MCP tool result"
                    if result is None
                    else result.get("content")
                    if is_error
                    else None
                ),
                "output": None if result is None else result.get("content"),
            }
        )

    stop_reason = response.get("stop_reason")
    response_status = "completed" if stop_reason not in {None, "max_tokens"} else "incomplete"
    if response.get("error"):
        response_status = "failed"

    return {
        "id": response.get("id"),
        "model": response.get("model"),
        "status": response_status,
        "output": calls,
        "usage": response.get("usage"),
        "provider": "anthropic",
        "provider_stop_reason": stop_reason,
    }


def planning_manifest(
    *,
    model: str,
    case_ids: Sequence[str],
    estimated_input_tokens_per_case: int,
    max_output_tokens_per_case: int,
) -> dict[str, Any]:
    spec = get_model_spec(model)
    case_list = list(case_ids)
    if not case_list:
        raise ValueError("at least one case id is required")
    return {
        "schema": "hardware_splicer.frontier_operator_plan.v2",
        "provider": spec.provider,
        "model": spec.model,
        "experiment_live_path": spec.experiment_live_path,
        "case_ids": case_list,
        "case_count": len(case_list),
        "estimated_input_tokens_per_case": estimated_input_tokens_per_case,
        "max_output_tokens_per_case": max_output_tokens_per_case,
        "estimated_api_text_token_envelope_usd": estimate_experiment_cost_usd(
            model=model,
            case_count=len(case_list),
            estimated_input_tokens_per_case=estimated_input_tokens_per_case,
            max_output_tokens_per_case=max_output_tokens_per_case,
        ),
        "remote_mcp": spec.remote_mcp,
        "image_input": spec.image_input,
        "planned_live_execution": False,
        "network_io_performed": False,
        "physical_authority_granted": False,
        "claim_boundary": (
            "Planning and adapter construction are not model competence, engineering "
            "correctness, physical correctness, or physical authority."
        ),
    }
