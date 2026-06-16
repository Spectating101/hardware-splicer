"""Qwen Model Studio policy — per-stage models, per-model 1M free pools, rotation.

Each enabled Singapore model has its own free-token pool (typically 1M). Pools are
shared across workspaces and API keys on the same DashScope account — not one global 1M.

Stage profiles follow docs/DASHSCOPE_MODEL_GUIDE.md (llm_automation repo).
"""

from __future__ import annotations

import os
from typing import Dict, List, Literal, Set, Tuple

from ..env_local import load_env_local

QwenTextStage = Literal[
    "salvage",
    "build_pick",
    "module_pick",
    "compose",
    "compose_retry",
    "workshop",
    "narrative",
    "general",
]

QwenVisionStage = Literal["board", "ocr", "escalation", "general"]

QWEN_TEXT_STAGES: Tuple[QwenTextStage, ...] = (
    "salvage",
    "build_pick",
    "module_pick",
    "compose",
    "compose_retry",
    "workshop",
    "narrative",
    "general",
)

QWEN_VISION_STAGES: Tuple[QwenVisionStage, ...] = ("board", "ocr", "escalation", "general")

# --- Global defaults (ultimate fallback when stage pools exhaust) ---

DEFAULT_QWEN_TEXT_MODEL = "qwen3.5-flash"

DEFAULT_TEXT_MODEL_ROTATION: tuple[str, ...] = (
    "qwen3.5-flash",
    "qwen-flash",
    "qwen3-coder-flash",
    "deepseek-v3.2",
    "qwen-plus-2025-07-28",
    "qwen3.5-plus",
    "qwen3-30b-a3b-instruct-2507",
    "qwen3.5-flash-2026-02-23",
    "qwen-turbo",
)

DEFAULT_QWEN_VISION_MODEL = "qwen3-vl-flash-2026-01-22"

DEFAULT_VISION_MODEL_ROTATION: tuple[str, ...] = (
    "qwen3-vl-flash-2026-01-22",
    "qwen3-vl-flash-2025-10-15",
    "qwen-vl-ocr-2025-11-20",
    "qwen-vl-ocr",
    "qwen3-vl-flash",
    "qwen-vl-plus",
)

DEFAULT_LOW_QUOTA_TEXT_MODELS: tuple[str, ...] = ("qwen-turbo",)
DEFAULT_LOW_QUOTA_VISION_MODELS: tuple[str, ...] = ("qwen3-vl-flash",)

# --- Per-stage tuned profiles (spread quota across model families) ---

TEXT_STAGE_PROFILES: Dict[QwenTextStage, Dict[str, tuple[str, ...] | str]] = {
    "salvage": {
        "primary": "qwen3.5-flash",
        "rotation": (
            "qwen3.5-flash",
            "qwen-flash",
            "deepseek-v3.2",
            "qwen3.5-flash-2026-02-23",
            "qwen-plus-2025-07-28",
        ),
    },
    "build_pick": {
        "primary": "qwen3.5-flash",
        "rotation": (
            "qwen3.5-flash",
            "qwen-flash",
            "qwen-plus-2025-07-28",
        ),
    },
    "module_pick": {
        "primary": "qwen3.5-flash",
        "rotation": (
            "qwen3.5-flash",
            "qwen3-coder-flash",
            "qwen-flash",
            "qwen3.5-plus",
        ),
    },
    "compose": {
        "primary": "qwen3-coder-flash",
        "rotation": (
            "qwen3-coder-flash",
            "qwen3-coder-flash-2025-07-28",
            "qwen3.5-flash",
            "qwen3-coder-30b-a3b-instruct",
        ),
    },
    "compose_retry": {
        "primary": "qwen3-coder-flash",
        "rotation": (
            "qwen3-coder-flash",
            "qwen3-coder-plus",
            "qwen3.5-plus",
            "qwen3.5-flash",
        ),
    },
    "workshop": {
        "primary": "qwen3.5-plus",
        "rotation": (
            "qwen3.5-plus",
            "qwen-plus-2025-07-28",
            "qwen3.5-flash",
            "deepseek-v3.2",
        ),
    },
    "narrative": {
        "primary": "qwen-flash",
        "rotation": (
            "qwen-flash",
            "qwen3.5-flash",
            "qwen-mt-flash",
        ),
    },
    "general": {
        "primary": DEFAULT_QWEN_TEXT_MODEL,
        "rotation": DEFAULT_TEXT_MODEL_ROTATION,
    },
}

