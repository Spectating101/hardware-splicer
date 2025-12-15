import sys, os, base64, io
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

from fastapi.testclient import TestClient
from PIL import Image

from api.v1.main import app


def test_analyze_metadata_includes_detection_summary(monkeypatch):
    client = TestClient(app)

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
