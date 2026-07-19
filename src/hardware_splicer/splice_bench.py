"""S3 splice bench — evidence gate sessions for donor splices (agent-first, no UI required)."""

from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Sequence

SCHEMA_VERSION = "hardware_splicer.splice_bench.v1"
SESSION_FILE = "SPLICE_BENCH_SESSION.json"

_CRITICAL_PATTERNS = (
    "polarity", "ground", "voltage", "current", "short", "continuity",
    "do not connect", "input polarity", "rail voltage", "battery", "mains", "hazard",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(text: str, *, limit: int = 48) -> str:
    safe = re.sub(r"[^a-z0-9]+", "_", str(text or "").lower()).strip("_")
    return (safe[:limit] or "gate")


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _gate(
    *,
    gate_id: str,
    source: str,
    prompt: str,
    stage: str = "before_power_on",
    block_id: str = "",
    board_id: str = "",
    gate_type: str = "",
    critical: bool | None = None,
) -> Dict[str, Any]:
    text = f"{prompt} {gate_type}".lower()
    if critical is None:
        critical = any(token in text for token in _CRITICAL_PATTERNS) or stage == "before_power_on"
    return {
        "gate_id": gate_id,
        "source": source,
        "prompt": prompt,
        "stage": stage,
        "critical": critical,
        "block_id": block_id,
        "board_id": board_id,
        "gate_type": gate_type,
        "status": "open",
        "measurement": None,
        "closed_at": None,
        "notes": [],
    }


def _gates_from_splice_plan(splice_package: Mapping[str, Any]) -> List[Dict[str, Any]]:
    splice_plan = splice_package.get("splice_plan") if isinstance(splice_package.get("splice_plan"), dict) else {}
    gates: List[Dict[str, Any]] = []
    for index, prompt in enumerate(splice_plan.get("required_measurements") or []):
        if not str(prompt).strip():
            continue
        gates.append(_gate(gate_id=f"sp_measure_{index + 1}", source="splice_plan", prompt=str(prompt), stage="before_power_on", gate_type="measurement"))
    for index, prompt in enumerate(splice_plan.get("do_not_connect_until") or []):
        if not str(prompt).strip():
            continue
        gates.append(_gate(gate_id=f"sp_dnc_{index + 1}", source="splice_plan", prompt=str(prompt), stage="before_power_on", gate_type="interconnect_hold"))
    functional = splice_plan.get("functional_reuse_plan") if isinstance(splice_plan.get("functional_reuse_plan"), dict) else {}
    for index, block in enumerate(functional.get("ready_blocks") or []):
        if not isinstance(block, dict):
            continue
        for missing in block.get("missing_evidence") or block.get("required_tests") or []:
            text = str(missing).strip()
            if not text:
                continue
            gates.append(_gate(gate_id=f"fr_{_slug(block.get('block_id', 'block'))}_{index + 1}", source="functional_reuse_plan", prompt=text, stage="before_first_splice", block_id=str(block.get("block_id") or ""), gate_type="functional_check"))
    return gates


def _gates_from_functional_salvage(root: Mapping[str, Any]) -> List[Dict[str, Any]]:
    gates: List[Dict[str, Any]] = []
    boards = []
    circuit = root.get("circuit") if isinstance(root.get("circuit"), dict) else {}
    for board in circuit.get("boards") or []:
        if isinstance(board, dict):
            boards.append(board)
    fs_top = root.get("functional_salvage")
    if isinstance(fs_top, dict):
        boards.append({"board_id": fs_top.get("board_id"), "functional_salvage": fs_top})

    for board in boards:
        fs = board.get("functional_salvage") if isinstance(board.get("functional_salvage"), dict) else {}
        board_id = str(fs.get("board_id") or board.get("board_id") or "donor_board")
        for gate in fs.get("evidence_gates") or []:
            if not isinstance(gate, dict):
                continue
            gate_id = str(gate.get("gate_id") or gate.get("measurement_id") or "").strip()
            if not gate_id:
                gate_id = f"fs_{_slug(board_id)}_{_slug(str(gate.get('prompt') or 'gate'))}"
            gates.append(_gate(gate_id=gate_id, source="functional_salvage", prompt=str(gate.get("prompt") or gate.get("target") or gate_id), stage="before_power_on", board_id=board_id, gate_type=str(gate.get("gate_type") or gate.get("type") or "")))
        for block in fs.get("reusable_blocks") or []:
            if not isinstance(block, dict):
                continue
            block_id = str(block.get("block_id") or "")
            for gate in block.get("evidence_gates") or []:
                if not isinstance(gate, dict):
                    continue
                gate_id = str(gate.get("gate_id") or gate.get("measurement_id") or "").strip()
                if not gate_id:
                    gate_id = f"fs_{_slug(block_id)}_{_slug(str(gate.get('prompt') or 'gate'))}"
                gates.append(_gate(gate_id=gate_id, source="functional_salvage", prompt=str(gate.get("prompt") or gate.get("target") or gate_id), stage="before_power_on", block_id=block_id, board_id=board_id, gate_type=str(gate.get("gate_type") or gate.get("type") or "")))
            for missing in block.get("missing_evidence") or []:
                text = str(missing).strip()
                if not text:
                    continue
                gates.append(_gate(gate_id=f"fs_{_slug(block_id)}_missing_{_slug(text)}", source="functional_salvage", prompt=text, stage="before_power_on", block_id=block_id, board_id=board_id, gate_type="missing_evidence"))
    return gates


def _gates_from_evidence_integrations(splice_package: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Translate canonical interface packages into the existing Bench gate model."""
    integrations = splice_package.get("evidence_integrations")
    if not isinstance(integrations, Mapping):
        return []
    gates: List[Dict[str, Any]] = []
    for package in integrations.get("interfaces") or []:
        if not isinstance(package, Mapping):
            continue
        contract = package.get("interface_contract") if isinstance(package.get("interface_contract"), Mapping) else {}
        interface_id = str(contract.get("interface_id") or "donor-interface")
        board_id = str(contract.get("board_id") or "")
        block_id = str(contract.get("block_id") or "")
        for blocker in package.get("blockers") or contract.get("unresolved_fields") or []:
            field = str(blocker).strip()
            if not field:
                continue
            gate = _gate(
                gate_id=f"evidence_{_slug(interface_id)}_field_{_slug(field)}",
                source="evidence_interface",
                prompt=f"Resolve donor interface field `{field}` for {interface_id}.",
                stage="before_power_on",
                block_id=block_id,
                board_id=board_id,
                gate_type="interface_contract_field",
                critical=True,
            )
            gate.update({
                "interface_id": interface_id,
                "evidence_field": field,
                "requires_contract_edit": True,
            })
            gates.append(gate)

        recipe = package.get("bench_recipe") if isinstance(package.get("bench_recipe"), Mapping) else {}
        for phase in recipe.get("phases") or []:
            if not isinstance(phase, Mapping):
                continue
            phase_title = str(phase.get("title") or phase.get("phase_id") or "Evidence phase")
            for measurement in phase.get("measurements") or []:
                if not isinstance(measurement, Mapping):
                    continue
                measurement_id = str(measurement.get("measurement_id") or "measurement")
                description = str(measurement.get("description") or measurement_id)
                gate = _gate(
                    gate_id=f"evidence_{_slug(interface_id)}_measurement_{_slug(measurement_id)}",
                    source="evidence_recipe",
                    prompt=f"{phase_title}: {description}",
                    stage="before_power_on",
                    block_id=block_id,
                    board_id=board_id,
                    gate_type="interface_measurement",
                    critical=True,
                )
                gate.update({
                    "interface_id": interface_id,
                    "phase_id": phase.get("phase_id"),
                    "measurement_id": measurement_id,
                    "expected_unit": measurement.get("unit"),
                    "lower": measurement.get("lower"),
                    "upper": measurement.get("upper"),
                    "required": bool(measurement.get("required", True)),
                    "validators": list(measurement.get("validators") or []),
                })
                gates.append(gate)
    return gates


def _gates_from_bringup(bringup: Mapping[str, Any]) -> List[Dict[str, Any]]:
    gates: List[Dict[str, Any]] = []
    for index, check in enumerate(bringup.get("bench_checks") or []):
        text = str(check).strip()
        if not text:
            continue
        gates.append(_gate(gate_id=f"bringup_{index + 1}", source="bringup_card", prompt=text, stage="before_power_on", gate_type="bench_check"))
    return gates


def _dedupe_gates(gates: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for row in gates:
        gate_id = str(row.get("gate_id") or "").strip()
        prompt_key = str(row.get("prompt") or "").strip().lower()
        key = gate_id or prompt_key
        if not key or key in seen:
            continue
        seen.add(key)
        kept.append(dict(row))
    return kept


def collect_bench_gates(build_dir: Path) -> List[Dict[str, Any]]:
    """Gather open evidence gates from splice output artifacts."""
    root = build_dir.resolve()
    splice_package = _read_json(root / "SPLICE_PLAN.json")
    if not splice_package:
        intake_plan = _read_json(root / "PROJECT_INTAKE.json")
        splice_package = intake_plan.get("salvage_package") if isinstance(intake_plan.get("salvage_package"), dict) else {}

    intake_body = _read_json(root / "PROJECT_INTAKE.json")
    bringup = _read_json(root / "BRINGUP_CARD.json")
    if not bringup and isinstance(splice_package.get("bringup_card"), dict):
        bringup = splice_package["bringup_card"]

    gates: List[Dict[str, Any]] = []
    gates.extend(_gates_from_splice_plan(splice_package))
    gates.extend(_gates_from_functional_salvage(intake_body))
    gates.extend(_gates_from_evidence_integrations(splice_package))
    gates.extend(_gates_from_bringup(bringup))
    gates = _dedupe_gates(gates)
    from .standard_bench_gates import inject_standard_safety_gates

    return inject_standard_safety_gates(gates, intake_body)


def _readiness_summary(gates: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    open_gates = [row for row in gates if str(row.get("status") or "open") != "closed"]
    closed_gates = [row for row in gates if str(row.get("status") or "") == "closed"]
    critical_open = [row for row in open_gates if row.get("critical")]
    if not gates:
        level = "no_bench_gates"
    elif not open_gates:
        level = "bench_complete"
    elif not critical_open:
        level = "ready_for_power_on"
    else:
        level = "bench_gates_open"
    return {
        "readiness": level,
        "gate_count": len(gates),
        "open_gate_count": len(open_gates),
        "closed_gate_count": len(closed_gates),
        "critical_open_count": len(critical_open),
        "power_on_authorized": level in {"ready_for_power_on", "bench_complete"},
        "bench_complete": level == "bench_complete",
    }


def _session_path(build_dir: Path) -> Path:
    return build_dir.resolve() / SESSION_FILE


def load_bench_session(build_dir: str | Path) -> Dict[str, Any]:
    path = _session_path(Path(build_dir))
    if not path.is_file():
        raise FileNotFoundError(f"bench session not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def open_bench_session(build_dir: str | Path, *, force: bool = False) -> Dict[str, Any]:
    """Create or reload SPLICE_BENCH_SESSION.json for a splice build directory."""
    root = Path(build_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    path = _session_path(root)
    if path.is_file() and not force:
        session = load_bench_session(root)
        summary = _readiness_summary(session.get("gates") or [])
        session.update(summary)
        return session

    gates = collect_bench_gates(root)
    splice_package = _read_json(root / "SPLICE_PLAN.json")
    summary = _readiness_summary(gates)
    session = {
        "schema_version": SCHEMA_VERSION,
        "build_dir": str(root),
        "opened_at": _now(),
        "updated_at": _now(),
        "project_name": splice_package.get("project_name") or _read_json(root / "PROJECT_INTAKE.json").get("project_name"),
        "build_id": _read_json(root / "PROJECT_INTAKE.json").get("recommended_build_id"),
        "gates": gates,
        **summary,
        "next_actions": _next_actions(gates, summary),
        "agent_notes": [
            "Submit measurements with splice_bench_submit before claiming power-on is safe.",
            "Close critical gates (voltage, polarity, ground, continuity) first.",
            "Interface-contract field gates require an explicit contract edit; a scalar measurement cannot close them.",
            "Carrier KiCad DRC pass does not replace bench measurements on donor harnesses.",
        ],
    }
    path.write_text(json.dumps(session, indent=2), encoding="utf-8")
    session["session_path"] = str(path)
    return session


def _next_actions(gates: Sequence[Mapping[str, Any]], summary: Mapping[str, Any]) -> List[str]:
    if summary.get("bench_complete"):
        return ["All bench gates closed — supervised power-on and functional check may proceed."]
    actions: List[str] = []
    for row in gates:
        if str(row.get("status") or "open") == "closed":
            continue
        prefix = "CRITICAL" if row.get("critical") else "optional"
        actions.append(f"[{prefix}] {row.get('gate_id')}: {row.get('prompt')}")
        if len(actions) >= 8:
            break
    if not actions:
        actions.append("No open gates — review BRINGUP_CARD.md before power-on.")
    return actions


def bench_status(build_dir: str | Path) -> Dict[str, Any]:
    """Return bench gate status; opens a session if missing."""
    root = Path(build_dir).resolve()
    try:
        session = load_bench_session(root)
    except FileNotFoundError:
        session = open_bench_session(root)
    gates = list(session.get("gates") or [])
    summary = _readiness_summary(gates)
    session.update(summary)
    session["updated_at"] = _now()
    session["next_actions"] = _next_actions(gates, summary)
    session["open_gates"] = [row for row in gates if str(row.get("status") or "open") != "closed"]
    session["closed_gates"] = [row for row in gates if str(row.get("status") or "") == "closed"]
    session["session_path"] = str(_session_path(root))
    _session_path(root).write_text(json.dumps(session, indent=2), encoding="utf-8")
    return session


def _validate_evidence_measurement(gate: Mapping[str, Any], item: Mapping[str, Any]) -> tuple[bool, str]:
    """Validate evidence-recipe values before a gate may close."""
    if str(gate.get("gate_type") or "") != "interface_measurement":
        return True, "not an evidence measurement"
    value = item.get("value", item.get("measured_value"))
    required = bool(gate.get("required", True))
    if value is None or (isinstance(value, str) and not value.strip()):
        return (not required), "required measurement missing"
    expected_unit = str(gate.get("expected_unit") or "").strip().lower()
    supplied_unit = str(item.get("unit") or "").strip().lower()
    if expected_unit and supplied_unit and supplied_unit != expected_unit:
        return False, f"unit {supplied_unit!r} does not match expected {expected_unit!r}"
    lower = gate.get("lower")
    upper = gate.get("upper")
    if lower is None and upper is None:
        return True, "recorded"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False, "measurement is not numeric"
    if lower is not None and numeric < float(lower):
        return False, f"{numeric} < lower bound {lower}"
    if upper is not None and numeric > float(upper):
        return False, f"{numeric} > upper bound {upper}"
    return True, "within bounds"


def submit_bench_measurements(
    build_dir: str | Path,
    measurements: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Record bench measurements and close matching gates."""
    root = Path(build_dir).resolve()
    session = bench_status(root)
    gates: List[MutableMapping[str, Any]] = [dict(row) for row in session.get("gates") or []]
    by_id = {str(row.get("gate_id") or ""): row for row in gates}

    applied: List[Dict[str, Any]] = []
    for item in measurements:
        if not isinstance(item, dict):
            continue
        gate_id = str(item.get("gate_id") or "").strip()
        if not gate_id or gate_id not in by_id:
            applied.append({"gate_id": gate_id, "ok": False, "error": "unknown_gate_id"})
            continue
        gate = by_id[gate_id]
        if gate.get("requires_contract_edit"):
            gate["status"] = "open"
            gate.setdefault("notes", []).append(
                "This gate represents interface structure and must be closed by updating the canonical interface contract."
            )
            applied.append({"gate_id": gate_id, "ok": False, "error": "contract_edit_required"})
            continue
        status = str(item.get("status") or "closed").strip().lower()
        validation_ok, validation_reason = _validate_evidence_measurement(gate, item)
        closing_status = status in {"pass", "closed", "ok", "verified"}
        if closing_status and not validation_ok:
            gate["status"] = "blocked"
        elif closing_status:
            gate["status"] = "closed"
        elif status in {"fail", "blocked", "open", "hold"}:
            gate["status"] = "open" if status == "open" else "blocked"
        else:
            gate["status"] = "closed" if validation_ok else "blocked"
        measurement = {
            "value": item.get("value", item.get("measured_value")),
            "unit": item.get("unit"),
            "operator": item.get("operator"),
            "method": item.get("method"),
            "recorded_at": _now(),
        }
        gate["measurement"] = measurement
        if item.get("notes"):
            gate.setdefault("notes", [])
            gate["notes"].append(str(item["notes"]))
        if gate["status"] == "closed":
            gate["closed_at"] = _now()
        if closing_status and not validation_ok:
            gate.setdefault("notes", []).append(f"Measurement validation failed: {validation_reason}")
            applied.append({
                "gate_id": gate_id,
                "ok": False,
                "status": gate["status"],
                "error": "measurement_validation_failed",
                "reason": validation_reason,
            })
        else:
            applied.append({"gate_id": gate_id, "ok": True, "status": gate["status"]})

    session["gates"] = gates
    summary = _readiness_summary(gates)
    session.update(summary)
    session["updated_at"] = _now()
    session["last_submission"] = {"applied": applied, "recorded_at": _now()}
    session["next_actions"] = _next_actions(gates, summary)
    session["open_gates"] = [row for row in gates if str(row.get("status") or "open") != "closed"]
    session["closed_gates"] = [row for row in gates if str(row.get("status") or "") == "closed"]
    _session_path(root).write_text(json.dumps(session, indent=2), encoding="utf-8")
    session["session_path"] = str(_session_path(root))
    return session
