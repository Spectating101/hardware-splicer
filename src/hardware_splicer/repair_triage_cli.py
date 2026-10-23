"""Generate inspectable repair triage packages from structured user observations.

Usage:
    python -m hardware_splicer.repair_triage_cli <intake.json> <out_dir>

The output describes proposed observations; it does not validate that tests
were performed, authorize disassembly/power-on, or make a repair decision.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from .repair_intake import repair_intake_report


def _safe(text: Any) -> str:
    """Keep line-derived markdown free of unintended new headings/formatting."""
    return " ".join(str(text or "").replace("|", "/").split())


def _render(report: Mapping[str, Any]) -> str:
    diagnostic = dict(report.get("repair_path_diagnostic") or {})
    lines = [
        "# Hardware Splicer — physical repair triage",
        "",
        "**Status: PROPOSED INVESTIGATION ONLY. NOT A VERIFIED REPAIR.**",
        "",
        f"**Device (declared):** {_safe(report.get('device_hint')) or 'unspecified'}",
        f"**Fault assessment:** {_safe(diagnostic.get('verdict')) or 'no structured path observations provided'}",
    ]
    if diagnostic.get("reason"):
        lines.append(f"**Insufficient evidence reason:** {_safe(diagnostic['reason'])}")
    lines += [
        "",
        "## Source symptoms",
        "",
    ]
    symptoms = report.get("symptoms") or []
    lines += [f"- {_safe(s)}" for s in symptoms] or [
        "- None supplied: do not infer facts from device category."
    ]
    if diagnostic:
        quality = diagnostic.get("evidence_quality") or {}
        lines += [
            "",
            "## Evidence-quality audit",
            "",
            f"- Independent component routes declared: {int(quality.get('distinct_component_route_count') or 0)}",
            f"- Observation count: {int(quality.get('reported_observation_count') or 0)}",
            f"- Condition-confounded routes: {len(quality.get('contradictory_same_route_observations') or [])}",
            f"- Supported component discrimination: {'yes (triage only)' if quality.get('discriminating_topology_supported') else 'NO'}",
            "",
            "## Unverified component hypotheses",
            "",
        ]
        candidates = diagnostic.get("candidates") or []
        if not candidates:
            lines.append("No component ranked. Collect discriminating evidence instead of guessing.")
        else:
            lines.append("| Priority | Candidate | Triage score (not probability) |")
            lines.append("| --- | --- | ---: |")
            for n, item in enumerate(candidates[:8],1):
                lines.append(
                    f"| {n} | {_safe(item.get('label') or item.get('component_id'))} "
                    f"| {item.get('triage_evidence_score_not_probability')} |"
                )
            if diagnostic.get("highest_evidence_score_tie_count", 0) > 1:
                lines.append("")
                lines.append("**Evidence tie:** top candidate ordering uses declared serviceability; it does not identify a uniquely failed component.")
        lines += ["", "## Proposed next observations — operator review required", ""]
        tests=diagnostic.get("recommended_tests") or []
        if not tests:
            lines.append("- No independently justified test proposal available.")
        for n, item in enumerate(tests,1):
            lines.append(f"{n}. **{_safe(item.get('code'))}** — {_safe(item.get('purpose'))}")
            lines.append(f"   - Evidence to collect: {_safe(item.get('proposed_observation'))}")
            lines.append(f"   - What it might distinguish: {_safe(item.get('discriminating_result'))}")
        lines += [
            "",
            "## Release and safety restrictions",
            "",
            "- Physical repair verified: **NO**",
            "- Power-on, fabrication, disassembly or operational authority granted: **NO**",
            "- Path membership, service-cost tiers and test reports are user declarations, not independently instrumented truth.",
            "- Follow manufacturer service precautions, qualification and applicable device hazards; no speculative live measurements.",
        ]
    else:
        lines += [
            "",
            "**No component hypothesis:** Only symptom intake was provided. "
            "Add structured physical path observations before requesting a diagnosis."
        ]
    return "\n".join(lines)+"\n"


def write_repair_triage_package(intake: Mapping[str, Any], output: str | Path) -> dict[str, Any]:
    target=Path(output)
    target.mkdir(parents=True, exist_ok=True)
    report=repair_intake_report(intake)
    j=target/"REPAIR_TRIAGE.json"
    m=target/"REPAIR_TRIAGE.md"
    j.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    m.write_text(_render(report),encoding="utf-8")
    return {
        "verdict": (report.get("repair_path_diagnostic") or {}).get("verdict") or "no_structured_diagnosis",
        "report_json": str(j),
        "report_markdown": str(m),
        "power_on_authorized": False,
        "physical_repair_verified": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="Report physical fault hypotheses without unsafe action authority")
    parser.add_argument("intake_json",type=Path)
    parser.add_argument("output_directory",type=Path)
    args=parser.parse_args(argv)
    body=json.loads(args.intake_json.read_text(encoding="utf-8"))
    if not isinstance(body,dict):
        parser.error("repair intake must be a JSON object")
    result=write_repair_triage_package(body,args.output_directory)
    print(json.dumps(result,indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
