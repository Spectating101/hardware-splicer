"""
Golden image smoke test scaffold.
Set GOLDEN_IMAGE_PATH to a real image to enable.
"""

import os
import sys
import base64
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "src")
for path in (ROOT, SRC):
    if path not in sys.path:
        sys.path.insert(0, path)

from circuit_agent import CircuitAgent

# Default to a real sample in the repo so the smoke test can run out of the box.
DEFAULT_GOLDEN = os.path.join(
    ROOT,
    "datasets",
    "ElectroCom61 A Multiclass Dataset for Detection of Electronic Components",
    "ElectroCom-61_v2",
    "test",
    "images",
    "IMG_20240228_122819_jpg.rf.549f931f79ce6af1acb40d1d98720cd7.jpg",
)
GOLDEN_IMAGE_PATH = os.getenv("GOLDEN_IMAGE_PATH", DEFAULT_GOLDEN)


@pytest.mark.asyncio
async def test_golden_image_smoke():
    if not GOLDEN_IMAGE_PATH or not os.path.exists(GOLDEN_IMAGE_PATH):
        pytest.skip("Set GOLDEN_IMAGE_PATH to run golden image smoke test")

    with open(GOLDEN_IMAGE_PATH, "rb") as f:
        img_str = base64.b64encode(f.read()).decode()

    agent = CircuitAgent(knowledge_path="knowledge_base")
    resp = await agent.process_request("Smoke test", image_b64=img_str, mode="standard")

    det_summary = resp.get("detection_summary", {})
    det_count = det_summary.get("count", 0)
    quality = det_summary.get("quality", "none")

    assert det_count >= 5, f"Expected at least 5 detections, got {det_count}"
    assert quality in ("medium", "high"), f"Detection quality too low: {quality}"
    assert "Board Type" in resp.get("vision_report", ""), "Board classification missing in report"