VISION_STAGE_PROFILES: Dict[QwenVisionStage, Dict[str, tuple[str, ...] | str]] = {
    "board": {
        "primary": "qwen3-vl-flash-2026-01-22",
        "rotation": (
            "qwen3-vl-flash-2026-01-22",
            "qwen3-vl-flash-2025-10-15",
            "qwen3-vl-flash",
            "qwen-vl-plus",
        ),
    },
    "ocr": {
        "primary": "qwen-vl-ocr-2025-11-20",
        "rotation": (
            "qwen-vl-ocr-2025-11-20",
            "qwen-vl-ocr",
            "qwen3-vl-flash-2026-01-22",
        ),
    },
    "escalation": {
        "primary": "qwen3-vl-30b-a3b-thinking",
        "rotation": (
            "qwen3-vl-30b-a3b-thinking",
            "qwen3-vl-plus",
            "qwen3-vl-flash-2026-01-22",
        ),
    },
    "general": {
        "primary": DEFAULT_QWEN_VISION_MODEL,
        "rotation": DEFAULT_VISION_MODEL_ROTATION,
    },
}

TEXT_STAGE_ENV: Dict[QwenTextStage, Tuple[str, str]] = {
    "salvage": (
        "HARDWARE_SPLICER_QWEN_SALVAGE_MODEL",
        "HARDWARE_SPLICER_QWEN_SALVAGE_MODEL_ROTATION",
    ),
    "build_pick": (
        "HARDWARE_SPLICER_QWEN_BUILD_PICK_MODEL",
        "HARDWARE_SPLICER_QWEN_BUILD_PICK_MODEL_ROTATION",
    ),
    "module_pick": (
        "HARDWARE_SPLICER_QWEN_MODULE_PICK_MODEL",
        "HARDWARE_SPLICER_QWEN_MODULE_PICK_MODEL_ROTATION",
    ),
    "compose": (
        "HARDWARE_SPLICER_QWEN_COMPOSE_MODEL",
        "HARDWARE_SPLICER_QWEN_COMPOSE_MODEL_ROTATION",
    ),
    "compose_retry": (
        "HARDWARE_SPLICER_QWEN_COMPOSE_RETRY_MODEL",
        "HARDWARE_SPLICER_QWEN_COMPOSE_RETRY_MODEL_ROTATION",
    ),
    "workshop": (
        "HARDWARE_SPLICER_QWEN_WORKSHOP_MODEL",
        "HARDWARE_SPLICER_QWEN_WORKSHOP_MODEL_ROTATION",
    ),
    "narrative": (
        "HARDWARE_SPLICER_QWEN_NARRATIVE_MODEL",
        "HARDWARE_SPLICER_QWEN_NARRATIVE_MODEL_ROTATION",
    ),
    "general": (
        "HARDWARE_SPLICER_QWEN_TEXT_MODEL",
        "HARDWARE_SPLICER_QWEN_TEXT_MODEL_ROTATION",
    ),
}

VISION_STAGE_ENV: Dict[QwenVisionStage, Tuple[str, str]] = {
    "board": (
        "HARDWARE_SPLICER_QWEN_VISION_BOARD_MODEL",
        "HARDWARE_SPLICER_QWEN_VISION_BOARD_MODEL_ROTATION",
    ),
    "ocr": (
        "HARDWARE_SPLICER_QWEN_VISION_OCR_MODEL",
        "HARDWARE_SPLICER_QWEN_VISION_OCR_MODEL_ROTATION",
    ),
    "escalation": (
        "HARDWARE_SPLICER_QWEN_VISION_ESCALATION_MODEL",
        "HARDWARE_SPLICER_QWEN_VISION_ESCALATION_MODEL_ROTATION",
    ),
    "general": (
        "HARDWARE_SPLICER_VISION_MODEL",
        "HARDWARE_SPLICER_QWEN_VISION_MODEL_ROTATION",
    ),
}

# No free tier on account (or wrong API surface for chat completions).
BLOCKED_CHAT_MODELS: Set[str] = {
    "qwen-plus",
    "qwen-plus-character-ja",
    "qwen-plus-2025-01-25",
    "qwen-omni-turbo-latest",
    "qwen-omni-turbo-realtime-latest",
}

