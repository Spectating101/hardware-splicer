from __future__ import annotations

import json

from hardware_splicer.codex_exec_trace import audit_codex_backend_results


def _backend_call(
    *,
    operation_id: str,
    method: str,
    path: str,
    project_id: str = "exp-1",
    query: dict | None = None,
    body_project_id: str | None = None,
) -> dict:
    arguments: dict = {
        "operation_id": operation_id,
        "path_params": {"project_id": project_id},
    }
    if query is not None:
        arguments["query"] = query
    payload = {
        "ok": True,
        "status_code": 200,
        "content_type": "application/json",
        "byte_length": 2,
        "sha256": "0" * 64,
        "headers": {"content-type": "application/json"},
        "body": {"project_id": body_project_id or project_id},
        "operation_id": operation_id,
        "method": method,
        "path": path,
    }
    wrapper = {
        "content": [{"type": "text", "text": json.dumps(payload)}],
        "structured_content": None,
    }
    return {
        "type": "mcp_call",
        "name": "hs_backend_call",
        "arguments": arguments,
        "status": "completed",
        "error": None,
        "output": json.dumps(wrapper),
    }


def _audit(*calls: dict) -> dict:
    return audit_codex_backend_results(
        {"output": list(calls)},
        expected_project_id="exp-1",
    )


def test_canonical_latest_project_load_is_accepted() -> None:
    result = _audit(
        _backend_call(
            operation_id="get_project",
            method="GET",
            path="/v1/projects/exp-1",
        )
    )
    assert result["final_project_readback_pass"] is True
    assert result["successful_project_readback_count"] == 1
    assert result["rejected_project_readback_candidates"] == []


def test_project_related_get_cannot_impersonate_final_readback() -> None:
    result = _audit(
        _backend_call(
            operation_id="list_project_reviews",
            method="GET",
            path="/v1/projects/exp-1/reviews",
        )
    )
    assert result["final_project_readback_pass"] is False
    assert result["successful_project_readback_count"] == 0
    assert result["rejected_project_readback_candidates"][0]["reason"] == (
        "not the canonical project-load path"
    )


def test_historical_revision_load_cannot_certify_latest_state() -> None:
    result = _audit(
        _backend_call(
            operation_id="get_project",
            method="GET",
            path="/v1/projects/exp-1",
            query={"revision": 1},
        )
    )
    assert result["final_project_readback_pass"] is False
    assert "historical revision" in result["rejected_project_readback_candidates"][0]["reason"]


def test_other_query_parameters_do_not_certify_latest_state() -> None:
    result = _audit(
        _backend_call(
            operation_id="get_project",
            method="GET",
            path="/v1/projects/exp-1",
            query={"unexpected": "value"},
        )
    )
    assert result["final_project_readback_pass"] is False
    assert result["rejected_project_readback_candidates"][0]["reason"] == (
        "canonical latest readback must not include query parameters"
    )


def test_readback_must_occur_after_last_successful_mutation() -> None:
    readback = _backend_call(
        operation_id="get_project",
        method="GET",
        path="/v1/projects/exp-1",
    )
    mutation = _backend_call(
        operation_id="save_project",
        method="PUT",
        path="/v1/projects/exp-1/snapshot",
    )
    result = _audit(readback, mutation)
    assert result["successful_project_readback_count"] == 1
    assert result["last_successful_mutation_index"] == 1
    assert result["final_project_readback_pass"] is False


def test_response_must_confirm_expected_project_identity() -> None:
    result = _audit(
        _backend_call(
            operation_id="get_project",
            method="GET",
            path="/v1/projects/exp-1",
            body_project_id="other-project",
        )
    )
    assert result["final_project_readback_pass"] is False
    assert result["successful_project_readback_count"] == 0
