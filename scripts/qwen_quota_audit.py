#!/usr/bin/env python3
"""Estimate DashScope free-quota status from local ledgers + optional rotation probe.

Alibaba does NOT expose a public API for remaining free-quota per model — console only.
See: https://www.alibabacloud.com/help/en/model-studio/new-free-quota
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Set

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.env_local import load_env_local
from hardware_splicer.integrations.qwen_model_policy import (
    QWEN_TEXT_STAGES,
    QWEN_VISION_STAGES,
    is_qwen_free_quota_exhausted,
    model_studio_summary,
    qwen_text_model_candidates,
    qwen_vision_model_candidates,
)
from hardware_splicer.integrations.qwen_text_client import qwen_api_key
from hardware_splicer.vision_evidence_assistant import DEFAULT_QWEN_BASE_URL
from hardware_splicer.text_usage_ledger import usage_summary as text_usage_summary
from hardware_splicer.vision_usage_ledger import usage_summary

DEFAULT_FREE_TIER_PER_MODEL = 1_000_000


def _collect_local_ledgers() -> Dict[str, Any]:
    load_env_local()
    hs_vision = usage_summary(provider="qwen")
    hs_text = text_usage_summary()
    extra_paths = [
        ROOT / "data" / "vision" / "qwen-spend-ledger.json",
        ROOT / "apps" / "circuit-ai" / "data" / "vision" / "qwen-spend-ledger.json",
        ROOT / "apps" / "circuit-ai" / "eval" / "qwen_trial" / "vision-spend-ledger.json",
    ]
    extra: List[Dict[str, Any]] = []
    for path in extra_paths:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            entries = data.get("entries") or []
            tokens = sum(int(e.get("total_tokens") or e.get("tokens") or 0) for e in entries if isinstance(e, dict))
            extra.append({"path": str(path), "entries": len(entries), "total_tokens": tokens})
        except (OSError, json.JSONDecodeError):
            extra.append({"path": str(path), "error": "unreadable"})
    return {"hardware_splicer_vision": hs_vision, "hardware_splicer_text": hs_text, "other_ledgers": extra}


def _rotation_models() -> List[str]:
    seen: Set[str] = set()
    ordered: List[str] = []
    for stage in QWEN_TEXT_STAGES:
        for model in qwen_text_model_candidates(stage=stage):
            if model not in seen:
                seen.add(model)
                ordered.append(model)
    for stage in QWEN_VISION_STAGES:
        for model in qwen_vision_model_candidates(stage=stage):
            if model not in seen:
                seen.add(model)
                ordered.append(model)
    return ordered


def _probe_model(model: str, *, base_url: str, api_key: str, timeout_s: int = 25) -> Dict[str, Any]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "temperature": 0,
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            body = json.loads(response.read().decode("utf-8"))
            usage = body.get("usage") or {}
            return {
                "model": model,
                "status": "ok",
                "probe_tokens": int(usage.get("total_tokens") or 0),
            }
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        exhausted = is_qwen_free_quota_exhausted(detail)
        return {
            "model": model,
            "status": "quota_exhausted" if exhausted and exc.code == 403 else f"http_{exc.code}",
            "detail_excerpt": detail[:200],
        }
    except Exception as exc:
        return {"model": model, "status": "error", "message": str(exc)}


def _theoretical_capacity(model_count: int) -> Dict[str, Any]:
    return {
        "models_in_active_rotation": model_count,
        "if_each_has_1m_pool_tokens": model_count * DEFAULT_FREE_TIER_PER_MODEL,
        "note": (
            "DashScope grants ~1M tokens per enabled model (Singapore), separate pools. "
            "Your account may have 80+ models enabled — console shows each pool. "
            "This script only probes models in Hardware-Splicer rotation unless you use --all-catalog."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="DashScope quota audit (local + optional probe)")
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Send 1-token ping to each rotation model (costs a few tokens per model; detects 403 exhausted)",
    )
    parser.add_argument("--probe-limit", type=int, default=0, help="Max models to probe (0 = all rotation)")
    args = parser.parse_args()

    load_env_local()
    local = _collect_local_ledgers()
    rotation = _rotation_models()
    report: Dict[str, Any] = {
        "schema_version": "hardware_splicer.qwen_quota_audit.v1",
        "console_required": (
            "Remaining free quota per model is ONLY authoritative in Model Studio console "
            "(Singapore → Model Usage → Free Quota tab). No public quota API exists."
        ),
        "email_alerts": "Alibaba emails at ~20% remaining and at exhaustion (per-model pools).",
        "local_tracking": local,
        "local_tracking_gaps": [
            "Circuit-AI / benchmarks / other tools may consume pools not visible in HS ledgers.",
            "Console Free Quota tab remains authoritative for remaining DashScope pools.",
        ],
        "active_rotation_models": rotation,
        "theoretical": _theoretical_capacity(len(rotation)),
        "model_studio_policy": model_studio_summary().get("active"),
    }

    api_key = qwen_api_key()
    if args.probe:
        if not api_key:
            report["probe"] = {"error": "missing_api_key", "message": "Set DASHSCOPE_API_KEY or QWEN_API_KEY"}
        else:
            base_url = os.environ.get("HARDWARE_SPLICER_QWEN_BASE_URL") or os.environ.get("QWEN_BASE_URL") or DEFAULT_QWEN_BASE_URL
            limit = args.probe_limit or len(rotation)
            probes: List[Dict[str, Any]] = []
            probe_tokens = 0
            for model in rotation[:limit]:
                row = _probe_model(model, base_url=base_url, api_key=api_key)
                probes.append(row)
                probe_tokens += int(row.get("probe_tokens") or 0)
            ok = [r["model"] for r in probes if r.get("status") == "ok"]
            exhausted = [r["model"] for r in probes if r.get("status") == "quota_exhausted"]
            other = [r for r in probes if r.get("status") not in {"ok", "quota_exhausted"}]
            report["probe"] = {
                "probed": len(probes),
                "probe_tokens_spent": probe_tokens,
                "ok": ok,
                "quota_exhausted": exhausted,
                "other_errors": other,
                "estimated_full_pools_remaining": len(ok),
                "estimated_exhausted_pools": len(exhausted),
            }

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print(report["console_required"])
    print()
    hs = local["hardware_splicer_vision"]
    print(f"Local vision ledger: {hs.get('ledger_path')}")
    print(f"  calls={hs.get('call_count')} tokens={hs.get('total_tokens')} (month={hs.get('month_tokens')})")
    for model, stats in (hs.get("by_model") or {}).items():
        est = (hs.get("free_tier_estimates") or {}).get(model) or {}
        rem = est.get("estimated_remaining_tokens")
        print(f"  - {model}: tracked {stats.get('total_tokens')} tokens", end="")
        if rem is not None:
            print(f" → est. {rem:,} left of 1M (local only)", end="")
        print()
    ht = local.get("hardware_splicer_text") or {}
    if ht:
        print(f"\nLocal text ledger: {ht.get('ledger_path')}")
        print(
            f"  calls={ht.get('call_count')} cache_hits={ht.get('cache_hits')} "
            f"tokens={ht.get('total_tokens')} (month={ht.get('month_tokens')})"
        )
        for stage, stats in sorted((ht.get("by_stage") or {}).items()):
            print(
                f"  - {stage}: calls={stats.get('calls')} cached={stats.get('cached_calls')} "
                f"tokens={stats.get('total_tokens')}"
            )
    if local.get("other_ledgers"):
        print("\nOther local ledgers:")
        for row in local["other_ledgers"]:
            print(f"  {row}")
    print()
    print(f"Rotation models tracked by policy: {len(rotation)}")
    print(f"Theoretical if each has 1M: {len(rotation) * DEFAULT_FREE_TIER_PER_MODEL:,} tokens")
    print("\nGaps: console is source of truth for DashScope remaining quota; agy uses separate Antigravity budget.")
    if args.probe and "probe" in report:
        p = report["probe"]
        if p.get("error"):
            print(f"\nProbe skipped: {p.get('message')}")
        else:
            print(f"\nProbe ({p.get('probed')} models, ~{p.get('probe_tokens_spent')} tokens spent):")
            print(f"  OK ({len(p.get('ok') or [])}): {', '.join((p.get('ok') or [])[:8])}{'…' if len(p.get('ok') or []) > 8 else ''}")
            if p.get("quota_exhausted"):
                print(f"  EXHAUSTED: {', '.join(p['quota_exhausted'])}")
            if p.get("other_errors"):
                print(f"  Other errors: {len(p['other_errors'])}")
    print("\nConsole: https://modelstudio.console.alibabacloud.com/ (Singapore) → Model Usage → Free Quota")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
