from __future__ import annotations

from hardware_splicer.ai_project_decision import (
    review_proposed_action,
    select_next_proposed_action,
)


def session():
    return {
        "mission": "Produce a verifiable SPI flash adapter design proposal.",
        "constraints": {"voltage": "3.3V"},
        "requirements": [{"id": "r1", "statement": "Verify pin mapping", "authority": "proposed"}],
        "open_questions": ["Is the donor board pinout verified?"],
        "architecture_candidates": [],
        "summary": "Pinout evidence is incomplete.",
        "actions": [
            {
                "action_id": "action-evidence",
                "action_type": "identify_missing_evidence",
                "title": "Verify donor pinout",
                "rationale": "Pin mapping is not yet evidence-backed.",
                "source_ids": ["source-1"],
                "status": "proposed",
                "authority": "proposed",
                "automatic_execution": False,
            },
            {
                "action_id": "action-package",
                "action_type": "prepare_engineering_package",
                "title": "Prepare package",
                "rationale": "Package current design.",
                "source_ids": [],
                "status": "proposed",
                "authority": "proposed",
                "automatic_execution": False,
            },
        ],
        "automatic_execution": False,
        "physical_authority_unchanged": True,
    }


def transport_for(choice, confidence=0.95):
    def transport(payload, *, api_key, endpoint, timeout):
        assert api_key == "test-key"
        authority = payload["state"]["authority"]
        assert authority["automatic_execution"] is False
        assert authority["power_on_authorized"] is False
        assert authority["release_authorized"] is False
        return {
            "answers": {
                "decision": {
                    "choice": choice,
                    "confidence": confidence,
                    "probabilities": {choice: confidence},
                }
            }
        }
    return transport


def test_selects_evidence_action_without_executing_it():
    result = select_next_proposed_action(
        session(),
        api_key="test-key",
        transport=transport_for("action-evidence"),
    )
    assert result.status == "selected_proposal"
    assert result.choice == "action-evidence"
    assert result.selected_action["action_type"] == "identify_missing_evidence"
    assert result.selected_action["automatic_execution"] is False
    assert result.selected_action["authority"] == "proposed"


def test_low_confidence_requires_system2_review():
    result = select_next_proposed_action(
        session(),
        api_key="test-key",
        min_confidence=0.85,
        transport=transport_for("action-package", confidence=0.55),
    )
    assert result.status == "needs_supervisor"
    assert result.reason == "low_confidence"
    assert result.selected_action is None


def test_missing_key_fails_closed():
    result = select_next_proposed_action(session(), api_key="")
    assert result.status == "needs_supervisor"
    assert result.choice == "escalate"
    assert result.selected_action is None


def test_review_can_request_revision_but_not_change_authority():
    action = session()["actions"][0]
    result = review_proposed_action(
        session(),
        action,
        api_key="test-key",
        transport=transport_for("revise"),
    )
    assert result.status == "reviewed"
    assert result.choice == "revise"
    assert action["authority"] == "proposed"
    assert action["automatic_execution"] is False
