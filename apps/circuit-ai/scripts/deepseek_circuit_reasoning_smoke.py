#!/usr/bin/env python3
"""Run one live DeepSeek-backed circuit reasoning smoke test.

Usage:
  LLM_PROVIDER=deepseek \
  LLM_MODEL=deepseek-v4-flash \
  DEEPSEEK_API_KEY=... \
  python3 scripts/deepseek_circuit_reasoning_smoke.py

The script never prints the API key. It exits before the model call if runtime
status says the live provider is not ready.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.engines.circuit_board_graph import analyze_circuit_design
from src.intelligence.circuit_ai_reasoner import CircuitAIReasoner, circuit_ai_model_status


def main() -> int:
    status = circuit_ai_model_status()
    print(json.dumps({"model_runtime": status}, indent=2))
    if not status.get("ready_for_live_model"):
        return 2

    netlist = PROJECT_ROOT / "examples" / "main_ctrl_esp32_servo.net"
    circuit = analyze_circuit_design(
        {
            "description": "DeepSeek circuit reasoning smoke test",
            "board": {
                "board_id": "main_ctrl",
                "path": str(netlist),
                "kind": "netlist",
            },
        }
    )
    reasoning = CircuitAIReasoner(enable_llm=True).assess(
        {
            "goal": "Identify which low-voltage board function is safest to reuse first, and explain missing evidence.",
            "analysis": circuit,
        }
    )
    summary = {
        "backend": reasoning.get("backend"),
        "verifier": reasoning.get("verifier"),
        "input_summary": reasoning.get("input_summary"),
        "evidence_packet_summary": {
            "candidate_block_count": len((reasoning.get("evidence_packet") or {}).get("candidate_blocks") or []),
            "connector_contract_count": len((reasoning.get("evidence_packet") or {}).get("connector_contracts") or []),
            "known_part_evidence_count": len((reasoning.get("evidence_packet") or {}).get("known_part_evidence") or []),
        },
        "model_hypotheses": reasoning.get("model_hypotheses") or [],
        "proposed_splices": reasoning.get("proposed_splices") or [],
        "proof_summary": reasoning.get("proof_summary") or {},
        "recommended_first_action": reasoning.get("recommended_first_action") or {},
        "proof_matrix_top": (reasoning.get("proof_matrix") or [])[:5],
        "adapter_recommendations": reasoning.get("adapter_recommendations") or [],
        "recommended_next_actions": reasoning.get("recommended_next_actions") or [],
    }
    print(json.dumps(summary, indent=2))
    return 0 if reasoning.get("backend", {}).get("status") == "llm_used" else 1


if __name__ == "__main__":
    raise SystemExit(main())
