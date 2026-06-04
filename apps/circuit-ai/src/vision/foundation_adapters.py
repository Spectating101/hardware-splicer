"""Optional foundation-model adapter contracts for Circuit-AI vision.

The production API should not fail just because SAM 2, Grounding DINO, Florence,
or PaddleOCR are not installed locally. This module records the backend contract,
checks availability without importing heavy packages, and builds an assist plan
that the scan/intake/frontend layers can display or execute later.
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class FoundationBackend:
    """Optional model/tool backend that can assist the core detector."""

    backend_id: str
    display_name: str
    lane: str
    import_names: tuple[str, ...]
    source_url: str
    install_hint: str
    best_for: tuple[str, ...]
    output_contract: tuple[str, ...]
    priority: int
    env_any_names: tuple[str, ...] = ()


def foundation_backend_registry() -> tuple[FoundationBackend, ...]:
    """Return optional foundation backends and their stable contracts."""

    return (
        FoundationBackend(
            backend_id="ultralytics",
            display_name="Ultralytics YOLO",
            lane="production_component_detection",
            import_names=("ultralytics",),
            source_url="https://docs.ultralytics.com/models/yolo11/",
            install_hint="pip install ultralytics",
            best_for=(
                "fast trained component boxes",
                "batch model benchmarking",
                "edge/deployment-friendly inference",
            ),
            output_contract=("bbox", "class_name", "confidence", "model_id", "provenance"),
            priority=1,
        ),
        FoundationBackend(
            backend_id="qwen_vl",
            display_name="Qwen VL",
            lane="native_vision_language_board_reasoning",
            import_names=(),
            source_url="https://www.alibabacloud.com/help/en/model-studio/",
            install_hint="set QWEN_API_KEY or DASHSCOPE_API_KEY",
            best_for=(
                "native board-photo reasoning",
                "component and connector description",
                "hazard candidate extraction from images",
            ),
            output_contract=("board_evidence", "component_candidates", "hazard_candidates", "provenance"),
            priority=1,
            env_any_names=("QWEN_API_KEY", "DASHSCOPE_API_KEY"),
        ),
        FoundationBackend(
            backend_id="sam2",
            display_name="Meta SAM 2",
            lane="component_masks_and_video_tracking",
            import_names=("sam2",),
            source_url="https://github.com/facebookresearch/sam2",
            install_hint="install from facebookresearch/sam2 following the official README",
            best_for=(
                "component and board masks",
                "corrosion or burn-region masks",
                "repair-video object tracking",
            ),
            output_contract=("mask", "bbox", "prompt_source", "confidence", "provenance"),
            priority=1,
        ),
        FoundationBackend(
            backend_id="grounding_dino",
            display_name="Grounding DINO",
            lane="open_vocab_discovery",
            import_names=("groundingdino",),
            source_url="https://github.com/IDEA-Research/GroundingDINO",
            install_hint="install from IDEA-Research/GroundingDINO following the official README",
            best_for=(
                "open-vocabulary part proposals",
                "defect prompt proposals",
                "unknown electronics triage",
            ),
            output_contract=("bbox", "phrase", "confidence", "prompt", "provenance"),
            priority=1,
        ),
        FoundationBackend(
            backend_id="florence2",
            display_name="Microsoft Florence-2",
            lane="caption_ocr_grounding",
            import_names=("transformers", "torch"),
            source_url="https://huggingface.co/microsoft/Florence-2-base",
            install_hint="pip install transformers torch",
            best_for=(
                "dense captions",
                "OCR-style region context",
                "phrase grounding second opinions",
            ),
            output_contract=("text", "bbox", "task", "confidence", "provenance"),
            priority=2,
        ),
        FoundationBackend(
            backend_id="paddleocr",
            display_name="PaddleOCR",
            lane="marking_ocr",
            import_names=("paddleocr",),
            source_url="https://github.com/PaddlePaddle/PaddleOCR",
            install_hint="install paddleocr and the matching paddlepaddle CPU/GPU package",
            best_for=(
                "IC markings",
                "silkscreen and connector labels",
                "manual or warning-label text",
            ),
            output_contract=("text", "bbox", "confidence", "language", "provenance"),
            priority=2,
        ),
        FoundationBackend(
            backend_id="easyocr",
            display_name="EasyOCR",
            lane="marking_ocr",
            import_names=("easyocr",),
            source_url="https://github.com/JaidedAI/EasyOCR",
            install_hint="pip install easyocr",
            best_for=("current OCR fallback", "component crop text", "silkscreen text"),
            output_contract=("text", "confidence", "provenance"),
            priority=3,
        ),
        FoundationBackend(
            backend_id="supervision",
            display_name="Roboflow supervision",
            lane="dataset_evaluation_and_visualization",
            import_names=("supervision",),
            source_url="https://github.com/roboflow/supervision",
            install_hint="pip install supervision",
            best_for=("annotation transforms", "visual QA overlays", "offline dataset metrics"),
            output_contract=("dataset", "annotations", "metrics", "visualization_path"),
            priority=3,
        ),
    )


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _configured_env_any(names: tuple[str, ...]) -> bool:
    if any(os.getenv(name) for name in names):
        return True
    if {"QWEN_API_KEY", "DASHSCOPE_API_KEY"} & set(names):
        try:
            from src.config import settings

            return bool(settings.qwen_api_key or settings.dashscope_api_key)
        except Exception:
            return False
    return False


def foundation_backend_status(backend: FoundationBackend) -> dict[str, Any]:
    """Return availability metadata for one backend without heavy imports."""

    missing = [name for name in backend.import_names if not _module_available(name)]
    adapter_backend = "native"
    missing_native_imports = list(missing)
    if backend.backend_id == "grounding_dino" and missing:
        hf_missing = [name for name in ("transformers", "torch") if not _module_available(name)]
        if not hf_missing:
            missing = []
            adapter_backend = "transformers"
    missing_env_vars = []
    env_configured = _configured_env_any(backend.env_any_names) if backend.env_any_names else False
    if backend.env_any_names and not env_configured:
        missing_env_vars = list(backend.env_any_names)
    return {
        **asdict(backend),
        "available": len(missing) == 0 and not missing_env_vars,
        "missing_imports": missing,
        "missing_env_vars": missing_env_vars,
        "api_key_configured": env_configured,
        "missing_native_imports": missing_native_imports,
        "adapter_backend": adapter_backend,
    }


def foundation_backend_statuses() -> list[dict[str, Any]]:
    """Return availability metadata for all optional backends."""

    return [foundation_backend_status(backend) for backend in foundation_backend_registry()]


def prompt_bank_for_case(
    *,
    device_hint: str | None = None,
    symptoms: tuple[str, ...] = (),
    goal: str = "unknown_electronics_intake",
) -> tuple[str, ...]:
    """Build conservative open-vocabulary prompts for unknown electronics."""

    base = [
        "printed circuit board",
        "microcontroller",
        "integrated circuit",
        "capacitor",
        "resistor",
        "diode",
        "transistor",
        "voltage regulator",
        "crystal oscillator",
        "connector",
        "USB port",
        "battery connector",
        "motor driver",
        "relay",
        "fuse",
        "burn mark",
        "corrosion",
        "missing component",
        "broken solder joint",
    ]
    if device_hint:
        hint = device_hint.strip()
        if hint:
            base.extend(
                [
                    hint,
                    f"{hint} main board",
                    f"{hint} connector",
                    f"{hint} power section",
                ]
            )
    for symptom in symptoms:
        text = symptom.strip()
        if not text:
            continue
        if "heat" in text.lower() or "burn" in text.lower():
            base.extend(["overheated component", "charred component", "burnt capacitor"])
        if "charge" in text.lower() or "charging" in text.lower() or "usb" in text.lower():
            base.extend(["charging port", "USB connector", "charging IC"])
        if "motor" in text.lower() or "spin" in text.lower():
            base.extend(["motor connector", "motor driver IC", "fan header"])
    if goal in {"salvage", "recommerce", "listing"}:
        base.extend(["useful module", "wireless module", "display module", "sensor module", "power supply module"])
    return tuple(dict.fromkeys(base))


def build_foundation_assist_plan(
    *,
    device_hint: str | None = None,
    symptoms: tuple[str, ...] = (),
    has_video: bool = False,
    goal: str = "unknown_electronics_intake",
) -> dict[str, Any]:
    """Create an executable plan for optional foundation-model assistance."""

    statuses = foundation_backend_statuses()
    status_by_id = {item["backend_id"]: item for item in statuses}
    prompts = prompt_bank_for_case(device_hint=device_hint, symptoms=symptoms, goal=goal)

    steps: list[dict[str, Any]] = [
        {
            "id": "quality_polish",
            "uses": "src/vision/image_polisher.py",
            "why": "normalize lighting/sharpness before detectors and OCR",
            "required": True,
        },
        {
            "id": "trained_detector",
            "uses": "src/vision/detector.py",
            "backend": "ultralytics" if status_by_id.get("ultralytics", {}).get("available") else "classical",
            "why": "production path starts with measured component boxes",
            "required": True,
        },
        {
            "id": "ocr_markings",
            "uses": "src/vision/ocr_engine.py",
            "backend": (
                "paddleocr"
                if status_by_id.get("paddleocr", {}).get("available")
                else "easyocr/tesseract"
            ),
            "why": "markings and labels connect vision to datasheets and repair evidence",
            "required": False,
        },
        {
            "id": "qwen_vl_board_reasoning",
            "uses": "src/vision/qwen_board_vision.py",
            "backend": "qwen_vl" if status_by_id.get("qwen_vl", {}).get("available") else "not_configured",
            "why": "ask native vision-language model for board evidence and hazard candidates; deterministic gates still decide release",
            "required": False,
            "output_contract": ("board_evidence", "component_candidates", "hazard_candidates", "provenance"),
            "api_endpoint": "/vision/qwen/board-evidence",
        },
        {
            "id": "open_vocab_proposals",
            "uses": "Grounding DINO or Florence-2",
            "backend": (
                "grounding_dino"
                if status_by_id.get("grounding_dino", {}).get("available")
                else "florence2"
                if status_by_id.get("florence2", {}).get("available")
                else "not_available"
            ),
            "why": "discover unlabeled useful parts and likely defect regions",
            "required": False,
            "prompt_count": len(prompts),
        },
        {
            "id": "mask_refinement",
            "uses": "SAM 2",
            "backend": "sam2" if status_by_id.get("sam2", {}).get("available") else "not_available",
            "why": "convert boxes/prompts into masks for defects, cutouts, and video tracking",
            "required": False,
        },
        {
            "id": "review_and_retrain",
            "uses": "eval/competitive_engine and scripts/train_pcb_detector.py",
            "why": "foundation outputs become reviewed training data, not production truth",
            "required": True,
        },
    ]

    if has_video:
        steps.insert(
            -1,
            {
                "id": "video_part_tracking",
                "uses": "SAM 2 video predictor when installed",
                "backend": "sam2" if status_by_id.get("sam2", {}).get("available") else "not_available",
                "why": "keep repair steps attached to the same part through disassembly footage",
                "required": False,
            },
        )

    return {
        "goal": goal,
        "device_hint": device_hint or "",
        "symptoms": list(symptoms),
        "prompt_bank": prompts,
        "backend_statuses": statuses,
        "steps": steps,
        "claim_boundary": (
            "Foundation backends propose evidence and labels. Production AOI decisions still require "
            "trained detectors, golden references, measurements, or human-reviewed labels."
        ),
    }
