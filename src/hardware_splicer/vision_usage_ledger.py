from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional


LEDGER_SCHEMA_VERSION = "hardware_splicer.vision_usage_ledger.v1"
DEFAULT_LEDGER_PATH = Path("data/vision/hardware-splicer-vision-usage.json")
DEFAULT_FREE_TIER_BY_MODEL = {
    "qwen3-vl-flash": 1_000_000,
    "qwen-vl-ocr-2025-11-20": 1_000_000,
}


def ledger_path(configured: Optional[str] = None) -> Path:
    raw = str(configured or os.getenv("HARDWARE_SPLICER_VISION_LEDGER") or DEFAULT_LEDGER_PATH).strip()
    return Path(raw)


def record_vision_usage(
    *,
    provider: str,
    model: str,
    usage: Mapping[str, Any],
    source_ids: Optional[List[str]] = None,
    goal: str = "",
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    prompt_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or prompt_tokens + completion_tokens)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "model": model,
        "source_ids": list(source_ids or []),
        "goal_excerpt": str(goal or "")[:160],
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }
    target = path or ledger_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    data = _load_ledger(target)
    entries = list(data.get("entries") or [])
    entries.append(entry)
    data["entries"] = entries[-2000:]
    data["updated_at"] = entry["ts"]
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return entry


def usage_summary(*, path: Optional[Path] = None, provider: str = "qwen") -> Dict[str, Any]:
    target = path or ledger_path()
    data = _load_ledger(target)
    entries = [row for row in _list_dicts(data.get("entries")) if str(row.get("provider") or "") == provider]
    now = datetime.now(timezone.utc)
    month_prefix = now.strftime("%Y-%m")
    day_prefix = now.strftime("%Y-%m-%d")

    total_tokens = 0
    month_tokens = 0
    day_tokens = 0
    by_model: Dict[str, Dict[str, int]] = {}

    for row in entries:
        tokens = int(row.get("total_tokens") or 0)
        model = str(row.get("model") or "unknown")
        total_tokens += tokens
        ts = str(row.get("ts") or "")
        if ts.startswith(month_prefix):
            month_tokens += tokens
        if ts.startswith(day_prefix):
            day_tokens += tokens
        bucket = by_model.setdefault(model, {"calls": 0, "total_tokens": 0})
        bucket["calls"] += 1
        bucket["total_tokens"] += tokens

    model_estimates = {
        model: _free_tier_estimate(model, stats["total_tokens"])
        for model, stats in by_model.items()
    }

    return {
        "schema_version": "hardware_splicer.vision_usage_summary.v1",
        "ledger_path": str(target),
        "provider": provider,
        "call_count": len(entries),
        "total_tokens": total_tokens,
        "month_tokens": month_tokens,
        "day_tokens": day_tokens,
        "by_model": by_model,
        "free_tier_estimates": model_estimates,
    }


def _free_tier_estimate(model: str, consumed_tokens: int) -> Dict[str, Any]:
    configured = os.getenv(f"QWEN_FREE_TIER_TOTAL_{model.upper().replace('-', '_')}")
    env_total = os.getenv("QWEN_VISION_FREE_TIER_TOTAL")
    total = int(configured or env_total or DEFAULT_FREE_TIER_BY_MODEL.get(model) or 0)
    if total <= 0:
        return {"model": model, "tracked_consumed_tokens": consumed_tokens, "estimated_remaining_tokens": None}
    remaining = max(0, total - consumed_tokens)
    return {
        "model": model,
        "assumed_free_tier_total_tokens": total,
        "tracked_consumed_tokens": consumed_tokens,
        "estimated_remaining_tokens": remaining,
        "note": "Remaining is estimated from local ledger only; verify in Model Studio console.",
    }


def _load_ledger(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"schema_version": LEDGER_SCHEMA_VERSION, "entries": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("schema_version", LEDGER_SCHEMA_VERSION)
            data.setdefault("entries", [])
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"schema_version": LEDGER_SCHEMA_VERSION, "entries": []}


def _list_dicts(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(row) for row in value if isinstance(row, Mapping)]
