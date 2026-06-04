import json

from src.intelligence.certainty_ledger import CertaintyLedgerBuilder


def test_certainty_ledger_tracks_strong_board_and_part_evidence():
    ledger = CertaintyLedgerBuilder().build(
        detections=[
            {
                "class_name": "ic_chip",
                "bbox": [20, 20, 80, 80],
                "confidence": 0.92,
                "semantic_confidence": 0.9,
                "ocr_text": "ATMEGA328P",
                "provenance": {"backend": "yolo"},
            },
            {
                "class_name": "connector",
                "bbox": [5, 30, 18, 90],
                "confidence": 0.86,
                "ocr_text": "VIN GND TX RX",
                "provenance": {"backend": "yolo"},
            },
        ],
        detection_summary={
            "total_components": 2,
            "backend_breakdown": {"yolo": 2},
            "average_semantic_confidence": 0.88,
            "review_required": False,
        },
        marking_analysis={
            "confidence": 0.82,
            "connector_labels": ["VIN", "GND", "TX", "RX"],
            "components": [
                {
                    "component_id": "cmp_1_ic_chip",
                    "class_name": "ic_chip",
                    "text": "ATMEGA328P",
                    "part_tokens": ["ATMEGA328P"],
                    "silk_labels": [],
                    "candidates": [
                        {
                            "part_number": "ATMEGA328P",
                            "confidence": 0.72,
                            "match_type": "known_pinout_or_datasheet",
                            "datasheet": {"url": "https://example.test/atmega.pdf"},
                            "pinout": {"pin_count": 28, "package": "DIP"},
                        }
                    ],
                }
            ],
        },
        board_understanding={
            "confidence": 0.74,
            "board_identity": {
                "primary_type": "controller_or_embedded_compute",
                "confidence": 0.74,
                "evidence": ["1 ic_chip", "marking evidence: atmega"],
            },
            "functional_blocks": [
                {
                    "block_type": "compute_control",
                    "label": "Compute/control logic",
                    "component_count": 1,
                    "confidence": 0.7,
                    "function": "Runs firmware/control logic",
                }
            ],
        },
        machine_connection_map={
            "connector_count": 1,
            "interfaces": [{"type": "uart_serial"}, {"type": "power"}],
            "confidence": 0.72,
            "splice_plan": {"required_measurements": ["measure voltage", "confirm logic level"]},
        },
        visual_topology={"trace_count": 6, "connection_count": 3, "confidence": 0.56},
        defect_inspection={"defect_count": 0, "defects": []},
        aoi_inspection={"readiness": "prototype_ready", "score": 0.68, "blockers": []},
        reference_aoi={"status": "PASS"},
        topology_aoi={"status": "PASS"},
        golden_aoi={"status": "unavailable"},
        salvage_opportunities={
            "confidence": 0.72,
            "opportunities": [{"name": "USB/UART Debug Adapter", "score": 0.63}],
            "best_opportunity": {
                "name": "USB/UART Debug Adapter",
                "type": "build_from_salvage",
                "score": 0.63,
                "matched_assets": ["controller", "connector"],
                "missing_assets": [],
                "next_steps": ["verify pinout", "test part"],
            },
        },
    )

    assert ledger["overall"]["level"] in {"likely", "certain"}
    assert ledger["counts"]["total"] >= 6
    assert any(item["claim_type"] == "marking" and item["certainty"] in {"likely", "certain"} for item in ledger["items"])
    assert any("golden reference image" in item for item in ledger["missing_evidence"])
    json.dumps(ledger)


def test_certainty_ledger_exposes_missing_evidence_for_weak_scan():
    ledger = CertaintyLedgerBuilder().build(
        detections=[],
        detection_summary={"total_components": 0, "review_required": True},
        marking_analysis={"components": [], "connector_labels": [], "confidence": 0.0},
        board_understanding={
            "confidence": 0.0,
            "board_identity": {"primary_type": "unknown_board", "confidence": 0.0, "evidence": []},
            "functional_blocks": [],
        },
        visual_topology={"trace_count": 0, "connection_count": 0, "confidence": 0.0},
        aoi_inspection={
            "readiness": "research_preview",
            "score": 0.0,
            "scan_quality": {"score": 0.25, "reason": "blur"},
            "blockers": ["scan quality is below production threshold"],
        },
        reference_aoi={"status": "unavailable"},
        topology_aoi={"status": "unavailable"},
        golden_aoi={"status": "unavailable"},
    )

    assert ledger["overall"]["level"] == "unknown"
    assert ledger["training_queue"]["should_capture"] is True
    assert "whole-board image with visible components" in ledger["missing_evidence"]
    assert any("retake scan" in item for item in ledger["missing_evidence"])
    json.dumps(ledger)
