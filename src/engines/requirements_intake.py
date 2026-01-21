#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


LANES: Dict[str, str] = {
    "generic": "Generic PCB design / respin-prevention",
    "power": "Power / SMPS / high-current",
    "rf": "RF / antenna / impedance-controlled",
    "automotive": "Automotive constraints intake",
    "compliance": "Safety / compliance driven",
}

DESIGN_INTENTS: Dict[str, str] = {
    "prototype": "Prototype / functional-first (aesthetics optional)",
    "professional": "Production / polished (enclosure, DFM polish, presentation)",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _missing_fields(req: Dict[str, Any], required_paths: List[str]) -> List[str]:
    missing: List[str] = []
    for dotted in required_paths:
        cur: Any = req
        ok = True
        for part in dotted.split("."):
            if isinstance(cur, dict) and part in cur and cur[part] not in (None, "", [], {}):
                cur = cur[part]
                continue
            ok = False
            break
        if not ok:
            missing.append(dotted)
    return missing


def evaluate_requirements(req: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluate how "ready" a requirements object is for downstream work.

    Returns:
    - readiness_level: draft|reviewable|manufacturable
    - blockers: list[str] (items that prevent claiming higher readiness)
    - completeness_score: 0-100 (heuristic)
    """
    meta = req.get("meta") or {}
    manufacturing = req.get("manufacturing") or {}
    board = req.get("board") or {}
    intent = (meta.get("design_intent") or "prototype").strip()
    lane = (meta.get("lane") or "generic").strip()

    must_for_reviewable = [
        "meta.project_name",
        "manufacturing.fab.name",
        "board.layers",
    ]
    must_for_manufacturable = [
        "risk_and_validation.what_good_looks_like",
        "manufacturing.dnp_policy",
    ]

    # Lane-specific “to confidently validate” fields (still not a hard block to generate files).
    if lane == "power":
        must_for_manufacturable += [
            "power.sources",
            "power.rails",
            "power.loads",
        ]
    if lane == "rf":
        # Require explicit impedance/stackup notes to claim anything beyond draft.
        must_for_reviewable += ["board.stackup.notes"]

    blockers_reviewable = _missing_fields(req, must_for_reviewable)
    blockers_manufacturable = _missing_fields(req, must_for_manufacturable)

    # Professional intent expects enclosure/presentation constraints to be at least discussed.
    if intent == "professional":
        # Not hard-required, but we count it against score.
        pass

    # Simple scoring model based on filled “signal” fields.
    signal_fields = [
        ("meta.project_name", 10),
        ("manufacturing.fab.name", 10),
        ("board.layers", 10),
        ("board.constraints.min_trace_mm", 6),
        ("board.constraints.min_space_mm", 6),
        ("board.constraints.via_min_drill_mm", 4),
        ("board.constraints.copper_weight_oz", 4),
        ("risk_and_validation.what_good_looks_like", 10),
        ("risk_and_validation.test_plan", 6),
        ("manufacturing.dnp_policy", 4),
        ("manufacturing.preferred_part_source", 4),
        ("power.sources", 6),
        ("power.rails", 6),
        ("power.loads", 6),
        ("board.stackup.manufacturer", 4),
        ("board.stackup.notes", 4),
    ]
    score = 0
    for dotted, pts in signal_fields:
        if dotted not in _missing_fields(req, [dotted]):
            score += pts
    score = max(0, min(100, score))

    if blockers_reviewable:
        level = "draft"
        blockers = blockers_reviewable
    elif blockers_manufacturable:
        level = "reviewable"
        blockers = blockers_manufacturable
    else:
        level = "manufacturable"
        blockers = []

    return {
        "readiness_level": level,
        "blockers": blockers,
        "completeness_score": score,
        "lane": lane,
        "design_intent": intent,
    }


def template_for_lane(lane: str) -> Dict[str, Any]:
    lane = (lane or "").strip() or "generic"
    base: Dict[str, Any] = {
        "meta": {
            "lane": lane,
            "design_intent": "prototype",
            "generated_at": _utc_now(),
            "client_name": "",
            "project_name": "",
            "timezone": "",
        },
        "deliverables": {
            "schematic": True,
            "pcb_layout": True,
            "bom": True,
            "pnp": True,
            "gerbers": True,
            "dfm_memo": True,
            "bringup_notes": False,
        },
        "board": {
            "layers": None,
            "dimensions_mm": {"x": None, "y": None},
            "stackup": {"manufacturer": "", "notes": ""},
            "constraints": {
                "min_trace_mm": None,
                "min_space_mm": None,
                "via_min_drill_mm": None,
                "copper_weight_oz": None,
            },
        },
        "interfaces": [],
        "power": {
            "rails": [],
            "sources": [],
            "loads": [],
        },
        "manufacturing": {
            "fab": {"name": "", "url": "", "notes": ""},
            "assembly": {"name": "", "notes": ""},
            "dnp_policy": "explicit",
            "preferred_part_source": "",
        },
        "risk_and_validation": {
            "what_good_looks_like": "",
            "test_plan": "",
            "known_risks": [],
            "explicit_exclusions": [],
        },
    }

    if lane == "power":
        base["power"]["rails"] = [
            {"name": "VIN", "voltage_v": None, "max_current_a": None, "notes": ""},
            {"name": "3V3", "voltage_v": 3.3, "max_current_a": None, "notes": "Target rail"},
        ]
        base["risk_and_validation"]["explicit_exclusions"] = [
            "No conducted/radiated EMI compliance testing (needs lab).",
            "No thermal chamber validation unless provided by client.",
        ]
    elif lane == "rf":
        base["board"]["stackup"]["notes"] = "Provide impedance targets + fab stackup (dielectric, Er, copper thickness) for controlled impedance."
        base["interfaces"] = [{"name": "RF path", "type": "RF", "targets": {"impedance_ohms": 50}, "notes": ""}]
        base["risk_and_validation"]["explicit_exclusions"] = [
            "No antenna matching/tuning without measurements (VNA) or hard reference constraints.",
            "No RF certification / regulatory signoff.",
        ]
    elif lane == "automotive":
        base["power"]["rails"] = [
            {"name": "VBAT", "voltage_v": 12.0, "max_current_a": None, "notes": "Define load dump/cold crank specs."},
            {"name": "5V", "voltage_v": 5.0, "max_current_a": None, "notes": ""},
            {"name": "3V3", "voltage_v": 3.3, "max_current_a": None, "notes": ""},
        ]
        base["risk_and_validation"]["explicit_exclusions"] = [
            "No ISO 26262 process compliance unless explicitly contracted.",
            "No EMC/ESD certification testing (lab).",
        ]
    elif lane == "compliance":
        base["risk_and_validation"]["explicit_exclusions"] = [
            "No formal certification issuance; certification requires accredited lab testing.",
        ]

    return base


def compile_to_circuit_ai_hints(req: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert intake requirements into Circuit-AI 'hints' (best-effort).

    Circuit-AI currently supports hints such as `sources`, `loads_cc`, and `voltage_constraints`
    for the KiCad validation workflow.
    """
    rails = (req.get("power") or {}).get("rails") or []
    sources = (req.get("power") or {}).get("sources") or []
    loads = (req.get("power") or {}).get("loads") or []

    hint_sources: List[Dict[str, Any]] = []
    for s in sources:
        if isinstance(s, dict):
            hint_sources.append(
                {
                    "name": s.get("name") or "source",
                    "voltage_v": s.get("voltage_v"),
                    "max_current_a": s.get("max_current_a"),
                    "notes": s.get("notes") or "",
                }
            )

    loads_cc: List[Dict[str, Any]] = []
    for l in loads:
        if isinstance(l, dict):
            loads_cc.append(
                {
                    "name": l.get("name") or "load",
                    "rail": l.get("rail") or "",
                    "current_a": l.get("current_a"),
                    "notes": l.get("notes") or "",
                }
            )

    v_constraints: List[Dict[str, Any]] = []
    for r in rails:
        if isinstance(r, dict) and r.get("name") and r.get("voltage_v") is not None:
            v_constraints.append(
                {
                    "rail": r.get("name"),
                    "nominal_v": r.get("voltage_v"),
                    "min_v": r.get("min_v"),
                    "max_v": r.get("max_v"),
                    "notes": r.get("notes") or "",
                }
            )

    return {
        "sources": hint_sources,
        "loads_cc": loads_cc,
        "voltage_constraints": v_constraints,
    }


def build_questions_and_assumptions(req: Dict[str, Any]) -> Tuple[List[str], List[str], List[str]]:
    lane = ((req.get("meta") or {}).get("lane") or "generic").strip()
    intent = ((req.get("meta") or {}).get("design_intent") or "prototype").strip()
    required = [
        "meta.project_name",
        "manufacturing.fab.name",
        "risk_and_validation.what_good_looks_like",
    ]
    if lane in ("rf", "compliance", "automotive", "power"):
        required += ["board.layers"]

    missing = _missing_fields(req, required)
    questions: List[str] = []
    assumptions: List[str] = []
    risks: List[str] = []

    for m in missing:
        questions.append(f"Please provide `{m}` (required to avoid guessing).")

    questions += [
        "What is the target PCB manufacturer (or at least their min trace/space/via rules)?",
        "Any mechanical constraints (enclosure, connectors placement, keepouts)?",
        "Is this a single-pass deliverable or an iterative revision loop?",
    ]

    if intent == "professional":
        questions += [
            "Are there any presentation/aesthetic requirements (board outline, silkscreen quality, labels, testpoints)?",
            "Do you have an enclosure/3D model and mounting hole requirements?",
        ]
    else:
        questions += [
            "Is this explicitly a prototype (OK if placement is utilitarian as long as it works)?",
            "Any constraints about reusing parts/wiring (flying leads, off-board components, tall parts allowed)?",
        ]

    if lane == "rf":
        questions += [
            "What impedance targets are required (50 ohm single-ended, 90/100 ohm diff)?",
            "Do you have the exact fab stackup (dielectric thickness, Er, copper thickness)?",
            "Do you have measurement capability (VNA), or should RF be treated as 'layout toward reference only'?",
        ]
        risks += [
            "RF performance cannot be guaranteed without constraints + measurements; treat as 'best-effort to reference design' unless VNA/targets are provided.",
        ]
    if lane == "power":
        questions += [
            "Provide max current per rail + transient requirements (startup, inrush, load step).",
            "Any thermal limits (ambient temp, enclosure, airflow)?",
            "Any EMI constraints (sensitive radios, conducted emissions target)?",
        ]
        risks += [
            "SMPS stability/EMI/thermal may require iteration and/or lab validation; scope accordingly.",
        ]
    if lane == "automotive":
        questions += [
            "Define input transients: load dump, cold crank, reverse battery, jump start specs.",
            "Define ESD/EMC targets (OEM requirements / ISO standards) if any.",
        ]
        risks += [
            "Automotive-grade robustness depends on transient specs; avoid implicit liability without explicit requirements.",
        ]
    if lane == "compliance":
        questions += [
            "What compliance targets apply (UL/IEC standard, CE directives, creepage/clearance requirements)?",
            "What is the working voltage category/pollution degree/environment?",
        ]
        risks += [
            "Compliance is a process; layout can be prepared toward targets but certification requires lab testing.",
        ]

    assumptions += [
        "Work proceeds iteratively: deliver Draft-1 quickly, collect client corrections, then converge to manufacturing package.",
        "Anything not provided as a requirement is treated as an open question and will be flagged, not silently assumed.",
    ]

    return questions, assumptions, risks


def render_sow(req: Dict[str, Any], questions: List[str], assumptions: List[str], risks: List[str]) -> str:
    meta = req.get("meta") or {}
    proj = meta.get("project_name") or "PROJECT"
    lane = meta.get("lane") or "generic"
    intent = meta.get("design_intent") or "prototype"
    excl = ((req.get("risk_and_validation") or {}).get("explicit_exclusions") or []) if isinstance(req.get("risk_and_validation"), dict) else []
    deliver = req.get("deliverables") or {}

    def yn(v: Any) -> str:
        return "yes" if bool(v) else "no"

    lines: List[str] = []
    lines.append(f"# SOW — {proj}")
    lines.append("")
    lines.append(f"- Lane: `{lane}`")
    lines.append(f"- Design intent: `{intent}`")
    lines.append(f"- Generated: `{_utc_now()}` (UTC)")
    lines.append("")
    lines.append("## Deliverables")
    lines.append(f"- Schematic: `{yn(deliver.get('schematic'))}`")
    lines.append(f"- PCB layout: `{yn(deliver.get('pcb_layout'))}`")
    lines.append(f"- BOM: `{yn(deliver.get('bom'))}`")
    lines.append(f"- Pick-and-place: `{yn(deliver.get('pnp'))}`")
    lines.append(f"- Gerbers: `{yn(deliver.get('gerbers'))}`")
    lines.append(f"- DFM memo: `{yn(deliver.get('dfm_memo'))}`")
    lines.append(f"- Bring-up notes: `{yn(deliver.get('bringup_notes'))}`")
    lines.append("")
    lines.append("## Open Questions (must answer to avoid guessing)")
    if questions:
        for q in questions[:60]:
            lines.append(f"- {q}")
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## Assumptions")
    for a in assumptions:
        lines.append(f"- {a}")
    lines.append("")
    lines.append("## Risks / Validation Notes")
    for r in risks:
        lines.append(f"- {r}")
    lines.append("")
    lines.append("## Exclusions (explicit)")
    if excl:
        for e in excl:
            lines.append(f"- {e}")
    else:
        lines.append("- None listed")
    lines.append("")
    lines.append("## Acceptance Criteria (practical)")
    lines.append("- Deliverables package generated and reproducible (BOM/PnP/Gerbers/DFM memo).")
    lines.append("- Critical issues enumerated with proposed fixes; client confirms priorities for trade-offs.")
    lines.append("- Missing constraints are explicitly documented (no silent assumptions).")
    return "\n".join(lines).rstrip() + "\n"
