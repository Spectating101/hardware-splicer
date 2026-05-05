import json

import numpy as np

from src.core.ingest import CircuitAnalyzer
from src.intelligence.trace_analyzer import Connection, Trace, TraceAnalyzer
from src.vision.defect_detector import DefectDetection


def test_trace_analyzer_accepts_detector_dicts_for_nearby_components():
    analyzer = TraceAnalyzer()
    components = [
        {
            "class_name": "connector",
            "bbox": [10.0, 10.0, 30.0, 30.0],
            "center": [20.0, 20.0],
        }
    ]

    assert analyzer._find_nearby_components((22, 21), components, radius=10) == ["connector"]


def test_trace_issue_detection_is_bounded_for_dense_maps(monkeypatch):
    analyzer = TraceAnalyzer()
    analyzer.max_short_check_traces = 2
    calls = {"count": 0}

    def fake_distance(_trace1, _trace2):
        calls["count"] += 1
        return 100.0

    monkeypatch.setattr(analyzer, "_minimum_trace_distance", fake_distance)
    traces = [
        Trace(
            trace_id=f"trace_{idx}",
            start_point=(idx, 0),
            end_point=(idx + 10, 0),
            path_points=[(idx, 0), (idx + 10, 0)],
            width_px=8,
            length_px=float(idx + 1),
        )
        for idx in range(5)
    ]

    issues = analyzer._detect_trace_issues(traces, [])

    assert calls["count"] == 1
    assert any(issue["issue"] == "Dense trace map truncated" for issue in issues)


def test_circuit_analyzer_returns_serializable_visual_topology(monkeypatch):
    analyzer = CircuitAnalyzer()
    detection = {
        "class_name": "connector",
        "bbox": [10.0, 10.0, 30.0, 30.0],
        "center": [20.0, 20.0],
        "confidence": 0.8,
        "semantic_confidence": 0.8,
        "provenance": {"backend": "yolo"},
    }
    trace = Trace(
        trace_id="trace_1",
        start_point=(20, 20),
        end_point=(80, 20),
        path_points=[(20, 20), (50, 20), (80, 20)],
        width_px=4,
        length_px=60,
    )
    connection = Connection(
        component1="connector",
        component2="capacitor",
        trace_id="trace_1",
        connection_type="direct",
    )

    monkeypatch.setattr(analyzer.detector, "preprocess_image", lambda image: image)
    monkeypatch.setattr(analyzer.detector, "detect_components", lambda *_args, **_kwargs: [detection])
    monkeypatch.setattr(
        analyzer.detector,
        "get_detection_summary",
        lambda _detections: {
            "total_components": 1,
            "components_by_type": {"connector": 1},
            "backend_breakdown": {"yolo": 1},
            "average_confidence": 0.8,
            "average_semantic_confidence": 0.8,
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
        lambda *_args, **_kwargs: {
            "traces": [trace],
            "connections": [connection],
            "trace_count": 1,
            "connection_count": 1,
            "issues": [],
            "scale_mm_per_px": None,
        },
    )
    monkeypatch.setattr(
        analyzer.defect_detector,
        "detect_defects",
        lambda *_args, **_kwargs: [
            DefectDetection(
                defect_type="solder_bridge",
                bbox=[40, 42, 62, 48],
                confidence=0.74,
                severity=0.9,
                description="candidate solder bridge",
                repair_action="Inspect and remove excess solder if confirmed",
                metadata={"detector": "test", "score": np.float32(0.74)},
            )
        ],
    )

    results = analyzer.analyze_pcb(np.zeros((120, 120, 3), dtype=np.uint8), backend="hybrid", enable_ocr=False)

    assert results["visual_topology"]["trace_count"] == 1
    assert results["visual_topology"]["connection_count"] == 1
    assert results["defect_inspection"]["defect_count"] == 1
    assert results["defect_inspection"]["defects"][0]["defect_type"] == "solder_bridge"
    assert results["aoi_inspection"]["defect_candidate_count"] == 1
    assert results["aoi_inspection"]["readiness"] in {"prototype_ready", "pilot_ready"}
    json.dumps(results)


def test_circuit_analyzer_downscales_large_visual_topology_inputs(monkeypatch):
    analyzer = CircuitAnalyzer()
    captured = {}
    detection = {
        "class_name": "connector",
        "bbox": [100.0, 200.0, 300.0, 400.0],
        "center": [200.0, 300.0],
        "confidence": 0.8,
        "semantic_confidence": 0.8,
        "provenance": {"backend": "yolo"},
    }
    summary = {
        "total_components": 1,
        "backend_breakdown": {"yolo": 1},
        "average_semantic_confidence": 0.8,
        "review_required": False,
    }

    def fake_analyze_traces(image, detections):
        captured["shape"] = image.shape
        captured["center"] = detections[0]["center"]
        return {
            "traces": [],
            "connections": [],
            "trace_count": 0,
            "connection_count": 0,
            "issues": [],
            "scale_mm_per_px": None,
        }

    monkeypatch.setattr(analyzer.trace_analyzer, "analyze_traces", fake_analyze_traces)

    topology = analyzer._analyze_visual_topology(
        np.zeros((2200, 1100, 3), dtype=np.uint8),
        [detection],
        summary,
    )

    assert captured["shape"][:2] == (1600, 800)
    assert captured["center"] == [200.0 * (1600 / 2200), 300.0 * (1600 / 2200)]
    assert topology["analysis_resize_scale"] == round(1600 / 2200, 4)
