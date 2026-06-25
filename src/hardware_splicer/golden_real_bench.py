"""Golden real S3 path — manual bench capture (not simulator)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping

from .bench_capture_bridge import submit_bench_capture, sync_bench_session_template
from .project_intake import splice_and_build_from_intake
from .splice_bench import bench_status, open_bench_session

SCHEMA = "hardware_splicer.splice_golden_real.v1"
REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = REPO_ROOT / "tests" / "data" / "golden"
DEFAULT_PHOTO = GOLDEN_DIR / "rc_toy_motor_board.jpg"
DEFAULT_CAPTURE = GOLDEN_DIR / "rc_motor_manual_bench_capture.v1.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_golden_bench_capture(path: str | Path | None = None) -> Dict[str, Any]:
    capture_path = Path(path or DEFAULT_CAPTURE).resolve()
    if not capture_path.is_file():
        raise FileNotFoundError(f"golden bench capture not found: {capture_path}")
    data = json.loads(capture_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("golden bench capture must be a JSON object")
    return data


def filter_capture_for_template(capture: Mapping[str, Any], template: Mapping[str, Any]) -> Dict[str, Any]:
    """Keep only measurement rows that match open gates in the current build template."""
    allowed = {
        str(row.get("gate_id") or "")
        for row in (template.get("measurements") or [])
        if isinstance(row, dict) and str(row.get("gate_id") or "")
    }
    rows: List[Dict[str, Any]] = []
    for row in capture.get("measurements") or []:
        if not isinstance(row, dict):
            continue
        gate_id = str(row.get("gate_id") or "")
        if gate_id in allowed:
            rows.append(dict(row))
    body = dict(capture)
    body["measurements"] = rows
    body["filtered_for_template"] = True
    body["matched_gate_count"] = len(rows)
    return body


def run_splice_golden_real(
    intake: Mapping[str, Any],
    *,
    out_dir: str | Path,
    capture_path: str | Path | None = None,
    export_gerber: bool = False,
    request_id: str | None = None,
) -> Dict[str, Any]:
    """Build splice output then close gates using committed manual bench capture."""
    out_path = Path(out_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    build = splice_and_build_from_intake(
        intake,
        out_dir=out_path,
        export_gerber=export_gerber,
        request_id=request_id,
    )
    before = open_bench_session(out_path, force=True)
    template_sync = sync_bench_session_template(out_path)
    template = dict(template_sync.get("template") or {})
    golden = load_golden_bench_capture(capture_path)
    capture = filter_capture_for_template(golden, template)
    if not capture.get("measurements"):
        return {
            "schema_version": SCHEMA,
            "passed": False,
            "error": "golden_capture_no_matching_gates",
            "template_gate_ids": [row.get("gate_id") for row in template.get("measurements") or []],
            "golden_gate_ids": [row.get("gate_id") for row in golden.get("measurements") or []],
        }

    bench_result = submit_bench_capture(str(out_path), capture)
    after = (
        bench_result.get("bench_session")
        if isinstance(bench_result.get("bench_session"), dict)
        else bench_status(out_path)
    )

    drc_pass = bool(((build.get("build_compilation") or {}).get("design_quality") or {}).get("drc_pass"))
    simulated = bool(golden.get("simulated"))
    report = {
        "schema_version": SCHEMA,
        "ran_at": _now(),
        "out_dir": str(out_path),
        "build_id": build.get("build_id"),
        "drc_pass": drc_pass,
        "donor_vision_applied": int((build.get("donor_board_vision_report") or {}).get("applied_board_count") or 0),
        "golden_capture_path": str(Path(capture_path or DEFAULT_CAPTURE).resolve()),
        "golden_photo_path": str(DEFAULT_PHOTO) if DEFAULT_PHOTO.is_file() else None,
        "matched_measurement_count": capture.get("matched_gate_count"),
        "simulated": simulated,
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
        "bench_submission_ok": bool(bench_result.get("ok")),
        "passed": bool(
            drc_pass
            and bench_result.get("ok")
            and after.get("power_on_authorized")
            and not simulated
        ),
    }
    report_path = out_path / "SPLICE_GOLDEN_REAL_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(report_path)
    return report
