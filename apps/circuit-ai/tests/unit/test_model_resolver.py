from pathlib import Path

import json

import src.vision.model_resolver as resolver
from src.vision.model_resolver import is_generic_yolo_path, resolve_pcb_model_path, resolve_pcb_model_paths


def test_generic_yolo_path_is_not_treated_as_pcb_model():
    assert is_generic_yolo_path("models/yolo11n.pt")
    assert is_generic_yolo_path("models/yolov8n.pt")
    assert is_generic_yolo_path("models/yolo/yolov8m.pt")
    assert not is_generic_yolo_path("models/pcb/electrocom61_v1.pt")


def test_resolver_prefers_real_pcb_model_over_generic_config():
    resolved = resolve_pcb_model_path("models/yolov8n.pt")
    assert resolved is not None
    assert Path(resolved).name == "electrocom61_nano_320.pt"
    assert Path(resolved).exists()


def test_resolver_ignores_generic_yolo_env_override(monkeypatch):
    monkeypatch.setenv("CIRCUIT_AI_PCB_MODEL_PATH", "models/yolo11n.pt")
    resolved = resolve_pcb_model_path(None)
    assert resolved is not None
    assert Path(resolved).name == "electrocom61_nano_320.pt"


def test_resolver_returns_primary_and_local_specialist_models():
    resolved = resolve_pcb_model_paths("models/yolov8n.pt")
    names = [Path(path).name for path in resolved]
    assert names[0] == "electrocom61_nano_320.pt"
    assert "pcb_components_yolo11n_thawed.pt" in names
    assert "electrocom61_nano_320.pt" in names


def test_resolver_honors_local_benchmark_ranking(monkeypatch, tmp_path):
    first = tmp_path / "first.pt"
    second = tmp_path / "second.pt"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    ranking_file = tmp_path / "model_rankings.json"
    ranking_file.write_text(
        json.dumps({"rankings": [{"model_path": str(second)}, {"model_path": str(first)}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(resolver, "RANKING_FILE", ranking_file)

    assert resolver.existing_model_paths([str(first), str(second)]) == [str(second), str(first)]


def test_resolver_honors_explicit_configured_model_before_rankings(monkeypatch, tmp_path):
    preferred = tmp_path / "preferred.pt"
    ranked = tmp_path / "ranked.pt"
    preferred.write_bytes(b"preferred")
    ranked.write_bytes(b"ranked")
    ranking_file = tmp_path / "model_rankings.json"
    ranking_file.write_text(
        json.dumps({"rankings": [{"model_path": str(ranked)}, {"model_path": str(preferred)}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(resolver, "RANKING_FILE", ranking_file)
    monkeypatch.setattr(resolver, "PCB_MODEL_CANDIDATES", (str(ranked), str(preferred)))

    assert resolver.resolve_pcb_model_path(str(preferred)) == str(preferred)
    assert resolver.resolve_pcb_model_paths(str(preferred))[:2] == [str(preferred), str(ranked)]


def test_resolver_skips_onnx_when_runtime_is_missing(monkeypatch, tmp_path):
    onnx_model = tmp_path / "model.onnx"
    pt_model = tmp_path / "model.pt"
    onnx_model.write_bytes(b"onnx")
    pt_model.write_bytes(b"pt")
    monkeypatch.setattr(resolver.importlib.util, "find_spec", lambda name: None)
    monkeypatch.setattr(resolver, "PCB_MODEL_CANDIDATES", (str(onnx_model),))

    assert resolver.existing_model_paths([str(onnx_model), str(pt_model)]) == [str(pt_model)]
    assert resolver.resolve_pcb_model_path(str(onnx_model)) is None
