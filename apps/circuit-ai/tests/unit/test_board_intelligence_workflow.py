from __future__ import annotations

from pathlib import Path

from src.api.v1 import main as main_module
from src.engines.board_intelligence import (
    analyze_board_intelligence,
    analyze_board_session_intelligence,
    assess_downstream_capabilities,
)
from src.engines.circuit_board_graph import analyze_circuit_design
from src.intelligence.board_session_store import BoardSessionStore


ROOT = Path(__file__).resolve().parents[4]
DEMO_NETLIST = ROOT / "examples" / "main_ctrl_esp32_servo.net"


def test_board_intelligence_analyzes_controller_design_evidence():
    result = analyze_board_intelligence(
        {
            "machine_name": "pan_tilt_controller",
            "boards": [
                {
                    "board_id": "main_ctrl",
                    "board_name": "Main Controller",
                    "path": str(DEMO_NETLIST),
                    "kind": "netlist",
                }
            ],
        }
    )

    assert result["mode"] == "circuit_ai_board_intelligence"
    assert result["overall_disposition"] in {"actionable", "needs_review"}
    board = result["boards"][0]
    assert board["primary_role"] == "controller"
    assert board["controller"]["count"] == 1
    assert board["controller"]["programming_paths"]
    assert board["power"]["rails"]
    assert board["functional_salvage"]["mode"] == "functional_salvage_assessment"
    assert result["functional_salvage"]["mode"] == "functional_salvage_portfolio"
    assert result["circuit_reasoning"]["mode"] == "circuit_ai_reasoning"
    assert result["circuit_reasoning"]["ai_integration"]["location"] == "circuit_graph_and_salvage_pipeline"
    assert result["circuit_reasoning"]["input_summary"]["functional_block_count"] >= 1
    assert result["circuit_proof"]["summary"]["schema_version"] == "circuit_ai_proof_matrix.v1"
    assert result["circuit_proof"]["recommended_first_action"]["action_type"] == "measurement"
    assert board["action_plan"]
    assert result["downstream_capabilities"]["mecha_splicer"]["status"] == "available"
    assert result["downstream_capabilities"]["splicer3d"]["status"] == "available"
    assert result["readiness"]["level"] in {"design_review_ready", "evidence_review_required"}
    assert result["evidence_coverage"]["score"] > 0.6
    assert result["next_evidence_tasks"]


def test_board_intelligence_can_consume_circuit_graph_functional_salvage():
    circuit = analyze_circuit_design(
        {
            "board": {
                "board_id": "main_ctrl",
                "path": str(DEMO_NETLIST),
                "kind": "netlist",
            }
        }
    )

    result = analyze_board_intelligence({"analysis": circuit})

    assert result["mode"] == "circuit_ai_board_intelligence"
    assert result["boards"][0]["functional_salvage"]["mode"] == "functional_salvage_assessment"
    assert result["functional_salvage"]["reusable_block_count"] >= 3
    assert result["boards"][0]["circuit"]["splice_contract"]["mode"] == "circuit_board_splice_contract"
    assert result["circuit_reasoning"]["input_summary"]["functional_block_count"] >= 3
    assert result["circuit_proof"]["summary"]["top_candidate"]["block_id"] == "main_ctrl_external_interface_j2"
    assert result["circuit_proof"]["recommended_first_action"]["block_id"] == "main_ctrl_external_interface_j2"


def test_board_intelligence_api_can_commit_session(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    user = {"user_id": "user-1"}

    response = main_module.board_intelligence_analyze_design(
        {
            "description": "Pan tilt controller evidence",
            "board": {
                "board_id": "main_ctrl",
                "path": str(DEMO_NETLIST),
                "kind": "netlist",
            },
        },
        commit_session=True,
        current_user=user,
        store=store,
    )

    assert response["status"] == "success"
    assert response["session"]["route"] == "board_intelligence"
    session = store.get_session(response["session"]["session_id"])
    assert session is not None
    assert session["analyses"][0]["results"]["mode"] == "circuit_ai_board_intelligence"
    assert session["evidence_tasks"]


def test_board_session_intelligence_fuses_evidence_and_outcomes(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    design_intelligence = analyze_board_intelligence(
        {
            "board": {
                "board_id": "main_ctrl",
                "board_name": "Main Controller",
                "path": str(DEMO_NETLIST),
                "kind": "netlist",
            },
        }
    )
    session = store.create_session(
        {
            "description": "Main controller bring-up case",
            "route": "board_intelligence",
            "analysis": design_intelligence,
            "source": "design_evidence",
            "captures": [{"kind": "top_side_scan", "filename": "main-top.jpg"}],
        },
        user_id="operator-1",
    )
    store.add_measurement(
        session["session_id"],
        {"type": "voltage", "target": "5V rail", "value": 5.01, "unit": "V"},
    )
    first_open_task = store.review_queue()[0]
    store.review_task(
        session["session_id"],
        {"task_id": first_open_task["task_id"], "action": "accepted", "notes": "design extraction matches scan"},
    )
    store.record_outcome(
        session["session_id"],
        {"decision": "bringup_passed", "time_saved_minutes": 20, "notes": "controller flashed over USB"},
    )

    result = analyze_board_session_intelligence(store.get_session(session["session_id"]))

    assert result["session_context"]["measurement_count"] == 1
    assert result["session_context"]["outcome_count"] == 1
    assert result["readiness"]["level"] == "calibrated_case"
    assert result["overall_disposition"] == "actionable"
    gate_status = {gate["gate_id"]: gate["status"] for gate in result["evidence_coverage"]["gates"]}
    assert gate_status["programming_path"] == "pass"
    assert gate_status["measurement_evidence"] == "pass"
    assert result["dossier"]["known"]


def test_board_intelligence_session_api_appends_analysis(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    user = {"user_id": "user-1"}
    created = main_module.board_intelligence_analyze_design(
        {
            "description": "Controller board evidence",
            "board": {
                "board_id": "main_ctrl",
                "path": str(DEMO_NETLIST),
                "kind": "netlist",
            },
        },
        commit_session=True,
        current_user=user,
        store=store,
    )
    session_id = created["session"]["session_id"]
    main_module.board_sessions_add_measurement(
        session_id,
        {"type": "voltage", "target": "5V rail", "value": 5.0, "unit": "V"},
        current_user=user,
        store=store,
    )

    response = main_module.board_intelligence_analyze_session(
        session_id,
        {},
        commit_analysis=True,
        current_user=user,
        store=store,
    )

    assert response["status"] == "success"
    assert response["intelligence"]["session_context"]["measurement_count"] == 1
    saved = store.get_session(session_id)
    assert saved["analyses"][-1]["source"] == "board_intelligence_session"
    assert saved["analyses"][-1]["results"]["readiness"]["level"] in {
        "bringup_ready",
        "operator_workflow_ready",
        "calibrated_case",
        "design_review_ready",
    }


def test_downstream_capability_assessment_is_circuit_ai_centered():
    capabilities = assess_downstream_capabilities()

    assert capabilities["mecha_splicer"]["role"].startswith("downstream")
    assert capabilities["splicer3d"]["role"].startswith("optional")
