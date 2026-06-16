"""Qwen plain-language JARVIS summary over electrical trust artifacts."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Mapping, Optional

from .qwen_text_client import call_qwen_chat, qwen_configured

SCHEMA_VERSION = "hardware_splicer.jarvis_narrative.v1"


def jarvis_narrative_enabled() -> bool:
    if os.environ.get("HARDWARE_SPLICER_LLM_TRUST", "1").strip().lower() in {"0", "false", "no", "off"}:
        return False
    return qwen_configured()


def generate_jarvis_narrative(
    *,
    goal: str,
    trust_report: Mapping[str, Any],
    design_quality: Mapping[str, Any] | None = None,
    compose_mode: str | None = None,
) -> Dict[str, Any]:
    """Turn machine trust gates into a maker-facing explanation."""
    if not jarvis_narrative_enabled():
        return {
            "ok": False,
            "skipped": True,
            "error": "jarvis_narrative_disabled",
            "summary": str(trust_report.get("summary_markdown") or ""),
        }

    dq = dict(design_quality or {})
    compact = {
        "goal": goal,
        "compose_mode": compose_mode,
        "trust_level": trust_report.get("trust_level"),
        "trust_score": trust_report.get("trust_score"),
        "gates": trust_report.get("gates"),
        "blockers": trust_report.get("blockers"),
        "warnings": trust_report.get("warnings"),
        "simulation": trust_report.get("simulation"),
        "design_quality": {
            "build_ready": dq.get("build_ready"),
            "kicad_drc_errors": dq.get("kicad_drc_errors"),
            "copper_tier": dq.get("copper_tier"),
            "fab_recommendation": dq.get("fab_recommendation"),
        },
    }
    prompt = f"""You are JARVIS for a hardware workshop compiler. Explain this electrical build result to a maker in 4-6 short sentences.

Be honest: KiCad DRC and simulation gates are the truth, not your opinion. If copper is preview-only, say review before ordering boards. If build is trusted, say what they can do next (bench test, download KiCad, order parts).

Machine report JSON:
{json.dumps(compact, indent=2)}

Return JSON only:
{{
  "headline": "one line verdict",
  "summary": "4-6 sentences, plain language",
  "next_steps": ["step 1", "step 2", "step 3"],
  "confidence": "high|medium|low"
}}
"""
    response = call_qwen_chat(
        prompt,
        json_mode=True,
        stage="narrative",
        system="You explain hardware compile results clearly. Never claim fab-ready if fab_recommendation is review_required_preview_copper.",
    )
    if not response.get("ok"):
        return {**response, "skipped": False}

    try:
        parsed = json.loads(str(response.get("content") or "{}"))
    except json.JSONDecodeError:
        parsed = {"headline": "Build reviewed", "summary": str(response.get("content") or ""), "next_steps": [], "confidence": "medium"}

    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "provider": response.get("provider"),
        "model": response.get("model"),
        "usage": response.get("usage"),
        "headline": parsed.get("headline"),
        "summary": parsed.get("summary"),
        "next_steps": parsed.get("next_steps") or [],
        "confidence": parsed.get("confidence"),
    }


def attach_jarvis_narrative_to_trust_report(
    trust_report_path: str,
    narrative: Mapping[str, Any],
    *,
    goal: str = "",
) -> str:
    from pathlib import Path

    path = Path(trust_report_path)
    body = json.loads(path.read_text(encoding="utf-8"))
    body["jarvis"] = dict(narrative)
    if narrative.get("headline"):
        body["jarvis_headline"] = narrative.get("headline")
    if narrative.get("summary"):
        body["jarvis_summary"] = narrative.get("summary")
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")
    md_path = path.with_suffix(".md")
    lines = [
        f"# Electrical trust — {goal or body.get('build_id') or 'build'}",
        "",
        f"**{narrative.get('headline') or body.get('trust_level')}**",
        "",
        str(narrative.get("summary") or body.get("summary_markdown") or ""),
        "",
    ]
    steps = narrative.get("next_steps") or []
    if steps:
        lines.append("## Next steps")
        lines.extend(f"- {step}" for step in steps)
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return str(path)
