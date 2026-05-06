import json

from src.intelligence.board_session_store import BoardSessionStore


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
