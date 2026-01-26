from __future__ import annotations

from typing import Any, Dict, List, Optional


def render_ee_quality_report_md(
    *,
    requirements: Dict[str, Any],
    readiness: Dict[str, Any],
    lane_checks: Dict[str, Any],
    capabilities: Dict[str, Any],
    sow_md: Optional[str] = None,
    layout_report_md: Optional[str] = None,
) -> str:
    meta = requirements.get("meta") or {}
    proj = meta.get("project_name") or "PROJECT"
    lane = meta.get("lane") or "generic"
    intent = meta.get("design_intent") or "prototype"

    quality = (lane_checks or {}).get("quality") if isinstance((lane_checks or {}).get("quality"), dict) else {}
    score = quality.get("score")
    grade = quality.get("grade")
    confidence = quality.get("confidence")

    lines: List[str] = []
    lines.append(f"# EE Quality Report — {proj}")
    lines.append("")
    lines.append(f"- Lane: `{lane}`")
    lines.append(f"- Design intent: `{intent}`")
    lines.append(f"- Readiness: `{(readiness or {}).get('readiness_level')}`")
    if grade is not None:
        lines.append(f"- Quality grade: `{grade}` (score `{score}`, confidence `{confidence}`)")
    lines.append("")

    lines.append("## Capability Matrix (bounded)")
    caps = (capabilities or {}).get("capabilities") if isinstance((capabilities or {}).get("capabilities"), dict) else {}
    if caps:
        for k in sorted(caps.keys()):
            c = caps[k] or {}
            lines.append(f"- `{k}`: `{c.get('status')}` — {c.get('notes') or ''}".rstrip())
            blockers = c.get("blockers") or []
            if blockers:
                # Keep compact.
                lines.append(f"  - blockers: `{', '.join(blockers[:8])}`" + (" …" if len(blockers) > 8 else ""))
    else:
        lines.append("- None")
    lines.append("")

    lines.append("## Key Issues (from checks)")
    issues = (lane_checks or {}).get("issues") or []
    if issues:
        for issue in issues[:40]:
            if isinstance(issue, dict):
                sev = issue.get("severity") or "warning"
                it = issue.get("type") or "issue"
                msg = issue.get("message") or ""
                lines.append(f"- `{sev}` `{it}`: {msg}".rstrip())
    else:
        lines.append("- None detected (or missing inputs prevented checks).")
    lines.append("")

    mi = (lane_checks or {}).get("missing_inputs") or []
    lines.append("## Missing Inputs (requested)")
    if mi:
        lines.append(f"- Count: `{len(mi)}`")
        for m in mi[:40]:
            lines.append(f"- `{m}`")
    else:
        lines.append("- None")
    lines.append("")

    if sow_md:
        lines.append("## SOW / Scope (generated)")
        lines.append(sow_md.strip())
        lines.append("")

    if layout_report_md:
        lines.append("## Layout Advice (heuristic)")
        lines.append(layout_report_md.strip())
        lines.append("")

    lines.append("## Notes")
    lines.append("- This report is conservative: it prefers asking for missing constraints over guessing.")
    lines.append("- It is not a certification; treat it as a structured engineering preflight + iteration aid.")
    return "\n".join(lines).rstrip() + "\n"

