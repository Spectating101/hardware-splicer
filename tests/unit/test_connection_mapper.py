import io
import json
import types

import numpy as np
from PIL import Image
from starlette.datastructures import UploadFile

from src.api.v1 import main as main_module
from src.core.ingest import CircuitAnalyzer
from src.intelligence.connection_mapper import ConnectionMapper


def _blank_upload(name="view.png"):
    img = Image.new("RGB", (32, 32), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return UploadFile(filename=name, file=buf)


def test_connection_mapper_builds_power_serial_splice_plan():
    detections = [
        {"class_name": "connector", "bbox": [10, 10, 110, 30], "confidence": 0.84},
        {"class_name": "ic_chip", "bbox": [40, 50, 100, 110], "confidence": 0.86},
    ]
    marking = {
        "connector_labels": ["VIN", "GND", "TX", "RX"],
    }
    board = {
        "board_identity": {"primary_type": "controller_or_embedded_compute"},
        "machine_context": {
            "pinout_evidence": [{"part_number": "CP2102", "pin_count": 28}],
        },
    }

    result = ConnectionMapper().map_connections(detections, marking, board)

    assert result["connector_count"] == 1
    assert any(interface["type"] == "power" for interface in result["interfaces"])
    assert any(interface["type"] == "uart_serial" for interface in result["interfaces"])
    assert result["splice_plan"]["safest_entry_points"] == ["conn_0_connector"]
    assert "logic high voltage" in result["splice_plan"]["required_measurements"]
    json.dumps(result)


def test_circuit_analyzer_summary_includes_machine_connection_map(monkeypatch):
    analyzer = CircuitAnalyzer()
    detections = [
        {"class_name": "connector", "bbox": [5, 10, 80, 30], "confidence": 0.9, "ocr_text": "VIN GND TX RX", "provenance": {"backend": "yolo"}},
        {"class_name": "ic_chip", "bbox": [40, 50, 100, 110], "confidence": 0.88, "ocr_text": "CP2102", "provenance": {"backend": "yolo"}},
    ]

    monkeypatch.setattr(analyzer.detector, "preprocess_image", lambda image, include_metadata=False: (image, {}) if include_metadata else image)
    monkeypatch.setattr(analyzer.detector, "detect_components", lambda *_args, **_kwargs: detections)
    monkeypatch.setattr(
        analyzer.detector,
        "get_detection_summary",
        lambda _detections: {
            "total_components": len(detections),
            "components_by_type": {"connector": 1, "ic_chip": 1},
            "backend_breakdown": {"yolo": len(detections)},
            "average_semantic_confidence": 0.85,
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

    result = analyzer.analyze_pcb(np.zeros((140, 160, 3), dtype=np.uint8), backend="hybrid", enable_ocr=True)
    summary = analyzer.get_analysis_summary(result)

    assert result["machine_connection_map"]["connector_count"] == 1
    assert result["analysis_metadata"]["connector_count"] == 1
    assert summary["machine_connection_map"]["connector_count"] == 1
    assert "Machine connection map" in summary["summary_text"]
    json.dumps(result)


def test_api_multiview_endpoint_uses_analyze_board_set():
    calls = {}

    def fake_analyze_board_set(images, backend=None, enable_ocr=None):
        calls["image_count"] = len(images)
        calls["backend"] = backend
        calls["enable_ocr"] = enable_ocr
        return {
            "mode": "multi_image_board_analysis",
            "summary": "fused summary",
            "fused_board_understanding": {
                "confidence": 0.77,
                "board_identity": {"primary_type": "io_interface_or_adapter"},
            },
            "views": [],
        }

    fake_analyzer = types.SimpleNamespace(
        analyze_board_set=fake_analyze_board_set,
        analyze_pcb=lambda *args, **kwargs: {},
        get_analysis_summary=lambda result: {},
    )

    response = main_module.analyze_multiview(
        files=[_blank_upload("front.png"), _blank_upload("back.png")],
        backend="hybrid",
        enable_ocr=True,
        current_user={"user_id": "user-1"},
        analyzer=fake_analyzer,
    )

    assert calls == {"image_count": 2, "backend": "hybrid", "enable_ocr": True}
    assert response["metadata"]["view_count"] == 2
    assert response["metadata"]["fused_board_type"] == "io_interface_or_adapter"
    assert response["summary"] == "fused summary"
