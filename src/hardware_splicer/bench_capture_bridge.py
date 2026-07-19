"""Bridge bench_topology_capture.v1 packets into splice bench gate submissions."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

from .splice_bench import SESSION_FILE, bench_status, submit_bench_measurements

SCHEMA_VERSION = "hardware_splicer.bench_capture_bridge.v1"
BENCH_CAPTURE_SCHEMA = "bench_topology_capture.v1"
TEMPLATE_FILE = "BENCH_CAPTURE_TEMPLATE.json"

_PASS = {"pass", "passed", "ok", "verified", "measured", "normal", "closed"}
_FAIL = {"fail", "failed", "unsafe", "short", "shorted", "blocked", "hold", "open"}

_KIND_BY_GATE_TYPE = {
    "voltage": "voltage",
    "continuity": "continuity",
    "measurement": "voltage",
    "functional_check": "continuity",
    "missing_evidence": "voltage",
    "bench_check": "continuity",
    "interconnect_hold": "continuity",
    "psu_ramp": "psu_ramp",
    "thermal": "thermal",
    "interface_measurement": "voltage",
    "interface_contract_field": "contract",
}


def _gate_kind(gate: Mapping[str, Any]) -> str:
    gate_type = str(gate.get("gate_type") or "").strip().lower()
    if gate_type in _KIND_BY_GATE_TYPE:
        return _KIND_BY_GATE_TYPE[gate_type]
    prompt = str(gate.get("prompt") or "").lower()
    if "continuity" in prompt or "short" in prompt:
        return "continuity"
    if "voltage" in prompt or "vmotor" in prompt or "polarity" in prompt:
        return "voltage"
    if "current" in prompt:
        return "current"
    if "thermal" in prompt or "flir" in prompt or "hotspot" in prompt:
        return "thermal"
    if "current-limited" in prompt or "current limited" in prompt:
        return "psu_ramp"
    return "voltage"


def build_bench_capture_template_from_gates(
    gates: Sequence[Mapping[str, Any]],
    *,
    project_name: str = "",
    build_id: str = "",
) -> Dict[str, Any]:
    """Build bench_topology_capture.v1 skeleton from open measurable gates.

    Interface-structure gates are intentionally excluded from measurement rows. They
    are returned as contract actions because a DMM reading cannot define signal
    direction, protocol, or controller-pin binding.
    """
    measurements: List[Dict[str, Any]] = []
    contract_actions: List[Dict[str, Any]] = []
    for gate in gates:
        if str(gate.get("status") or "open") == "closed":
            continue
        if gate.get("requires_contract_edit") or str(gate.get("gate_type") or "") == "interface_contract_field":
            contract_actions.append(
                {
                    "gate_id": str(gate.get("gate_id") or ""),
                    "interface_id": gate.get("interface_id"),
                    "evidence_field": gate.get("evidence_field"),
                    "target": str(gate.get("prompt") or gate.get("gate_id") or ""),
                    "action": "update_interface_contract",
                }
            )
            continue
        kind = _gate_kind(gate)
        row: Dict[str, Any] = {
            "gate_id": str(gate.get("gate_id") or ""),
            "kind": kind,
            "target": str(gate.get("prompt") or gate.get("gate_id") or ""),
            "status": "open",
            "notes": str(gate.get("prompt") or ""),
            "block_id": gate.get("block_id") or "",
            "board_id": gate.get("board_id") or "",
        }
        expected_unit = gate.get("expected_unit")
        if kind == "voltage":
            row["unit"] = expected_unit or "V"
        elif kind == "current":
            row["unit"] = expected_unit or "A"
        elif kind == "psu_ramp":
            row["unit"] = expected_unit or "A"
            row["current_limit_a"] = 0.5
        elif kind == "thermal":
            row["artifact_kind"] = "thermal_image"
            row["artifact_uri"] = ""
        for key in ("lower", "upper", "required", "validators", "measurement_id", "phase_id", "interface_id"):
            if gate.get(key) is not None:
                row[key] = gate.get(key)
        measurements.append(row)

    return {
        "schema_version": BENCH_CAPTURE_SCHEMA,
        "capture_id": f"{_slug(project_name or 'splice')}_bench",
        "project_name": project_name,
        "build_id": build_id,
        "source": "hardware_splicer.splice_bench.v1",
        "operator_id": "",
        "recorded_at": "",
        "instruments": [
            {"instrument_id": "bench_dmm_01", "instrument_type": "calibrated_dmm", "calibration_status": "valid"},
            {"instrument_id": "bench_supply_01", "instrument_type": "current_limited_supply", "calibration_status": "valid"},
        ],
        "measurements": measurements,
        "contract_actions": contract_actions,
        "artifacts": [
            {"kind": "photo", "uri": "", "notes": "Connector or test point photo for this capture."},
            {"kind": "thermal_image", "uri": "", "notes": "Optional FLIR / thermal baseline image."},
            {"kind": "measurement_log", "uri": "", "notes": "Instrument log backing submitted readings."},
        ],
        "policy": {
            "vision_alone_is_not_evidence": True,
            "fill_status_pass_fail_after_physical_measurement": True,
            "contract_actions_are_not_measurements": True,
            "submit_via": "hs_splice_bench_submit_capture or POST /v1/splice-bench/submit-capture",
        },
    }


def write_bench_capture_template(build_dir: str | Path, session: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    """Write BENCH_CAPTURE_TEMPLATE.json for open gates in a splice build directory."""
    root = Path(build_dir).resolve()
    if session is None:
        session = bench_status(root)
    gates = list(session.get("gates") or [])
    template = build_bench_capture_template_from_gates(
        gates,
        project_name=str(session.get("project_name") or ""),
        build_id=str(session.get("build_id") or ""),
    )
    path = root / TEMPLATE_FILE
    path.write_text(json.dumps(template, indent=2), encoding="utf-8")
    template["template_path"] = str(path)
    template["open_measurement_count"] = len(template.get("measurements") or [])
    template["open_contract_action_count"] = len(template.get("contract_actions") or [])
    return template


def load_bench_capture_template(build_dir: str | Path) -> Dict[str, Any]:
    path = Path(build_dir).resolve() / TEMPLATE_FILE
    if not path.is_file():
        template = write_bench_capture_template(build_dir)
        return template
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data["template_path"] = str(path)
    return data if isinstance(data, dict) else {}


def sync_bench_session_template(build_dir: str | Path) -> Dict[str, Any]:
    """Refresh capture template and attach path to SPLICE_BENCH_SESSION.json."""
    root = Path(build_dir).resolve()
    session = bench_status(root)
    template = write_bench_capture_template(root, session)
    session_path = root / SESSION_FILE
    if session_path.is_file():
        body = json.loads(session_path.read_text(encoding="utf-8"))
        body["bench_capture_template"] = template.get("template_path")
        body["open_measurement_count"] = template.get("open_measurement_count")
        body["open_contract_action_count"] = template.get("open_contract_action_count")
        session_path.write_text(json.dumps(body, indent=2), encoding="utf-8")
        session["bench_capture_template"] = template.get("template_path")
        session["open_measurement_count"] = template.get("open_measurement_count")
        session["open_contract_action_count"] = template.get("open_contract_action_count")
    return {"session": session, "template": template}


def _rows(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def extract_bench_capture(packet: Mapping[str, Any]) -> Dict[str, Any]:
    """Find a bench_topology_capture.v1 dict in common wrapper shapes."""
    if str(packet.get("schema_version") or "") == BENCH_CAPTURE_SCHEMA:
        return dict(packet)
    nested = packet.get("bench_topology_capture")
    if isinstance(nested, dict):
        return dict(nested)
    for key in ("capture", "bench_capture", "analysis"):
        row = packet.get(key)
        if isinstance(row, dict) and str(row.get("schema_version") or "") == BENCH_CAPTURE_SCHEMA:
            return dict(row)
        if isinstance(row, dict):
            inner = row.get("bench_topology_capture")
            if isinstance(inner, dict):
                return dict(inner)
    return {}


def collect_capture_measurements(capture: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Flatten measurement rows from a bench capture packet."""
    rows: List[Dict[str, Any]] = []
    for key in ("measurements", "observations", "readings", "tests"):
        rows.extend(_rows(capture.get(key)))
    evidence = capture.get("evidence") if isinstance(capture.get("evidence"), dict) else {}
    for key in ("measurements", "observations"):
        rows.extend(_rows(evidence.get(key)))
    return rows


