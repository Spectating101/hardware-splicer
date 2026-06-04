import json

import numpy as np

from src.intelligence.salvage_pipeline import SalvageToProductPipeline
from src.intelligence.salvage_workflow_engine import SalvageWorkflowEngine


class FakeAnalyzer:
    def analyze_pcb(self, image, backend=None, enable_ocr=None):
        return {
            "detection_summary": {"total_components": 2, "components_by_type": {"ic_chip": 1, "connector": 1}},
            "board_understanding": {
                "board_identity": {"primary_type": "controller_or_embedded_compute", "confidence": 0.72},
                "functional_blocks": [{"block_type": "compute_control"}],
            },
            "marking_analysis": {
                "confidence": 0.82,
                "components": [{"candidates": [{"part_number": "ESP32"}]}],
            },
            "machine_connection_map": {
                "connector_count": 1,
                "interfaces": [{"type": "power"}, {"type": "uart_serial"}],
            },
            "defect_inspection": {"defect_count": 0},
            "salvage_opportunities": {
                "asset_summary": {
                    "capabilities": {"controller": 1, "wireless": 1, "power": 1, "connector": 1},
                    "parts": {"esp32": 1},
                    "connector_count": 1,
                    "defect_count": 0,
                    "evidence": ["part marking: esp32", "interface: power"],
                }
            },
        }

    def get_analysis_summary(self, result):
        return {"summary_text": "fake scan summary"}


def test_salvage_pipeline_writes_complete_artifacts(tmp_path):
    pipeline = SalvageToProductPipeline(
        analyzer=FakeAnalyzer(),
        workflow=SalvageWorkflowEngine(tmp_path / "inventory.json"),
    )

    result = pipeline.run(
        images=[np.zeros((16, 16, 3), dtype=np.uint8)],
        listings=[
            {
                "title": "ESP32 relay lot",
                "price_usd": 5.0,
                "shipping_usd": 1.0,
                "expected_capabilities": ["wireless", "actuator_driver", "power"],
                "expected_parts": ["esp32", "relay"],
            }
        ],
        commit=True,
        output_dir=tmp_path / "artifacts",
    )

    paths = result["artifact_paths"]
    assert set(paths) >= {"analysis", "workflow_report", "build_package", "markdown_report"}
    assert (tmp_path / "artifacts" / "README.md").exists()
    assert result["workflow_report"]["build_package"]["mode"] == "salvage_build_package"
    assert "Salvage-To-Product Report" in result["markdown_report"]
    json.loads((tmp_path / "artifacts" / "workflow_report.json").read_text())


def test_salvage_pipeline_can_run_listing_only(tmp_path):
    pipeline = SalvageToProductPipeline(
        analyzer=FakeAnalyzer(),
        workflow=SalvageWorkflowEngine(tmp_path / "inventory.json"),
    )

    result = pipeline.run(
        listings=[
            {
                "title": "cheap ESP32 sensor display lot",
                "price_usd": 8.0,
                "expected_capabilities": ["controller", "wireless", "sensor_or_adc", "display_or_ui"],
                "expected_parts": ["esp32", "bme280", "oled_ssd1306"],
            }
        ],
        commit=False,
    )

    assert result["workflow_report"]["build_package"]["mode"] == "salvage_build_package"
    assert "No image analysis" in result["markdown_report"]
