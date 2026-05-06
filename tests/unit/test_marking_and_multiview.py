import json

import numpy as np

from src.core.ingest import CircuitAnalyzer
from src.intelligence.marking_resolver import MarkingResolver


def test_marking_resolver_matches_known_pinout_and_datasheet():
    detections = [
        {
            "class_name": "ic_chip",
            "bbox": [10, 10, 60, 40],
            "ocr_text": "ATMEGA328P PU",
        },
        {
            "class_name": "connector",
            "bbox": [80, 10, 120, 45],
            "ocr_text": "VIN GND TX RX",
        },
    ]

    result = MarkingResolver().resolve_detections(detections)

    assert result["confidence"] > 0.5
    assert {"VIN", "GND", "TX", "RX"}.issubset(set(result["connector_labels"]))
    atmega = result["components"][0]["candidates"][0]
    assert atmega["part_number"] == "ATMEGA328P"
    assert atmega["pinout"]["pin_count"] == 28
    assert atmega["datasheet"]["manufacturer"] == "Microchip"
    json.dumps(result)


def test_board_understanding_uses_marking_evidence_to_boost_role():
    analyzer = CircuitAnalyzer()
    detections = [
        {"class_name": "connector", "bbox": [10, 10, 30, 80], "confidence": 0.8, "ocr_text": "TX RX GND"},
        {"class_name": "ic_chip", "bbox": [60, 20, 120, 80], "confidence": 0.82, "ocr_text": "CP2102"},
    ]
    marking = analyzer._resolve_markings(detections)
    board = analyzer._infer_board_understanding(
        np.zeros((120, 160, 3), dtype=np.uint8),
        detections,
        {"total_components": 2, "backend_breakdown": {"yolo": 2}, "detection_quality": "high"},
        {"confidence": 0.25},
        {"defect_count": 0, "defects": []},
        marking,
    )

    assert board["board_identity"]["primary_type"] in {"io_interface_or_adapter", "controller_or_embedded_compute"}
    assert board["machine_context"]["pinout_evidence"]
    assert "TX" in board["machine_context"]["connector_label_evidence"]


def test_multi_view_fusion_combines_roles_labels_and_pinouts():
    analyzer = CircuitAnalyzer()
    view1 = {
        "view_id": "view_1",
        "detection_summary": {"components_by_type": {"connector": 1}},
        "marking_analysis": {"connector_labels": ["VIN", "GND"]},
        "board_understanding": {
            "confidence": 0.55,
            "board_identity": {
                "primary_type": "io_interface_or_adapter",
                "confidence": 0.55,
                "evidence": ["1 connector"],
                "alternatives": [],
            },
            "functional_blocks": [{"block_type": "io_connectivity"}],
            "machine_context": {"pinout_evidence": []},
            "reuse_and_splice": {"candidate_regions": [{"region_id": "crop_1", "confidence": 0.5}]},
        },
    }
    view2 = {
        "view_id": "view_2",
        "detection_summary": {"components_by_type": {"ic_chip": 1}},
        "marking_analysis": {"connector_labels": ["TX", "RX"]},
        "board_understanding": {
            "confidence": 0.7,
            "board_identity": {
                "primary_type": "controller_or_embedded_compute",
                "confidence": 0.7,
                "evidence": ["ATMEGA328P marking"],
                "alternatives": [{"type": "io_interface_or_adapter", "confidence": 0.45, "evidence": ["TX RX"]}],
            },
            "functional_blocks": [{"block_type": "compute_control"}],
            "machine_context": {
                "pinout_evidence": [{"part_number": "ATMEGA328P", "pin_count": 28}],
            },
            "reuse_and_splice": {"candidate_regions": [{"region_id": "crop_2", "confidence": 0.7}]},
        },
    }

    fused = analyzer._fuse_board_views([view1, view2])

    assert fused["board_identity"]["primary_type"] == "controller_or_embedded_compute"
    assert fused["confidence"] > 0.7
    assert {"VIN", "GND", "TX", "RX"}.issubset(set(fused["machine_context"]["connector_label_evidence"]))
    assert fused["machine_context"]["pinout_evidence"][0]["part_number"] == "ATMEGA328P"
    assert fused["reuse_and_splice"]["candidate_regions"][0]["view_id"] == "view_2"
    json.dumps(fused)
