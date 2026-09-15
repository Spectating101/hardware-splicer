from __future__ import annotations

import json

from hardware_splicer.codex_astra_context_profile import (
    profile_codex_astra_context,
    profile_codex_astra_trace,
)


def _call(tool: str, arguments: dict, text: str) -> dict:
    return {
        "type": "item.completed",
        "item": {
            "type": "mcp_tool_call",
            "server": "hardware-splicer-backend",
            "tool": tool,
            "arguments": arguments,
            "status": "completed",
            "error": None,
            "result": {"content": [{"type": "text", "text": text}]},
        },
    }


def test_context_profile_separates_reported_tokens_from_material_estimates() -> None:
    events = [
        _call("hs_backend_list_operations", {"text": "project"}, "x" * 40),
        _call("hs_backend_list_operations", {"text": "project"}, "x" * 40),
        _call(
            "hs_backend_call",
            {"operation_id": "load_project", "arguments": {"project_id": "p"}},
            "y" * 80,
        ),
        {
            "type": "turn.completed",
            "usage": {"input_tokens": 415_000, "cached_input_tokens": 300_000},
        },
    ]

    report = profile_codex_astra_context(
        events, static_artifact_sizes={"CASE_SNAPSHOT.json": 1000}
    )

    assert report["reported_usage"]["input_tokens"] == 415_000
    assert report["material_totals"][
        "estimated_raw_mcp_result_tokens_characters_div_4"
    ] == 43
    assert report["measurement_boundary"][
        "material_estimates_are_not_provider_token_counts"
    ] is True
    assert report["duplicate_call_groups"][0]["avoidable_repeat_count"] == 1
    assert report["calls"][2]["backend_operation_id"] == "load_project"
    assert report["model_inference_performed"] is False


def test_context_profile_reads_jsonl_and_static_artifact_sizes(tmp_path) -> None:
    trace = tmp_path / "trace.jsonl"
    trace.write_text(
        "\n".join(
            json.dumps(row)
            for row in [
                _call("hs_backend_status", {}, "ready"),
                {"type": "turn.completed", "usage": {"input_tokens": 10}},
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    snapshot = tmp_path / "CASE_SNAPSHOT.json"
    snapshot.write_bytes(b"12345")

    report = profile_codex_astra_trace(
        trace, static_artifact_paths=[snapshot], target_input_tokens=20
    )

    assert report["mcp_call_count"] == 1
    assert report["material_totals"]["static_artifact_bytes"] == 5
    assert not any(
        row["finding"] == "reported input exceeds the experiment target"
        for row in report["recommendations"]
    )
