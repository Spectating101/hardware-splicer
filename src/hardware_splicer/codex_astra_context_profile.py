"""Offline context-material profiling for durable Codex/Astra JSONL traces.

The Codex usage report is authoritative for billed/reported tokens. This module only
attributes serialized prompt material by bytes and a clearly labelled characters/4 token
estimate; it never presents that estimate as provider token accounting.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "hardware_splicer.codex_astra_context_profile.v1"


def _json_bytes(value: Any) -> int:
    return len(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    )


def _text_char_count(value: Any) -> int:
    if isinstance(value, str):
        return len(value)
    if isinstance(value, Mapping):
        return sum(_text_char_count(child) for child in value.values())
    if isinstance(value, list):
        return sum(_text_char_count(child) for child in value)
    return 0


def _estimated_tokens(characters: int) -> int:
    return (characters + 3) // 4


def _operation_id(item: Mapping[str, Any]) -> str | None:
    arguments = item.get("arguments")
    if not isinstance(arguments, Mapping):
        return None
    value = arguments.get("operation_id")
    return str(value) if value else None


def profile_codex_astra_context(
    events: Iterable[Mapping[str, Any]],
    *,
    static_artifact_sizes: Mapping[str, int] | None = None,
    target_input_tokens: int = 200_000,
) -> dict[str, Any]:
    """Profile durable trace material without contacting Codex or a model provider."""

    calls: list[dict[str, Any]] = []
    usage: dict[str, Any] = {}
    for event in events:
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), Mapping):
            usage = dict(event["usage"])
        item = event.get("item")
        if event.get("type") != "item.completed" or not isinstance(item, Mapping):
            continue
        if item.get("type") != "mcp_tool_call":
            continue
        arguments = item.get("arguments") if isinstance(item.get("arguments"), Mapping) else {}
        result = item.get("result")
        error = item.get("error")
        result_bytes = _json_bytes(result)
        text_characters = _text_char_count(result)
        calls.append(
            {
                "sequence": len(calls) + 1,
                "server": item.get("server"),
                "tool": item.get("tool"),
                "backend_operation_id": _operation_id(item),
                "status": item.get("status"),
                "argument_bytes": _json_bytes(arguments),
                "result_bytes": result_bytes,
                "result_text_characters": text_characters,
                "estimated_result_tokens_characters_div_4": _estimated_tokens(
                    text_characters
                ),
                "error_present": error is not None,
                "call_signature": json.dumps(
                    [item.get("tool"), arguments],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            }
        )

    signature_counts = Counter(row["call_signature"] for row in calls)
    duplicate_groups = [
        {
            "tool": next(
                row["tool"] for row in calls if row["call_signature"] == signature
            ),
            "backend_operation_id": next(
                row["backend_operation_id"]
                for row in calls
                if row["call_signature"] == signature
            ),
            "count": count,
            "avoidable_repeat_count": count - 1,
        }
        for signature, count in sorted(signature_counts.items())
        if count > 1
    ]
    total_text_characters = sum(row["result_text_characters"] for row in calls)
    total_result_bytes = sum(row["result_bytes"] for row in calls)
    discovery_calls = [
        row
        for row in calls
        if row["tool"] in {"hs_backend_list_operations", "hs_backend_describe_operation"}
    ]
    largest = sorted(calls, key=lambda row: row["result_bytes"], reverse=True)[:10]
    static_rows = [
        {"artifact": name, "size_bytes": int(size)}
        for name, size in sorted((static_artifact_sizes or {}).items())
    ]
    reported_input = int(usage.get("input_tokens") or 0)
    recommendations: list[dict[str, Any]] = []
    list_count = sum(row["tool"] == "hs_backend_list_operations" for row in calls)
    if list_count > 1:
        recommendations.append(
            {
                "priority": 1,
                "finding": "operation catalog discovery was repeated",
                "evidence": {"hs_backend_list_operations_calls": list_count},
                "action": "cache one filtered operation catalog per run and reuse it",
            }
        )
    if discovery_calls:
        recommendations.append(
            {
                "priority": 2,
                "finding": "operation discovery contributes retained tool transcript material",
                "evidence": {
                    "discovery_call_count": len(discovery_calls),
                    "result_bytes": sum(row["result_bytes"] for row in discovery_calls),
                },
                "action": "offer a compact task-scoped operation manifest with request/response field summaries",
            }
        )
    if largest and largest[0]["result_bytes"] >= 20_000:
        recommendations.append(
            {
                "priority": 3,
                "finding": "at least one tool response is large enough to dominate retained transcript context",
                "evidence": {
                    "tool": largest[0]["tool"],
                    "backend_operation_id": largest[0]["backend_operation_id"],
                    "result_bytes": largest[0]["result_bytes"],
                },
                "action": "add a bounded assurance/task projection instead of returning the full project surface",
            }
        )
    if reported_input > target_input_tokens:
        recommendations.append(
            {
                "priority": 4,
                "finding": "reported input exceeds the experiment target",
                "evidence": {
                    "reported_input_tokens": reported_input,
                    "target_input_tokens": target_input_tokens,
                },
                "action": "require an offline profile comparison before the next paid live run",
            }
        )

    clean_calls = [
        {key: value for key, value in row.items() if key != "call_signature"}
        for row in calls
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "profiled",
        "measurement_boundary": {
            "reported_usage_is_provider_authoritative": True,
            "material_estimates_are_not_provider_token_counts": True,
            "token_estimate_method": "ceil(result text characters / 4)",
            "exact_per_turn_token_attribution_available": False,
        },
        "reported_usage": usage,
        "target_input_tokens": target_input_tokens,
        "mcp_call_count": len(calls),
        "discovery_call_count": len(discovery_calls),
        "duplicate_call_groups": duplicate_groups,
        "material_totals": {
            "mcp_result_bytes": total_result_bytes,
            "mcp_result_text_characters": total_text_characters,
            "estimated_raw_mcp_result_tokens_characters_div_4": _estimated_tokens(
                total_text_characters
            ),
            "static_artifact_bytes": sum(row["size_bytes"] for row in static_rows),
        },
        "static_artifacts": static_rows,
        "largest_mcp_results": [
            {key: value for key, value in row.items() if key != "call_signature"}
            for row in largest
        ],
        "calls": clean_calls,
        "recommendations": sorted(recommendations, key=lambda row: row["priority"]),
        "authority_effect": "none",
        "model_inference_performed": False,
    }


def profile_codex_astra_trace(
    trace_path: str | Path,
    *,
    static_artifact_paths: Iterable[str | Path] = (),
    target_input_tokens: int = 200_000,
) -> dict[str, Any]:
    path = Path(trace_path).expanduser().resolve()
    events = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    static_sizes = {
        Path(value).name: Path(value).expanduser().resolve().stat().st_size
        for value in static_artifact_paths
    }
    return profile_codex_astra_context(
        events,
        static_artifact_sizes=static_sizes,
        target_input_tokens=target_input_tokens,
    )
