import sys, os, base64, io
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "src")
for path in (ROOT, SRC):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    from circuit_agent import CircuitAgent
except ImportError:
    pytest.skip("CircuitAgent not importable", allow_module_level=True)


@pytest.mark.skip("Add a small fixture image path and enable to run smoke test with real model")
def test_golden_image_smoke():
    """
    Smoke test placeholder: load a small fixture image and ensure the agent returns
    detection summary and vision report without errors.
    """
    fixture_path = os.getenv("GOLDEN_IMAGE_PATH", "")
    if not fixture_path or not os.path.exists(fixture_path):
        pytest.skip("No golden image provided")

    with open(fixture_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    agent = CircuitAgent(knowledge_path="knowledge_base")

    import asyncio

    async def run():
        await agent.initialize()
        res = await agent.process_request("smoke test", image_b64=img_b64)
        assert "detection_summary" in res
        assert "vision_report" in res

    asyncio.get_event_loop().run_until_complete(run())
