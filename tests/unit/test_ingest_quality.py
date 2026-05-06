from src.core.ingest import CircuitAnalyzer


def test_confidence_band_is_stratified():
    analyzer = CircuitAnalyzer()

    assert analyzer._confidence_band(0.92) == "high"
    assert analyzer._confidence_band(0.64) == "medium"
    assert analyzer._confidence_band(0.39) == "low"


def test_low_scan_quality_blocks_pilot_readiness():
    analyzer = CircuitAnalyzer()
    result = analyzer._assess_aoi_readiness(
        {
            "total_components": 8,
            "backend_breakdown": {"yolo": 8},
            "average_semantic_confidence": 0.9,
            "review_required": False,
        },
        {"confidence": 0.6},
        reference_aoi={"status": "PASS", "component_delta": 0},
        topology_aoi={"status": "PASS", "topology_delta": 0},
        scan_quality={"score": 0.1, "reason": "low_contrast"},
    )

    assert result["readiness"] != "pilot_ready"
    assert result["scan_quality"]["score"] == 0.1
    assert result["blockers"][0].startswith("scan quality is below production threshold")


def test_golden_image_failure_penalizes_aoi_readiness():
    analyzer = CircuitAnalyzer()
    result = analyzer._assess_aoi_readiness(
        {
            "total_components": 8,
            "backend_breakdown": {"yolo": 8},
            "average_semantic_confidence": 0.9,
            "review_required": False,
        },
        {"confidence": 0.6},
        reference_aoi={"status": "PASS", "component_delta": 0},
        topology_aoi={"status": "PASS", "topology_delta": 0},
        scan_quality={"score": 0.9, "reason": "tracked"},
        golden_aoi={
            "status": "FAIL",
            "defect_count": 2,
            "defects": [{"severity": 0.9}],
        },
    )

    assert result["golden_status"] == "FAIL"
    assert result["golden_defect_count"] == 2
    assert result["readiness"] != "pilot_ready"
    assert result["blockers"][0].startswith("golden image AOI found")
