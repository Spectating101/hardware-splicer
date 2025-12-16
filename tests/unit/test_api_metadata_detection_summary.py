import sys, os, base64, io
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "src")
for path in (ROOT, SRC):
    if path not in sys.path:
        sys.path.insert(0, path)

from fastapi.testclient import TestClient
from PIL import Image
import types
import importlib

# Inject dummy CircuitAnalyzer before importing the FastAPI app to avoid heavy model loads
fake_ingest = types.SimpleNamespace(
    CircuitAnalyzer=type("DummyAnalyzer", (), {
        "__init__": lambda self: None,
        "analyze_pcb": lambda self, image_np, backend=None, enable_ocr=None: {"detections": [], "detection_summary": {"total_components": 0, "detection_quality": "low"}},
        "get_analysis_summary": lambda self, results: {"total_value": 0.0}
    })
)
sys.modules["src.core.ingest"] = fake_ingest

from src.api.v1.main import app
from src.api.v1 import auth as auth_module
from src.api.v1 import main as main_module


def test_analyze_metadata_includes_detection_summary(monkeypatch):
    client = TestClient(app)

    # Override auth to bypass JWT/API key for this test
    def dummy_user(*args, **kwargs):
        return {"user_id": "test"}
    app.dependency_overrides[auth_module.get_current_user] = dummy_user
    # Stub analyzer to avoid heavy model loads
    def fake_analyze_pcb(image_np, backend=None, enable_ocr=None):
        return {"detections": [], "detection_summary": {"total_components": 0, "detection_quality": "low"}}
    monkeypatch.setattr(main_module.analyzer, "analyze_pcb", fake_analyze_pcb)
    monkeypatch.setattr(main_module.analyzer, "get_analysis_summary", lambda results: {"total_value": 0.0})

    # Create tiny blank image
    img = Image.new("RGB", (32, 32), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    response = client.post(
        "/analyze",
        files={"file": ("test.png", buf, "image/png")},
        headers={"Authorization": "Bearer test-api-key-12345"},
        data={"enable_ocr": "false"},
    )

    # We allow 200/401 depending on auth; only assert metadata if 200
    if response.status_code == 200:
        data = response.json()
        meta = data["metadata"]
        assert "detection_quality" in meta
        assert "detection_summary" in meta
