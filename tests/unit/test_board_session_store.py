import json

from src.intelligence.board_session_store import BoardSessionStore
from src.intelligence.salvage_splice_planner import SalvageSplicePlanner


def _analysis_payload():
    return {
        "detections": [
            {
                "class_name": "ic_chip",
                "bbox": [10, 10, 40, 40],
                "confidence": 0.86,
                "ocr_text": "ESP32",
                "provenance": {"backend": "yolo"},
            }
        ],
        "detection_summary": {"total_components": 1, "review_required": False},
        "board_understanding": {
            "confidence": 0.62,
            "board_identity": {"primary_type": "controller_or_embedded_compute", "confidence": 0.62},
        },
        "machine_connection_map": {
            "connector_count": 1,
            "splice_plan": {"required_measurements": ["measure voltage at VIN", "continuity from GND to connector"]},
        },
        "certainty_ledger": {
            "overall": {"score": 0.58, "level": "possible", "summary": "Needs evidence."},
            "counts": {"possible": 2, "total": 2},
            "missing_evidence": [
                "close-up photos of IC/package markings and silk labels",
                "connector close-up plus voltage/continuity measurements",
                "golden reference image for defect AOI",
            ],
            "next_actions": ["capture connector closeup"],
            "training_queue": {"should_capture": True, "candidate_labels": ["Detected ic_chip"]},
            "items": [
                {
                    "item_id": "component_1_ic_chip",
                    "claim_type": "component",
                    "claim": "Detected ic_chip",
                    "certainty": "possible",
                    "score": 0.52,
                    "next_actions": ["review bounding box and class label against the photo"],
                    "usable_for": ["training", "salvage"],
                }
            ],
        },
    }


def test_board_session_store_creates_review_queue_and_export(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    session = store.create_session(
        {
            "description": "ESP32 board from a parts lot",
            "device_hint": "ESP32 relay",
            "symptoms": ["unknown condition"],
            "route": "salvage",
            "analysis": _analysis_payload(),
            "summary": {"summary_text": "Found one IC."},
        },
        user_id="user-1",
    )

    assert session["session_id"].startswith("board_")
    assert session["metrics"]["training_capture_recommended"] is True
    assert any(task["type"] == "measurement" for task in session["evidence_tasks"])
    assert any(task["type"] == "capture" for task in session["evidence_tasks"])

    queue = store.review_queue()
    assert queue
    capture = store.attach_capture(
        session["session_id"],
        {"kind": "marking_closeup", "filename": "ic-marking.jpg", "notes": "clear top-side marking"},
    )
    assert capture["capture"]["capture_id"] == "capture_1"
    assert capture["session"]["metrics"]["capture_burden"] >= 1
    assert any(task.get("status") == "resolved" and task.get("type") == "capture" for task in capture["session"]["evidence_tasks"])

    first_task = queue[0]
    reviewed = store.review_task(
        session["session_id"],
        {"task_id": first_task["task_id"], "action": "accepted", "notes": "looks correct"},
    )
    assert reviewed["task"]["status"] == "resolved"

    measurement = store.add_measurement(
        session["session_id"],
        {"type": "voltage", "target": "VIN", "value": 5.02, "unit": "V"},
    )
    assert measurement["measurement"]["value"] == 5.02

    export = store.export_training_package(session["session_id"], tmp_path / "export")
    assert export["training_export"]["counts"]["component_labels"] == 1
    assert export["training_export"]["counts"]["repair_cases"] == 1
    assert (tmp_path / "export" / "manifest.json").exists()
    assert (tmp_path / "export" / "repair_cases.jsonl").exists()
    json.dumps(export["package"])


def test_board_session_benchmark_reports_launch_gates(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    session = store.create_session({"analysis": _analysis_payload(), "description": "repair board"})
    task_id = store.review_queue()[0]["task_id"]
    store.review_task(session["session_id"], {"task_id": task_id, "action": "accepted"})
    store.record_outcome(
        session["session_id"],
        {"decision": "salvaged", "value_recovered_usd": 8, "time_saved_minutes": 12},
    )

    report = store.benchmark_report()

    assert report["summary"]["session_count"] == 1
    assert report["summary"]["launch_readiness_score"] > 0
    assert report["competitive_scorecard"]
    assert "collect 50 real board-in-hand sessions" in report["next_actions"][0]


def test_board_session_store_exports_reuse_splice_case(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    plan = SalvageSplicePlanner().plan(
        {
            "title": "USB fan salvage",
            "goal": "reuse as fume extractor",
            "available_parts": ["5V USB cable", "small DC motor and fan blade", "switch", "wire connector", "plastic case"],
        }
    )

    session = store.create_session(plan["session_payload"], user_id="operator-1")

    assert session["route"] == "salvage"
    assert session["salvage_splice_plan"]["target"]["recommended_build_id"] in {"usb_fume_extractor", "low_voltage_motor_test_jig"}
    assert any(task["source"].startswith("salvage_splice") for task in session["evidence_tasks"])
    assert any(task["type"] == "measurement" for task in session["evidence_tasks"])
    assert any(task["type"] == "capture" for task in session["evidence_tasks"])

    export = store.export_training_package(session["session_id"], tmp_path / "reuse_export")

    assert export["training_export"]["counts"]["reuse_cases"] == 1
    assert export["package"]["examples"]["reuse_cases"][0]["target_build_id"] in {"usb_fume_extractor", "low_voltage_motor_test_jig"}
    assert (tmp_path / "reuse_export" / "reuse_cases.jsonl").exists()
    json.dumps(export["package"])


def test_board_session_store_exports_production_aoi_case(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    analysis = {
        **_analysis_payload(),
        "production_aoi": {
            "mode": "production_aoi_certainty_gate",
            "disposition": "hold_for_reference",
            "release_authorized": False,
            "certainty_score": 0.52,
            "certainty_level": "not_production_ready",
            "blockers": ["golden_visual_reference: golden image not supplied"],
            "critical_findings": [],
            "required_evidence": ["capture known-good golden board under the same fixture and lighting"],
            "operator_checklist": ["capture known-good golden board under the same fixture and lighting"],
            "gates": [
                {"gate_id": "golden_visual_reference", "status": "missing", "score": 0.0},
            ],
            "audit_packet": {"reference_statuses": {"component": "unavailable", "golden": "unavailable"}},
        },
    }

    session = store.create_session(
        {"description": "AOI board", "route": "aoi", "analysis": analysis},
        user_id="operator-1",
    )

    assert any(task["source"].startswith("production_aoi") for task in session["evidence_tasks"])

    export = store.export_training_package(session["session_id"], tmp_path / "aoi_export")

    assert export["training_export"]["counts"]["aoi_cases"] == 1
    assert export["package"]["examples"]["aoi_cases"][0]["disposition"] == "hold_for_reference"
    assert (tmp_path / "aoi_export" / "aoi_cases.jsonl").exists()
    json.dumps(export["package"])
