from __future__ import annotations

import json

import pytest

from hardware_splicer.dual_agent_cleanroom import (
    CleanroomContractError,
    run_embedded_operator_turn,
)


def _proposal_response(*, source_id: str = "source-1") -> dict:
    return {
        "summary": "Inspect the evidence before selecting an engineering action.",
        "requirements": [
            {
                "id": "req-1",
                "statement": "Respect the observed interface evidence.",
                "source_ids": [source_id],
                "assumptions": [],
            }
        ],
        "open_questions": ["What evidence is still missing before verification?"],
        "architecture_candidates": [
            {
                "id": "candidate-1",
                "title": "Evidence-bounded candidate",
                "summary": "Keep unresolved electrical properties blocked.",
                "tradeoffs": [],
                "assumptions": [],
                "source_ids": [source_id],
            }
        ],
        "actions": [
            {
                "action_type": "identify_missing_evidence",
                "title": "Resolve the remaining interface evidence",
                "rationale": "The product-visible source does not justify guessing missing values.",
                "inputs": {},
                "source_ids": [source_id],
            }
        ],
    }


def _fake_llm(content: dict):
    def call(prompt, **kwargs):
        assert "source_code" not in prompt
        assert "golden_answer" not in prompt
        return {
            "ok": True,
            "content": json.dumps(content),
            "provider": "cleanroom-test",
            "model": "deterministic-fixture",
            "usage": {},
        }

    return call


def _snapshot() -> dict:
    return {
        "name": "cleanroom-project",
        "currentStage": "evidence",
        "engineeringSources": [
            {
                "source_id": "source-1",
                "source_type": "engineering_source_json",
                "content_hash": "abc123",
                "authority_ceiling": "declared",
                "metadata": {"label": "operator-visible interface evidence"},
            }
        ],
        "engineeringBlockers": ["interface voltage remains unresolved"],
    }


def test_embedded_operator_turn_is_source_blind_and_zero_authority() -> None:
    result = run_embedded_operator_turn(
        "project-1",
        3,
        _snapshot(),
        mission="Determine the next defensible engineering action.",
        llm_callable=_fake_llm(_proposal_response()),
    )

    assert result["role"] == "embedded_operator"
    assert result["isolation"]["repository_source_visible"] is False
    assert result["isolation"]["golden_answer_visible"] is False
    assert result["authority_effect"] == "none"
    assert result["power_on_authorized"] is False
    action = result["operator_session"]["actions"][0]
    assert action["status"] == "proposed"
    assert action["source_ids"] == ["source-1"]


def test_embedded_operator_rejects_outer_engineer_or_golden_context() -> None:
    snapshot = _snapshot()
    snapshot["outer_agent_analysis"] = {"expected_architecture": "secret-answer"}

    with pytest.raises(CleanroomContractError, match="forbidden outer-only field"):
        run_embedded_operator_turn(
            "project-1",
            3,
            snapshot,
            mission="Try the project.",
            llm_callable=_fake_llm(_proposal_response()),
        )


def test_embedded_operator_rejects_invented_evidence_identity() -> None:
    with pytest.raises(CleanroomContractError, match="invented product evidence identities"):
        run_embedded_operator_turn(
            "project-1",
            3,
            _snapshot(),
            mission="Try the project.",
            llm_callable=_fake_llm(_proposal_response(source_id="source-does-not-exist")),
        )