def _normalize_status(raw: Any) -> str:
    text = str(raw or "pass").strip().lower()
    if text in _PASS:
        return "closed"
    if text in _FAIL:
        return "open" if text == "open" else "blocked"
    return "closed"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text or "").lower()).strip("_")


def _match_gate_id(
    measurement: Mapping[str, Any],
    gates: Sequence[Mapping[str, Any]],
) -> str:
    explicit = str(measurement.get("gate_id") or measurement.get("requirement_id") or "").strip()
    if explicit:
        return explicit
    target = str(measurement.get("target") or measurement.get("label") or measurement.get("prompt") or "").strip().lower()
    kind = str(measurement.get("kind") or measurement.get("gate_type") or measurement.get("type") or "").strip().lower()
    if not target and not kind:
        return ""
    best_id = ""
    best_score = 0
    for gate in gates:
        gate_id = str(gate.get("gate_id") or "")
        prompt = str(gate.get("prompt") or "").lower()
        gate_type = str(gate.get("gate_type") or "").lower()
        score = 0
        if target and target in prompt:
            score += 3
        if kind and kind in prompt:
            score += 2
        if kind and kind == gate_type:
            score += 2
        if target and _slug(target) in _slug(gate_id):
            score += 2
        if score > best_score:
            best_score = score
            best_id = gate_id
    return best_id if best_score >= 2 else ""


