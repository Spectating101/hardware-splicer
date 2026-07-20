"""Polished splice golden loop: build → bench template → capture submit → authority verdict."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping

from .bench_loop import build_simulated_capture, run_bench_loop_closure
from .project_intake import splice_and_build_from_intake
from .splice_bench import bench_status

SCHEMA = "hardware_splicer.splice_golden_loop.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_splice_golden_loop(
    intake: Mapping[str, Any],
    *,
    out_dir: str | Path,
    export_gerber: bool = False,
    simulate_bench: bool = True,
    request_id: str | None = None,
) -> Dict[str, Any]:
    """Run splice build then optional simulated bench workflow.

    A loop passes when compilation succeeds and the simulated measurement workflow
    reaches a truthful authority outcome. That outcome may be either physically
    authorized or correctly blocked by unresolved interface structure.
    """
    out_path = Path(out_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    build = splice_and_build_from_intake(
        intake,
        out_dir=out_path,
        export_gerber=export_gerber,
        request_id=request_id,
    )
    before = bench_status(out_path)
    bench_loop: Dict[str, Any] | None = None
    after = before

    if simulate_bench:
        bench_loop = run_bench_loop_closure(
            out_path,
            simulate_bench=True,
            operator_id="golden_loop_sim",
        )
        after = bench_loop.get("bench_after") or before

    drc_pass = bool(((build.get("build_compilation") or {}).get("design_quality") or {}).get("drc_pass"))
    bench_workflow_passed = bool(bench_loop.get("passed")) if bench_loop else None
    report = {
        "schema_version": SCHEMA,
        "ran_at": _now(),
        "out_dir": str(out_path),
        "build_id": build.get("build_id"),
        "drc_pass": drc_pass,
        "donor_vision_applied": int((build.get("donor_board_vision_report") or {}).get("applied_board_count") or 0),
        "bench_before": bench_loop.get("bench_before") if bench_loop else {
            "readiness": before.get("readiness"),
            "open_gate_count": before.get("open_gate_count"),
            "critical_open_count": before.get("critical_open_count"),
            "power_on_authorized": before.get("power_on_authorized"),
        },
        "bench_after": bench_loop.get("bench_after") if bench_loop else {
            "readiness": after.get("readiness"),
            "open_gate_count": after.get("open_gate_count"),
            "critical_open_count": after.get("critical_open_count"),
            "power_on_authorized": after.get("power_on_authorized"),
        },
        "simulate_bench": simulate_bench,
        "bench_submission_ok": bench_loop.get("bench_submission_ok") if bench_loop else None,
        "bench_workflow_passed": bench_workflow_passed,
        "measurements_complete": bench_loop.get("measurements_complete") if bench_loop else None,
        "physical_authorized": bench_loop.get("physical_authorized") if bench_loop else bool(after.get("power_on_authorized")),
        "authorization_outcome": bench_loop.get("authorization_outcome") if bench_loop else (
            "authorized" if after.get("power_on_authorized") else "not_run"
        ),
        "authority_gates_remaining": bench_loop.get("authority_gates_remaining") if bench_loop else None,
        "bench_loop_report": bench_loop.get("report_path") if bench_loop else None,
        "artifacts": build.get("artifacts") or {},
        "passed": bool(drc_pass and (not simulate_bench or bench_workflow_passed)),
    }
    report_path = out_path / "SPLICE_GOLDEN_LOOP_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(report_path)

    story = [
        "# Splice golden loop",
        "",
        "End-to-end: donor intake → splice compile → evidence capture → authority verdict.",
        "",
        f"- **Build:** `{build.get('build_id')}` (DRC pass: `{report['drc_pass']}`)",
        f"- **Donor vision blocks applied:** {report['donor_vision_applied']}",
        f"- **Bench before:** `{before.get('readiness')}` ({before.get('open_gate_count')} open gates)",
        f"- **Bench after:** `{after.get('readiness')}` (power_on: `{after.get('power_on_authorized')}`)",
        f"- **Authority outcome:** `{report['authorization_outcome']}`",
        f"- **Simulated bench:** `{simulate_bench}`",
        f"- **Workflow pass:** `{report['passed']}`",
        "",
        "A correctly blocked authority outcome is a passing safety result; it is not physical power authorization.",
        "",
        "Artifacts: `SPLICE_GOLDEN_LOOP_REPORT.json`, `BENCH_CAPTURE_TEMPLATE.json`, `SPLICE_BENCH_SESSION.json`",
        "",
    ]
    (out_path / "SPLICE_GOLDEN_LOOP_STORY.md").write_text("\n".join(story), encoding="utf-8")
    return report


# Back-compat re-export for tests importing from golden_loop
__all__ = ["build_simulated_capture", "run_splice_golden_loop"]
