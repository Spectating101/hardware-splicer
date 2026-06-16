#!/usr/bin/env python3
"""Audit regex/keyword scaffolds vs LLM-first paths in Hardware-Splicer."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "hardware_splicer"
APPS = ROOT / "apps"


@dataclass
class ScaffoldFinding:
    id: str
    severity: str  # high | medium | low | ok
    layer: str
    path: str
    summary: str
    llm_replacement: str
    env_knob: str = ""


FINDINGS: List[ScaffoldFinding] = [
    ScaffoldFinding(
        "module_resolver_patterns",
        "medium",
        "salvage",
        "src/hardware_splicer/module_resolver.py",
        "40+ regex _MODULE_PATTERNS — offline fallback only since llm_first salvage",
        "resolve_parts_to_modules_with_llm + call_qwen_salvage_map_intake",
        "HARDWARE_SPLICER_SALVAGE_RESOLVE=llm_first",
    ),
    ScaffoldFinding(
        "module_picker_hints",
        "high",
        "open_compose",
        "src/hardware_splicer/module_picker.py",
        "MODULE_HINTS regex stack picks modules from NL goals",
        "call_qwen_module_pick before pick_modules_for_goal",
        "HARDWARE_SPLICER_QWEN_MODULE_PICK=1",
    ),
    ScaffoldFinding(
        "phrase_expander",
        "high",
        "routing",
        "src/hardware_splicer/phrase_expander.py",
        "REWRITES regex maps casual speech to canned phrases",
        "LLM phrase normalize or pass raw goal to Qwen compose",
        "disable via compose path — no env yet",
    ),
    ScaffoldFinding(
        "salvage_pick_build_id",
        "medium",
        "salvage",
        "src/hardware_splicer/salvage_bridge.py",
        "Keyword any(word in text) still offline fallback; LLM build pick runs first when keyed",
        "call_qwen_build_pick (default when keyed)",
        "HARDWARE_SPLICER_QWEN_BUILD_PICK=1",
    ),
    ScaffoldFinding(
        "project_intake_keywords",
        "medium",
        "intake",
        "src/hardware_splicer/project_intake.py",
        "Duplicate keyword build/slot inference",
        "Reuse qwen_build_pick + salvage LLM map",
        "",
    ),
    ScaffoldFinding(
        "netlist_catalog_hint",
        "medium",
        "compose",
        "src/hardware_splicer/integrations/qwen_netlist_compose.py",
        "Tiny hardcoded _MODULE_CATALOG_HINT (~15 modules)",
        "catalog_context_for_goal (full library slice)",
        "",
    ),
    ScaffoldFinding(
        "compose_module_picker_fallback",
        "medium",
        "open_compose",
        "src/hardware_splicer/integrations/qwen_netlist_compose.py",
        "Regex module_picker only when OFFLINE_COMPOSE=1 or QWEN_COMPOSE=0",
        "qwen netlist → qwen_module_pick chain when keyed",
        "HARDWARE_SPLICER_OFFLINE_COMPOSE=1 for regex fallback",
    ),
    ScaffoldFinding(
        "scratch_deterministic_fixup",
        "medium",
        "compile_retry",
        "src/hardware_splicer/scratch_pipeline.py",
        "_deterministic_fixup hardcodes module adds per attempt",
        "qwen_compose_retry + workshop review",
        "HARDWARE_SPLICER_QWEN_COMPOSE_RETRY=1",
    ),
    ScaffoldFinding(
        "gap_fill_l298n",
        "low",
        "salvage",
        "src/hardware_splicer/module_resolver.py",
        "fill_salvage_gaps adds l298n by rule",
        "qwen_workshop_review (optional)",
        "HARDWARE_SPLICER_QWEN_WORKSHOP=1",
    ),
    ScaffoldFinding(
        "firmware_scaffold",
        "ok",
        "firmware",
        "src/hardware_splicer/firmware_scaffold.py",
        "Template Arduino/C++ stubs — intentional receipt, not NL routing",
        "Keep; optional LLM firmware later",
        "",
    ),
    ScaffoldFinding(
        "catalog_recipes",
        "ok",
        "compile",
        "src/hardware_splicer/data/catalog_recipes.json",
        "Hand-curated wiring recipes — compile truth, not NL intelligence",
        "LLM picks recipe via build_pick; DRC validates",
        "",
    ),
    ScaffoldFinding(
        "kicad_drc_ngspice",
        "ok",
        "truth",
        "src/hardware_splicer/netlist/compile.py",
        "External prove gates — keep deterministic",
        "Never LLM-judge",
        "",
    ),
    ScaffoldFinding(
        "circuit_ai_intent_parser",
        "high",
        "legacy_apps",
        "apps/circuit-ai/src/intelligence/intent_parser.py",
        "Legacy keyword PROJECT_KEYWORDS parser",
        "llm_intent_parser.py (exists, use LLM path)",
        "use_llm=True",
    ),
    ScaffoldFinding(
        "frontend_plan_to_graph",
        "ok",
        "frontend",
        "apps/circuit-ai/circuit-ai-frontend/lib/salvage/plan-to-graph.ts",
        "Recipe translator — fed by Python engine plans",
        "Python plan_to_graph + LLM upstream",
        "",
    ),
    ScaffoldFinding(
        "robotics_platform_authority",
        "medium",
        "mech",
        "src/hardware_splicer/robotics_platform_authority.py",
        "Keyword platform classification (deferred mech path)",
        "Defer / LLM when mech returns",
        "",
    ),
]


def _scan_repo_patterns() -> List[Dict[str, Any]]:
    """Ripgrep-style counts for maintenance signal."""
    patterns = {
        "re.compile": 0,
        "any(word in text": 0,
        "MODULE_HINTS": 0,
        "matched_on": 0,
        "module_picker_fallback": 0,
        "fallback": 0,
    }
    for path in list(SRC.rglob("*.py")) + list((APPS / "circuit-ai" / "src").rglob("*.py") if (APPS / "circuit-ai" / "src").is_dir() else []):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for key in patterns:
            patterns[key] += text.count(key)
    return patterns


def _env_defaults() -> Dict[str, str]:
    import os
    from hardware_splicer.env_local import load_env_local
    from hardware_splicer.integrations.qwen_text_client import qwen_configured
    from hardware_splicer.integrations.qwen_salvage_resolver import salvage_resolve_mode

    load_env_local()
    return {
        "qwen_configured": str(qwen_configured()),
        "salvage_resolve_mode": salvage_resolve_mode(),
        "QWEN_SALVAGE": os.environ.get("HARDWARE_SPLICER_QWEN_SALVAGE", "1"),
        "QWEN_COMPOSE": os.environ.get("HARDWARE_SPLICER_QWEN_COMPOSE", "1"),
            "HARDWARE_SPLICER_QWEN_WORKSHOP": os.environ.get("HARDWARE_SPLICER_QWEN_WORKSHOP", "1"),
        "QWEN_BUILD_PICK": os.environ.get("HARDWARE_SPLICER_QWEN_BUILD_PICK", "1"),
        "QWEN_MODULE_PICK": os.environ.get("HARDWARE_SPLICER_QWEN_MODULE_PICK", "1"),
        "SALVAGE_RESOLVE": os.environ.get("HARDWARE_SPLICER_SALVAGE_RESOLVE", "(auto)"),
    }


def build_report() -> Dict[str, Any]:
    sys.path.insert(0, str(ROOT / "src"))
    high = [asdict(f) for f in FINDINGS if f.severity == "high"]
    medium = [asdict(f) for f in FINDINGS if f.severity == "medium"]
    return {
        "schema_version": "hardware_splicer.weak_scaffold_audit.v1",
        "summary": {
            "high_priority_weak": len(high),
            "medium_priority_weak": len(medium),
            "principle": "LLM reasons; catalog validates module_id; DRC/sim judges compile",
        },
        "env": _env_defaults(),
        "pattern_counts": _scan_repo_patterns(),
        "findings": [asdict(f) for f in FINDINGS],
        "recommended_defaults_when_keyed": {
            "HARDWARE_SPLICER_SALVAGE_RESOLVE": "llm_first",
            "HARDWARE_SPLICER_QWEN_SALVAGE": "1",
            "HARDWARE_SPLICER_QWEN_COMPOSE": "1",
            "HARDWARE_SPLICER_QWEN_MODULE_PICK": "1",
            "HARDWARE_SPLICER_QWEN_BUILD_PICK": "1",
            "HARDWARE_SPLICER_QWEN_WORKSHOP": "1",
            "HARDWARE_SPLICER_QWEN_COMPOSE_RETRY": "1",
            "HARDWARE_SPLICER_LLM_TRUST": "1",
            "offline_only": "set SALVAGE_RESOLVE=heuristic and QWEN_*=0",
        },
    }


def main() -> int:
    report = build_report()
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "WEAK_SCAFFOLD_AUDIT.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"\nhigh_priority_weak={report['summary']['high_priority_weak']}")
    print(f"report={out}")
    for f in report["findings"]:
        if f["severity"] in ("high", "medium"):
            print(f"  [{f['severity']}] {f['id']}: {f['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
