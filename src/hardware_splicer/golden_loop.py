"""Polished splice golden loop: build → bench template → capture submit → gate closure."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping

from .bench_capture_bridge import load_bench_capture_template, submit_bench_capture
from .project_intake import splice_and_build_from_intake
from .splice_bench import bench_status

SCHEMA = "hardware_splicer.splice_golden_loop.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_simulated_capture(template: Mapping[str, Any], *, operator_id: str = "golden_loop_sim") -> Dict[str, Any]:
    """Fill an open template with simulated pass measurements (CI / demo loop closure)."""
    capture = dict(template)
    capture["operator_id"] = operator_id
    capture["recorded_at"] = _now()
    capture["instruments"] = capture.get("instruments") or [
        {"instrument_id": "sim_dmm_01", "instrument_type": "calibrated_dmm", "calibration_status": "simulated"}
    ]
    filled: List[Dict[str, Any]] = []
    for row in template.get("measurements") or []:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind") or "voltage")
        item = {
            "gate_id": row.get("gate_id"),
            "kind": kind,
            "target": row.get("target"),
            "status": "pass",
            "method": "golden_loop_simulator",
            "instrument_id": "sim_dmm_01",
            "operator_id": operator_id,
        }
        if kind == "voltage":
            item["value"] = 6.0
            item["unit"] = row.get("unit") or "V"
        elif kind == "current":
            item["value"] = 0.12
            item["unit"] = row.get("unit") or "A"
        elif kind == "psu_ramp":
            item["value"] = float(row.get("current_limit_a") or 0.5)
            item["unit"] = "A"
            item["current_limit_a"] = item["value"]
            item["ramp_observation"] = "idle_current_normal_no_hotspot"
        elif kind == "thermal":
            item["value"] = "pass"
            item["artifact_kind"] = "thermal_image"
            item["artifact_uri"] = row.get("artifact_uri") or "sim://thermal_baseline_ok"
        else:
            item["value"] = "pass"
        filled.append(item)
    capture["measurements"] = filled
    capture["simulated"] = True
    policy = capture.get("policy") if isinstance(capture.get("policy"), dict) else {}
    capture["policy"] = {
        **policy,
        "note": "Simulated bench closure for golden-loop CI — replace with real instrument capture in production.",
    }
    return capture


def run_splice_golden_loop(
    intake: Mapping[str, Any],
    *,
    out_dir: str | Path,
    export_gerber: bool = False,
    simulate_bench: bool = True,
    request_id: str | None = None,
) -> Dict[str, Any]:
    """Run splice build then optional simulated bench capture closure."""
    out_path = Path(out_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    build = splice_and_build_from_intake(
        intake,
        out_dir=out_path,
        export_gerber=export_gerber,
        request_id=request_id,
    )
    before = bench_status(out_path)
    bench_result: Dict[str, Any] | None = None
    after = before

    if simulate_bench:
        template = load_bench_capture_template(out_path)
        capture = build_simulated_capture(template)
        bench_result = submit_bench_capture(str(out_path), capture)
        after = (
            bench_result.get("bench_session")
            if isinstance(bench_result.get("bench_session"), dict)
            else bench_status(out_path)
        )

    drc_pass = bool(((build.get("build_compilation") or {}).get("design_quality") or {}).get("drc_pass"))
    report = {
        "schema_version": SCHEMA,
        "ran_at": _now(),
        "out_dir": str(out_path),
        "build_id": build.get("build_id"),
        "drc_pass": drc_pass,
        "donor_vision_applied": int((build.get("donor_board_vision_report") or {}).get("applied_board_count") or 0),
        "bench_before": {
            "readiness": before.get("readiness"),
            "open_gate_count": before.get("open_gate_count"),
            "critical_open_count": before.get("critical_open_count"),
            "power_on_authorized": before.get("power_on_authorized"),
        },
        "bench_after": {
            "readiness": after.get("readiness"),
            "open_gate_count": after.get("open_gate_count"),
            "critical_open_count": after.get("critical_open_count"),
            "power_on_authorized": after.get("power_on_authorized"),
        },
        "simulate_bench": simulate_bench,
        "bench_submission_ok": bool((bench_result or {}).get("ok")) if simulate_bench else None,
        "artifacts": build.get("artifacts") or {},
        "passed": bool(drc_pass and (not simulate_bench or after.get("power_on_authorized"))),
    }
    report_path = out_path / "SPLICE_GOLDEN_LOOP_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(report_path)

    story = [
        "# Splice golden loop",
        "",
        "End-to-end: donor intake → splice compile → bench template → capture → gate closure.",
        "",
        f"- **Build:** `{build.get('build_id')}` (DRC pass: `{report['drc_pass']}`)",
        f"- **Donor vision blocks applied:** {report['donor_vision_applied']}",
        f"- **Bench before:** `{before.get('readiness')}` ({before.get('open_gate_count')} open gates)",
        f"- **Bench after:** `{after.get('readiness')}` (power_on: `{after.get('power_on_authorized')}`)",
        f"- **Simulated bench:** `{simulate_bench}`",
        f"- **Loop pass:** `{report['passed']}`",
        "",
        "Artifacts: `SPLICE_GOLDEN_LOOP_REPORT.json`, `BENCH_CAPTURE_TEMPLATE.json`, `SPLICE_BENCH_SESSION.json`",
        "",
    ]
    (out_path / "SPLICE_GOLDEN_LOOP_STORY.md").write_text("\n".join(story), encoding="utf-8")
    return report
