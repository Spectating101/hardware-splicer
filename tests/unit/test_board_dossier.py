from src.intelligence.board_dossier import BoardDossierBuilder
from src.intelligence.board_session_store import BoardSessionStore


def _session():
    return {
        "session_id": "board-1",
        "title": "AOI board",
        "device_hint": "USB controller",
        "route": "aoi",
        "status": "open",
        "evidence": {
            "captures": [{"capture_id": "capture_1", "kind": "primary_scan", "filename": "board.jpg"}],
            "measurements": [{"measurement_id": "measurement_1", "type": "continuity", "target": "GND", "value": "pass"}],
        },
        "reviews": [{"review_id": "review_1", "task_id": "task_1", "action": "accepted"}],
        "outcomes": [{"outcome_id": "outcome_1", "decision": "rework", "aoi_actual_status": "rework"}],
        "evidence_tasks": [{"task_id": "task_1", "type": "reference", "prompt": "supply golden reference", "status": "open"}],
        "analyses": [
            {
                "results": {
                    "detections": [{"class_name": "ic_chip", "confidence": 0.91, "bbox": [1, 2, 3, 4]}],
                    "detection_summary": {"total_components": 1, "components_by_type": {"ic_chip": 1}},
                    "board_understanding": {
                        "board_identity": {"primary_type": "controller", "confidence": 0.72}
                    },
                    "production_aoi": {
                        "disposition": "rework",
                        "release_authorized": False,
                        "certainty_score": 0.67,
                        "certainty_level": "review_ready",
                        "blockers": ["topology_reference: 1 topology mismatch(es)"],
                        "required_evidence": ["hold board for continuity/netlist review"],
                        "gates": [{"gate_id": "topology_reference", "status": "fail", "score": 0.84}],
                    },
                }
            }
        ],
    }


def test_board_dossier_summarizes_evidence_and_next_actions():
    dossier = BoardDossierBuilder().build(_session())

    assert dossier["mode"] == "board_dossier"
    assert dossier["status"] == "rework"
    assert "Production AOI disposition" in dossier["executive_summary"]
    assert dossier["aoi"]["disposition"] == "rework"
    assert dossier["components"]["counts"]["ic_chip"] == 1
    assert dossier["evidence"]["graph_summary"]["claim_count"] >= 1
    assert any("topology_reference" in item for item in dossier["uncertain"])
    assert dossier["next_actions"]


def test_board_session_store_returns_dossier(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    store.sessions.append(_session())

    dossier = store.dossier("board-1")

    assert dossier["session_id"] == "board-1"
    assert store.dossier("missing")["error"] == "session not found: missing"


def test_board_dossier_promotes_confirmed_repair_findings():
    session = {
        "session_id": "fan-1",
        "title": "USB fan no spin",
        "device_hint": "USB fan controller board",
        "route": "repair",
        "evidence": {
            "captures": [{"capture_id": "capture_1", "kind": "connector_closeup"}],
            "measurements": [
                {
                    "measurement_id": "measurement_1",
                    "type": "voltage",
                    "target": "USB input under attempted startup",
                    "value": 4.91,
                    "unit": "V",
                    "notes": "supply holds up while fan fails to spin",
                }
            ],
        },
        "repair_guide": {
            "device_family": {"id": "small_dc_motor_gadget", "confidence": 0.6},
            "fault_candidates": [{"name": "Driver stage or motor/load path fault", "confidence": 0.7}],
            "safety_profile": {"risk_level": "low_to_medium"},
        },
        "evidence_tasks": [
            {
                "task_id": "task_1",
                "type": "measurement",
                "prompt": "connector continuity while gently flexing the harness",
                "status": "resolved",
                "review": {"action": "accepted", "notes": "operator confirmed cracked solder at motor harness"},
            },
            {
                "task_id": "task_2",
                "type": "measurement",
                "prompt": "driver output voltage with current limit and dummy load",
                "status": "open",
            },
        ],
        "outcomes": [
            {
                "outcome_id": "outcome_1",
                "decision": "repaired",
                "notes": "reflowed harness joint and fan spins normally",
            }
        ],
    }

    dossier = BoardDossierBuilder().build(session)

    assert dossier["repair_reuse"]["top_fault"] == "Connector, solder joint, or harness intermittency"
    assert dossier["repair_reuse"]["top_fault_source"] == "confirmed_evidence"
    assert any("cracked solder at motor harness" in item for item in dossier["known"])
    assert any("4.91 V" in item for item in dossier["known"])
    assert any("driver output voltage" in action for action in dossier["next_actions"])
