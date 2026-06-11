#!/usr/bin/env python3
"""Run the tier-5 plant-watering path with Qwen vision, splice, fab build, audits, and scoring."""
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

from hardware_splicer.project_intake import load_project_intake, run_project_intake, splice_and_build_from_intake  # noqa: E402
from hardware_splicer.scoring_summary import scorecard_from_artifacts  # noqa: E402
from hardware_splicer.vision_usage_ledger import usage_summary  # noqa: E402


BRIEF = ROOT / "examples" / "intakes" / "plant_watering_tier5_brief.json"
OUT_ROOT = Path(os.environ.get("HARDWARE_SPLICER_QWEN_OUT", "/tmp/hardware_splicer_plant_qwen_full"))


def _ensure_root_env_local() -> None:
    target = ROOT / ".env.local"
    if target.is_file():
        return
    for candidate in [
        ROOT / "apps" / "circuit-ai" / "circuit-ai-frontend" / ".env.local",
        ROOT / "apps" / "circuit-ai" / ".env.local",
    ]:
        if not candidate.is_file():
            continue
        lines = []
        for line in candidate.read_text(encoding="utf-8").splitlines():
            key = line.split("=", 1)[0].strip() if "=" in line else ""
            if key in {"QWEN_API_KEY", "DASHSCOPE_API_KEY", "DASHSCOPE_BASE_URL", "QWEN_BASE_URL"}:
                lines.append(line)
        if lines:
            target.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return


def _load_env_local() -> None:
    env_file = ROOT / ".env.local"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip("'\"")


def _run_make(target: str) -> dict:
    proc = subprocess.run(
        ["make", target],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return {"target": target, "returncode": proc.returncode, "stdout": proc.stdout[-2000:], "stderr": proc.stderr[-1000:]}


def _run_tier_scores() -> dict:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "score_intake_tiers.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=os.environ.copy(),
    )
    payload = {}
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = {"raw_stdout": proc.stdout[-4000:]}
    return {"returncode": proc.returncode, "report": payload, "stderr": proc.stderr[-1000:]}


def main() -> int:
    _ensure_root_env_local()
    _load_env_local()
    if not (os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")):
        print(json.dumps({"ok": False, "error": "Set QWEN_API_KEY or DASHSCOPE_API_KEY in .env.local"}, indent=2))
        return 1

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    intake = load_project_intake(BRIEF)

    intake_result = run_project_intake(
        intake,
        out_dir=OUT_ROOT / "intake",
        start_splicer=False,
        request_id="desk_plant_watering_assistant_tier5",
    )
    splice_result = splice_and_build_from_intake(
        intake,
        out_dir=OUT_ROOT / "splice_build",
        export_gerber=True,
        request_id="desk_plant_watering_assistant_tier5",
    )
    scorecard = scorecard_from_artifacts(OUT_ROOT / "intake")
    usage = usage_summary(provider="qwen")
    benchmark = _run_make("benchmark-backend")
    audit = _run_make("audit-functional-delivery")
    tier_scores = _run_tier_scores()

    vision_report = intake_result.get("vision_evidence_report") or {}
    report = {
        "ok": bool(intake_result.get("ok")) and bool(splice_result.get("ok")),
        "brief": str(BRIEF),
        "out_root": str(OUT_ROOT),
        "intake_ok": intake_result.get("ok"),
        "splice_ok": splice_result.get("ok"),
        "scoring": scorecard,
        "vision": {
            "provider": vision_report.get("provider"),
            "model": vision_report.get("model"),
            "candidate_count": vision_report.get("candidate_count"),
            "error_count": vision_report.get("error_count"),
            "applied_note_count": vision_report.get("applied_note_count"),
            "errors": vision_report.get("errors"),
            "usage_tracking": vision_report.get("usage_tracking"),
        },
        "functional_delivery": splice_result.get("functional_delivery"),
        "artifacts": {
            "vision_report": intake_result.get("artifacts", {}).get("vision_evidence_report"),
            "production_release_metrics": str(OUT_ROOT / "intake" / "PRODUCTION_RELEASE_METRICS.json"),
            "project_authority": str(OUT_ROOT / "intake" / "PROJECT_AUTHORITY.json"),
            "functional_delivery": splice_result.get("artifacts", {}).get("functional_delivery"),
            "fab_package_zip": splice_result.get("artifacts", {}).get("fab_package_zip"),
            "kicad_pcb": splice_result.get("artifacts", {}).get("kicad_pcb"),
        },
        "qwen_usage": usage,
        "tier_scores": tier_scores.get("report"),
        "benchmark_backend": benchmark,
        "audit_functional_delivery": audit,
    }
    report_path = OUT_ROOT / "QWEN_PLANT_PIPELINE_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    ok = (
        report["ok"]
        and benchmark["returncode"] == 0
        and audit["returncode"] == 0
        and float(scorecard.get("production_readiness_score") or 0) >= 0.99
        and int(scorecard.get("gates_passed") or 0) >= int(scorecard.get("gates_total") or 9)
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
