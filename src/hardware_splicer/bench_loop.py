"""Bench loop closure — capture template → submit → gate verdict (compose + splice builds)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping

from .bench_capture_bridge import load_bench_capture_template, submit_bench_capture, sync_bench_session_template
from .splice_bench import bench_status

SCHEMA_VERSION = "hardware_splicer.bench_loop.v1"
REPORT_FILE = "BENCH_LOOP_REPORT.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bounded_simulated_value(row: Mapping[str, Any]) -> float | None:
    """Return an in-range deterministic value when numeric bounds are declared."""
    lower = row.get("lower")
    upper = row.get("upper")
    if lower is None and upper is None:
        return None
    try:
        if lower is not None and upper is not None:
            return (float(lower) + float(upper)) / 2.0
        if lower is not None:
            return float(lower)
        return float(upper) / 2.0
    except (TypeError, ValueError):
        return None


def build_simulated_capture(
    template: Mapping[str, Any],
    *,
    operator_id: str = "bench_loop_sim",
) -> Dict[str, Any]:
    """Fill an open capture template with simulated pass readings (CI / demo only)."""
    capture = dict(template)
    capture["operator_id"] = operator_id
    capture["recorded_at"] = _now()
    capture["instruments"] = capture.get("instruments") or [
        {
            "instrument_id": "sim_dmm_01",
            "instrument_type": "calibrated_dmm",
            "calibration_status": "simulated",
        }
    ]
    filled: List[Dict[str, Any]] = []
    for row in template.get("measurements") or []:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind") or "measurement")
        item: Dict[str, Any] = {
            "gate_id": row.get("gate_id"),
            "kind": kind,
            "target": row.get("target"),
            "status": "pass",
            "method": "bench_loop_simulator",
            "instrument_id": "sim_dmm_01",
            "operator_id": operator_id,
        }
        bounded = _bounded_simulated_value(row)
        if bounded is not None:
            item["value"] = bounded
            if row.get("unit"):
                item["unit"] = row.get("unit")
        elif kind == "voltage":
            item["value"] = 3.3
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
            if row.get("unit"):
                item["unit"] = row.get("unit")
        filled.append(item)
    capture["measurements"] = filled
    capture["simulated"] = True
    policy = capture.get("policy") if isinstance(capture.get("policy"), dict) else {}
    capture["policy"] = {
        **policy,
        "note": "Simulated bench closure for CI/demo — replace with real instrument capture in production.",
    }
    return capture


def _open_gates(session: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    return [
        row
        for row in (session.get("gates") or [])
        if isinstance(row, Mapping) and str(row.get("status") or "open") != "closed"
    ]


def _authority_gate(row: Mapping[str, Any]) -> bool:
    return bool(
        row.get("requires_contract_edit")
        or str(row.get("gate_type") or "") == "interface_contract_field"
        or str(row.get("source") or "") == "evidence_interface"
    )


def _evidence_measurement_gate(row: Mapping[str, Any]) -> bool:
    return bool(
        str(row.get("gate_type") or "") == "interface_measurement"
        or str(row.get("source") or "") == "evidence_recipe"
    )


def run_bench_loop_closure(
    build_dir: str | Path,
    *,
    simulate_bench: bool = False,
    capture_packet: Mapping[str, Any] | None = None,
    operator_id: str = "bench_loop_sim",
) -> Dict[str, Any]:
    """Refresh capture template and optionally submit capture to close bench gates.

    Pipeline success and physical authorization are intentionally separate. A simulated
    capture may prove that measurable gates close while canonical interface-structure
    gates correctly remain open.
    """
    out_path = Path(build_dir).resolve()
    if not out_path.is_dir():
        raise ValueError(f"build_dir not found: {out_path}")

    before = bench_status(out_path)
    template_sync = sync_bench_session_template(out_path)
    template = dict(template_sync.get("template") or load_bench_capture_template(out_path))

    bench_result: Dict[str, Any] | None = None
    after = dict(before)
    submitted_capture = False

    if capture_packet is not None:
        bench_result = submit_bench_capture(str(out_path), capture_packet)
        submitted_capture = True
    elif simulate_bench:
        capture = build_simulated_capture(template, operator_id=operator_id)
        bench_result = submit_bench_capture(str(out_path), capture)
        submitted_capture = True

    if bench_result is not None:
        session = bench_result.get("bench_session")
        if isinstance(session, dict):
            after = dict(session)
        else:
            after = bench_status(out_path)

    remaining = _open_gates(after)
    authority_remaining = [row for row in remaining if _authority_gate(row)]
    evidence_measurements_remaining = [row for row in remaining if _evidence_measurement_gate(row)]
    submission_ok = bool((bench_result or {}).get("ok")) if submitted_capture else None
    measurements_complete = bool(submitted_capture and submission_ok and not evidence_measurements_remaining)
    physical_authorized = after.get("power_on_authorized") is True
    correctly_blocked = bool(measurements_complete and authority_remaining and not physical_authorized)
    if physical_authorized:
        authorization_outcome = "authorized"
    elif correctly_blocked:
        authorization_outcome = "correctly_blocked"
    else:
        authorization_outcome = "incomplete"
    workflow_passed = bool(
        submitted_capture
        and submission_ok
        and measurements_complete
        and authorization_outcome in {"authorized", "correctly_blocked"}
    )

    report: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "ran_at": _now(),
        "build_dir": str(out_path),
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
        "simulate_bench": bool(simulate_bench and capture_packet is None),
        "submitted_capture": submitted_capture,
        "bench_submission_ok": submission_ok,
        "bench_capture_template": template.get("template_path"),
        "open_measurement_count": template.get("open_measurement_count"),
        "open_contract_action_count": template.get("open_contract_action_count"),
        "evidence_measurements_remaining": len(evidence_measurements_remaining),
        "authority_gates_remaining": len(authority_remaining),
        "measurements_complete": measurements_complete,
        "physical_authorized": physical_authorized,
        "authorization_outcome": authorization_outcome,
        "passed": workflow_passed,
    }
    report_path = out_path / REPORT_FILE
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(report_path)
    if bench_result:
        report["gates_closed"] = bench_result.get("gates_closed")
        report["gates_remaining_open"] = bench_result.get("gates_remaining_open")
    return report


def run_compose_agent_bench_loop(
    *,
    simulate_bench: bool = True,
    capture_packet: Mapping[str, Any] | None = None,
    operator_id: str = "bench_loop_sim",
    **compose_kwargs: Any,
) -> Dict[str, Any]:
    """Compose agent-loop (with package) then optional bench capture closure on same build_dir."""
    from .compose_agent_loop import compose_agent_loop

    compose_kwargs = dict(compose_kwargs)
    compose_kwargs["finalize_package"] = True
    compose = compose_agent_loop(**compose_kwargs)
    out_dir = compose.get("out_dir")
    if not out_dir:
        raise ValueError("compose agent-loop missing out_dir")

    bench_loop = run_bench_loop_closure(
        out_dir,
        simulate_bench=simulate_bench and capture_packet is None,
        capture_packet=capture_packet,
        operator_id=operator_id,
    )
    bench_session = bench_status(out_dir)
    return {
        **compose,
        "bench_loop": bench_loop,
        "bench_session": {
            "readiness": bench_session.get("readiness"),
            "open_gate_count": bench_session.get("open_gate_count"),
            "critical_open_count": bench_session.get("critical_open_count"),
            "power_on_authorized": bench_session.get("power_on_authorized"),
            "level": bench_session.get("level"),
            "gates": bench_session.get("gates"),
            "bench_capture_template": bench_session.get("bench_capture_template"),
        },
    }
