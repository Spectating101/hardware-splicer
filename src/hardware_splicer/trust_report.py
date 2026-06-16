"""Plain-language electrical trust report for CLI/chat consumers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

SCHEMA_VERSION = "hardware_splicer.trust_report.v1"


def build_trust_report(
    *,
    design_quality: Mapping[str, Any],
    simulation: Optional[Mapping[str, Any]] = None,
    erc: Optional[Mapping[str, Any]] = None,
    build_id: str = "",
) -> Dict[str, Any]:
    q = dict(design_quality or {})
    sim = dict(simulation or {})
    erc_body = dict(erc or {})

    gates = {
        "erc_pass": bool(q.get("erc_pass") if q.get("erc_pass") is not None else erc_body.get("pass")),
        "electrical_safety_pass": bool(q.get("electrical_safety_pass")),
        "kicad_drc_pass": bool(q.get("kicad_drc_pass")),
        "kicad_erc_pass": bool(q.get("kicad_erc_pass", True)),
        "build_graph_compiled": bool(q.get("build_graph_compiled")),
        "simulation_pass": sim.get("simulation_pass"),
        "simulation_skipped": bool(sim.get("skipped")),
    }

    blockers: list[str] = []
    warnings: list[str] = []

    if not gates["build_graph_compiled"]:
        blockers.append("Build graph did not compile.")
    if not gates["electrical_safety_pass"]:
        blockers.append("Electrical safety checks failed.")
    if not gates["kicad_drc_pass"]:
        blockers.append(f"KiCad DRC has {int(q.get('kicad_drc_errors') or 0)} error(s).")
    if gates["erc_pass"] is False:
        blockers.append("Schematic ERC failed.")
    if sim.get("enabled") and sim.get("simulation_pass") is False:
        blockers.append("Electrical simulation or power budget check failed.")
    for issue in (sim.get("power_budget") or {}).get("issues") or []:
        msg = str(issue.get("message") or "")
        if not msg:
            continue
        if str(issue.get("severity")).lower() in {"warn", "warning"}:
            warnings.append(msg)
        elif str(issue.get("severity")).lower() == "error" and msg not in blockers:
            blockers.append(msg)

    if q.get("fab_recommendation"):
        warnings.append(f"Fab guidance: {q.get('fab_recommendation')}")

    score = 0.0
    if gates["build_graph_compiled"]:
        score += 0.15
    if gates["electrical_safety_pass"]:
        score += 0.2
    if gates["kicad_drc_pass"]:
        score += 0.25
    if gates["erc_pass"]:
        score += 0.15
    if sim.get("simulation_pass") is True:
        score += 0.15
    elif sim.get("skipped"):
        score += 0.05
    if bool(q.get("build_ready")):
        score += 0.1

    trust_level = "blocked"
    if not blockers and bool(q.get("build_ready")):
        trust_level = "build_trusted"
    elif not blockers:
        trust_level = "review_recommended"

    summary_lines = [
        f"Build `{build_id or q.get('effective_build_id') or 'unknown'}` electrical trust report.",
        f"Trust level: **{trust_level}** (score {min(score, 1.0):.2f}).",
    ]
    if gates["kicad_drc_pass"]:
        summary_lines.append("KiCad DRC: clean.")
    else:
        summary_lines.append("KiCad DRC: failed.")
    if sim.get("skipped"):
        summary_lines.append("Simulation: skipped.")
    elif sim.get("simulation_pass") is True:
        load = (sim.get("power_budget") or {}).get("estimated_load_a")
        summary_lines.append(f"Simulation: pass (estimated load ~{load}A).")
    elif sim.get("enabled"):
        summary_lines.append("Simulation: failed or inconclusive.")
    if blockers:
        summary_lines.append("Blockers: " + "; ".join(blockers))
    if warnings:
        summary_lines.append("Warnings: " + "; ".join(warnings[:4]))

    return {
        "schema_version": SCHEMA_VERSION,
        "build_id": build_id or q.get("effective_build_id"),
        "trust_level": trust_level,
        "trust_score": round(min(score, 1.0), 3),
        "gates": gates,
        "blockers": blockers,
        "warnings": warnings,
        "summary_markdown": "\n".join(summary_lines),
        "design_quality": {
            "build_ready": q.get("build_ready"),
            "fabrication_ready": q.get("fabrication_ready"),
            "copper_tier": q.get("copper_tier"),
            "fab_recommendation": q.get("fab_recommendation"),
            "kicad_drc_errors": q.get("kicad_drc_errors"),
        },
        "simulation": {
            "pass": sim.get("simulation_pass"),
            "skipped": sim.get("skipped"),
            "estimated_load_a": (sim.get("power_budget") or {}).get("estimated_load_a"),
            "margin_a": (sim.get("power_budget") or {}).get("margin_a"),
            "ngspice_ok": (sim.get("spice") or {}).get("ok"),
        },
        "editor_note": (
            "CLI/chat is the primary path; open KiCad exports only when you want to inspect the receipt."
        ),
    }


def write_trust_report(
    out_dir: str | Path,
    *,
    design_quality: Mapping[str, Any],
    simulation: Optional[Mapping[str, Any]] = None,
    erc: Optional[Mapping[str, Any]] = None,
    build_id: str = "",
) -> str:
    report = build_trust_report(
        design_quality=design_quality,
        simulation=simulation,
        erc=erc,
        build_id=build_id,
    )
    path = Path(out_dir) / "TRUST_REPORT.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path = Path(out_dir) / "TRUST_REPORT.md"
    md_path.write_text(str(report.get("summary_markdown") or "") + "\n", encoding="utf-8")
    return str(path)
