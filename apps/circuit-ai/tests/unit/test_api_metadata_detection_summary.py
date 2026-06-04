import io
import types

from PIL import Image
from starlette.datastructures import UploadFile

from src.api.v1 import main as main_module


def test_analyze_metadata_includes_detection_summary(monkeypatch):
    def fake_analyze_pcb(image_np, backend=None, enable_ocr=None):
        return {"detections": [], "detection_summary": {"total_components": 0, "detection_quality": "low"}}
    fake_analyzer = types.SimpleNamespace(
        analyze_pcb=fake_analyze_pcb,
        get_analysis_summary=lambda results: {"total_value": 0.0},
    )

    # Create tiny blank image
    img = Image.new("RGB", (32, 32), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    upload = UploadFile(filename="test.png", file=buf)

    data = main_module.analyze(
        file=upload,
        backend=None,
        enable_ocr=False,
        current_user={"user_id": "test"},
        analyzer=fake_analyzer,
    )
    meta = data["metadata"]
    assert "detection_quality" in meta
    assert "detection_summary" in meta