BLOCKED_CHAT_PREFIXES: tuple[str, ...] = (
    "wan",
    "qwen-image",
    "happyhorse",
    "z-image",
    "qwen-omni",
    "qwen3-omni",
    "qwen3.5-omni",
)

MODEL_STUDIO_CATALOG: Dict[str, Dict[str, str]] = {
    "text_workhorse": {
        "role": "Salvage map, build pick, module pick — NL + constrained JSON",
        "models": "qwen3.5-flash, qwen-flash, qwen3.5-flash-2026-02-23",
        "quota": "1M each (separate pools)",
        "stage": "salvage, build_pick, module_pick",
    },
    "text_structured": {
        "role": "Netlist compose + DRC retry — schema-heavy JSON",
        "models": "qwen3-coder-flash, qwen3-coder-flash-2025-07-28, qwen3-coder-plus",
        "quota": "1M each",
        "stage": "compose, compose_retry",
    },
    "text_reasoning": {
        "role": "Ambiguous salvage, workshop review",
        "models": "deepseek-v3.2, qwen3.5-plus, qwen-plus-2025-07-28",
        "quota": "1M each (larger = slower)",
        "stage": "salvage fallback, workshop",
    },
    "text_narrative": {
        "role": "JARVIS trust summaries — cheap prose JSON",
        "models": "qwen-flash, qwen-mt-flash",
        "quota": "1M each",
        "stage": "narrative",
    },
    "vision_board": {
        "role": "Bench photos, board scene evidence",
        "models": "qwen3-vl-flash-2026-01-22, qwen3-vl-flash-2025-10-15",
        "quota": "1M per variant",
        "stage": "board",
    },
    "vision_ocr": {
        "role": "Silkscreen / chip marking readout",
        "models": "qwen-vl-ocr-2025-11-20, qwen-vl-ocr",
        "quota": "1M each",
        "stage": "ocr",
    },
    "vision_thinking": {
        "role": "Low-confidence boards — slow escalation",
        "models": "qwen3-vl-30b-a3b-thinking, qwen3-vl-plus",
        "quota": "1M each",
        "stage": "escalation",
    },
    "depleted_account": {
        "role": "Still usable — rotation tries these last",
        "models": "qwen-turbo, qwen3-vl-flash",
        "quota": "Account-specific; check Model Studio console",
        "stage": "low_quota tail",
    },
    "not_for_hardware_splicer": {
        "role": "Video gen, image gen, realtime omni — wrong API / tiny quotas",
        "models": "wan*, qwen-image*, happyhorse*, omni-realtime",
        "quota": "50–200 for video/image; omni often Not Enabled",
        "stage": "blocked",
    },
}


def is_blocked_chat_model(model: str) -> bool:
    mid = str(model or "").strip()
    if not mid:
        return True
    if mid in BLOCKED_CHAT_MODELS:
        return True
    lowered = mid.lower()
    return any(lowered.startswith(prefix) for prefix in BLOCKED_CHAT_PREFIXES)


def is_qwen_free_quota_exhausted(detail: str) -> bool:
    lowered = str(detail or "").lower()
    return (
        "allocationquota" in lowered
        or "freetieronly" in lowered
        or "freequota" in lowered
        or "free quota" in lowered
    )


def should_rotate_qwen_model(*, status: int, detail: str, has_more_candidates: bool) -> bool:
    if not has_more_candidates:
        return False
    if status == 429:
        return True
    if status == 403 and is_qwen_free_quota_exhausted(detail):
        return True
    return False


def _parse_csv_env(*names: str) -> List[str]:
    for name in names:
        raw = os.environ.get(name, "").strip()
        if raw:
            return [part.strip() for part in raw.split(",") if part.strip()]
    return []


def _normalize_text_stage(stage: str | None) -> QwenTextStage:
    value = str(stage or "general").strip().lower().replace("-", "_")
    if value in QWEN_TEXT_STAGES:
        return value  # type: ignore[return-value]
    return "general"


def _normalize_vision_stage(stage: str | None) -> QwenVisionStage:
    value = str(stage or "general").strip().lower().replace("-", "_")
    if value in QWEN_VISION_STAGES:
        return value  # type: ignore[return-value]
    return "general"


def qwen_low_quota_text_models() -> Set[str]:
    load_env_local()
    values = _parse_csv_env(
        "HARDWARE_SPLICER_QWEN_LOW_QUOTA_MODELS",
        "QWEN_LOW_QUOTA_MODELS",
    )
    if not values:
        values = list(DEFAULT_LOW_QUOTA_TEXT_MODELS)
    return set(values)


