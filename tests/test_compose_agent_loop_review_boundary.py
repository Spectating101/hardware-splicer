from __future__ import annotations

from pathlib import Path

import pytest

from hardware_splicer.compose_agent_loop import compose_agent_loop


def test_semantic_review_stops_retries_and_package_finalization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatch_calls: list[dict] = []

    def review_result(**kwargs):
        dispatch_calls.append(dict(kwargs))
        return {
            "ok": False,
            "mode": "llm_first",
            "compose_mode": "semantic_module_proposal",
            "out_dir": str(tmp_path),
            "module_ids": ["candidate-a", "candidate-b"],
            "design_quality": {},
            "requires_human_review": True,
            "semantic_intent": {"goal_summary": "typed intent"},
            "semantic_selection": {"selected_module_ids": ["candidate-a", "candidate-b"]},
            "authority_effect": "none",
            "automatic_execution": False,
            "error": "semantic_module_review_required",
        }

    monkeypatch.setattr(
        "hardware_splicer.compose_agent_loop.compose_dispatch",
        review_result,
    )

    def fail_if_finalized(*args, **kwargs):
        raise AssertionError("review-only semantic proposal reached package finalization")

    monkeypatch.setattr(
        "hardware_splicer.sdk.finalize_compose_job_result",
        fail_if_finalized,
    )

    result = compose_agent_loop(
        phrase="novel hardware goal",
        allow_llm_first=True,
        out_dir=tmp_path,
        finalize_package=True,
        max_manual_retries=2,
    )

    assert len(dispatch_calls) == 1
    assert result["requires_human_review"] is True
    assert result["agent_loop"]["review_blocked"] is True
    assert result["agent_loop"]["resolved"] is False
    assert result["agent_loop"]["final_kicad_drc_errors"] is None
    assert result["package_finalization"] == {
        "status": "blocked",
        "reason": "semantic_module_review_required",
        "requires_human_review": True,
        "authority_effect": "none",
    }
    assert "project_package" not in result
