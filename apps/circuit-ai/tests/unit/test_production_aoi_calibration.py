from src.intelligence.board_session_store import BoardSessionStore
from src.intelligence.production_aoi_calibration import ProductionAOICalibrator


def _aoi(disposition="release", release=True, score=0.91, gates=None):
    return {
        "production_aoi": {
            "mode": "production_aoi_certainty_gate",
            "disposition": disposition,
            "release_authorized": release,
            "certainty_score": score,
            "certainty_level": "production_release" if release else "review_ready",
            "blockers": [] if release else ["golden_visual_reference: golden image not supplied"],
            "gates": gates
            or [
                {"gate_id": "capture_quality", "status": "pass", "score": 0.9},
                {"gate_id": "component_reference", "status": "pass", "score": 1.0},
                {"gate_id": "golden_visual_reference", "status": "pass", "score": 1.0},
                {"gate_id": "topology_reference", "status": "pass", "score": 1.0},
            ],
        },
        "certainty_ledger": {"overall": {"score": 0.9, "level": "likely"}},
    }


def test_production_aoi_calibrator_flags_false_accept():
    sessions = [
        {
            "session_id": "aoi-1",
            "route": "aoi",
            "analyses": [{"results": _aoi()}],
            "outcomes": [{"outcome_id": "outcome_1", "aoi_actual_status": "rework"}],
        }
    ]

    report = ProductionAOICalibrator().build_report(sessions)

    assert report["summary"]["false_accept_count"] == 1
    assert report["summary"]["readiness"] == "unsafe_to_relax_release"
    assert report["recommended_profile_patch"]["min_release_score"] > 0.86
    assert "freeze automatic release" in report["next_actions"][1]


def test_production_aoi_calibrator_counts_false_reject_gates():
    sessions = [
        {
            "session_id": "aoi-1",
            "route": "aoi",
            "analyses": [
                {
                    "results": _aoi(
                        disposition="hold_for_reference",
                        release=False,
                        score=0.62,
                        gates=[
                            {"gate_id": "capture_quality", "status": "pass", "score": 0.9},
                            {"gate_id": "golden_visual_reference", "status": "missing", "score": 0.0},
                        ],
                    )
                }
            ],
            "outcomes": [{"outcome_id": "outcome_1", "aoi_actual_status": "pass"}],
        }
    ]

    report = ProductionAOICalibrator().build_report(sessions)

    assert report["summary"]["false_reject_count"] == 1
    assert report["gate_report"]["false_reject_gate_counts"]["golden_visual_reference"] == 1
    assert report["cases"][0]["result_class"] == "false_reject"


def test_board_session_store_reports_aoi_calibration_and_preserves_truth(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    session = store.create_session({"route": "aoi", "analysis": _aoi()})

    store.record_outcome(
        session["session_id"],
        {"decision": "released", "aoi_actual_status": "pass", "aoi_release_ok": True},
    )

    report = store.aoi_calibration_report()

    assert report["summary"]["labeled_case_count"] == 1
    assert report["summary"]["true_release_count"] == 1
    assert store.sessions[0]["outcomes"][0]["aoi_actual_status"] == "pass"
