from pathlib import Path

from src.vision.model_resolver import is_generic_yolo_path, resolve_pcb_model_path, resolve_pcb_model_paths


def test_generic_yolo_path_is_not_treated_as_pcb_model():
    assert is_generic_yolo_path("models/yolo11n.pt")
    assert is_generic_yolo_path("models/yolov8n.pt")
    assert is_generic_yolo_path("models/yolo/yolov8m.pt")
    assert not is_generic_yolo_path("models/pcb/electrocom61_v1.pt")


def test_resolver_prefers_real_pcb_model_over_generic_config():
    resolved = resolve_pcb_model_path("models/yolov8n.pt")
    assert resolved is not None
    assert Path(resolved).name == "pcb_components_yolo11n_thawed.pt"
    assert Path(resolved).exists()


def test_resolver_ignores_generic_yolo_env_override(monkeypatch):
    monkeypatch.setenv("CIRCUIT_AI_PCB_MODEL_PATH", "models/yolo11n.pt")
    resolved = resolve_pcb_model_path(None)
    assert resolved is not None
    assert Path(resolved).name == "pcb_components_yolo11n_thawed.pt"


def test_resolver_returns_primary_and_local_specialist_models():
    resolved = resolve_pcb_model_paths("models/yolov8n.pt")
    names = [Path(path).name for path in resolved]
    assert names[:2] == ["pcb_components_yolo11n_thawed.pt", "electrocom61_nano_320.pt"]
