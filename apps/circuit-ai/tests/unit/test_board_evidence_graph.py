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


def test_board_evidence_graph_links_qwen_board_evidence_candidates():
    session = _session()
    session["analyses"].append(
        {
            "analysis_id": "analysis_2",
            "source": "qwen_vl",
            "results": {
                "board_evidence": {
                    "schema_version": "board_evidence.v1",
                    "components": [
                        {"id": "u1", "label": "CH340C USB serial bridge IC", "kind": "integrated_circuit", "confidence": 0.78}
                    ],
                    "connectors": [
                        {"id": "h1", "label": "UART header", "kind": "header", "confidence": 0.7}
                    ],
                    "damage": [
                        {"id": "d1", "label": "corrosion near connector", "severity": "review", "confidence": 0.68}
                    ],
                    "salvage_candidates": [
                        {"id": "s1", "label": "USB UART bridge section", "capabilities": ["usb_serial", "connector"], "confidence": 0.7}
                    ],
                }
            },
        }
    )

    graph = BoardEvidenceGraphBuilder().build(session)

    assert any(node["kind"] == "vision_evidence" for node in graph["nodes"])
    assert any(node["kind"] == "qwen_component" and "CH340C" in node["label"] for node in graph["nodes"])
    assert any(node["kind"] == "qwen_damage" for node in graph["nodes"])
    assert any("Vision-language evidence proposes salvage candidate" in claim["claim"] for claim in graph["weak_claims"])


def test_board_evidence_graph_links_topology_evidence_candidates():
    session = _session()
    session["analyses"].append(
        {
            "analysis_id": "analysis_3",
            "source": "topology_evidence",
            "results": {
                "topology_evidence": {
                    "schema_version": "topology_evidence.v1",
                    "connectors": [
                        {
                            "ref": "J1",
                            "label": "UART header",
                            "pins": [
                                {"pin": "1", "net": "GND", "role": "ground", "status": "verified"},
                                {"pin": "2", "net": "3V3", "role": "power", "voltage": 3.3, "status": "verified"},
                                {"pin": "3", "net": "UART_TX", "role": "uart_tx", "logic_voltage": 3.3, "status": "verified"},
                                {"pin": "4", "net": "UART_RX", "role": "uart_rx", "logic_voltage": 3.3, "status": "verified"},
                            ],
                        }
                    ],
                    "nets": [{"net": "GND", "role": "ground", "nodes": ["J1:1"]}],
                }
            },
        }
    )

    graph = BoardEvidenceGraphBuilder().build(session)

    assert any(node["kind"] == "topology_evidence" for node in graph["nodes"])
    assert any(node["kind"] == "topology_connector" and "UART" in node["label"] for node in graph["nodes"])
    assert any(node["kind"] == "topology_pin" and node.get("role") == "uart_tx" for node in graph["nodes"])
    assert any("Measured topology covers" in claim["claim"] for claim in graph["grounded_claims"])
