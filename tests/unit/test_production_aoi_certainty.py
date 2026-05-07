from src.intelligence.production_aoi_certainty import ProductionAOICertaintyGate


def _strong_inputs():
    return {
        "detection_summary": {
            "total_components": 12,
            "backend_breakdown": {"yolo": 12},
            "average_semantic_confidence": 0.91,
            "review_required": False,
        },
        "visual_topology": {"confidence": 0.68},
        "defect_inspection": {"defect_count": 0, "max_severity": 0.0, "defects": []},
        "reference_aoi": {"status": "PASS", "component_delta": 0},
        "topology_aoi": {"status": "PASS", "topology_delta": 0},
        "golden_aoi": {"status": "PASS", "defect_count": 0, "defects": []},
        "aoi_inspection": {"score": 0.92, "scan_quality": {"score": 0.88, "reason": "tracked"}},
        "certainty_ledger": {"overall": {"score": 0.86, "level": "certain"}},
        "profile": {
            "line_id": "line-a",
            "station_id": "station-1",
            "fixture_id": "fixture-1",
            "calibration_id": "cal-2026-05",
            "operator_id": "operator-1",
            "lot_id": "lot-7",
            "board_serial": "pcb-001",
            "board_revision": "rev-a",
        },
    }


def test_production_aoi_gate_releases_only_with_full_traceable_evidence():
    gate = ProductionAOICertaintyGate()

    result = gate.evaluate(**_strong_inputs())

    assert result["disposition"] == "release"
    assert result["release_authorized"] is True
    assert result["certainty_level"] in {"production_release", "production_certified"}
    assert not result["blockers"]
    assert {row["gate_id"] for row in result["gates"]} >= {
        "capture_quality",
        "component_reference",
        "golden_visual_reference",
        "topology_reference",
        "calibration_traceability",
    }


def test_production_aoi_gate_reworks_golden_failures():
    payload = _strong_inputs()
    payload["golden_aoi"] = {
        "status": "FAIL",
        "defect_count": 2,
        "defects": [{"defect_type": "missing_component", "severity": 0.9}],
    }

    result = ProductionAOICertaintyGate().evaluate(**payload)

    assert result["disposition"] == "rework"
    assert result["release_authorized"] is False
    assert any("golden_visual_reference" in blocker for blocker in result["blockers"])
    assert any("golden visual mismatch" in finding for finding in result["critical_findings"])


def test_production_aoi_gate_holds_when_references_are_missing():
    payload = _strong_inputs()
    payload["reference_aoi"] = {"status": "unavailable"}
    payload["topology_aoi"] = {"status": "unavailable"}
    payload["golden_aoi"] = {"status": "unavailable"}

    result = ProductionAOICertaintyGate().evaluate(**payload)

    assert result["disposition"] == "hold_for_reference"
    assert result["release_authorized"] is False
    assert any("component_reference" in blocker for blocker in result["blockers"])
    assert any("golden_visual_reference" in blocker for blocker in result["blockers"])


def test_production_aoi_gate_holds_blurry_capture_before_review():
    payload = _strong_inputs()
    payload["aoi_inspection"] = {"score": 0.52, "scan_quality": {"score": 0.24, "reason": "blur"}}

    result = ProductionAOICertaintyGate().evaluate(**payload)

    assert result["disposition"] == "hold_for_capture"
    assert result["release_authorized"] is False
    assert any("capture_quality" in blocker for blocker in result["blockers"])
