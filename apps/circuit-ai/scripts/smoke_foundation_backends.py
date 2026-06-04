#!/usr/bin/env python3
"""Smoke-test optional foundation backends without making them API requirements."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.vision.foundation_adapters import foundation_backend_statuses
from src.vision.ocr_engine import OCREngine


def _marking_image() -> np.ndarray:
    image = Image.new("RGB", (420, 120), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
    except Exception:
        font = None
    draw.text((18, 30), "ATMEGA328P VIN", fill="black", font=font)
    return np.array(image)


def _rectangle_image() -> np.ndarray:
    image = Image.new("RGB", (320, 240), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((70, 60, 250, 180), fill=(30, 80, 160))
    return np.array(image)


def _run_ocr(backend: str) -> dict:
    started = time.perf_counter()
    try:
        engine = OCREngine(preferred_backend=backend)
        text = engine.read_text(_marking_image())
        return {
            "backend": backend,
            "status": "ok" if text else "empty",
            "selected_backend": engine.backend,
            "text": text,
            "seconds": round(time.perf_counter() - started, 3),
        }
    except Exception as exc:
        return {
            "backend": backend,
            "status": "error",
            "error": repr(exc),
            "seconds": round(time.perf_counter() - started, 3),
        }


def _run_sam2(checkpoint: str, config: str) -> dict:
    started = time.perf_counter()
    try:
        import torch
        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor

        image = _rectangle_image()
        model = build_sam2(config, checkpoint, device="cpu")
        predictor = SAM2ImagePredictor(model)
        predictor.set_image(image)
        box = np.array([60, 44, 184, 146], dtype=np.float32)
        with torch.inference_mode():
            masks, scores, _logits = predictor.predict(box=box, multimask_output=False)
        return {
            "backend": "sam2",
            "status": "ok",
            "checkpoint": checkpoint,
            "config": config,
            "score": round(float(scores[0]), 5),
            "mask_pixels": int(masks[0].sum()),
            "seconds": round(time.perf_counter() - started, 3),
        }
    except Exception as exc:
        return {
            "backend": "sam2",
            "status": "error",
            "error": repr(exc),
            "seconds": round(time.perf_counter() - started, 3),
        }


def _run_grounding_dino(model_id: str) -> dict:
    started = time.perf_counter()
    try:
        import torch
        from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

        image = Image.fromarray(_rectangle_image())
        text = "a rectangle. a blue object."
        processor = AutoProcessor.from_pretrained(model_id)
        model = AutoModelForZeroShotObjectDetection.from_pretrained(model_id).to("cpu")
        inputs = processor(images=image, text=text, return_tensors="pt")
        with torch.no_grad():
            outputs = model(**inputs)
        try:
            results = processor.post_process_grounded_object_detection(
                outputs,
                inputs.input_ids,
                box_threshold=0.25,
                text_threshold=0.2,
                target_sizes=[image.size[::-1]],
            )[0]
        except TypeError:
            results = processor.post_process_grounded_object_detection(
                outputs,
                threshold=0.25,
                text_threshold=0.2,
                target_sizes=[image.size[::-1]],
            )[0]
        labels = results.get("text_labels") or results.get("labels") or []
        detections = []
        for box, score, label in zip(results["boxes"], results["scores"], labels):
            detections.append(
                {
                    "label": str(label),
                    "score": round(float(score), 5),
                    "box": [round(float(value), 2) for value in box],
                }
            )
        return {
            "backend": "grounding_dino_transformers",
            "status": "ok" if detections else "empty",
            "model_id": model_id,
            "detections": detections,
            "seconds": round(time.perf_counter() - started, 3),
        }
    except Exception as exc:
        return {
            "backend": "grounding_dino_transformers",
            "status": "error",
            "error": repr(exc),
            "seconds": round(time.perf_counter() - started, 3),
        }


def _run_florence2(model_id: str) -> dict:
    started = time.perf_counter()
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoProcessor

        image = Image.fromarray(_marking_image())
        prompt = "<OCR>"
        processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            trust_remote_code=True,
            attn_implementation="eager",
        ).to("cpu")
        model.config.use_cache = False
        model.generation_config.use_cache = False
        inputs = processor(text=prompt, images=image, return_tensors="pt")
        with torch.no_grad():
            generated_ids = model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=64,
                num_beams=1,
                use_cache=False,
            )
        raw = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
        parsed = processor.post_process_generation(raw, task=prompt, image_size=image.size)
        return {
            "backend": "florence2",
            "status": "ok" if parsed.get(prompt) else "empty",
            "model_id": model_id,
            "raw": raw,
            "parsed": parsed,
            "seconds": round(time.perf_counter() - started, 3),
        }
    except Exception as exc:
        return {
            "backend": "florence2",
            "status": "error",
            "error": repr(exc),
            "seconds": round(time.perf_counter() - started, 3),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test optional foundation backends")
    parser.add_argument("--output", default="eval/competitive_engine/foundation_backend_smoke.json")
    parser.add_argument("--sam2-checkpoint", default="models/foundation/sam2/sam2.1_hiera_tiny.pt")
    parser.add_argument("--sam2-config", default="configs/sam2.1/sam2.1_hiera_t.yaml")
    parser.add_argument("--grounding-model", default="IDEA-Research/grounding-dino-tiny")
    parser.add_argument("--florence-model", default="microsoft/Florence-2-base")
    args = parser.parse_args()

    results = {
        "backend_statuses": foundation_backend_statuses(),
        "smoke_tests": [
            _run_ocr("paddleocr"),
            _run_ocr("easyocr"),
            _run_sam2(args.sam2_checkpoint, args.sam2_config),
            _run_grounding_dino(args.grounding_model),
            _run_florence2(args.florence_model),
        ],
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"wrote {output_path}")
    for test in results["smoke_tests"]:
        detail = (
            test.get("text")
            or (test.get("parsed") or {}).get("<OCR>")
            or test.get("score")
            or len(test.get("detections", []))
        )
        print(f"{test['backend']}: {test['status']} ({detail})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
