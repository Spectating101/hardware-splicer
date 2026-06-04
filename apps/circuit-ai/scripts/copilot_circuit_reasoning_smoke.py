#!/usr/bin/env python3
"""Live Copilot circuit-reasoning smoke for Circuit-AI.

Prints only readiness booleans, model names, and verifier counts. It never
prints OAuth tokens, GitHub tokens, raw prompts, or raw model output.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.intelligence.circuit_ai_reasoner import CircuitAIReasoner, circuit_ai_model_status
from src.intelligence.copilot_provider import DEFAULT_COPILOT_MODEL, copilot_provider_status
from src.config import settings


def main() -> int:
    os.environ["LLM_PROVIDER"] = "copilot"
    os.environ.setdefault("LLM_MODEL", os.environ.get("COPILOT_MODEL") or DEFAULT_COPILOT_MODEL)
    settings.llm_provider = "copilot"
    settings.llm_model = os.environ["LLM_MODEL"]
    settings.copilot_model = os.environ["LLM_MODEL"]

    provider = copilot_provider_status(os.environ.get("LLM_MODEL"))
    print(
        json.dumps(
            {
                "copilot_status": provider.get("status"),
                "selected": provider.get("selected"),
                "providers": {
                    name: {
                        key: value
                        for key, value in row.items()
                        if key
                        in {
                            "ready",
                            "command_available",
                            "command_runnable",
                            "gh_authenticated",
                            "token_marker_configured",
                        }
                    }
                    for name, row in (provider.get("providers") or {}).items()
                },
                "secrets_returned": False,
            },
            indent=2,
        )
    )

    payload = {
        "goal": "choose the first safe evidence-gathering step for reusing a low-voltage board connector",
        "use_llm_reasoner": True,
        "analysis": {
            "mode": "circuit_board_system",
            "boards": [
                {
                    "board_id": "demo_ctrl",
                    "functional_salvage": {
                        "mode": "functional_salvage_assessment",
                        "schema_version": "functional_salvage.v1",
                        "board_id": "demo_ctrl",
                        "reusable_blocks": [
                            {
                                "block_id": "demo_ctrl_external_interface_j1",
                                "name": "4-pin external connector J1",
                                "function_type": "external_interface",
                                "status": "blocked_until_evidence",
                                "capabilities": ["i2c_breakout", "low_voltage_power"],
                                "connector_refs": ["J1"],
                                "source_refs": ["J1"],
                                "evidence_gates": [
                                    {"gate": "measure connector voltage", "status": "open"},
                                    {"gate": "confirm ground continuity", "status": "open"},
                                    {"gate": "confirm logic level", "status": "open"},
                                ],
                            }
                        ]
                    },
                    "connector_contracts": [
                        {
                            "connector_ref": "J1",
                            "pins": [
                                {"pin": "1", "net": "+3V3", "kind": "power"},
                                {"pin": "2", "net": "0", "kind": "ground"},
                                {"pin": "3", "net": "SCL", "kind": "signal"},
                                {"pin": "4", "net": "SDA", "kind": "signal"},
                            ],
                        }
                    ],
                }
            ],
        },
    }
    reasoning = CircuitAIReasoner(enable_llm=True).assess(payload)
    backend = reasoning.get("backend") or {}
    verifier = reasoning.get("verifier") or {}
    print(
        json.dumps(
            {
                "runtime_status": circuit_ai_model_status().get("status"),
                "backend_status": backend.get("status"),
                "backend_model": backend.get("model"),
                "raw_response_parsed": backend.get("raw_response_parsed"),
                "verifier_status": verifier.get("status"),
                "blocked_model_claim_count": verifier.get("blocked_model_claim_count"),
                "needs_review_model_claim_count": verifier.get("needs_review_model_claim_count"),
                "secrets_returned": False,
            },
            indent=2,
        )
    )
    return 0 if backend.get("status") == "llm_used" else 1


if __name__ == "__main__":
    raise SystemExit(main())
