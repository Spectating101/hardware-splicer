import io
import types
from typing import Dict, Any

from PIL import Image
from starlette.datastructures import UploadFile

from src.api.v1 import main as main_module


def _fake_analysis_result():
    return {
        "detection_summary": {"total_components": 0, "detection_quality": "low", "components_by_type": {}},
        "functionality_analysis": {"project_potential": "none"},
        "visual_topology": {"trace_count": 0, "connection_count": 0, "confidence": 0.0, "uncertainty": "high"},
        "reference_aoi": {"status": "unavailable", "component_delta": 0, "missing": [], "extra": []},
        "topology_aoi": {"status": "PASS", "topology_delta": 0, "missing": [], "extra": []},
        "aoi_inspection": {"readiness": "research_preview"},
        "analysis_metadata": {
            "backend": "hybrid",
            "ocr": True,
            "reference_aoi_status": "unavailable",
            "reference_component_delta": 0,
            "topology_aoi_status": "PASS",
            "topology_aoi_delta": 0,
        },
    }


def _blank_file():
    img = Image.new("RGB", (32, 32), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return UploadFile(filename="test.png", file=buf)


def test_analyze_accepts_reference_topology_json():
    calls: Dict[str, Any] = {}

    def fake_analyze_pcb(image_np, backend=None, enable_ocr=None, reference_counts=None, reference_topology=None):
        calls["reference_topology"] = reference_topology
        return _fake_analysis_result()

    fake_analyzer = types.SimpleNamespace(
        analyze_pcb=fake_analyze_pcb,
        get_analysis_summary=lambda results: {"total_components": 0},
    )

    response = main_module.analyze(
        file=_blank_file(),
        backend="hybrid",
        enable_ocr=False,
        reference_topology='{"nets":{"NET_1":{"nodes":[{"ref":"R1","pin":"1"},{"ref":"R2","pin":"2"}]}}, "components":{"R1":{"value":"10k"},"R2":{"value":"10k"}}}',
        current_user={"user_id": "user-1"},
        analyzer=fake_analyzer,
    )

    assert calls["reference_topology"]["components"]["R1"]["value"] == "10k"
    assert response["metadata"]["reference"]["topology_status"] == "PASS"
    assert response["metadata"]["reference"]["input"]["topology"] is True
    assert response["metadata"]["reference"]["input"]["reference_source"] == "topology_json"


def test_analyze_accepts_reference_topology_file():
    calls: Dict[str, Any] = {}

    def fake_analyze_pcb(image_np, backend=None, enable_ocr=None, reference_counts=None, reference_topology=None):
        calls["reference_topology"] = reference_topology
        return _fake_analysis_result()

    file_payload = (
        b'{"nets":{"NET_1":{"nodes":[{"ref":"R1","pin":"1"},{"ref":"R2","pin":"2"}]}},'
        b'"components":{"R1":{"value":"10k"},"R2":{"value":"10k"}}}'
    )
    ref_file = UploadFile(filename="reference_topology.json", file=io.BytesIO(file_payload))

    fake_analyzer = types.SimpleNamespace(
        analyze_pcb=fake_analyze_pcb,
        get_analysis_summary=lambda results: {"total_components": 0},
    )

    response = main_module.analyze(
        file=_blank_file(),
        backend="hybrid",
        enable_ocr=False,
        reference_topology_file=ref_file,
        current_user={"user_id": "user-1"},
        analyzer=fake_analyzer,
    )

    assert calls["reference_topology"]["components"]["R1"]["value"] == "10k"
    assert response["metadata"]["reference"]["input"]["topology"] is True
    assert response["metadata"]["reference"]["input"]["reference_source"] == "topology_file"
