"""Model path discovery for PCB component detectors."""

from __future__ import annotations

import json
import os
import importlib.util
from pathlib import Path
from typing import Iterable, Optional

RANKING_FILE = Path("models/pcb/model_rankings.json")

DEFAULT_UPSTREAM_REPO = "https://github.com/aryan-programmer/pcb-fault-detection"
DEFAULT_UPSTREAM_BRANCH = "master"

PCB_MODEL_CANDIDATES = (
    "models/pcb/pcb_components_yolo11n_thawed.pt",
    "models/pcb/yolo11n_best_fully_thawed.pt",
    "models/pcb/yolo11n_best_small_component.pt",
    "models/pcb/yolo11n_best_zoomed.pt",
    "models/pcb/yolo11n_best_thawed.pt",
    "models/pcb/electrocom61_nano_320.pt",
    "pcb_runs/electrocom61_nano_320/weights/best.pt",
    "models/pcb/electrocom61_v1.pt",
    "pcb_runs/electrocom61_v2/weights/best.pt",
    "models/pcb/yolo11n_best_thawed.onnx",
    "models/pcb/electrocom61_v1.onnx",
)

PCB_REMOTE_MODEL_CATALOG = (
    {
        "file": "yolo11n_best_thawed.pt",
        "url": f"{DEFAULT_UPSTREAM_REPO}/raw/{DEFAULT_UPSTREAM_BRANCH}/pcb-components-detection/yolo11n_best_thawed.pt",
    },
    {
        "file": "yolo11n_best_fully_thawed.pt",
        "url": f"{DEFAULT_UPSTREAM_REPO}/raw/{DEFAULT_UPSTREAM_BRANCH}/pcb-components-detection/yolo11n_best_fully_thawed.pt",
    },
    {
        "file": "yolo11n_best_small_component.pt",
        "url": f"{DEFAULT_UPSTREAM_REPO}/raw/{DEFAULT_UPSTREAM_BRANCH}/pcb-components-detection/yolo11n_best_small_component.pt",
    },
    {
        "file": "yolo11n_best_zoomed.pt",
        "url": f"{DEFAULT_UPSTREAM_REPO}/raw/{DEFAULT_UPSTREAM_BRANCH}/pcb-components-detection/yolo11n_best_zoomed.pt",
    },
    {
        "file": "yolo11n_best_thawed.onnx",
        "url": f"{DEFAULT_UPSTREAM_REPO}/raw/{DEFAULT_UPSTREAM_BRANCH}/pcb-components-detection/yolo11n_best_thawed.onnx",
    },
)


GENERIC_YOLO_FILENAMES = {
    "yolo11n.pt",
    "yolo11s.pt",
    "yolo11m.pt",
    "yolo11l.pt",
    "yolo11x.pt",
    "yolov8n.pt",
    "yolov8s.pt",
    "yolov8m.pt",
    "yolov8l.pt",
    "yolov8x.pt",
}


def is_generic_yolo_path(path: str | os.PathLike[str] | None) -> bool:
    if not path:
        return False
    return Path(path).name.lower() in GENERIC_YOLO_FILENAMES


def is_model_runtime_available(path: str | os.PathLike[str] | None) -> bool:
    """Return whether the current Python environment can execute this model."""

    if not path:
        return False
    suffix = Path(path).suffix.lower()
    if suffix == ".onnx":
        return importlib.util.find_spec("onnxruntime") is not None
    return True


def _normalize_model_path(path: str) -> str:
    normalized = os.path.normcase(os.path.normpath(str(path)))
    return str(Path(normalized))


def list_remote_pcb_models() -> tuple[dict[str, str], ...]:
    """Return remote PCB model candidate descriptors."""

    return PCB_REMOTE_MODEL_CATALOG


def get_model_rankings() -> list[dict[str, object]]:
    """Load ranking metadata produced by benchmarking."""

    if not RANKING_FILE.exists():
        return []
    try:
        with RANKING_FILE.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return []

    rankings = payload.get("rankings") if isinstance(payload, dict) else None
    if not isinstance(rankings, list):
        return []
    return [entry for entry in rankings if isinstance(entry, dict)]


def _ranked_candidates(candidates: list[str]) -> list[str]:
    """Return candidates sorted by benchmark ranking (best first)."""

    rankings = get_model_rankings()
    if not rankings:
        return candidates

    rank_by_path: dict[str, int] = {}
    for idx, entry in enumerate(rankings):
        for key in ("model_path", "path"):
            if key in entry:
                rank_by_path[_normalize_model_path(str(entry[key]))] = idx

    source_order = {_normalize_model_path(item): idx for idx, item in enumerate(candidates)}
    return sorted(
        candidates,
        key=lambda item: (
            rank_by_path.get(_normalize_model_path(item), len(candidates)),
            source_order.get(_normalize_model_path(item), len(candidates)),
        ),
    )


def _existing_model_paths_unranked(paths: Iterable[str | os.PathLike[str] | None]) -> list[str]:
    """Return existing model paths in source order without applying rankings."""

    found: list[str] = []
    seen: set[str] = set()
    for raw_path in paths:
        if not raw_path:
            continue
        path = Path(raw_path)
        if path.exists() and path.is_file() and is_model_runtime_available(path):
            resolved = str(path)
            if resolved not in seen:
                found.append(resolved)
                seen.add(resolved)
    return found


def existing_model_path(paths: Iterable[str | os.PathLike[str] | None]) -> Optional[str]:
    paths_list = [
        str(path)
        for path in existing_model_paths(paths)
        if not is_generic_yolo_path(path)
    ]
    return paths_list[0] if paths_list else None


def existing_model_paths(paths: Iterable[str | os.PathLike[str] | None]) -> list[str]:
    found = _existing_model_paths_unranked(paths)
    return _ranked_candidates(found)


def resolve_pcb_model_path(configured_path: str | None = None) -> Optional[str]:
    """Resolve the best available PCB detector model.

    A generic COCO YOLO model is intentionally skipped for PCB detection. It can
    be useful as a smoke-test dependency, but it is not a component detector.
    """

    env_path = os.getenv("CIRCUIT_AI_PCB_MODEL_PATH")
    env_is_pcb = env_path and not is_generic_yolo_path(env_path)
    configured_is_pcb = configured_path and not is_generic_yolo_path(configured_path)

    explicit = _existing_model_paths_unranked(
        (
            env_path if env_is_pcb else None,
            configured_path if configured_is_pcb else None,
        )
    )
    if explicit:
        return explicit[0]

    return existing_model_path(_ranked_candidates(list(PCB_MODEL_CANDIDATES)))


def resolve_pcb_model_paths(configured_path: str | None = None) -> list[str]:
    """Resolve all available PCB detector models in priority order."""

    env_path = os.getenv("CIRCUIT_AI_PCB_MODEL_PATH")
    env_is_pcb = env_path and not is_generic_yolo_path(env_path)
    configured_is_pcb = configured_path and not is_generic_yolo_path(configured_path)
    ranked = _ranked_candidates(list(PCB_MODEL_CANDIDATES))

    explicit = _existing_model_paths_unranked(
        (
            env_path if env_is_pcb else None,
            configured_path if configured_is_pcb else None,
        )
    )
    ranked_existing = existing_model_paths(ranked)

    ordered: list[str] = []
    seen: set[str] = set()
    for path in (*explicit, *ranked_existing):
        if path not in seen:
            ordered.append(path)
            seen.add(path)
    return ordered
