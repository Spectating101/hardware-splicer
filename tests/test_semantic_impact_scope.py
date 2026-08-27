from __future__ import annotations

import json

import pytest

from hardware_splicer.semantic_impact_scope import (
    SemanticImpactScopeError,
    impact_scope_prompt,
    interpret_impact_scope,
    parse_impact_scope_proposal,
)


def test_semantic_impact_scope_accepts_only_bounded_domains() -> None:
    proposal = parse_impact_scope_proposal(
        {
            "status": "model_proposed",
            "domains": ["electrical", "firmware", "electrical"],
            "reasoning": "The declared change crosses the electrical/firmware interface.",
            "confidence": 0.7,
            "unresolved_questions": [],
            "source": "model_proposed",
            "authority_effect": "none",
            "automatic_execution": False,
        }
    )
    assert proposal.domains == ["electrical", "firmware"]
    assert proposal.authority_effect == "none"
    assert proposal.automatic_execution is False


def test_semantic_impact_scope_rejects_invented_domain_and_authority() -> None:
    with pytest.raises(SemanticImpactScopeError):
        parse_impact_scope_proposal(
            {
                "domains": ["magic_fixture_domain"],
                "authority_effect": "release",
                "automatic_execution": True,
            }
        )


def test_impact_scope_prompt_contains_vocabulary_not_keyword_answer_table() -> None:
    prompt = impact_scope_prompt(
        ["The interface stops responding after the candidate revision."],
        mode="modify",
        topology_summary={"robot_genre": "generic_mechatronics"},
        subsystem_summary=[{"subsystem_id": "electrical-system", "domain": "electrical"}],
    )
    assert "Allowed domains" in prompt
    assert "magic_fixture" not in prompt
    assert "brownout → electrical" not in prompt
    assert "battery -> electrical" not in prompt
    assert "Do not choose component, subsystem" in prompt


def test_interpreter_preserves_unresolved_model_response_without_guessing() -> None:
    def fake_llm(prompt: str, **kwargs: object) -> dict:
        return {
            "ok": True,
            "provider": "semantic-test",
            "model": "deterministic",
            "content": json.dumps(
                {
                    "status": "unresolved",
                    "domains": [],
                    "reasoning": "The failure statement does not establish which discipline owns the defect.",
                    "confidence": 0.0,
                    "unresolved_questions": ["Which measured interface first deviates from baseline?"],
                    "source": "model_proposed",
                    "authority_effect": "none",
                    "automatic_execution": False,
                }
            ),
        }

    proposal = interpret_impact_scope(
        ["The system behaves differently after the revision."],
        mode="modify",
        llm_callable=fake_llm,
    )
    assert proposal.status == "unresolved"
    assert proposal.domains == []
    assert proposal.unresolved_questions == ["Which measured interface first deviates from baseline?"]