def qwen_low_quota_vision_models() -> Set[str]:
    load_env_local()
    values = _parse_csv_env("HARDWARE_SPLICER_QWEN_LOW_QUOTA_VISION_MODELS")
    if not values:
        values = list(DEFAULT_LOW_QUOTA_VISION_MODELS)
    return set(values)


def qwen_text_model_rotation() -> tuple[str, ...]:
    load_env_local()
    values = _parse_csv_env(
        "HARDWARE_SPLICER_QWEN_TEXT_MODEL_ROTATION",
        "QWEN_TEXT_MODEL_ROTATION",
    )
    if values:
        return tuple(values)
    return DEFAULT_TEXT_MODEL_ROTATION


def qwen_vision_model_rotation() -> tuple[str, ...]:
    load_env_local()
    values = _parse_csv_env(
        "HARDWARE_SPLICER_QWEN_VISION_MODEL_ROTATION",
        "QWEN_VISION_MODEL_ROTATION",
    )
    if values:
        return tuple(values)
    return DEFAULT_VISION_MODEL_ROTATION


def _stage_primary_and_rotation(
    *,
    stage_key: str,
    profiles: Dict[str, Dict[str, tuple[str, ...] | str]],
    env_map: Dict[str, Tuple[str, str]],
    global_rotation: tuple[str, ...],
    global_primary_env: tuple[str, ...],
    default_primary: str,
) -> Tuple[str, tuple[str, ...]]:
    profile = profiles.get(stage_key) or profiles["general"]
    model_env, rotation_env = env_map.get(stage_key, env_map["general"])

    primary = (
        os.environ.get(model_env, "").strip()
        or next((os.environ.get(name, "").strip() for name in global_primary_env if os.environ.get(name, "").strip()), "")
        or str(profile["primary"])
        or default_primary
    )

    rotation_values = _parse_csv_env(rotation_env)
    stage_rotation = tuple(rotation_values) if rotation_values else tuple(profile["rotation"])  # type: ignore[arg-type]

    seen = {primary, *stage_rotation}
    fallback = tuple(model for model in global_rotation if model not in seen)
    return primary, stage_rotation + fallback


def _order_candidates(
    *,
    primary: str,
    rotation: tuple[str, ...],
    low_quota: Set[str],
) -> List[str]:
    ordered: List[str] = []
    for candidate in (primary, *rotation):
        if is_blocked_chat_model(candidate) or candidate in ordered:
            continue
        ordered.append(candidate)
    head = [model for model in ordered if model not in low_quota or model == primary]
    tail = [model for model in ordered if model in low_quota and model != primary]
    return head + tail


def qwen_text_model_candidates(
    explicit_model: str | None = None,
    *,
    stage: str | QwenTextStage | None = None,
) -> List[str]:
    load_env_local()
    stage_key = _normalize_text_stage(stage)

    if explicit_model:
        primary = str(explicit_model).strip()
        rotation = qwen_text_model_rotation()
        if stage and stage_key != "general":
            _, stage_rotation = _stage_primary_and_rotation(
                stage_key=stage_key,
                profiles=TEXT_STAGE_PROFILES,
                env_map=TEXT_STAGE_ENV,
                global_rotation=qwen_text_model_rotation(),
                global_primary_env=("HARDWARE_SPLICER_QWEN_TEXT_MODEL", "QWEN_MODEL"),
                default_primary=DEFAULT_QWEN_TEXT_MODEL,
            )
            seen = {primary, *stage_rotation}
            rotation = stage_rotation + tuple(m for m in rotation if m not in seen)
    else:
        primary, rotation = _stage_primary_and_rotation(
            stage_key=stage_key,
            profiles=TEXT_STAGE_PROFILES,
            env_map=TEXT_STAGE_ENV,
            global_rotation=qwen_text_model_rotation(),
            global_primary_env=("HARDWARE_SPLICER_QWEN_TEXT_MODEL", "QWEN_MODEL"),
            default_primary=DEFAULT_QWEN_TEXT_MODEL,
        )

    return _order_candidates(
        primary=primary,
        rotation=rotation,
        low_quota=qwen_low_quota_text_models(),
    )


