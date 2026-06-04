import json

import numpy as np

from src.core.ingest import CircuitAnalyzer
from src.intelligence.board_function_inference import BoardFunctionInferencer


def test_infers_controller_board_and_splice_regions():
    detections = [
        {"class_name": "ic_chip", "bbox": [80, 70, 150, 140], "confidence": 0.9, "provenance": {"backend": "yolo"}},
        {"class_name": "crystal", "bbox": [160, 85, 190, 110], "confidence": 0.82, "provenance": {"backend": "yolo"}},
        {"class_name": "connector", "bbox": [10, 50, 45, 160], "confidence": 0.88, "provenance": {"backend": "yolo"}},
        {"class_name": "connector", "bbox": [235, 55, 275, 160], "confidence": 0.84, "provenance": {"backend": "yolo"}},
        {"class_name": "resistor", "bbox": [90, 155, 130, 170], "confidence": 0.8, "provenance": {"backend": "yolo"}},
        {"class_name": "capacitor", "bbox": [130, 155, 155, 180], "confidence": 0.8, "provenance": {"backend": "yolo"}},
    ]

    result = BoardFunctionInferencer().analyze(
        detections,
        detection_summary={
            "total_components": len(detections),
            "backend_breakdown": {"yolo": len(detections)},
            "detection_quality": "high",
        },
        visual_topology={"confidence": 0.52},
        defect_inspection={"defect_count": 0, "defects": []},
        image_shape=(220, 300, 3),
    )

    assert result["board_identity"]["primary_type"] == "controller_or_embedded_compute"
    assert result["confidence"] >= 0.5
    assert any(block["block_type"] == "compute_control" for block in result["functional_blocks"])
    assert result["reuse_and_splice"]["candidate_regions"]
    assert result["reuse_and_splice"]["board_spec_for_splicer"]["io_ports"]
    json.dumps(result)


def test_infers_power_board_from_power_signature():
    detections = [
        {"class_name": "Transformer", "bbox": [20, 20, 120, 130], "confidence": 0.86},
        {"class_name": "Diode", "bbox": [135, 40, 160, 65], "confidence": 0.76},
        {"class_name": "Cap4", "bbox": [170, 35, 215, 90], "confidence": 0.78},
        {"class_name": "connector", "bbox": [230, 50, 270, 110], "confidence": 0.8},
        {"class_name": "Mov", "bbox": [130, 90, 155, 125], "confidence": 0.7},
    ]

    result = BoardFunctionInferencer().analyze(
        detections,
        detection_summary={"total_components": len(detections), "backend_breakdown": {"yolo": len(detections)}, "detection_quality": "high"},
        visual_topology={"confidence": 0.45},
        image_shape=(180, 300, 3),
    )

    assert result["board_identity"]["primary_type"] == "power_supply_or_regulator"
    assert any(block["block_type"] == "power_input_protection" for block in result["functional_blocks"])
    assert any(role["role"] == "power_node" for role in result["machine_context"]["likely_roles"])


def test_splice_candidate_confidence_is_penalized_by_overlapping_defect():
    detections = [
        {"class_name": "mosfet", "bbox": [40, 40, 90, 90], "confidence": 0.86},
        {"class_name": "relay", "bbox": [100, 40, 170, 105], "confidence": 0.84},
        {"class_name": "connector", "bbox": [185, 45, 230, 100], "confidence": 0.82},
    ]
    clean = BoardFunctionInferencer().analyze(
        detections,
        detection_summary={"total_components": 3, "backend_breakdown": {"yolo": 3}, "detection_quality": "high"},
        visual_topology={"confidence": 0.4},
        defect_inspection={"defect_count": 0, "defects": []},
        image_shape=(160, 260, 3),
    )
    risky = BoardFunctionInferencer().analyze(
        detections,
        detection_summary={"total_components": 3, "backend_breakdown": {"yolo": 3}, "detection_quality": "high"},
        visual_topology={"confidence": 0.4},
        defect_inspection={
            "defect_count": 1,
            "defects": [{"bbox": [70, 50, 155, 105], "severity": 0.9, "confidence": 0.9}],
        },
        image_shape=(160, 260, 3),
    )

    clean_driver = next(c for c in clean["reuse_and_splice"]["candidate_regions"] if c["source_block"] == "actuator_drive")
    risky_driver = next(c for c in risky["reuse_and_splice"]["candidate_regions"] if c["source_block"] == "actuator_drive")

    assert risky_driver["risk"]["level"] == "high"
    assert risky_driver["confidence"] < clean_driver["confidence"]


def test_circuit_analyzer_includes_board_understanding_in_results(monkeypatch):
    analyzer = CircuitAnalyzer()
    detections = [
        {"class_name": "ic_chip", "bbox": [30, 30, 80, 80], "confidence": 0.9, "provenance": {"backend": "yolo"}},
        {"class_name": "connector", "bbox": [5, 30, 20, 90], "confidence": 0.85, "provenance": {"backend": "yolo"}},
        {"class_name": "crystal", "bbox": [90, 40, 110, 55], "confidence": 0.8, "provenance": {"backend": "yolo"}},
    ]

    monkeypatch.setattr(analyzer.detector, "preprocess_image", lambda image, include_metadata=False: (image, {}) if include_metadata else image)
    monkeypatch.setattr(analyzer.detector, "detect_components", lambda *_args, **_kwargs: detections)
    monkeypatch.setattr(
        analyzer.detector,
        "get_detection_summary",
        lambda _detections: {
            "total_components": len(detections),
            "components_by_type": {"ic_chip": 1, "connector": 1, "crystal": 1},
            "backend_breakdown": {"yolo": len(detections)},
            "average_semantic_confidence": 0.82,
            "detection_quality": "high",
            "semantic_quality": "high",
            "review_required": False,
            "limitations": [],
        },
    )
    monkeypatch.setattr(analyzer.mapper, "map_detections_to_functionality", lambda _detections: {"project_potential": "fair"})
    monkeypatch.setattr(analyzer.mapper, "generate_project_recommendations", lambda _functionality: [])
    monkeypatch.setattr(
        analyzer.trace_analyzer,
        "analyze_traces",
        lambda *_args, **_kwargs: {"traces": [], "connections": [], "trace_count": 0, "connection_count": 0, "issues": []},
    )
    monkeypatch.setattr(analyzer.defect_detector, "detect_defects", lambda *_args, **_kwargs: [])

    results = analyzer.analyze_pcb(np.zeros((120, 140, 3), dtype=np.uint8), backend="yolo", enable_ocr=False)
    summary = analyzer.get_analysis_summary(results)

    assert results["board_understanding"]["board_identity"]["primary_type"] == "controller_or_embedded_compute"
    assert results["analysis_metadata"]["board_type"] == "controller_or_embedded_compute"
    assert results["certainty_ledger"]["overall"]["level"] in {"possible", "likely", "certain"}
    assert results["analysis_metadata"]["certainty_level"] == results["certainty_ledger"]["overall"]["level"]
    assert summary["board_understanding"]["primary_type"] == "controller_or_embedded_compute"
    assert summary["certainty_ledger"]["overall"]["level"] == results["certainty_ledger"]["overall"]["level"]
    assert "Evidence certainty" in summary["summary_text"]
    json.dumps(results)
