from __future__ import annotations

import json

import pytest

from hardware_splicer.semantic_robot_genre import (
    SemanticRobotGenreError,
    interpret_robot_genre,
    parse_robot_genre_proposal,
    robot_genre_prompt,
    unresolved_robot_genre_proposal,
)


def test_robot_genre_prompt_exposes_bounded_vocabulary_without_phrase_rules() -> None:
    prompt = robot_genre_prompt(
        "A mobile platform carries an articulated tool assembly.",
        [{"name": "drive actuator", "type": "motor", "quantity": 2}],
        {"degrees_of_freedom": 6},
    )

    assert '"mobile_manipulator"' in prompt
    assert '"generic_mechatronics"' in prompt
    assert "robot dog" not in prompt
    assert "rover, wheels" not in prompt.lower()
    assert "quadcopter" not in prompt.lower()


def test_model_proposal_is_validated_against_allowed_genres() -> None:
    def fake_llm(prompt: str, **kwargs: object) -> dict:
        return {
            "ok": True,
            "content": json.dumps(
                {
                    "genre": "mobile_manipulator",
                    "reasoning": "The declared machine combines mobile translation and an articulated tool chain.",
                    "confidence": 0.82,
                    "unresolved_questions": ["Tool joint limits are not yet evidenced."],
                    "authority_effect": "none",
                    "automatic_execution": False,
                }
            ),
        }

    proposal = interpret_robot_genre(
        "Machine combines a mobile base and articulated tool.",
        parts=[],
        constraints={"degrees_of_freedom": 6},
        llm_callable=fake_llm,
    )

    assert proposal.genre == "mobile_manipulator"
    assert proposal.source == "model_proposed"
    assert proposal.authority_effect == "none"
    assert proposal.automatic_execution is False


def test_unknown_genre_is_rejected() -> None:
    with pytest.raises(SemanticRobotGenreError):
        parse_robot_genre_proposal(
            {
                "genre": "secret_demo_robot",
                "reasoning": "fixture-specific answer",
                "confidence": 1.0,
                "authority_effect": "none",
                "automatic_execution": False,
            }
        )


def test_proposal_cannot_elevate_authority_or_execute() -> None:
    with pytest.raises(SemanticRobotGenreError):
        parse_robot_genre_proposal(
            {
                "genre": "rover",
                "authority_effect": "motion_authorized",
                "automatic_execution": False,
            }
        )

    with pytest.raises(SemanticRobotGenreError):
        parse_robot_genre_proposal(
            {
                "genre": "rover",
                "authority_effect": "none",
                "automatic_execution": True,
            }
        )


def test_unresolved_genre_stays_generic_and_fail_closed() -> None:
    proposal = unresolved_robot_genre_proposal("machine class is ambiguous")

    assert proposal.status == "unresolved"
    assert proposal.genre == "generic_mechatronics"
    assert proposal.source == "unresolved"
    assert proposal.confidence == 0.0
    assert proposal.unresolved_questions == ["machine class is ambiguous"]
    assert proposal.authority_effect == "none"
    assert proposal.automatic_execution is False
