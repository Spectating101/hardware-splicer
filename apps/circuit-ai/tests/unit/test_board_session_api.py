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


def _authority_analysis():
    analysis = _analysis()
    analysis["evidence_trust"] = {
        "score": 0.84,
        "level": "high",
        "launch_readiness": "private_alpha_candidate",
        "blockers": ["No electrical measurements are attached yet."],
        "required_evidence": [
            "Continuity/no-short check on power rails and ground.",
            "Current-limited voltage measurement on expected rails.",
            "Functional output or symptom reproduction test after safe power-up.",
        ],
        "gates": [
            {
                "id": "electrical_validation",
                "label": "Electrical validation",
                "status": "fail",
                "score": 0,
                "reason": "Image-only evidence has no continuity, voltage, resistance, or power-on measurements.",
            }
        ],
    }
    analysis["repair_authority"] = {
        "status": "visual_only",
        "score": 0.46,
        "required_measurements": [
            "Continuity/no-short check on power rails and ground.",
            "Unpowered resistance measurement between power input and ground.",
            "Current-limited voltage measurement on expected rails.",
        ],
        "blocked_decisions": ["production repair release"],
        "gates": [
            {
                "id": "measurement_presence",
                "label": "Measurement presence",
                "status": "fail",
                "score": 0,
                "reason": "No bench measurements are attached.",
            }
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
        {
            "decision": "repaired",
            "selected_resource_ids_used": ["usb_ground_repair"],
            "measurements_recorded": True,
            "cash_spent_usd": 0.5,
            "value_recovered_usd": 12,
            "time_spent_minutes": 15,
            "deviations_from_plan": [],
            "failure_or_stop_reason": "",
            "output_function_verified": True,
        },
        current_user=user,
        store=store,
    )
    assert outcome["result"]["outcome"]["decision"] == "repaired"
    assert outcome["result"]["outcome"]["selected_resource_ids_used"] == ["usb_ground_repair"]
    assert outcome["result"]["outcome"]["measurements_recorded"] is True
    assert outcome["result"]["outcome"]["cash_spent_usd"] == 0.5

    exported = main_module.board_sessions_training_export(
        session_id,
        current_user=user,
        store=store,
    )
    assert exported["result"]["training_export"]["counts"]["component_labels"] == 1
    assert exported["result"]["training_export"]["counts"]["repair_cases"] == 1

    benchmark = main_module.board_sessions_benchmark(current_user=user, store=store)
    assert benchmark["benchmark"]["summary"]["session_count"] == 1


def test_board_session_api_creates_tasks_from_evidence_trust_and_repair_authority(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    user = {"user_id": "user-1"}

    created = main_module.board_sessions_create(
        {"description": "Measured repair authority board", "analysis": _authority_analysis(), "route": "repair"},
        current_user=user,
        store=store,
    )

    tasks = created["session"]["evidence_tasks"]
    prompts = [task["prompt"] for task in tasks]
    sources = {task["source"] for task in tasks}

    assert any("Continuity/no-short" in prompt for prompt in prompts)
    assert any("production repair release" in prompt for prompt in prompts)
    assert "evidence_trust_required" in sources
    assert "repair_authority_gate" in sources
    assert any(task["type"] == "measurement" for task in tasks)


def test_board_session_api_appends_latest_repair_authority_snapshot(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    user = {"user_id": "user-1"}

    created = main_module.board_sessions_create(
        {"description": "Repair authority board", "analysis": _authority_analysis(), "route": "repair"},
        current_user=user,
        store=store,
    )
    session_id = created["session"]["session_id"]

    appended = main_module.board_sessions_append_analysis(
        session_id,
        {
            "source": "scan_verification",
            "summary": {"repair_authority_status": "authoritative_low_risk"},
            "analysis": {
                "repair_authority": {
                    "status": "authoritative_low_risk",
                    "score": 0.88,
                    "safety_level": "caution",
                    "summary": "Measurement-backed low-risk authority is available.",
                    "supported_decisions": ["low-risk repair decision for measured claims"],
                    "blocked_decisions": [],
                    "required_measurements": [],
                    "measurement_summary": {"count": 4, "failed": 0, "quality": "bench_recorded"},
                    "gates": [{"id": "measurement_integrity", "status": "pass", "reason": "bench recorded"}],
                }
            },
        },
        current_user=user,
        store=store,
    )

    session = appended["result"]["session"]
    latest = session["analyses"][-1]
    open_authority_tasks = [
        task for task in session["evidence_tasks"]
        if task.get("status", "open") == "open" and str(task.get("source") or "").startswith("repair_authority")
    ]

    assert latest["source"] == "scan_verification"
    assert latest["results"]["repair_authority"]["status"] == "authoritative_low_risk"
    assert open_authority_tasks == []


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
