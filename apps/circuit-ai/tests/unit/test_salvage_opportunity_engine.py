import json

import numpy as np

from src.core.ingest import CircuitAnalyzer
from src.intelligence.salvage_opportunity_engine import SalvageOpportunityEngine


def test_salvage_engine_turns_controller_driver_into_robot_opportunity():
    analysis = {
        "board_understanding": {
            "board_identity": {"primary_type": "controller_or_embedded_compute"},
            "functional_blocks": [
                {"block_type": "compute_control"},
                {"block_type": "actuator_drive"},
            ],
        },
        "marking_analysis": {
            "components": [
                {"candidates": [{"part_number": "ESP32"}]},
                {"candidates": [{"part_number": "ULN2003"}]},
            ]
        },
        "machine_connection_map": {
            "connector_count": 2,
            "interfaces": [{"type": "uart_serial"}, {"type": "power"}],
        },
        "defect_inspection": {"defect_count": 0},
    }

    result = SalvageOpportunityEngine().evaluate(analysis)

    names = [item["name"] for item in result["opportunities"]]
    assert "Robot Motor Controller" in names
    assert result["asset_summary"]["capabilities"]["controller"] >= 1
    assert result["best_opportunity"]["type"] in {"build_from_salvage", "resell_or_stock"}
    json.dumps(result)


def test_salvage_engine_scores_ecommerce_arbitrage_listing():
    result = SalvageOpportunityEngine().evaluate(
        {"board_understanding": {"board_identity": {"primary_type": "unknown_board"}}},
        market_context={
            "listings": [
                {
                    "id": "lot-1",
                    "title": "ESP32 relay boards lot",
                    "price_usd": 6.0,
                    "shipping_usd": 1.0,
                    "labor_usd": 1.0,
                    "failure_rate": 0.05,
                    "fee_rate": 0.1,
                    "expected_capabilities": ["wireless", "actuator_driver", "power"],
                    "expected_parts": ["esp32", "relay"],
                }
            ]
        },
    )

    arbitrage = [item for item in result["opportunities"] if item["type"] == "ecommerce_arbitrage"]
    assert arbitrage
    assert arbitrage[0]["adjusted_margin_usd"] > 0
    assert arbitrage[0]["assumptions"]["fee_rate"] == 0.1


def test_salvage_engine_accepts_direct_asset_summary_from_inventory():
    result = SalvageOpportunityEngine().evaluate(
        {
            "salvage_opportunities": {
                "asset_summary": {
                    "capabilities": {"controller": 1, "wireless": 1, "actuator_driver": 1, "power": 1},
                    "parts": {"esp32": 1, "relay": 1},
                    "connector_count": 1,
                    "defect_count": 0,
                    "evidence": ["inventory asset: esp32 relay"],
                }
            }
        }
    )

    assert result["opportunities"]
    assert result["asset_summary"]["capabilities"]["controller"] >= 1


def test_circuit_analyzer_includes_salvage_opportunities(monkeypatch):
    analyzer = CircuitAnalyzer()
    detections = [
        {"class_name": "connector", "bbox": [5, 10, 80, 30], "confidence": 0.9, "ocr_text": "VIN GND TX RX", "provenance": {"backend": "yolo"}},
        {"class_name": "ic_chip", "bbox": [40, 50, 100, 110], "confidence": 0.88, "ocr_text": "ESP32", "provenance": {"backend": "yolo"}},
        {"class_name": "mosfet", "bbox": [110, 50, 135, 90], "confidence": 0.82, "provenance": {"backend": "yolo"}},
    ]

    monkeypatch.setattr(analyzer.detector, "preprocess_image", lambda image, include_metadata=False: (image, {}) if include_metadata else image)
    monkeypatch.setattr(analyzer.detector, "detect_components", lambda *_args, **_kwargs: detections)
    monkeypatch.setattr(
        analyzer.detector,
        "get_detection_summary",
        lambda _detections: {
            "total_components": len(detections),
            "components_by_type": {"connector": 1, "ic_chip": 1, "mosfet": 1},
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

    assert result["salvage_opportunities"]["opportunities"]
    assert result["analysis_metadata"]["salvage_opportunity_count"] > 0
    assert summary["salvage_opportunities"]["best_opportunity"]
    assert "Best salvage/build opportunity" in summary["summary_text"]