def bench_capture_to_splice_measurements(
    capture: Mapping[str, Any],
    *,
    gates: Sequence[Mapping[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    """Convert bench capture rows into splice_bench_submit payloads."""
    gate_rows = list(gates or [])
    out: List[Dict[str, Any]] = []
    for row in collect_capture_measurements(capture):
        gate_id = _match_gate_id(row, gate_rows)
        if not gate_id:
            continue
        out.append(
            {
                "gate_id": gate_id,
                "status": _normalize_status(row.get("status") or row.get("result")),
                "value": row.get("value", row.get("measured_value")),
                "unit": row.get("unit"),
                "method": row.get("method") or row.get("instrument_id") or row.get("instrument_type"),
                "operator": row.get("operator_id"),
                "notes": row.get("notes") or row.get("target"),
            }
        )
    return out


def submit_bench_capture(
    build_dir: str,
    capture_packet: Mapping[str, Any],
) -> Dict[str, Any]:
    """Submit a bench_topology_capture packet against splice bench gates."""
    capture = extract_bench_capture(capture_packet)
    if not capture:
        raise ValueError(f"expected {BENCH_CAPTURE_SCHEMA} packet")
    session = bench_status(build_dir)
    gates = list(session.get("gates") or [])
    mapped = bench_capture_to_splice_measurements(capture, gates=gates)
    if not mapped:
        return {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "error": "no_capture_rows_matched_open_gates",
            "capture_measurement_count": len(collect_capture_measurements(capture)),
            "open_gate_count": session.get("open_gate_count"),
            "bench_session": session,
        }
    updated = submit_bench_measurements(build_dir, mapped)
    sync_bench_session_template(build_dir)
    applied = list(((updated.get("last_submission") or {}).get("applied") or []))
    failed = [row for row in applied if isinstance(row, Mapping) and not row.get("ok")]
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": not failed,
        "mapped_count": len(mapped),
        "mapped": mapped,
        "failed": failed,
        "bench_session": updated,
    }
