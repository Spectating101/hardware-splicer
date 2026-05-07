from src.api.v1 import main as main_module
from src.intelligence.board_session_store import BoardSessionStore


def _analysis():
    return {
        "detections": [{"class_name": "connector", "bbox": [1, 2, 20, 30], "confidence": 0.8}],
        "detection_summary": {"total_components": 1},
        "certainty_ledger": {
            "overall": {"score": 0.44, "level": "possible"},
            "counts": {"possible": 1, "total": 1},
            "missing_evidence": ["connector close-up plus voltage/continuity measurements"],
            "training_queue": {"should_capture": True},
            "items": [],
        },
    }


def _aoi_analysis():
    analysis = _analysis()
    analysis["production_aoi"] = {
        "mode": "production_aoi_certainty_gate",
        "disposition": "release",
        "release_authorized": True,
        "certainty_score": 0.92,
        "certainty_level": "production_release",
        "blockers": [],
        "gates": [
            {"gate_id": "capture_quality", "status": "pass", "score": 0.9},
            {"gate_id": "component_reference", "status": "pass", "score": 1.0},
            {"gate_id": "golden_visual_reference", "status": "pass", "score": 1.0},
        ],
    }
    return analysis


def test_board_session_api_create_review_export_and_benchmark(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    user = {"user_id": "user-1"}

    created = main_module.board_sessions_create(
        {"description": "USB fan board", "analysis": _analysis(), "route": "repair"},
        current_user=user,
        store=store,
    )
    session_id = created["session"]["session_id"]

    listed = main_module.board_sessions_list(current_user=user, store=store)
    assert listed["metadata"]["count"] == 1

    queue = main_module.board_sessions_review_queue(current_user=user, store=store)
    assert queue["tasks"]

    captured = main_module.board_sessions_add_capture(
        session_id,
        file=None,
        kind="connector_closeup",
        notes="operator added follow-up evidence",
        current_user=user,
        store=store,
    )
    assert captured["result"]["capture"]["kind"] == "connector_closeup"

    reviewed = main_module.board_sessions_review_task(
        session_id,
        {"task_id": queue["tasks"][0]["task_id"], "action": "accepted"},
        current_user=user,
        store=store,
    )
    assert reviewed["result"]["task"]["status"] == "resolved"

    measured = main_module.board_sessions_add_measurement(
        session_id,
        {"type": "continuity", "target": "USB ground to board ground", "value": "pass", "unit": ""},
        current_user=user,
        store=store,
    )
    assert measured["result"]["measurement"]["target"] == "USB ground to board ground"

    outcome = main_module.board_sessions_record_outcome(
        session_id,
        {"decision": "repaired", "value_recovered_usd": 12, "time_saved_minutes": 15},
        current_user=user,
        store=store,
    )
    assert outcome["result"]["outcome"]["decision"] == "repaired"

    exported = main_module.board_sessions_training_export(
        session_id,
        current_user=user,
        store=store,
    )
    assert exported["result"]["training_export"]["counts"]["component_labels"] == 1
    assert exported["result"]["training_export"]["counts"]["repair_cases"] == 1

    benchmark = main_module.board_sessions_benchmark(current_user=user, store=store)
    assert benchmark["benchmark"]["summary"]["session_count"] == 1


def test_board_session_api_aoi_calibration_report(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    user = {"user_id": "user-1"}
    created = main_module.board_sessions_create(
        {"description": "AOI production board", "analysis": _aoi_analysis(), "route": "aoi"},
        current_user=user,
        store=store,
    )

    main_module.board_sessions_record_outcome(
        created["session"]["session_id"],
        {"decision": "released", "aoi_actual_status": "field_return"},
        current_user=user,
        store=store,
    )

    calibration = main_module.board_sessions_aoi_calibration(current_user=user, store=store)

    assert calibration["calibration"]["summary"]["false_accept_count"] == 1
    assert calibration["calibration"]["summary"]["readiness"] == "unsafe_to_relax_release"


def test_board_session_api_evidence_graph(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    user = {"user_id": "user-1"}
    created = main_module.board_sessions_create(
        {"description": "AOI production board", "analysis": _aoi_analysis(), "route": "aoi"},
        current_user=user,
        store=store,
    )

    graph = main_module.board_sessions_evidence_graph(
        created["session"]["session_id"],
        current_user=user,
        store=store,
    )

    assert graph["graph"]["mode"] == "board_evidence_graph"
    assert graph["graph"]["summary"]["claim_count"] >= 1


def test_board_session_api_dossier(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    user = {"user_id": "user-1"}
    created = main_module.board_sessions_create(
        {"description": "AOI production board", "analysis": _aoi_analysis(), "route": "aoi"},
        current_user=user,
        store=store,
    )

    dossier = main_module.board_sessions_dossier(
        created["session"]["session_id"],
        current_user=user,
        store=store,
    )

    assert dossier["dossier"]["mode"] == "board_dossier"
    assert dossier["dossier"]["session_id"] == created["session"]["session_id"]
