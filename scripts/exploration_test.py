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
from hardware_splicer.runtime import SPLICER3D_VENV_PYTHON, runtime_status, scratch_path  # noqa: E402
from hardware_splicer.schemas import HardwareCompileSpec  # noqa: E402
from hardware_splicer import compile_hardware_bundle  # noqa: E402


OUT = Path(
    os.environ.get("HARDWARE_SPLICER_EXPLORATION_OUT", str(scratch_path("exploration"))),
)
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


def _splicer_cadquery_note() -> str:
    """Why a scenario built from CadQuery output cannot clear, so a failure names it and not only "claimable=False"."""
    override = os.environ.get("SPLICER3D_PYTHON", "").strip()
    python = override or (str(SPLICER3D_VENV_PYTHON) if SPLICER3D_VENV_PYTHON.exists() else sys.executable)
    try:
        probe = subprocess.run([python, "-c", "import cadquery"], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"3D-Splicer python {python} could not be probed for cadquery: {exc}"
    if probe.returncode == 0:
        return ""
    lines = probe.stderr.strip().splitlines()
    return f"3D-Splicer python {python} cannot import cadquery: {lines[-1] if lines else 'no message'}"


def _scenario_passes(scenario_path: Path, result_path: Path, proc: subprocess.CompletedProcess[str]) -> tuple[bool, str]:
    """Check software execution AND preservation of production safety gates.

    `scenario` CLI exits 1 if a project compiles but cannot obtain production
    authority. That is an EXPECTED safety outcome for an exploration/smoke
    harness, not an exception or an incomplete compile. It must still produce
    consistent, inspectable blocked-release evidence. This does NOT approve
    release, override any gate, or change a scenario's expected authority.
    """
    if not result_path.is_file():
        return False, proc.stderr.strip()[-200:] or "missing SCENARIO_RESULT.json"
    try:
        body = json.loads(result_path.read_text(encoding="utf-8"))
        if not isinstance(body, dict):
            raise ValueError("scenario result must be an object")
    except (ValueError, OSError) as exc:
        return False, f"invalid SCENARIO_RESULT.json: {exc}"

    if body.get("schema_version") != "hardware_splicer.scenario_result.v1":
        return False, "scenario result schema version missing or unsupported"
    compile_ok = body.get("compile_ok") is True
    authority = body.get("project_authority") or {}
    metrics = body.get("production_release_metrics") or {}
    if not isinstance(authority, dict) or not isinstance(metrics, dict):
        return False, "scenario authority and production metrics must be objects"
    if (authority.get("schema_version") != "hardware_splicer.project_authority.v1"
            or metrics.get("schema_version") != "hardware_splicer.production_release_metrics.v1"):
        return False, "scenario authority or production gate schema missing or unsupported"
    claimable = authority.get("claimable") is True
    production_ready = metrics.get("production_ready") is True
    scenario_ok = body.get("ok") is True
    negative = "bad_speed" in scenario_path.stem or "bad" in scenario_path.stem

    prefix = f"compile_ok={compile_ok} claimable={claimable} exit={proc.returncode}"
    if not compile_ok:
        return False, prefix + "; compilation failed"

    if claimable and production_ready and scenario_ok and proc.returncode == 0 and not negative:
        return True, prefix + "; outcome=production_authorized"

    gaps = metrics.get("evidence_gap_ids")
    blockers = metrics.get("what_blocks_production")
    passed = metrics.get("gates_passed")
    total = metrics.get("gates_total")
    mirrored_metrics = authority.get("production_release_metrics") or {}
    mirrored = mirrored_metrics.get("production_ready")
    mirrors_agree = (
        mirrored_metrics.get("schema_version") == metrics.get("schema_version")
        and mirrored_metrics.get("gates_passed") == passed
        and mirrored_metrics.get("gates_total") == total
        and mirrored_metrics.get("evidence_gap_ids") == gaps
    )
    release_level = authority.get("project_authority_level")
    blocked_consistently = (
        not claimable and not production_ready and not scenario_ok
        and isinstance(gaps, list) and bool(gaps)
        and all(isinstance(g, str) and bool(g) for g in gaps)
        and isinstance(blockers, list) and bool(blockers)
        and all(isinstance(v, str) and bool(v) for v in blockers)
        and type(passed) is int and type(total) is int
        and 0 <= passed < total
        and total - passed == len(gaps)
        and mirrored is False and mirrors_agree
        and release_level != "production_ready_project_package"
        and proc.returncode in (0, 1)
    )
    if blocked_consistently:
        kind = "negative_safety_scenario" if negative else "compiled_release_blocked"
        return True, prefix + f"; outcome={kind} gates={passed}/{total} gap_ids={','.join(gaps)}"

    detail = prefix + (
        f"; inconsistent release evidence (production_ready={production_ready}, "
        f"scenario_ok={scenario_ok}, gates={passed}/{total}, gap_ids={gaps})"
    )
    if not negative:
        note = _splicer_cadquery_note()
        if note:
            detail += "; " + note
    return False, detail


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
            result_path = target / "SCENARIO_RESULT.json"
            ok, detail = _scenario_passes(scenario, result_path, proc)
            # A passing exploration row does NOT assert production readiness.
            # Keep release authority separately queryable in the JSON report.
            extra: Dict[str, Any] = {}
            if result_path.is_file():
                try:
                    result = json.loads(result_path.read_text(encoding="utf-8"))
                    m = result.get("production_release_metrics") or {}
                    extra = {
                        "software_compile_ok": result.get("compile_ok") is True,
                        "scenario_release_authorized": result.get("ok") is True,
                        "production_ready": m.get("production_ready") is True,
                        "production_evidence_gap_ids": m.get("evidence_gap_ids") or [],
                        "gates_passed": m.get("gates_passed"),
                        "gates_total": m.get("gates_total"),
                    }
                except (OSError, ValueError, AttributeError):
                    extra = {"result_unreadable": True}
            rows.append(_row("scenario", name, ok, detail, extra))
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
        topo = str((splice.get("salvage_package") or {}).get("power_topology") or "")
        ok = bool(fd.get("functional_delivery_score", 0) >= 70) and bool(fd.get("honest_fabrication_ready"))
        rows.append(
            _row(
                "splice_build",
                "plant_watering_brief",
                ok and topo == "usb_5v",
                f"score={fd.get('functional_delivery_score')} honest={fd.get('honest_fabrication_ready')} topo={topo}",
            )
        )
    except Exception as exc:
        rows.append(_row("splice_build", "plant_watering_brief", False, str(exc)))


def _cleanup_stale_tmp() -> None:
    cleanup = ROOT / "scripts" / "cleanup_test_artifacts.sh"
    if cleanup.is_file():
        subprocess.run(["bash", str(cleanup)], check=False)


def main() -> int:
    os.environ.setdefault("HARDWARE_SPLICER_SKIP_VISION_LIVE", "1")
    _cleanup_stale_tmp()
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
