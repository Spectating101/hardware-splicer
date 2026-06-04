#!/usr/bin/env python3
"""Run a budget-capped Qwen native-vision trial over weak board cases.

Default mode is dry-run: it creates crops, request previews, and a comparison
report without calling Qwen. Add --live only after QWEN_API_KEY/DASHSCOPE_API_KEY
and VISION_MONTHLY_USD_LIMIT are configured.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from src.intelligence.vision_board_evidence import board_evidence_bridge  # noqa: E402
from src.vision.qwen_board_vision import DEFAULT_MAX_TOKENS, parse_qwen_board_response  # noqa: E402

ASSETS = ROOT / "assets" / "samples"
TRIAL_ROOT = ROOT / "eval" / "qwen_trial"
BASELINE = ROOT / "eval" / "qwen_readiness_baseline.json"
OUTPUT_JSON = TRIAL_ROOT / "latest_report.json"
OUTPUT_MD = TRIAL_ROOT / "latest_report.md"
LEDGER = TRIAL_ROOT / "vision-spend-ledger.json"
CACHE_DIR = TRIAL_ROOT / "cache"
CROPS_DIR = TRIAL_ROOT / "crops"
REQUESTS_DIR = TRIAL_ROOT / "requests"
PROMPT_VERSION = "qwen_trial_prompt_v4"
DEFAULT_VISION_ROTATION = ("qwen3-vl-flash", "qwen3-vl-30b-a3b-thinking", "qwen-vl-ocr-2025-11-20")
DEFAULT_LOW_QUOTA_MODELS = ("qwen-plus", "qwen-plus-2025-07-28")
KNOWN_UI_SCREENSHOT_IMAGES = {
    "iteration-1.png",
    "iteration-2.png",
    "iteration-3.png",
    "iteration-4.png",
}


SCENARIO_IMAGES = {
    "single_test_pcb": "test_pcb.png",
    "image_test_pcb": "test_pcb.png",
    "image_test_pcb_plus_sensor_listing": "test_pcb.png",
    "image_plus_sensor_listing": "test_pcb.png",
    "single_iteration_1": "iteration-1.png",
    "image_iteration-1": "iteration-1.png",
    "image_iteration-2": "iteration-2.png",
    "image_iteration-3": "iteration-3.png",
    "image_iteration-4": "iteration-4.png",
    "multiview_iteration_1_4": "iteration-1.png",
    "image_demo_pcb": "demo_pcb.png",
    "curated_test_pcb": "test_pcb.png",
    "curated_raspberry_pi": "curated/raspberry_pi.jpg",
    "curated_deeppcb_trace": "curated/deeppcb_00041200_test.jpg",
}

CURATED_ROWS = [
    {
        "scenario": "curated_test_pcb",
        "board_type": "toy_component_layout",
        "board_confidence": 1.0,
        "detections": 3,
        "connectors": 0,
        "ocr_resolved": 3,
        "aoi_readiness": "toy_fixture",
    },
    {
        "scenario": "curated_raspberry_pi",
        "board_type": "single_board_computer",
        "board_confidence": 1.0,
        "detections": None,
        "connectors": None,
        "ocr_resolved": None,
        "aoi_readiness": "real_photo_eval",
    },
    {
        "scenario": "curated_deeppcb_trace",
        "board_type": "bare_pcb_trace_defect",
        "board_confidence": 1.0,
        "detections": None,
        "connectors": None,
        "ocr_resolved": None,
        "aoi_readiness": "defect_eval",
    },
]

ANALYSIS_DIRS = [
    ROOT / "eval" / "capability_smoke_fixed",
    ROOT / "eval" / "rerun_full_product",
]


@dataclass
class Crop:
    crop_id: str
    path: Path
    source_bbox: list[float]
    crop_bbox: list[int]
    label: str
    confidence: float | None
    purpose: str


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
      for chunk in iter(lambda: handle.read(1024 * 1024), b""):
          digest.update(chunk)
    return digest.hexdigest()


def image_data_url(path: Path) -> str:
    media = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{media};base64,{data}"


def scenario_analysis_path(scenario: str, artifact: str | None = None) -> Path | None:
    candidates: list[Path] = []
    if artifact:
        parent = ROOT / artifact
        if parent.name == "summary.json":
            candidates.append(parent.parent / scenario / "analysis.json")
    candidates.extend(base / scenario / "analysis.json" for base in ANALYSIS_DIRS)
    for path in candidates:
        if path.exists():
            return path
    return None


def detections_from_analysis(path: Path | None) -> list[dict[str, Any]]:
    if not path:
        return []
    data = load_json(path, {})
    results = data.get("results") if isinstance(data, dict) else None
    detections = results.get("detections") if isinstance(results, dict) else None
    return [row for row in detections or [] if isinstance(row, dict)]


def clamp(value: float, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(round(value))))


def expanded_crop_bbox(bbox: list[Any], width: int, height: int, *, scale: float = 1.75) -> list[int] | None:
    if len(bbox) != 4:
        return None
    try:
        x1, y1, x2, y2 = [float(value) for value in bbox]
    except (TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    bw = max(32.0, (x2 - x1) * scale)
    bh = max(32.0, (y2 - y1) * scale)
    crop = [
        clamp(cx - bw / 2, 0, width - 1),
        clamp(cy - bh / 2, 0, height - 1),
        clamp(cx + bw / 2, 1, width),
        clamp(cy + bh / 2, 1, height),
    ]
    if crop[2] <= crop[0] or crop[3] <= crop[1]:
        return None
    return crop


def crop_priority(det: dict[str, Any]) -> tuple[int, float]:
    label = str(det.get("class_name") or det.get("label") or "unknown").lower()
    text = str(det.get("ocr_text") or det.get("text") or det.get("part_number") or "").strip()
    confidence = float(det.get("confidence") or 0)
    priority = 0
    if text:
        priority += 80
    if any(word in label for word in ("ic", "chip", "mcu", "controller")):
        priority += 60
    if "connector" in label:
        priority += 45
    if any(word in label for word in ("power", "regulator", "inductor", "transistor", "mosfet")):
        priority += 40
    return (-priority, -confidence)


def looks_like_app_ui_detection(det: dict[str, Any]) -> bool:
    text = " ".join(
        str(det.get(key) or "")
        for key in ("ocr_text", "text", "part_number")
    ).lower()
    ui_words = (
        "componentsanalyzed",
        "activeusers",
        "projectscreated",
        "valuegenerated",
        "projectideas",
        "educationalinsights",
        "comprehensivelearning",
        "intelllgentsuggestions",
        "intelligentsuggestions",
    )
    return any(word in text.replace(" ", "") for word in ui_words)


def create_crops(scenario: str, image_path: Path, detections: list[dict[str, Any]], limit: int) -> list[Crop]:
    crops: list[Crop] = []
    out_dir = CROPS_DIR / scenario
    if out_dir.exists():
        shutil.rmtree(out_dir)
    if limit <= 0:
        return crops
    with Image.open(image_path) as image:
        image = image.convert("RGB")
        width, height = image.size
        candidate_detections = [det for det in detections if not looks_like_app_ui_detection(det)]
        for index, det in enumerate(sorted(candidate_detections, key=crop_priority)[:limit], start=1):
            bbox = det.get("bbox")
            if not isinstance(bbox, list):
                continue
            crop_bbox = expanded_crop_bbox(bbox, width, height)
            if not crop_bbox:
                continue
            label = str(det.get("part_number") or det.get("ocr_text") or det.get("class_name") or "unknown").strip()
            crop_id = f"{index:02d}_{label.lower().replace(' ', '_')[:24] or 'region'}"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{crop_id}.png"
            image.crop(tuple(crop_bbox)).save(out_path)
            crops.append(
                Crop(
                    crop_id=crop_id,
                    path=out_path,
                    source_bbox=[float(value) for value in bbox],
                    crop_bbox=crop_bbox,
                    label=label,
                    confidence=float(det["confidence"]) if isinstance(det.get("confidence"), (int, float)) else None,
                    purpose="Read markings/package/connector context for this candidate region.",
                )
            )
    return crops


def qwen_rates(model: str, input_tokens: int) -> tuple[float, float]:
    normalized = model.lower()
    high = input_tokens > 128_000
    mid = input_tokens > 32_000
    if "qwen3-vl-plus" in normalized:
        return (0.43, 4.301) if high else (0.215, 2.15) if mid else (0.143, 1.434)
    if "qwen3-vl-flash-us" in normalized:
        return (0.12, 0.96) if high else (0.075, 0.6) if mid else (0.05, 0.4)
    if "qwen3-vl-flash" in normalized:
        return (0.086, 0.859) if high else (0.043, 0.43) if mid else (0.022, 0.215)
    return (
        float(os.getenv("QWEN_INPUT_USD_PER_M", "0.05")),
        float(os.getenv("QWEN_OUTPUT_USD_PER_M", "0.4")),
    )


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    input_rate, output_rate = qwen_rates(model, input_tokens)
    return round((input_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate, 6)


def split_csv(value: Any) -> list[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def low_quota_models() -> list[str]:
    configured = os.getenv("QWEN_LOW_QUOTA_MODELS") or os.getenv("QWEN_BLOCKED_MODELS") or ",".join(DEFAULT_LOW_QUOTA_MODELS)
    return [item.lower() for item in split_csv(configured)]


def model_is_blocked(model: str, blocked: list[str]) -> bool:
    normalized = model.strip().lower()
    return any(normalized == item or normalized.startswith(f"{item}-") for item in blocked)


def qwen_model_candidates(requested: str | None) -> list[str]:
    raw_candidates = [
        *split_csv(os.getenv("QWEN_VISION_MODEL_ROTATION")),
        str(requested or os.getenv("QWEN_VISION_MODEL") or "").strip(),
        *DEFAULT_VISION_ROTATION,
    ]
    blocked = low_quota_models()
    candidates: list[str] = []
    seen = set()
    for raw in raw_candidates:
        model = str(raw or "").strip()
        key = model.lower()
        if not model or key in seen or model_is_blocked(model, blocked):
            continue
        candidates.append(model)
        seen.add(key)
    return candidates or [DEFAULT_VISION_ROTATION[0]]


def quota_error(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(marker in lowered for marker in ("allocationquota", "freequota", "free quota", "quota", "insufficient", "billing"))


def ledger_spent() -> tuple[float, float]:
    ledger = load_json(LEDGER, {"entries": []})
    entries = ledger.get("entries") if isinstance(ledger, dict) else []
    now = datetime.now()
    day_prefix = now.strftime("%Y-%m-%d")
    month_prefix = now.strftime("%Y-%m")
    daily = 0.0
    monthly = 0.0
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        ts = str(entry.get("ts") or "")
        value = float(entry.get("estimated_usd") or entry.get("estimatedUsd") or 0)
        if ts.startswith(month_prefix):
            monthly += value
        if ts.startswith(day_prefix):
            daily += value
    return daily, monthly


def append_ledger(entry: dict[str, Any]) -> None:
    ledger = load_json(LEDGER, {"schema_version": "qwen_trial_spend_ledger.v1", "entries": []})
    entries = ledger.get("entries") if isinstance(ledger, dict) else []
    if not isinstance(entries, list):
        entries = []
    entries.append(entry)
    write_json(LEDGER, {"schema_version": "qwen_trial_spend_ledger.v1", "entries": entries[-1000:]})


def build_prompt(scenario: str, baseline_row: dict[str, Any], crops: list[Crop]) -> str:
    crop_lines = [
        f"- crop {crop.crop_id}: {crop.label}, source_bbox={crop.source_bbox}, crop_bbox={crop.crop_bbox}"
        for crop in crops
    ]
    return "\n".join(
        [
            "You are Circuit-AI native vision. Inspect the board image and crops.",
            "Return ONLY one compact JSON object. Do not repeat keys.",
            "Use safety_level exactly one of safe, caution, hazard.",
            "Required top-level keys: safety_level, explanation, components, board_evidence.",
            "Each component must use: id, label, kind, bbox, warnings. Use bbox as {x,y,w,h}, never bbox_2d or box.",
            "board_evidence must use schema_version board_evidence.v1.",
            "Inside board_evidence, put localized parts under components, not detections.",
            "Put connectors, ports, sockets, headers, terminal blocks, USB, HDMI, Ethernet, and GPIO rows under connectors, not components.",
            "Use these board_evidence array keys exactly: components, markings, regions, damage, connectors, test_points, salvage_candidates.",
            "Keep the response compact: at most 8 components and one short sentence per explanation.",
            "Normalize all boxes to 0-1 coordinates relative to the full board image when possible.",
            "Do not invent pinouts, voltages, exact part numbers, nets, or reuse safety without visible evidence.",
            "Do not use product knowledge to name exact ICs unless their markings are legible in the image.",
            "Prefer unknown plus missing_evidence/recommended_checks when unsure.",
            f"Scenario: {scenario}",
            f"Current local baseline: board_type={baseline_row.get('board_type')}, confidence={baseline_row.get('board_confidence')}, detections={baseline_row.get('detections')}, connectors={baseline_row.get('connectors')}, ocr_resolved={baseline_row.get('ocr_resolved')}.",
            "Crop plan:",
            *(crop_lines or ["- no local detections produced crops; inspect the full image carefully."]),
        ]
    )


def build_request(model: str, image_path: Path, crops: list[Crop], prompt: str, max_tokens: int) -> dict[str, Any]:
    content: list[dict[str, Any]] = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": image_data_url(image_path)}},
    ]
    for crop in crops:
        content.extend(
            [
                {"type": "text", "text": f"Crop {crop.crop_id}: {crop.label}. {crop.purpose}"},
                {"type": "image_url", "image_url": {"url": image_data_url(crop.path)}},
            ]
        )
    body: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "user",
                "content": content,
            }
        ],
    }
    if os.getenv("QWEN_VL_HIGH_RESOLUTION_IMAGES", "false").lower() in {"1", "true", "yes", "on"}:
        body["vl_high_resolution_images"] = True
    return body


def preview_request(body: dict[str, Any]) -> dict[str, Any]:
    preview = json.loads(json.dumps(body))
    for message in preview.get("messages", []):
        for block in message.get("content", []):
            if block.get("type") == "image_url":
                url = block.get("image_url", {}).get("url", "")
                block["image_url"]["url"] = f"{url[:32]}...omitted-{len(url)}-chars"
    return preview


def call_qwen(body: dict[str, Any], timeout: int) -> dict[str, Any]:
    key = os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
    if not key:
        raise RuntimeError("QWEN_API_KEY or DASHSCOPE_API_KEY is required for --live")
    base = os.getenv("QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1").rstrip("/")
    endpoint = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"Qwen HTTP {exc.code}: {detail}") from exc


def call_qwen_rotating(body: dict[str, Any], model_candidates: list[str], timeout: int) -> tuple[dict[str, Any], str, list[dict[str, str]]]:
    quota_errors: list[dict[str, str]] = []
    for index, model in enumerate(model_candidates):
        request_body = dict(body)
        request_body["model"] = model
        try:
            return call_qwen(request_body, timeout), model, quota_errors
        except RuntimeError as exc:
            if index < len(model_candidates) - 1 and quota_error(str(exc)):
                quota_errors.append({"model": model, "error": str(exc)[:500]})
                continue
            raise
    raise RuntimeError("Qwen model rotation exhausted")


def extract_json_object(text: str) -> dict[str, Any]:
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        raw = raw.rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                parsed = json.loads(raw[start:end])
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
    return {}


def summarize_model_payload(payload: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_qwen_board_response(payload)
    diagnostics = parsed.get("parse_diagnostics") if isinstance(parsed.get("parse_diagnostics"), dict) else {}
    evidence = parsed.get("board_evidence") if isinstance(parsed.get("board_evidence"), dict) else {}
    bridge = board_evidence_bridge(evidence)
    normalized = bridge.get("board_evidence") if isinstance(bridge.get("board_evidence"), dict) else evidence
    evidence_components = evidence.get("components") or evidence.get("detections") or []
    normalized_components = normalized.get("components") or []
    normalized_connectors = normalized.get("connectors") or []
    top_components = parsed.get("components") or parsed.get("components/modules") or []
    return {
        "json_valid": bool(diagnostics.get("json_valid")),
        "truncated": bool(diagnostics.get("truncated")),
        "finish_reason": diagnostics.get("finish_reason"),
        "safety_level": parsed.get("safety_level"),
        "component_count": len(top_components),
        "module_count": len(parsed.get("modules") or []),
        "evidence_component_count": len(evidence_components),
        "normalized_component_count": len(normalized_components),
        "marking_count": len(evidence.get("markings") or []),
        "connector_count": len(normalized_connectors),
        "damage_count": len(normalized.get("damage") or []),
        "test_point_count": len(normalized.get("test_points") or []),
        "salvage_candidate_count": len(normalized.get("salvage_candidates") or []),
        "bridge_resource_count": len(bridge.get("resource_candidates") or []),
        "bridge_hazard_count": len((bridge.get("hazard_profile") or {}).get("hazards") or []),
        "uncertainty_level": (evidence.get("uncertainty") or {}).get("level") if isinstance(evidence.get("uncertainty"), dict) else None,
    }


def scenario_rows(limit: int, curated: bool = False) -> list[dict[str, Any]]:
    if curated:
        return CURATED_ROWS[:limit] if limit else CURATED_ROWS
    baseline = load_json(BASELINE, {})
    rows = baseline.get("weak_cases") if isinstance(baseline, dict) else []
    kept = [row for row in rows or [] if isinstance(row, dict)]
    return kept[:limit] if limit else kept


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Actually call Qwen. Default only writes dry-run artifacts.")
    parser.add_argument("--curated", action="store_true", help="Use curated real/sample board images instead of weak historical artifacts.")
    parser.add_argument("--limit", type=int, default=6, help="Max weak scenarios to include.")
    parser.add_argument("--max-crops", type=int, default=int(os.getenv("VISION_MAX_CROPS_PER_SCAN", "3")))
    parser.add_argument("--model", default=os.getenv("QWEN_VISION_MODEL"))
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--monthly-limit", type=float, default=float(os.getenv("VISION_MONTHLY_USD_LIMIT", "0") or "0"))
    parser.add_argument("--daily-limit", type=float, default=float(os.getenv("VISION_DAILY_USD_LIMIT", "1") or "1"))
    parser.add_argument("--max-usd-per-call", type=float, default=float(os.getenv("VISION_MAX_USD_PER_CALL", "0.05") or "0.05"))
    args = parser.parse_args()
    model_candidates = qwen_model_candidates(args.model)
    args.model = model_candidates[0]

    if args.live and args.monthly_limit <= 0:
        raise SystemExit("Refusing live Qwen call: set VISION_MONTHLY_USD_LIMIT or pass --monthly-limit > 0.")

    started = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    cache_hits = 0
    live_calls = 0
    skipped_budget = 0

    for baseline_row in scenario_rows(args.limit, args.curated):
        scenario = str(baseline_row.get("scenario") or "")
        image_name = SCENARIO_IMAGES.get(scenario)
        if not image_name:
            rows.append({"scenario": scenario, "status": "skipped", "reason": "no sample image mapping"})
            continue
        image_path = ASSETS / image_name
        if not image_path.exists():
            rows.append({"scenario": scenario, "status": "skipped", "reason": f"missing image {image_path}"})
            continue
        if image_name in KNOWN_UI_SCREENSHOT_IMAGES:
            rows.append({
                "scenario": scenario,
                "status": "skipped_bad_sample",
                "reason": "historical artifact is a Circuit-AI UI screenshot, not a board photo",
                "image": str(image_path.relative_to(ROOT)),
            })
            continue

        analysis_path = scenario_analysis_path(scenario, str(baseline_row.get("artifact") or ""))
        detections = detections_from_analysis(analysis_path)
        crops = create_crops(scenario, image_path, detections, args.max_crops)
        prompt = build_prompt(scenario, baseline_row, crops)
        input_token_estimate = 900 + 4096 + len(crops) * 1536
        output_token_estimate = args.max_tokens
        preflight_cost = estimate_cost(args.model, input_token_estimate, output_token_estimate)
        cache_key = hashlib.sha256(
            "|".join(
                [
                    PROMPT_VERSION,
                    sha256_file(image_path),
                    args.model,
                    str(args.max_crops),
                    str(args.max_tokens),
                    *(sha256_file(crop.path) for crop in crops),
                ]
            ).encode("utf-8")
        ).hexdigest()[:24]
        cache_path = CACHE_DIR / f"{cache_key}.json"
        request_body = build_request(args.model, image_path, crops, prompt, args.max_tokens)
        write_json(REQUESTS_DIR / f"{scenario}_{cache_key}.preview.json", preview_request(request_body))

        row: dict[str, Any] = {
            "scenario": scenario,
            "status": "dry_run",
            "image": str(image_path.relative_to(ROOT)),
            "analysis": str(analysis_path.relative_to(ROOT)) if analysis_path else None,
            "cache_key": cache_key,
            "crop_count": len(crops),
            "crops": [
                {
                    "crop_id": crop.crop_id,
                    "path": str(crop.path.relative_to(ROOT)),
                    "label": crop.label,
                    "source_bbox": crop.source_bbox,
                    "crop_bbox": crop.crop_bbox,
                    "confidence": crop.confidence,
                }
                for crop in crops
            ],
            "baseline": {
                "board_type": baseline_row.get("board_type"),
                "board_confidence": baseline_row.get("board_confidence"),
                "detections": baseline_row.get("detections"),
                "connectors": baseline_row.get("connectors"),
                "ocr_resolved": baseline_row.get("ocr_resolved"),
                "aoi_readiness": baseline_row.get("aoi_readiness"),
            },
            "preflight": {
                "estimated_input_tokens": input_token_estimate,
                "estimated_output_tokens": output_token_estimate,
                "estimated_usd": preflight_cost,
                "max_usd_per_call": args.max_usd_per_call,
                "model_rotation": model_candidates,
                "low_quota_models": low_quota_models(),
            },
        }

        if cache_path.exists():
            cached = load_json(cache_path, {})
            response = cached.get("response") if isinstance(cached, dict) else None
            if isinstance(response, dict):
                cached["qwen_summary"] = summarize_model_payload(response)
                write_json(cache_path, cached)
            row.update({"status": "cache_hit", "cached": True, "qwen": cached.get("qwen_summary"), "usage": cached.get("usage")})
            cache_hits += 1
        elif args.live:
            daily_spent, monthly_spent = ledger_spent()
            if preflight_cost > args.max_usd_per_call or daily_spent + preflight_cost > args.daily_limit or monthly_spent + preflight_cost > args.monthly_limit:
                row.update({"status": "skipped_budget", "daily_spent": daily_spent, "monthly_spent": monthly_spent})
                skipped_budget += 1
            else:
                before = time.time()
                response, selected_model, quota_errors = call_qwen_rotating(request_body, model_candidates, args.timeout)
                elapsed = round(time.time() - before, 3)
                usage = response.get("usage") if isinstance(response, dict) else {}
                input_tokens = int((usage or {}).get("prompt_tokens") or input_token_estimate)
                output_tokens = int((usage or {}).get("completion_tokens") or 0)
                actual_model = str(response.get("model") or selected_model)
                actual_cost = estimate_cost(actual_model, input_tokens, output_tokens)
                qwen_summary = summarize_model_payload(response)
                cached = {
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "request_preview": str((REQUESTS_DIR / f"{scenario}_{cache_key}.preview.json").relative_to(ROOT)),
                    "response": response,
                    "qwen_summary": qwen_summary,
                    "model_rotation": {"candidates": model_candidates, "selected_model": actual_model, "quota_errors": quota_errors},
                    "usage": {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "estimated_usd": actual_cost,
                        "elapsed_s": elapsed,
                    },
                }
                write_json(cache_path, cached)
                append_ledger(
                    {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "provider": "qwen",
                        "model": actual_model,
                        "scenario": scenario,
                        "cache_key": cache_key,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "estimated_usd": actual_cost,
                    }
                )
                row.update({"status": "live", "cached": False, "qwen": qwen_summary, "usage": cached["usage"]})
                live_calls += 1
        rows.append(row)

    report = {
        "created_at": started,
        "mode": "live" if args.live else "dry_run",
        "model": args.model,
        "limits": {
            "monthly_usd": args.monthly_limit,
            "daily_usd": args.daily_limit,
            "max_usd_per_call": args.max_usd_per_call,
            "max_crops": args.max_crops,
        },
        "summary": {
            "rows": len(rows),
            "cache_hits": cache_hits,
            "live_calls": live_calls,
            "skipped_budget": skipped_budget,
            "estimated_preflight_usd_total": round(sum((row.get("preflight") or {}).get("estimated_usd") or 0 for row in rows), 6),
            "actual_usd_total": round(sum((row.get("usage") or {}).get("estimated_usd") or 0 for row in rows), 6),
        },
        "rows": rows,
    }
    write_json(OUTPUT_JSON, report)
    write_markdown(report)
    print(f"Wrote {OUTPUT_JSON.relative_to(ROOT)}")
    print(f"Wrote {OUTPUT_MD.relative_to(ROOT)}")
    return 0


def write_markdown(report: dict[str, Any]) -> None:
    lines = [
        "# Qwen Vision Trial Report",
        "",
        f"- Created: `{report['created_at']}`",
        f"- Mode: `{report['mode']}`",
        f"- Model: `{report['model']}`",
        f"- Rows: `{report['summary']['rows']}`",
        f"- Live calls: `{report['summary']['live_calls']}`",
        f"- Cache hits: `{report['summary']['cache_hits']}`",
        f"- Estimated preflight total: `${report['summary']['estimated_preflight_usd_total']}`",
        f"- Actual recorded total: `${report['summary']['actual_usd_total']}`",
        "",
        "| Scenario | Status | Crops | Baseline | Qwen summary | Cost |",
        "|---|---:|---:|---|---|---:|",
    ]
    for row in report.get("rows") or []:
        baseline = row.get("baseline") or {}
        qwen = row.get("qwen") or {}
        usage = row.get("usage") or {}
        qwen_text = (
            f"json={qwen.get('json_valid')}, comps={qwen.get('evidence_component_count')}, "
            f"marks={qwen.get('marking_count')}, conn={qwen.get('connector_count')}, "
            f"salvage={qwen.get('salvage_candidate_count')}"
            if qwen
            else "pending"
        )
        baseline_text = (
            f"{baseline.get('board_type')} / conf={baseline.get('board_confidence')} / "
            f"det={baseline.get('detections')} / conn={baseline.get('connectors')} / ocr={baseline.get('ocr_resolved')}"
        )
        lines.append(
            f"| `{row.get('scenario')}` | `{row.get('status')}` | {row.get('crop_count', 0)} | "
            f"{baseline_text} | {qwen_text} | `${usage.get('estimated_usd', 0)}` |"
        )
    lines.extend(
        [
            "",
            "## Minimum Success Bar",
            "",
            "- Valid JSON with `board_evidence.v1` on every live sampled board.",
            "- Better markings/connectors/regions on weak baseline cases without invented pinouts.",
            "- Total spend stays inside the configured Qwen budget.",
        ]
    )
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
