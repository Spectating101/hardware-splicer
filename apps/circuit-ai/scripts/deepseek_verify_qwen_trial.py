#!/usr/bin/env python3
"""Verify live Qwen trial outputs with DeepSeek.

Dry-run mode writes prompt previews only. Add --live to call DeepSeek on cached
Qwen responses from eval/qwen_trial/cache.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TRIAL_ROOT = ROOT / "eval" / "qwen_trial"
CACHE_DIR = TRIAL_ROOT / "cache"
PROMPT_DIR = TRIAL_ROOT / "deepseek_verify_prompts"
OUTPUT_JSON = TRIAL_ROOT / "deepseek_verification_report.json"
OUTPUT_MD = TRIAL_ROOT / "deepseek_verification_report.md"


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def extract_json_object(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
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


def qwen_result_from_cache(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    cached = load_json(path, {})
    response = cached.get("response") if isinstance(cached, dict) else {}
    choices = response.get("choices") if isinstance(response, dict) else []
    message = choices[0].get("message") if choices and isinstance(choices[0], dict) else {}
    parsed = extract_json_object(str(message.get("content") or ""))
    evidence = parsed.get("board_evidence") if isinstance(parsed.get("board_evidence"), dict) else {}
    return cached, evidence


def prompt_for(cache_name: str, cached: dict[str, Any], evidence: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            "Verify this Qwen native-vision board evidence for Circuit-AI.",
            "Return ONLY JSON with: verifier_status, summary, contradictions, unsupported_claims, missing_measurements, recommended_next_actions, launch_readiness.",
            "Be strict: no safe-to-cut, reuse-ready, pinout, voltage, net, or repair claim passes without visible or measurement evidence.",
            "Be product-minded: identify what is demo-ready for an experimental MVP and what still blocks private alpha.",
            f"Cache file: {cache_name}",
            "Qwen usage/summary:",
            json.dumps({"usage": cached.get("usage"), "qwen_summary": cached.get("qwen_summary")}, indent=2),
            "Board evidence:",
            json.dumps(evidence, indent=2),
        ]
    )


def deepseek_endpoint() -> str:
    base = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    return base if base.endswith("/chat/completions") else f"{base}/chat/completions"


def call_deepseek(prompt: str, timeout: int) -> dict[str, Any]:
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY is required for --live")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    body = {
        "model": model,
        "max_tokens": 1400,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "messages": [
            {"role": "system", "content": "You are Circuit-AI's strict evidence verifier. Return JSON only."},
            {"role": "user", "content": prompt},
        ],
    }
    request = urllib.request.Request(
        deepseek_endpoint(),
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"DeepSeek HTTP {exc.code}: {detail}") from exc
    choices = payload.get("choices") or []
    content = choices[0].get("message", {}).get("content", "") if choices else ""
    parsed = extract_json_object(content)
    parsed["model"] = f"deepseek/{payload.get('model') or model}"
    parsed["usage"] = payload.get("usage") or {}
    return parsed


def write_markdown(report: dict[str, Any]) -> None:
    lines = [
        "# DeepSeek Verification Report",
        "",
        f"- Created: `{report['created_at']}`",
        f"- Mode: `{report['mode']}`",
        f"- Rows: `{report['summary']['rows']}`",
        f"- Live calls: `{report['summary']['live_calls']}`",
        "",
        "| Cache | Status | Verification | Launch |",
        "|---|---:|---|---|",
    ]
    for row in report.get("rows") or []:
        verification = row.get("verification") or {}
        launch = verification.get("launch_readiness") or {}
        lines.append(
            f"| `{row.get('cache')}` | `{row.get('status')}` | "
            f"{verification.get('verifier_status', 'pending')} | {launch.get('level', 'pending')} |"
        )
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Call DeepSeek instead of writing prompt previews only.")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()

    cache_files = sorted(CACHE_DIR.glob("*.json"))[: args.limit]
    rows: list[dict[str, Any]] = []
    live_calls = 0

    for cache_file in cache_files:
        cached, evidence = qwen_result_from_cache(cache_file)
        if not evidence:
            rows.append({"cache": cache_file.name, "status": "skipped", "reason": "no board_evidence in cached Qwen response"})
            continue
        prompt = prompt_for(cache_file.name, cached, evidence)
        prompt_path = PROMPT_DIR / f"{cache_file.stem}.prompt.txt"
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(prompt, encoding="utf-8")
        row: dict[str, Any] = {
            "cache": cache_file.name,
            "status": "dry_run",
            "prompt": str(prompt_path.relative_to(ROOT)),
            "evidence_counts": {
                "components": len(evidence.get("components") or []),
                "markings": len(evidence.get("markings") or []),
                "connectors": len(evidence.get("connectors") or []),
                "salvage_candidates": len(evidence.get("salvage_candidates") or []),
            },
        }
        if args.live:
            row["verification"] = call_deepseek(prompt, args.timeout)
            row["status"] = "live"
            live_calls += 1
        rows.append(row)

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "live" if args.live else "dry_run",
        "summary": {
            "rows": len(rows),
            "live_calls": live_calls,
            "cache_files_seen": len(cache_files),
        },
        "rows": rows,
    }
    write_json(OUTPUT_JSON, report)
    write_markdown(report)
    print(f"Wrote {OUTPUT_JSON.relative_to(ROOT)}")
    print(f"Wrote {OUTPUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
