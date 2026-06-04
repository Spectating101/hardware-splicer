"""Golden end-to-end workflows for circuit-backed salvage."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.engines.board_intelligence import analyze_board_intelligence
from src.engines.circuit_board_graph import analyze_circuit_design, analyze_circuit_session
from src.intelligence.board_session_store import BoardSessionStore
from src.intelligence.circuit_ai_reasoner import CircuitAIReasoner
from src.intelligence.salvage_splice_planner import SalvageSplicePlanner


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _default_netlist() -> Path:
    return _repo_root() / "examples" / "main_ctrl_esp32_servo.net"


def _status(value: bool) -> str:
    return "pass" if value else "fail"


def _find_block(blocks: List[Dict[str, Any]], *, function_type: str = "", connector_ref: str = "") -> Optional[Dict[str, Any]]:
    for block in blocks:
        if function_type and block.get("function_type") != function_type:
            continue
        if connector_ref and connector_ref not in (block.get("connector_refs") or block.get("source_refs") or []):
            continue
        return block
    return None


class FunctionalSalvageWorkflowRunner:
    """Run real circuit/session/salvage loops over a small scenario corpus."""

    def __init__(
        self,
        *,
        store: Optional[BoardSessionStore] = None,
        planner: Optional[SalvageSplicePlanner] = None,
    ) -> None:
        self.store = store
        self.planner = planner or SalvageSplicePlanner()

    def run(self, *, commit_sessions: bool = False) -> Dict[str, Any]:
        if commit_sessions and self.store is not None:
            return self._run_with_store(self.store, commit_sessions=True)
        with tempfile.TemporaryDirectory(prefix="circuit-ai-functional-salvage-") as tmp:
            store = BoardSessionStore(Path(tmp) / "sessions.json")
            return self._run_with_store(store, commit_sessions=False)

    def _run_with_store(self, store: BoardSessionStore, *, commit_sessions: bool) -> Dict[str, Any]:
        scenarios = [
            self._verified_sensor_connector(store),
            self._motor_connector_blocked(store),
            self._regulator_section_candidate(store),
            self._hazardous_lithium_hold(store),
        ]
        passed = len([row for row in scenarios if row.get("status") == "pass"])
        return {
            "mode": "functional_salvage_golden_workflow",
            "scenario_count": len(scenarios),
            "passed_count": passed,
            "failed_count": len(scenarios) - passed,
            "overall_status": "pass" if passed == len(scenarios) else "fail",
            "commit_sessions": commit_sessions,
            "scenarios": scenarios,
            "next_scale_targets": [
                "add Bluetooth/WiFi module reuse corpus",
                "add display/audio function reuse corpus",
                "add layout-aware extractability for board-section salvage",
                "attach frontend session view to recommended_first_splice",
            ],
        }

    def _create_circuit_session(
        self,
        store: BoardSessionStore,
        *,
        title: str,
        board_id: str = "main_ctrl",
    ) -> Dict[str, Any]:
        payload = {
            "description": title,
            "board": {
                "board_id": board_id,
                "path": str(_default_netlist()),
                "kind": "netlist",
            },
        }
        circuit = analyze_circuit_design(payload)
        session = store.create_session(
            {
                "description": title,
                "route": "circuit",
                "analysis": circuit,
                "summary": {
                    "overall_readiness": circuit.get("overall_readiness"),
                    "board_count": circuit.get("board_count"),
                },
                "source": "functional_salvage_workflow",
            },
            user_id="workflow-runner",
            commit=True,
        )
        return {"payload": payload, "circuit": circuit, "session": session}

    def _verified_sensor_connector(self, store: BoardSessionStore) -> Dict[str, Any]:
        created = self._create_circuit_session(store, title="Verified J2 sensor connector reuse")
        session_id = created["session"]["session_id"]
        for measurement in [
            {"type": "voltage", "target": "J2 +3V3", "value": 3.31, "unit": "V", "notes": "J2 power pin measured to ground"},
            {"type": "continuity", "target": "J2 ground", "value": "pass", "notes": "J2 ground continuity ok"},
            {"type": "logic_level", "target": "J2 SCL SDA", "value": "pass", "notes": "logic idle high at 3.3V on SCL/SDA"},
            {"type": "voltage", "target": "+3V3", "value": 3.31, "unit": "V", "notes": "rail measured to ground"},
        ]:
            store.add_measurement(session_id, measurement)
        session = store.get_session(session_id)
        circuit = analyze_circuit_session(session)
        intelligence = analyze_board_intelligence({"analysis": circuit, "session": session})
        splice = self.planner.plan(
            {
                "title": "verified sensor connector reuse",
                "goal": "reuse the verified J2 sensor connector in another low-voltage build",
                "analysis": circuit,
            }
        )
        reasoning = splice.get("circuit_reasoning") or CircuitAIReasoner(enable_llm=False).assess(
            {"goal": "reuse the verified J2 sensor connector", "analysis": circuit}
        )
        reuse = splice["functional_reuse_plan"]
        first = reuse["recommended_first_splice"]
        ok = (
            reuse.get("splice_readiness") == "ready_for_first_splice"
            and first.get("status") == "reuse_ready"
            and "main_ctrl:J2" in (first.get("entry_points") or [])
            and intelligence.get("functional_salvage", {}).get("ready_block_count", 0) >= 1
            and reasoning.get("verifier", {}).get("status") == "pass_with_gates"
        )
        return {
            "id": "verified_sensor_connector",
            "name": "Verified sensor connector reuse",
            "status": _status(ok),
            "session_id": session_id,
            "circuit_readiness": circuit.get("overall_readiness"),
            "board_intelligence": {
                "readiness": intelligence.get("readiness", {}).get("level"),
                "functional_ready_blocks": intelligence.get("functional_salvage", {}).get("ready_block_count"),
            },
            "splice_readiness": reuse.get("splice_readiness"),
            "recommended_first_splice": first,
            "circuit_reasoning": {
                "mode": reasoning.get("mode"),
                "backend": reasoning.get("backend", {}).get("status"),
                "verifier": reasoning.get("verifier", {}).get("status"),
                "proposed_splice_count": len(reasoning.get("proposed_splices") or []),
            },
            "evidence": {
                "measurement_count": len((session.get("evidence") or {}).get("measurements") or []),
                "closed_ready_block_count": reuse.get("ready_block_count"),
            },
        }

    def _motor_connector_blocked(self, store: BoardSessionStore) -> Dict[str, Any]:
        created = self._create_circuit_session(store, title="Motor connector blocked until source limit")
        circuit = created["circuit"]
        splice = self.planner.plan(
            {
                "title": "servo connector reuse attempt",
                "goal": "reuse the servo/motor output connector for a machine actuator",
                "analysis": circuit,
            }
        )
        reasoning = splice.get("circuit_reasoning") or {}
        blocks = circuit["boards"][0]["functional_salvage"]["reusable_blocks"]
        j3 = _find_block(blocks, function_type="external_interface", connector_ref="J3")
        ok = (
            bool(j3)
            and j3.get("status") == "blocked_until_evidence"
            and any("SERVO_5V" in item for item in (j3.get("missing_evidence") or []))
            and splice["functional_reuse_plan"].get("splice_readiness") == "blocked_until_evidence"
        )
        return {
            "id": "motor_connector_blocked",
            "name": "Motor/load connector blocked until current evidence",
            "status": _status(ok),
            "session_id": created["session"]["session_id"],
            "target_block": {
                "block_id": (j3 or {}).get("block_id"),
                "status": (j3 or {}).get("status"),
                "missing_evidence": (j3 or {}).get("missing_evidence") or [],
            },
            "splice_readiness": splice["functional_reuse_plan"].get("splice_readiness"),
            "recommended_first_splice": splice["functional_reuse_plan"].get("recommended_first_splice"),
            "circuit_reasoning": {
                "mode": reasoning.get("mode"),
                "backend": reasoning.get("backend", {}).get("status"),
                "verifier": reasoning.get("verifier", {}).get("status"),
            },
        }

    def _regulator_section_candidate(self, store: BoardSessionStore) -> Dict[str, Any]:
        created = self._create_circuit_session(store, title="Regulator board-section candidate")
        circuit = created["circuit"]
        blocks = circuit["boards"][0]["functional_salvage"]["reusable_blocks"]
        regulator = _find_block(blocks, function_type="power_regulation")
        extractability = (regulator or {}).get("extractability") or {}
        ok = (
            bool(regulator)
            and extractability.get("class") == "board_section_cut_candidate"
            and extractability.get("requires_layout_confirmation") is True
            and (regulator or {}).get("status") == "blocked_until_evidence"
        )
        return {
            "id": "regulator_section_candidate",
            "name": "Power regulator is treated as layout-gated section salvage",
            "status": _status(ok),
            "session_id": created["session"]["session_id"],
            "target_block": {
                "block_id": (regulator or {}).get("block_id"),
                "status": (regulator or {}).get("status"),
                "extractability": extractability,
                "missing_evidence": (regulator or {}).get("missing_evidence") or [],
            },
        }

    def _hazardous_lithium_hold(self, store: BoardSessionStore) -> Dict[str, Any]:
        splice = self.planner.plan(
            {
                "title": "swollen lithium power bank",
                "goal": "reuse cells for a gadget",
                "available_parts": ["swollen battery pack", "USB board", "case"],
            }
        )
        reasoning = splice.get("circuit_reasoning") or {}
        session = store.create_session(
            splice.get("session_payload") if isinstance(splice.get("session_payload"), dict) else {},
            user_id="workflow-runner",
            commit=True,
        )
        ok = splice.get("verdict") == "unsafe_hold" and session.get("route") == "safety"
        return {
            "id": "hazardous_lithium_hold",
            "name": "Damaged lithium source routes to safety hold",
            "status": _status(ok),
            "session_id": session.get("session_id"),
            "verdict": splice.get("verdict"),
            "route": session.get("route"),
            "circuit_reasoning": {
                "mode": reasoning.get("mode"),
                "backend": reasoning.get("backend", {}).get("status"),
                "verifier": reasoning.get("verifier", {}).get("status"),
            },
            "stop_conditions": splice.get("stop_conditions") or [],
        }
