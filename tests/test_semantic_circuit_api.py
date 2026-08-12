from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.semantic_circuit_api import create_semantic_circuit_router


def _client() -> TestClient:
    def fake_llm(prompt: str, **kwargs: object) -> dict:
        assert "Available bounded planners" in prompt
        return {
            "ok": True,
            "provider": "semantic-test",
            "model": "deterministic-fixture",
            "content": json.dumps(
                {
                    "selected_planner": "h_bridge",
                    "rationale": "The structured load requires controlled current in either direction.",
                    "unresolved_questions": [],
                    "assumptions": [],
                    "authority_effect": "none",
                    "automatic_execution": False,
                }
            ),
        }

    app = FastAPI()
    app.include_router(create_semantic_circuit_router(llm_callable=fake_llm))
    return TestClient(app)


def test_semantic_planner_registry_is_zero_authority() -> None:
    body = _client().get("/v1/engineering/circuit/semantic-planners").json()

    assert "h_bridge" in body["planners"]
    assert "motor_driver" in body["planners"]
    assert body["selection_authority_effect"] == "none"
    assert body["automatic_execution"] is False
    assert body["compile_authorized"] is False


def test_semantic_plan_returns_bounded_candidate_without_execution_authority() -> None:
    response = _client().post(
        "/v1/engineering/circuit/semantic-plan",
        json={
            "intent": {
                "goal": "The same 6 V load must rotate in either direction under 3.3 V logic control.",
                "supply_rails": [
                    {"name": "motor_supply", "voltage_v": 6.0, "max_current_a": 2.0}
                ],
                "load_requirements": [
                    {
                        "name": "drive_load",
                        "type": "dc_motor",
                        "voltage_v": 6.0,
                        "current_a": 0.8,
                        "direction_control": True,
                    }
                ],
                "signal_requirements": [
                    {"name": "direction", "type": "digital", "voltage_v": 3.3},
                    {"name": "speed", "type": "pwm", "voltage_v": 3.3},
                ],
            }
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["selected_planner"] == "h_bridge"
    assert body["requires_human_review"] is True
    assert body["authority_effect"] == "none"
    assert body["automatic_execution"] is False
    assert body["compile_authorized"] is False
    assert body["fabrication_authorized"] is False
    assert body["power_on_authorized"] is False
    assert body["trace"]["candidate"] is not None
    assert body["trace"]["candidate"]["metadata"]["dispatch"]["selection_source"] == "semantic_typed_selection"
