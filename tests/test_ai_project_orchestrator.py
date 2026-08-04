from __future__ import annotations

import json

import pytest

from hardware_splicer.ai_project_orchestrator import (
    InvalidAIProjectResponse,
    build_ai_project_context,
    parse_ai_project_response,
    run_ai_project_orchestrator,
)


def _valid_response() -> dict:
    return {
        "summary": "A differential-drive candidate is feasible but power evidence is missing.",
        "requirements": [
            {
                "id": "runtime",
                "statement": "The rover should operate for 90 minutes.",
                "source_ids": ["source-manual"],
                "assumptions": ["Nominal indoor duty cycle"],
            }
        ],
        "open_questions": ["What is the measured motor stall current?"],
        "architecture_candidates": [
            {
                "id": "candidate-a",
                "title": "Split compute and motor control",
                "summary": "Use an SBC for navigation and an MCU for bounded motor control.",
                "tradeoffs": ["More interfaces", "Clearer fault containment"],
                "assumptions": ["UART is available"],
                "source_ids": ["source-model"],
            }
        ],
        "actions": [
            {
                "action_type": "identify_missing_evidence",
                "title": "Request motor current evidence",
                "rationale": "The power budget cannot close without measured or declared current.",
                "inputs": {"measurement": "motor_stall_current"},
                "source_ids": ["source-manual"],
            },
            {
                "action_type": "generate_netlist_candidate",
                "title": "Generate the candidate power netlist",
                "rationale": "A typed candidate is needed before ERC can run.",
                "inputs": {"candidate_id": "candidate-a"},
                "source_ids": ["source-model"],
            },
        ],
    }


def test_context_omits_raw_content_and_closes_authority() -> None:
    snapshot = {
        "engineeringSources": [
            {
                "source_id": "source-manual",
                "source_type": "document",
                "content_hash": "sha256:abc",
                "content_base64": "SECRET-BYTES",
                "metadata": {
                    "content": "RAW MANUAL TEXT",
                    "power_on_authorized": True,
                    "label": "motor manual",
                },
            }
        ],
        "engineeringSourceParserRuns": [
            {
                "source_id": "source-manual",
                "status": "parsed",
                "output": {
                    "summary": "Motor driver limits",
                    "raw_bytes": "DO-NOT-INCLUDE",
                },
            }
        ],
        "release_authorized": True,
    }

    context = build_ai_project_context(
        "rover",
        7,
        snapshot,
        mission="Build an indoor rover",
    )
    encoded = json.dumps(context)

    assert "SECRET-BYTES" not in encoded
    assert "RAW MANUAL TEXT" not in encoded
    assert "DO-NOT-INCLUDE" not in encoded
    assert context["registered_sources"][0]["metadata"]["power_on_authorized"] is False
    assert context["context_policy"]["automatic_execution"] is False
    assert context["context_policy"]["release_authorized"] is False


def test_run_returns_revision_pinned_proposals_only() -> None:
    calls: list[dict] = []

    def fake_llm(prompt: str, **kwargs: object) -> dict:
        calls.append({"prompt": prompt, **kwargs})
        return {
            "ok": True,
            "provider": "test-provider",
            "model": "test-model",
            "content": json.dumps(_valid_response()),
            "usage": {"total_tokens": 123},
        }

    session = run_ai_project_orchestrator(
        "rover",
        4,
        {"engineeringSources": []},
        mission="Design an indoor inspection rover",
        llm_callable=fake_llm,
    )

    assert len(calls) == 1
    assert calls[0]["json_mode"] is True
    assert session["project_revision"] == 4
    assert session["provider"] == "test-provider"
    assert session["actions"][0]["status"] == "proposed"
    assert session["actions"][0]["automatic_execution"] is False
    assert session["actions"][0]["authority_effect"] == "none"
    assert session["architecture_candidates"][0]["authority"] == "proposed"
    assert session["power_on_authorized"] is False
    assert session["motion_authorized"] is False
    assert session["release_authorized"] is False


def test_json_fence_is_accepted_but_unsafe_action_is_rejected() -> None:
    response = _valid_response()
    response["actions"] = [
        {
            "action_type": "power_on",
            "title": "Power the rover",
            "rationale": "Unsafe and outside the action vocabulary.",
            "inputs": {},
            "source_ids": [],
        }
    ]

    with pytest.raises(InvalidAIProjectResponse, match="not allowed"):
        parse_ai_project_response(
            "```json\n" + json.dumps(response) + "\n```",
            session_id="session-1",
            project_id="rover",
            project_revision=1,
            max_actions=8,
        )


def test_authority_elevation_in_nested_inputs_is_rejected() -> None:
    response = _valid_response()
    response["actions"][0]["inputs"] = {"power_on_authorized": True}

    with pytest.raises(InvalidAIProjectResponse, match="physical authority"):
        parse_ai_project_response(
            json.dumps(response),
            session_id="session-1",
            project_id="rover",
            project_revision=1,
            max_actions=8,
        )
