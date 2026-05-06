from src.api.v1 import main as main_module
from src.intelligence.board_session_store import BoardSessionStore
from src.intelligence.repair_case_evaluator import RepairCase, RepairCaseEvaluator
from src.intelligence.repair_value_trial_store import RepairValueTrialStore


def _worked_session(tmp_path):
    session_store = BoardSessionStore(tmp_path / "sessions.json")
    evaluator = RepairCaseEvaluator(session_store=session_store)
    row = evaluator.evaluate_case(
        RepairCase(
            case_id="usb_fan_value",
            title="USB fan warms but motor will not spin",
            device_hint="USB fan controller board",
            symptoms=["motor will not spin", "warm board", "wire wiggle changes behavior"],
            source_url="local board-in-hand case",
            expected_lane="small_motor_usb",
        ),
        commit_session=True,
    )
    session_id = row["board_session"]["session_id"]
    session_store.attach_capture(
        session_id,
        {
            "kind": "connector_closeup",
            "filename": "connector.jpg",
            "notes": "top board and motor harness closeup",
        },
    )
    session_store.add_measurement(
        session_id,
        {
            "type": "voltage",
            "target": "USB input under startup",
            "value": 4.92,
            "unit": "V",
        },
    )
    open_tasks = session_store.review_queue(status="open")
    session_store.review_task(
        session_id,
        {
            "task_id": open_tasks[0]["task_id"],
            "action": "accepted",
            "notes": "operator confirmed cracked solder at motor harness",
        },
    )
    session_store.record_outcome(
        session_id,
        {
            "decision": "repaired",
            "time_saved_minutes": 28,
            "value_recovered_usd": 18,
            "notes": "reflowed harness joint and fan spins normally",
        },
    )
    session_store.export_training_package(session_id)
    return session_store, row


def test_value_trial_calls_plumbing_only_when_no_real_evidence(tmp_path):
    trials = RepairValueTrialStore(tmp_path / "trials.json", session_store=BoardSessionStore(tmp_path / "sessions.json"))

    trial = trials.create_trial(
        {
            "title": "button repair page opened",
            "lane_id": "controller_input",
            "workflow_score": 0.8,
            "case_verdict": "solvable_now",
        }
    )

    assert trial["verdict"] == "plumbing_only"
    assert trial["value_score"] < 0.55
    assert any("software flow only" in note for note in trial["honesty_notes"])


def test_value_trial_scores_measured_repair_as_real_value(tmp_path):
    session_store, row = _worked_session(tmp_path)
    trials = RepairValueTrialStore(tmp_path / "trials.json", session_store=session_store)

    trial = trials.create_trial(
        {
            "session_id": row["board_session"]["session_id"],
            "case_id": row["case_id"],
            "title": row["title"],
            "lane_id": "small_motor_usb",
            "source_url": row["source_url"],
            "symptoms": ["motor will not spin", "wire wiggle changes behavior"],
            "workflow_score": row["workflow_score"],
            "case_verdict": row["verdict"],
            "baseline": {
                "estimated_time_minutes": 55,
                "confidence": 0.2,
                "expected_value_usd": 20,
                "known_blockers": ["unknown driver or connector fault"],
            },
        }
    )

    assert trial["verdict"] == "value_proven"
    assert trial["value_score"] >= 0.72
    assert {gate["gate"] for gate in trial["evidence_gates"] if gate["passed"]} >= {
        "has_capture",
        "has_measurement",
        "has_review",
        "has_outcome",
        "has_measured_value",
        "has_learning_export",
    }

    benchmark = trials.benchmark_report()
    assert benchmark["summary"]["value_proven"] == 1
    assert benchmark["summary"]["measured_outcome_count"] == 1


def test_value_trial_api_create_list_and_benchmark(tmp_path):
    session_store, row = _worked_session(tmp_path)
    trials = RepairValueTrialStore(tmp_path / "trials.json", session_store=session_store)
    user = {"user_id": "user-1"}

    created = main_module.repair_value_trials_create(
        {
            "session_id": row["board_session"]["session_id"],
            "case_id": row["case_id"],
            "title": row["title"],
            "lane_id": "small_motor_usb",
            "workflow_score": row["workflow_score"],
            "case_verdict": row["verdict"],
            "baseline_confidence": 0.25,
        },
        current_user=user,
        trials=trials,
    )
    assert created["metadata"]["committed"] is True
    assert created["value_trial"]["verdict"] in {"value_proven", "value_likely"}

    listed = main_module.repair_value_trials_list(current_user=user, trials=trials)
    assert listed["metadata"]["count"] == 1
    assert listed["value_trials"][0]["session_id"] == row["board_session"]["session_id"]

    benchmark = main_module.repair_value_trials_benchmark(current_user=user, trials=trials)
    assert benchmark["benchmark"]["summary"]["trial_count"] == 1