def qwen_vision_model_candidates(
    explicit_model: str | None = None,
    *,
    stage: str | QwenVisionStage | None = None,
) -> List[str]:
    load_env_local()
    stage_key = _normalize_vision_stage(stage or os.environ.get("HARDWARE_SPLICER_VISION_STAGE", "").strip() or None)

    if explicit_model:
        primary = str(explicit_model).strip()
        rotation = qwen_vision_model_rotation()
        if stage_key != "general":
            _, stage_rotation = _stage_primary_and_rotation(
                stage_key=stage_key,
                profiles=VISION_STAGE_PROFILES,
                env_map=VISION_STAGE_ENV,
                global_rotation=qwen_vision_model_rotation(),
                global_primary_env=("HARDWARE_SPLICER_VISION_MODEL", "QWEN_VISION_MODEL"),
                default_primary=DEFAULT_QWEN_VISION_MODEL,
            )
            seen = {primary, *stage_rotation}
            rotation = stage_rotation + tuple(m for m in rotation if m not in seen)
    else:
        primary, rotation = _stage_primary_and_rotation(
            stage_key=stage_key,
            profiles=VISION_STAGE_PROFILES,
            env_map=VISION_STAGE_ENV,
            global_rotation=qwen_vision_model_rotation(),
            global_primary_env=("HARDWARE_SPLICER_VISION_MODEL", "QWEN_VISION_MODEL"),
            default_primary=DEFAULT_QWEN_VISION_MODEL,
        )

    return _order_candidates(
        primary=primary,
        rotation=rotation,
        low_quota=qwen_low_quota_vision_models(),
    )


def resolve_vision_stage(body: Dict[str, object] | None = None) -> QwenVisionStage:
    """Pick vision stage from intake body hints or env."""
    load_env_local()
    raw = body or {}
    vision_cfg = raw.get("vision_assistance") or raw.get("vision_model_assistance") or {}
    if isinstance(vision_cfg, dict):
        explicit = str(vision_cfg.get("vision_stage") or vision_cfg.get("stage") or "").strip().lower()
        if explicit:
            return _normalize_vision_stage(explicit)
        if vision_cfg.get("ocr_focus") or vision_cfg.get("ocr_mode"):
            return "ocr"

    for key in ("vision_stage", "ocr_focus"):
        if raw.get(key):
            return "ocr" if key == "ocr_focus" else _normalize_vision_stage(str(raw.get(key)))

    env_stage = os.environ.get("HARDWARE_SPLICER_VISION_STAGE", "").strip()
    if env_stage:
        return _normalize_vision_stage(env_stage)
    return "board"


def model_studio_summary() -> Dict[str, object]:
    """JSON-serializable catalog + active per-stage rotation for CLI / agents."""
    load_env_local()
    text_stages: Dict[str, object] = {}
    for stage in QWEN_TEXT_STAGES:
        if stage == "general":
            continue
        candidates = qwen_text_model_candidates(stage=stage)
        model_env, rotation_env = TEXT_STAGE_ENV[stage]
        text_stages[stage] = {
            "primary": candidates[0] if candidates else None,
            "rotation": candidates,
            "env_model": model_env,
            "env_rotation": rotation_env,
        }

    vision_stages: Dict[str, object] = {}
    for stage in QWEN_VISION_STAGES:
        if stage == "general":
            continue
        candidates = qwen_vision_model_candidates(stage=stage)
        model_env, rotation_env = VISION_STAGE_ENV[stage]
        vision_stages[stage] = {
            "primary": candidates[0] if candidates else None,
            "rotation": candidates,
            "env_model": model_env,
            "env_rotation": rotation_env,
        }

    return {
        "schema_version": "hardware_splicer.qwen_model_studio.v2",
        "guide": "../../../../llm_automation/docs/DASHSCOPE_MODEL_GUIDE.md",
        "quota_note": (
            "Each model has its own free pool (usually 1M tokens). "
            "Shared across workspaces on one DashScope account. "
            "Per-stage profiles spread load across model families."
        ),
        "active": {
            "text_general": list(qwen_text_model_candidates()),
            "text_stages": text_stages,
            "vision_general": list(qwen_vision_model_candidates()),
            "vision_stages": vision_stages,
            "low_quota_text": sorted(qwen_low_quota_text_models()),
            "low_quota_vision": sorted(qwen_low_quota_vision_models()),
        },
        "catalog_tiers": MODEL_STUDIO_CATALOG,
    }
