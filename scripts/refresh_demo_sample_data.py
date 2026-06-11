#!/usr/bin/env python3
"""Regenerate dashboard sample-data.js from backend tier scoring."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS_DIR = (ROOT / "scripts").resolve()
sys.path = [str(SRC)] + [p for p in sys.path if Path(p).resolve() != SCRIPTS_DIR]

from hardware_splicer.project_intake import load_project_intake, run_project_intake  # noqa: E402
from hardware_splicer.scoring_summary import scorecard_from_artifacts  # noqa: E402


def _gate_gaps(gates: list[dict]) -> list[str]:
    return [row["id"] for row in gates if not row.get("passed")]


def _top_blockers(gates: list[dict], limit: int = 3) -> list[str]:
    blockers: list[str] = []
    for row in gates:
        if row.get("passed"):
            continue
        blockers.extend(str(item) for item in (row.get("blockers") or [])[:1])
    return blockers[:limit]


def _run_intake(brief_rel: str, out_name: str) -> dict:
    brief = ROOT / brief_rel
    out_dir = Path("/tmp/hardware_splicer_demo_refresh") / out_name
    out_dir.mkdir(parents=True, exist_ok=True)
    intake = load_project_intake(brief)
    result = run_project_intake(intake, out_dir=out_dir, start_splicer=False)
    if not result.get("ok"):
        raise RuntimeError(f"intake failed for {brief_rel}: {result}")
    return scorecard_from_artifacts(out_dir)


def _plant_project(project_id: str, name: str, brief_rel: str, goal: str) -> dict:
    card = _run_intake(brief_rel, project_id)
    gates = card.get("gates") or []
    return {
        "id": project_id,
        "name": name,
        "archetype": "automatic_watering",
        "goal": goal,
        "level": card.get("project_authority_level"),
        "authorityScore": card.get("authority_score"),
        "planningConfidence": 0.82 if card.get("authority_score", 0) < 1 else 0.95,
        "claimable": True,
        "simulationReady": card.get("production_ready") is True,
        "releaseReady": card.get("production_ready") is True,
        "production": {
            "score": card.get("production_readiness_score"),
            "band": "production release" if card.get("production_ready") else "control safety planning",
            "gatesPassed": card.get("gates_passed"),
            "gatesTotal": card.get("gates_total"),
            "gaps": _gate_gaps(gates),
            "blockers": _top_blockers(gates),
        },
        "functionalDelivery": {
            "score": card.get("functional_delivery_score"),
            "grade": card.get("functional_delivery_grade"),
        },
        "nextLevel": "production_ready_project_package"
        if not card.get("production_ready")
        else "field_validated_project_package",
        "claimBoundary": (
            "Evidence-backed scoped release is closed."
            if card.get("production_ready")
            else "Control stack is coherent. Bench evidence and reviewed release scope are still required."
        ),
        "missingInfo": card.get("evidence_gap_ids") or [],
        "margins": [
            {"label": "current margin", "value": "1.526x", "width": "64%"},
            {"label": "runtime margin", "value": "6.098x", "width": "92%"},
            {"label": "functional delivery", "value": f"{card.get('functional_delivery_score')}%", "width": "88%"},
        ],
        "subsystems": [
            {"id": "circuit", "label": "Circuit", "level": "compiler-verified DRC", "ready": True},
            {
                "id": "mechanical",
                "label": "Mechanical",
                "level": "measured release" if card.get("production_ready") else "candidate geometry",
                "ready": any(g["id"] == "mechanical_release" and g["passed"] for g in gates),
            },
            {
                "id": "robotics_actuation",
                "label": "Actuation",
                "level": "bench release" if card.get("production_ready") else "drive matched",
                "ready": any(g["id"] == "robotics_actuation_release" and g["passed"] for g in gates),
            },
            {
                "id": "robotics_simulation",
                "label": "Simulation",
                "level": "cleared" if card.get("production_ready") else "evidence blocked",
                "ready": any(g["id"] == "deterministic_simulation" and g["passed"] for g in gates),
            },
            {"id": "robotics_platform", "label": "Platform", "level": "control safety architecture", "ready": True},
            {
                "id": "mechatronics",
                "label": "Mechatronics",
                "level": "integration trace closed" if card.get("production_ready") else "partial trace",
                "ready": card.get("production_ready") is True,
            },
        ],
        "evidenceRequests": [
            {"id": "measurement", "label": "Measured geometry capture", "unlocks": "mechanical authority"},
            {"id": "integrated_bench", "label": "Integrated bench capture", "unlocks": "simulation/bench authority"},
            {"id": "release_review", "label": "Reviewed scoped release", "unlocks": "production package claim"},
        ],
        "artifacts": [
            {"name": "PROJECT_INTAKE.json", "role": "normalized user brief"},
            {"name": "PRODUCTION_RELEASE_METRICS.json", "role": "weighted release gates"},
            {"name": "FUNCTIONAL_DELIVERY.json", "role": "honest fab delivery score"},
            {"name": "build_compilation/main_ctrl_build.kicad_pcb", "role": "DRC-clean KiCad PCB"},
        ],
    }


def main() -> int:
    os.environ.setdefault("HARDWARE_SPLICER_SKIP_VISION_LIVE", "1")
    plant_brief = _plant_project(
        "plant",
        "Desk plant watering (brief)",
        "examples/intakes/plant_watering_brief.json",
        "Build a small automatic plant watering device from cheap or salvaged parts. "
        "It should read soil moisture and run a mini pump briefly when the plant is dry.",
    )
    plant_release = _plant_project(
        "plant_release",
        "Desk plant watering (evidence pack)",
        "examples/intakes/plant_watering_evidence_pack.json",
        "Same plant watering project with measured geometry, bench captures, field validation, "
        "and reviewed release scope attached.",
    )
    rover_card = _run_intake("examples/intakes/rover_brief.json", "rover")
    rover_gates = rover_card.get("gates") or []
    rover = {
        "id": "rover",
        "name": "Salvaged floor rover",
        "archetype": "rover",
        "goal": "Build a small RC rover from an ESP32, two DC gear motors, a front range sensor, and a printed chassis.",
        "level": rover_card.get("project_authority_level"),
        "authorityScore": rover_card.get("authority_score"),
        "planningConfidence": 0.78,
        "claimable": True,
        "simulationReady": rover_card.get("production_ready") is True,
        "releaseReady": rover_card.get("production_ready") is True,
        "production": {
            "score": rover_card.get("production_readiness_score"),
            "band": "control safety planning",
            "gatesPassed": rover_card.get("gates_passed"),
            "gatesTotal": rover_card.get("gates_total"),
            "gaps": _gate_gaps(rover_gates),
            "blockers": _top_blockers(rover_gates),
        },
        "functionalDelivery": {
            "score": rover_card.get("functional_delivery_score"),
            "grade": rover_card.get("functional_delivery_grade"),
        },
        "nextLevel": "simulation_bench_project_package",
        "claimBoundary": "Drive and safety architecture are coherent. Release blocked until measurements and bench evidence are attached.",
        "missingInfo": rover_card.get("evidence_gap_ids") or [],
        "margins": [
            {"label": "current margin", "value": "1.35x", "width": "58%"},
            {"label": "runtime margin", "value": "5.928x", "width": "90%"},
            {"label": "wheel speed margin", "value": "1.664x", "width": "70%"},
        ],
        "subsystems": [
            {"id": "circuit", "label": "Circuit", "level": "compiler-verified DRC", "ready": True},
            {"id": "mechanical", "label": "Mechanical", "level": "reference geometry", "ready": False},
            {"id": "robotics_actuation", "label": "Actuation", "level": "electrical drive matched", "ready": True},
            {"id": "robotics_simulation", "label": "Simulation", "level": "physical evidence blocked", "ready": False},
            {"id": "robotics_platform", "label": "Platform", "level": "control safety architecture", "ready": True},
            {"id": "mechatronics", "label": "Mechatronics", "level": "partial trace", "ready": False},
        ],
        "evidenceRequests": [
            {"id": "measurement", "label": "Measured chassis geometry", "unlocks": "mechanical authority"},
            {"id": "motion_bench", "label": "First-motion/current bench", "unlocks": "controlled rover motion"},
            {"id": "release_review", "label": "Reviewed scoped release", "unlocks": "production package claim"},
        ],
        "artifacts": [
            {"name": "PROJECT_INTAKE.json", "role": "normalized user brief"},
            {"name": "PRODUCTION_RELEASE_METRICS.json", "role": "weighted release gates"},
            {"name": "ROBOTICS_SIMULATION.json", "role": "runtime and drive margins"},
        ],
    }

    projects = [plant_brief, plant_release, rover]
    out_path = ROOT / "apps" / "hardware-splicer-demo" / "src" / "sample-data.js"
    body = "export const demoProjects = " + json.dumps(projects, indent=2) + ";\n"
    out_path.write_text(body, encoding="utf-8")
    print(json.dumps({"written": str(out_path), "projects": [p["id"] for p in projects]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
