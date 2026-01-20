#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ReportArtifact:
    filename: str
    content_type: str
    content: str


def _md_escape(s: str) -> str:
    return (s or "").replace("\r", "").strip()


def _format_money(budget_usd: Optional[float]) -> str:
    if budget_usd is None:
        return "N/A"
    return f"${budget_usd:,.0f}"


def _issue_line(issue: Dict[str, Any]) -> str:
    sev = _md_escape(str(issue.get("severity") or ""))
    comp = _md_escape(str(issue.get("component") or ""))
    title = _md_escape(str(issue.get("issue") or ""))
    sol = _md_escape(str(issue.get("solution") or ""))
    phys = issue.get("physics")
    phys_s = ""
    if isinstance(phys, dict):
        bits = []
        for k in ("current_a", "voltage_drop", "current_width_mm", "required_width_mm"):
            if k in phys and phys[k] is not None:
                bits.append(f"{k}={phys[k]}")
        if bits:
            phys_s = " (" + ", ".join(bits) + ")"
    if sol:
        return f"- **{sev}** — {comp}: {title}{phys_s}\n  - Fix: {sol}"
    return f"- **{sev}** — {comp}: {title}{phys_s}"


def render_dfm_report_markdown(
    *,
    title: str,
    validation_response: Dict[str, Any],
    bom_summary: Optional[Dict[str, Any]] = None,
    pnp_csv_filename: Optional[str] = None,
    gerber_zip_filename: Optional[str] = None,
    export_method: Optional[str] = None,
    pnp_export_method: Optional[str] = None,
    netlist_export_method: Optional[str] = None,
) -> str:
    """
    Render a client-facing, audit-style report from the existing v2 validation response.
    This intentionally avoids overclaiming “RF signoff”, etc.
    """
    now = datetime.now(timezone.utc).isoformat()
    status = str(validation_response.get("status") or "")
    v = validation_response.get("validation") if isinstance(validation_response.get("validation"), dict) else {}

    issues = v.get("issues") if isinstance(v.get("issues"), list) else []
    counts = {
        "critical": int(v.get("critical") or 0),
        "errors": int(v.get("errors") or 0),
        "warnings": int(v.get("warnings") or 0),
        "issues_count": int(v.get("issues_count") or len(issues) or 0),
    }
    manufacturing_ready = bool(validation_response.get("manufacturing_ready"))

    lines: List[str] = []
    lines.append(f"# { _md_escape(title) }")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Generated: `{now}` (UTC)")
    lines.append(f"- Validation status: `{status}`")
    lines.append(f"- Manufacturing-ready (automated): `{manufacturing_ready}`")
    lines.append(
        f"- Issue counts: critical={counts['critical']}, errors={counts['errors']}, warnings={counts['warnings']} (total={counts['issues_count']})"
    )
    if export_method:
        lines.append(f"- Gerber export method: `{export_method}`")
    if export_method == "sample":
        lines.append("- ⚠️ Gerbers were produced by a placeholder generator (no `kicad-cli` available). Do not fabricate from these outputs.")
    if pnp_export_method:
        lines.append(f"- PnP export method: `{pnp_export_method}`")
    if netlist_export_method:
        lines.append(f"- Netlist source: `{netlist_export_method}`")
    lines.append("")

    lines.append("## Findings (Top)")
    if issues:
        for it in issues[:25]:
            if isinstance(it, dict):
                lines.append(_issue_line(it))
    else:
        lines.append("- No issues reported.")
    lines.append("")

    if bom_summary:
        lines.append("## BOM Summary")
        for k in ("total_components", "unique_parts", "parts_with_digikey_numbers", "estimated_total_cost"):
            if k in bom_summary:
                lines.append(f"- {k}: `{bom_summary[k]}`")
        lines.append("")

    lines.append("## Artifacts")
    if gerber_zip_filename:
        lines.append(f"- Gerbers ZIP: `{gerber_zip_filename}`")
    if pnp_csv_filename:
        lines.append(f"- Pick-and-place CSV: `{pnp_csv_filename}`")
    lines.append("")

    lines.append("## Notes / Limitations")
    lines.append("- This is an automated preflight report; it does not replace full EE review (RF/antenna, controlled impedance, safety compliance, etc.).")
    lines.append("- For full electrical power analysis, provide realistic power hints (`sources`, `loads_cc`, `voltage_constraints`) when validating.")
    lines.append("")

    ns = validation_response.get("next_steps")
    if isinstance(ns, list) and ns:
        lines.append("## Next Steps")
        for s in ns[:20]:
            lines.append(f"- { _md_escape(str(s)) }")
        lines.append("")

    return "\n".join(lines).strip() + "\n"
