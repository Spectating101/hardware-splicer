#!/usr/bin/env python3
"""Robust exploration test across Hardware-Splicer surfaces (not demo-only)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS_DIR = (ROOT / "scripts").resolve()
sys.path = [str(SRC)] + [p for p in sys.path if Path(p).resolve() != SCRIPTS_DIR]

from hardware_splicer.build_compiler import CATALOG_BUILD_IDS, compile_catalog_build  # noqa: E402
from hardware_splicer.fabrication_inspection import inspect_fabrication_package  # noqa: E402
from hardware_splicer.functional_delivery import build_functional_delivery_score  # noqa: E402
from hardware_splicer.project_intake import load_project_intake, run_project_intake, splice_and_build_from_intake  # noqa: E402
from hardware_splicer.runtime import runtime_status  # noqa: E402
from hardware_splicer.schemas import HardwareCompileSpec  # noqa: E402
from hardware_splicer import compile_hardware_bundle  # noqa: E402


OUT = Path(os.environ.get("HARDWARE_SPLICER_EXPLORATION_OUT", "/tmp/hardware_splicer_exploration"))
OUT.mkdir(parents=True, exist_ok=True)


def _row(category: str, name: str, ok: bool, detail: str = "", extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {
        "category": category,
        "name": name,
        "ok": ok,
        "detail": detail,
        "extra": extra or {},
    }


def _check_frontend_deps() -> Dict[str, Any]:
    frontend = ROOT / "apps" / "circuit-ai" / "circuit-ai-frontend"
    ts = frontend / "node_modules" / "typescript" / "lib" / "typescript.js"
    return {"frontend_npm_ready": ts.is_file(), "path": str(frontend)}


def test_doctor(rows: List[Dict[str, Any]]) -> None:
    status = runtime_status()
    deps = status.get("dependencies") or {}
    rows.append(_row("runtime", "doctor", bool(status.get("ok")), f"demo_ready={status.get('demo_ready')}", status))
    rows.append(_row("runtime", "node", bool(deps.get("node"))))
    rows.append(_row("runtime", "kicad_cli", bool(deps.get("kicad_cli"))))
    npm = _check_frontend_deps()
    rows.append(_row("runtime", "circuit_ai_frontend_npm", npm["frontend_npm_ready"], npm["path"]))


def test_catalog_builds(rows: List[Dict[str, Any]], export_gerber: bool) -> None:
    for build_id in CATALOG_BUILD_IDS:
        target = OUT / "catalog" / build_id
        try:
            result = compile_catalog_build(build_id, target, export_gerber=export_gerber)
            q = result.design_quality
            score = build_functional_delivery_score(build_compilation=result.to_dict())
            inspection = inspect_fabrication_package(
                build_compilation=result.to_dict(),
                artifacts={"out_dir": str(target), "build_kicad_pcb": result.kicad_pcb_file},
            )
            ok = (
                result.ok
                and bool(q.get("drc_pass"))
                and bool(q.get("electrical_safety_pass"))
                and int(q.get("electrical_warnings") or 0) == 0
                and bool(inspection.get("honest_fabrication_ready"))
            )
            rows.append(
                _row(
                    "catalog_build",
                    build_id,
                    ok,
                    f"drc={q.get('drc_pass')} honest={inspection.get('honest_fabrication_ready')} score={score.get('functional_delivery_score')}",
                    {"gerber_ready": q.get("gerber_ready"), "blockers": score.get("blockers")},
                )
            )
        except Exception as exc:
            rows.append(_row("catalog_build", build_id, False, str(exc)))


def test_intakes(rows: List[Dict[str, Any]]) -> None:
    briefs = sorted((ROOT / "examples" / "intakes").glob("*.json"))
    for brief in briefs:
        name = brief.stem
        target = OUT / "intakes" / name
        try:
            intake = load_project_intake(brief)
            result = run_project_intake(intake, out_dir=target, start_splicer=True)
            metrics_path = target / "PRODUCTION_RELEASE_METRICS.json"
            metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.is_file() else {}
            completed = (target / "PROJECT_INTAKE.json").is_file() and metrics_path.is_file()
            ok = completed and bool(result.get("ok") or metrics.get("gates_passed") is not None)
            rows.append(
                _row(
                    "intake",
                    name,
                    ok,
                    f"intake_ok={result.get('ok')} gates={metrics.get('gates_passed')}/{metrics.get('gates_total')} prod={metrics.get('production_readiness_score')}",
                )
            )
        except Exception as exc:
            rows.append(_row("intake", name, False, str(exc)))


def _scenario_passes(scenario_path: Path, result_path: Path, proc: subprocess.CompletedProcess[str]) -> tuple[bool, str]:
    if not result_path.is_file():
        return False, proc.stderr.strip()[-200:] or "missing SCENARIO_RESULT.json"
    body = json.loads(result_path.read_text(encoding="utf-8"))
    compile_ok = bool(body.get("compile_ok"))
    claimable = bool((body.get("project_authority") or {}).get("claimable"))
    negative = "bad_speed" in scenario_path.stem or "bad" in scenario_path.stem
    if negative:
        ok = compile_ok and not claimable
        detail = f"negative_test compile_ok={compile_ok} claimable={claimable}"
        return ok, detail
    ok = compile_ok and (proc.returncode == 0 or claimable)
    detail = f"compile_ok={compile_ok} claimable={claimable} exit={proc.returncode}"
    return ok, detail


def test_scenarios(rows: List[Dict[str, Any]]) -> None:
    scenarios = sorted((ROOT / "examples" / "scenarios").glob("*.json"))
    for scenario in scenarios:
        name = scenario.stem
        target = OUT / "scenarios" / name
        try:
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "hardware_splicer.py"),
                    "scenario",
                    "--scenario",
                    str(scenario),
                    "--out",
                    str(target),
                ],
                cwd=ROOT,
                env={**os.environ, "PYTHONPATH": str(SRC), "HARDWARE_SPLICER_SKIP_VISION_LIVE": "1"},
                capture_output=True,
                text=True,
                timeout=300,
            )
            ok, detail = _scenario_passes(scenario, target / "SCENARIO_RESULT.json", proc)
            rows.append(_row("scenario", name, ok, detail))
        except Exception as exc:
            rows.append(_row("scenario", name, False, str(exc)))


def test_closed_demos(rows: List[Dict[str, Any]]) -> None:
    specs = [
        "hardware_splicer_closed_mechatronics_demo.json",
        "hardware_splicer_robotics_platform_rover_demo.json",
        "hardware_splicer_demo.json",
    ]
    for spec_name in specs:
        spec_path = ROOT / "examples" / spec_name
        if not spec_path.is_file():
            continue
        target = OUT / "compile_specs" / spec_path.stem
        try:
            spec = HardwareCompileSpec.from_dict(json.loads(spec_path.read_text(encoding="utf-8")))
            use_3d = bool(spec_dict.get("use_3d_splicer")) if (spec_dict := json.loads(spec_path.read_text(encoding="utf-8"))) else False
            result = compile_hardware_bundle(spec, out_dir=target, start_splicer=use_3d)
            rows.append(_row("compile_spec", spec_name, result.ok, f"bundle={result.bundle_file}"))
        except Exception as exc:
            rows.append(_row("compile_spec", spec_name, False, str(exc)))


def test_splice_builds(rows: List[Dict[str, Any]], export_gerber: bool) -> None:
    plant = ROOT / "examples" / "intakes" / "plant_watering_brief.json"
    if not plant.is_file():
        return
    target = OUT / "splice" / "plant_watering"
    try:
        intake = load_project_intake(plant)
        splice = splice_and_build_from_intake(intake, out_dir=target, export_gerber=export_gerber)
        fd = splice.get("functional_delivery") or {}
        ok = bool(fd.get("functional_delivery_score", 0) >= 70) and bool(fd.get("honest_fabrication_ready"))
        rows.append(
            _row(
                "splice_build",
                "plant_watering_brief",
                ok,
                f"score={fd.get('functional_delivery_score')} honest={fd.get('honest_fabrication_ready')}",
            )
        )
    except Exception as exc:
        rows.append(_row("splice_build", "plant_watering_brief", False, str(exc)))


def main() -> int:
    os.environ.setdefault("HARDWARE_SPLICER_SKIP_VISION_LIVE", "1")
    export_gerber = shutil.which("kicad-cli") is not None and _check_frontend_deps()["frontend_npm_ready"]
    started = time.time()
    rows: List[Dict[str, Any]] = []

    test_doctor(rows)
    if not _check_frontend_deps()["frontend_npm_ready"]:
        rows.append(
            _row(
                "catalog_build",
                "_skipped_all",
                False,
                "circuit-ai-frontend npm install required — run: cd apps/circuit-ai/circuit-ai-frontend && npm install",
            )
        )
    else:
        test_catalog_builds(rows, export_gerber=export_gerber)
        test_splice_builds(rows, export_gerber=export_gerber)

    test_intakes(rows)
    test_scenarios(rows)
    test_closed_demos(rows)

    passed = sum(1 for row in rows if row["ok"])
    failed = [row for row in rows if not row["ok"]]
    report = {
        "schema_version": "hardware_splicer.exploration_test.v1",
        "duration_s": round(time.time() - started, 1),
        "export_gerber": export_gerber,
        "total": len(rows),
        "passed": passed,
        "failed": len(failed),
        "pass_rate": round(passed / max(len(rows), 1), 3),
        "failures": failed,
        "rows": rows,
    }
    report_path = OUT / "EXPLORATION_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"passed": passed, "failed": len(failed), "report": str(report_path)}, indent=2))
    for row in failed:
        print(f"FAIL [{row['category']}] {row['name']}: {row['detail']}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
