"""Optional live vision test — only runs when explicitly enabled and API key is set."""
from __future__ import annotations

import os

import pytest

from hardware_splicer.vision_evidence_assistant import build_vision_evidence_report


@pytest.mark.skipif(
    os.getenv("HARDWARE_SPLICER_RUN_VISION_LIVE", "").strip().lower() not in {"1", "true", "yes", "on"},
    reason="set HARDWARE_SPLICER_RUN_VISION_LIVE=1 to run live vision",
)
@pytest.mark.skipif(
    not (os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")),
    reason="QWEN_API_KEY or DASHSCOPE_API_KEY required for live vision",
)
def test_live_vision_returns_structured_report() -> None:
    intake = {
        "project_name": "vision_smoke",
        "goal": "automatic plant watering",
        "vision_assistance": {
            "enabled": True,
            "provider": "qwen",
            "attachments": [
                {
                    "id": "bench_photo",
                    "path": "examples/intakes/assets/plant_bench_reference.png",
                    "kind": "image",
                }
            ],
        },
    }
    report = build_vision_evidence_report(intake)
    assert report.get("schema_version")
    assert "candidate_count" in report
