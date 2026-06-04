#!/usr/bin/env python3
"""Generate a repair encyclopedia guide from a Circuit-AI analysis JSON file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.intelligence.repair_encyclopedia import RepairEncyclopedia


def _markdown(guide: Dict[str, Any]) -> str:
    family = guide.get("device_family") or {}
    evidence = guide.get("scan_evidence") or {}
    safety = guide.get("safety_profile") or {}
    lines: List[str] = [
        "# Repair Encyclopedia Guide",
        "",
        f"Quick summary: {guide.get('quick_summary', '')}",
        "",
        "## Device Family",
        f"- Family: {family.get('label')} (`{family.get('id')}`)",
        f"- Confidence: {family.get('confidence')}",
        f"- Evidence: {', '.join(family.get('evidence', []) or ['none'])}",
        "",
        "## Scan Evidence",
        f"- Board type: {evidence.get('board_type')}",
        f"- Board confidence: {evidence.get('board_confidence')}",
        f"- Components detected: {evidence.get('components_detected')}",
        f"- Components by type: {json.dumps(evidence.get('components_by_type', {}), sort_keys=True)}",
        f"- Connector candidates: {evidence.get('connector_count')}",
        f"- AOI readiness: {evidence.get('aoi_readiness')}",
        "",
        "## Safety",
        f"- Risk level: {safety.get('risk_level')}",
    ]
    for rule in safety.get("rules", []) or []:
        lines.append(f"- {rule}")

    lines.extend(["", "## Top Fault Candidates"])
    for candidate in (guide.get("fault_candidates") or [])[:4]:
        lines.append(f"- {candidate.get('name')} (`{candidate.get('fault_id')}`), likelihood {candidate.get('likelihood')}")
        for item in (candidate.get("evidence") or [])[:3]:
            lines.append(f"  - evidence: {item}")

    lines.extend(["", "## Diagnostic Flow"])
    for step in guide.get("diagnostic_flow", []) or []:
        lines.append(f"{step.get('order')}. {step.get('title')}")
        lines.append(f"   - Purpose: {step.get('purpose')}")
        lines.append(f"   - Pass: {step.get('pass_condition')}")
        lines.append(f"   - If fail: {step.get('fail_branch')}")

    tools = (guide.get("parts_and_tools") or {}).get("tools", [])
    parts = (guide.get("parts_and_tools") or {}).get("likely_parts", [])
    lines.extend(
        [
            "",
            "## Parts And Tools",
            f"- Tools: {', '.join(tools)}",
            f"- Likely parts: {', '.join(parts) if parts else 'none identified yet'}",
            "",
            "## Evidence To Collect Next",
        ]
    )
    for item in guide.get("evidence_to_collect_next", []) or []:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a repair guide from analysis JSON")
    parser.add_argument("--analysis", required=True, help="analysis JSON file")
    parser.add_argument("--symptom", action="append", default=[], help="reported symptom; repeatable")
    parser.add_argument("--device-hint", default="", help="device type hint")
    parser.add_argument("--output", required=True, help="JSON output path")
    parser.add_argument("--markdown-output", help="optional Markdown output path")
    args = parser.parse_args()

    analysis = json.loads(Path(args.analysis).read_text(encoding="utf-8"))
    guide = RepairEncyclopedia().generate(
        analysis=analysis,
        symptoms=args.symptom,
        device_hint=args.device_hint,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(guide, indent=2), encoding="utf-8")
    print(f"wrote {output}")

    if args.markdown_output:
        markdown_output = Path(args.markdown_output)
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(_markdown(guide), encoding="utf-8")
        print(f"wrote {markdown_output}")

    print(f"{guide['device_family']['label']} | top={guide['fault_candidates'][0]['name'] if guide['fault_candidates'] else 'none'} | confidence={guide['confidence']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
