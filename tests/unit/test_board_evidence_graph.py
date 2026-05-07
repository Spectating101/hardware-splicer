from src.intelligence.board_evidence_graph import BoardEvidenceGraphBuilder
from src.intelligence.board_session_store import BoardSessionStore


def _session():
    return {
        "session_id": "board-1",
        "title": "AOI board",
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
                    "detection_summary": {"total_components": 1, "average_confidence": 0.91},
                    "production_aoi": {
                        "disposition": "rework",
                        "release_authorized": False,
                        "certainty_score": 0.67,
                        "blockers": ["topology_reference: 1 topology mismatch(es)"],
                        "gates": [
                            {"gate_id": "capture_quality", "status": "pass", "score": 0.9},
                            {"gate_id": "topology_reference", "status": "fail", "score": 0.84},
                        ],
                    },
                    "certainty_ledger": {
                        "items": [
                            {"claim": "Topology needs review", "score": 0.4, "certainty": "possible", "usable_for": ["aoi"]}
                        ]
                    },
                }
            }
        ],
    }


def test_board_evidence_graph_links_claims_to_sources():
    graph = BoardEvidenceGraphBuilder().build(_session())

    assert graph["summary"]["claim_count"] >= 3
    assert graph["summary"]["source_count"] >= 3
    assert any(node["kind"] == "aoi_gate" for node in graph["nodes"])
    assert any(edge["relation"] == "supports" for edge in graph["edges"])
    assert any("Production AOI disposition" in claim["claim"] for claim in graph["weak_claims"])
    assert graph["next_grounding_actions"]


def test_board_session_store_returns_evidence_graph(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    store.sessions.append(_session())

    graph = store.evidence_graph("board-1")

    assert graph["mode"] == "board_evidence_graph"
    assert graph["session_id"] == "board-1"
    assert store.evidence_graph("missing")["error"] == "session not found: missing"
