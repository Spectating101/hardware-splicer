"""Model path discovery for PCB component detectors."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional


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


PCB_MODEL_CANDIDATES = (
    "models/pcb/pcb_components_yolo11n_thawed.pt",
    "models/pcb/electrocom61_nano_320.pt",
    "pcb_runs/electrocom61_nano_320/weights/best.pt",
    "models/pcb/electrocom61_v1.pt",
    "pcb_runs/electrocom61_v2/weights/best.pt",
    "models/pcb/electrocom61_v1.onnx",
)


def is_generic_yolo_path(path: str | os.PathLike[str] | None) -> bool:
    if not path:
        return False
    return Path(path).name.lower() in GENERIC_YOLO_FILENAMES


def existing_model_path(paths: Iterable[str | os.PathLike[str] | None]) -> Optional[str]:
    for raw_path in paths:
        if not raw_path:
            continue
        path = Path(raw_path)
        if path.exists() and path.is_file():
            return str(path)
    return None


def existing_model_paths(paths: Iterable[str | os.PathLike[str] | None]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for raw_path in paths:
        if not raw_path:
            continue
        path = Path(raw_path)
        if path.exists() and path.is_file():
            resolved = str(path)
            if resolved not in seen:
                found.append(resolved)
                seen.add(resolved)
    return found


def resolve_pcb_model_path(configured_path: str | None = None) -> Optional[str]:
    """Resolve the best available PCB detector model.

    A generic COCO YOLO model is intentionally skipped for PCB detection. It can
    be useful as a smoke-test dependency, but it is not a component detector.
    """

    env_path = os.getenv("CIRCUIT_AI_PCB_MODEL_PATH")
    env_is_pcb = env_path and not is_generic_yolo_path(env_path)
    configured_is_pcb = configured_path and not is_generic_yolo_path(configured_path)

    return existing_model_path(
        (
            env_path if env_is_pcb else None,
            configured_path if configured_is_pcb else None,
            *PCB_MODEL_CANDIDATES,
        )
    )


def resolve_pcb_model_paths(configured_path: str | None = None) -> list[str]:
    """Resolve all available PCB detector models in priority order."""

    env_path = os.getenv("CIRCUIT_AI_PCB_MODEL_PATH")
    env_is_pcb = env_path and not is_generic_yolo_path(env_path)
    configured_is_pcb = configured_path and not is_generic_yolo_path(configured_path)

    return existing_model_paths(
        (
            env_path if env_is_pcb else None,
            configured_path if configured_is_pcb else None,
            *PCB_MODEL_CANDIDATES,
        )
    )
