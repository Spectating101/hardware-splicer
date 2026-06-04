from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.engines.system_structure_extractor import extract_board_structure, synthesize_machine_topology
from src.intelligence.board_dossier import BoardDossierBuilder
from src.intelligence.board_evidence_graph import BoardEvidenceGraphBuilder
from src.intelligence.circuit_ai_reasoner import CircuitAIReasoner
from src.intelligence.functional_salvage import aggregate_functional_salvage


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _issue(severity: str, topic: str, message: str, action: str) -> Dict[str, str]:
    return {"severity": severity, "topic": topic, "message": message, "action": action}


def _dedupe_text(items: Iterable[Any], *, limit: int = 20) -> List[str]:
    kept: List[str] = []
    seen = set()
    for item in items:
        text = str(item or "").strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            kept.append(text)
        if len(kept) >= limit:
            break
    return kept


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _confidence_band(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.55:
        return "medium"
    if score >= 0.3:
        return "low"
    return "unknown"


def _board_spec_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(payload.get("boards"), list):
        rows = [row for row in payload.get("boards") or [] if isinstance(row, dict)]
    elif isinstance(payload.get("board"), dict):
        rows = [dict(payload.get("board") or {})]
    else:
        rows = [payload]
    return rows


def _payload_has_design_paths(payload: Dict[str, Any]) -> bool:
    for spec in _board_spec_rows(payload):
        if isinstance(spec, dict) and str(spec.get("path") or spec.get("design_path") or "").strip():
            return True
    return False


def _extract_boards(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    boards: List[Dict[str, Any]] = []
    for index, spec in enumerate(_board_spec_rows(payload), start=1):
        path = str(spec.get("path") or spec.get("design_path") or "").strip()
        if not path:
            raise ValueError(f"boards[{index - 1}].path is required")
        board_id = str(spec.get("board_id") or Path(path).stem or f"board_{index}").strip() or f"board_{index}"
        board_name = str(spec.get("board_name") or spec.get("name") or board_id).strip() or board_id
        kind = str(spec.get("kind") or "").strip().lower() or None
        structure = extract_board_structure(path, board_id=board_id, board_name=board_name, kind=kind)
        try:
            from src.engines.circuit_board_graph import build_circuit_board_model

            circuit_model = build_circuit_board_model(
                path,
                board_id=board_id,
                board_name=board_name,
                kind=kind,
            )
            structure = dict(circuit_model.get("raw_structure") or structure)
            structure["_circuit_model"] = {
                key: value for key, value in circuit_model.items() if key != "raw_structure"
            }
        except Exception:
            structure = dict(structure)
        boards.append(structure)
    return boards


def _board_confidence(board: Dict[str, Any]) -> float:
    summary = board.get("summary") or {}
    runtime = board.get("controller_runtime") or {}
    power = board.get("power") or {}
    score = 0.2
    if int(summary.get("component_count") or 0) > 0:
        score += 0.2
    if int(summary.get("connector_count") or 0) > 0:
        score += 0.15
    if int(summary.get("power_rail_count") or 0) > 0:
        score += 0.15
    if runtime.get("controllers"):
        score += 0.15
    if runtime.get("programming_paths"):
        score += 0.1
    if (power.get("regulators") or []):
        score += 0.05
    questions = len(board.get("questions") or [])
    score -= min(questions * 0.03, 0.18)
    return round(max(0.0, min(score, 0.95)), 2)


def _is_controller_role(role: Any) -> bool:
    text = str(role or "").lower()
    return any(term in text for term in ["controller", "embedded", "compute", "mcu", "microcontroller", "processor"])


def _normalized_role(role: Any) -> str:
    text = str(role or "unknown_board").strip() or "unknown_board"
    lower = text.lower()
    if _is_controller_role(lower):
        return "controller"
    if "power" in lower:
        return "power"
    if "motor" in lower or "driver" in lower:
        return "actuator_driver"
    if "sensor" in lower:
        return "sensor"
    if "interface" in lower or "connector" in lower:
        return "interface"
    return text


def _board_findings(board: Dict[str, Any]) -> List[Dict[str, str]]:
    findings: List[Dict[str, str]] = []
    runtime = board.get("controller_runtime") or {}
    power_control = board.get("power_control_analysis") or {}
    controllers = runtime.get("controllers") or []
    programming_paths = runtime.get("programming_paths") or []
    summary = board.get("summary") or {}

    if int(summary.get("connector_count") or 0) == 0:
        findings.append(
            _issue(
                "high",
                "connectors",
                "No connector evidence was extracted.",
                "Add netlist/PCB evidence with connector refs or manually identify board I/O.",
            )
        )
    if controllers and not programming_paths:
        findings.append(
            _issue(
                "high",
                "programming_path",
                "Controller evidence exists, but no programming/debug path was extracted.",
                "Confirm USB, UART, SWD, JTAG, or module-native programming access before firmware bring-up.",
            )
        )
    if not (board.get("power") or {}).get("rails"):
        findings.append(
            _issue(
                "high",
                "power",
                "No power rails were extracted.",
                "Provide netlist/PCB evidence or manual rail hints before relying on electrical conclusions.",
            )
        )
    for row in power_control.get("risk_findings") or []:
        if isinstance(row, dict):
            findings.append(
                _issue(
                    str(row.get("severity") or "medium"),
                    str(row.get("topic") or "power_control"),
                    str(row.get("message") or "Power/control risk found."),
                    str(row.get("fix") or "Review extracted power/control evidence and update the design."),
                )
            )
    for question in board.get("questions") or []:
        findings.append(
            _issue(
                "medium",
                "evidence_gap",
                str(question),
                "Capture the missing evidence or confirm the assumption in the board session.",
            )
        )
    return findings[:80]


def _action_plan(board: Dict[str, Any], findings: List[Dict[str, str]]) -> List[Dict[str, str]]:
    actions: List[Dict[str, str]] = []
    for step in board.get("bring_up_plan") or []:
        if isinstance(step, dict):
            actions.append(
                {
                    "stage": str(step.get("stage") or "bring_up"),
                    "title": str(step.get("title") or "Bring-up step"),
                    "action": str(step.get("action") or ""),
                    "expected": str(step.get("expected") or ""),
                }
            )
    for finding in findings:
        actions.append(
            {
                "stage": f"resolve_{finding['topic']}",
                "title": finding["message"],
                "action": finding["action"],
                "expected": "Finding is either resolved by evidence or accepted as a documented risk.",
            }
        )
    return actions[:80]


def _board_summary(board: Dict[str, Any]) -> Dict[str, Any]:
    runtime = board.get("controller_runtime") or {}
    power_control = board.get("power_control_analysis") or {}
    circuit_model = board.get("_circuit_model") if isinstance(board.get("_circuit_model"), dict) else {}
    functional_salvage = (
        circuit_model.get("functional_salvage")
        if isinstance(circuit_model.get("functional_salvage"), dict)
        else board.get("functional_salvage")
        if isinstance(board.get("functional_salvage"), dict)
        else None
    )
    findings = _board_findings(board)
    confidence = _board_confidence(board)
    hard_findings = [row for row in findings if row.get("severity") in {"critical", "error", "high"}]
    if confidence >= 0.7 and not hard_findings:
        disposition = "actionable"
    elif confidence >= 0.45:
        disposition = "needs_review"
    else:
        disposition = "insufficient_evidence"
    raw_structure = {key: value for key, value in board.items() if key != "_circuit_model"}
    summary = {
        "board_id": board.get("board_id"),
        "board_name": board.get("board_name"),
        "source": board.get("source"),
        "primary_role": _normalized_role(board.get("primary_role")),
        "disposition": disposition,
        "confidence": confidence,
        "confidence_band": _confidence_band(confidence),
        "summary": board.get("summary") or {},
        "controller": {
            "count": len(runtime.get("controllers") or []),
            "controllers": [
                row.get("part_number") or row.get("ref")
                for row in (runtime.get("controllers") or [])
                if isinstance(row, dict)
            ],
            "programming_paths": runtime.get("programming_paths") or [],
            "firmware_status": (runtime.get("firmware_readiness") or {}).get("status"),
            "buses": runtime.get("bus_inventory") or [],
        },
        "power": {
            "rails": (board.get("power") or {}).get("rails") or [],
            "regulators": (board.get("power") or {}).get("regulators") or [],
            "summary": power_control.get("summary") or {},
        },
        "connectors": board.get("connectors") or [],
        "findings": findings,
        "action_plan": _action_plan(board, findings),
        "raw_structure": raw_structure,
    }
    if functional_salvage:
        summary["functional_salvage"] = functional_salvage
    if circuit_model:
        summary["circuit"] = {
            "readiness": circuit_model.get("readiness"),
            "workflow_state": circuit_model.get("workflow_state"),
            "graph_summary": (circuit_model.get("graph") or {}).get("summary", {}),
            "splice_contract": circuit_model.get("splice_contract"),
            "electrical_viability": circuit_model.get("electrical_viability"),
        }
    return summary


def _latest_session_analysis(session: Dict[str, Any]) -> Dict[str, Any]:
    analyses = session.get("analyses") if isinstance(session.get("analyses"), list) else []
    if not analyses:
        return {}
    latest = analyses[-1] if isinstance(analyses[-1], dict) else {}
    results = latest.get("results")
    return results if isinstance(results, dict) else {}


def _session_counts(session: Optional[Dict[str, Any]]) -> Dict[str, int]:
    if not isinstance(session, dict):
        return {
            "capture_count": 0,
            "measurement_count": 0,
            "review_count": 0,
            "outcome_count": 0,
            "open_task_count": 0,
            "resolved_task_count": 0,
        }
    evidence = session.get("evidence") if isinstance(session.get("evidence"), dict) else {}
    tasks = session.get("evidence_tasks") if isinstance(session.get("evidence_tasks"), list) else []
    return {
        "capture_count": len(evidence.get("captures") or []),
        "measurement_count": len(evidence.get("measurements") or []),
        "review_count": len(session.get("reviews") or []),
        "outcome_count": len(session.get("outcomes") or []),
        "open_task_count": len([task for task in tasks if isinstance(task, dict) and str(task.get("status") or "open") == "open"]),
        "resolved_task_count": len([task for task in tasks if isinstance(task, dict) and str(task.get("status") or "") == "resolved"]),
    }


def _analysis_role(analysis: Dict[str, Any]) -> str:
    board = analysis.get("board_understanding") if isinstance(analysis.get("board_understanding"), dict) else {}
    identity = board.get("board_identity") if isinstance(board.get("board_identity"), dict) else {}
    return _normalized_role(identity.get("primary_type") or board.get("primary_type") or "unknown_board")


def _analysis_confidence(analysis: Dict[str, Any]) -> float:
    board = analysis.get("board_understanding") if isinstance(analysis.get("board_understanding"), dict) else {}
    identity = board.get("board_identity") if isinstance(board.get("board_identity"), dict) else {}
    ledger = analysis.get("certainty_ledger") if isinstance(analysis.get("certainty_ledger"), dict) else {}
    overall = ledger.get("overall") if isinstance(ledger.get("overall"), dict) else {}
    candidates = [
        identity.get("confidence"),
        board.get("confidence"),
        overall.get("score"),
        (analysis.get("detection_summary") or {}).get("average_confidence")
        if isinstance(analysis.get("detection_summary"), dict)
        else None,
    ]
    for value in candidates:
        score = _safe_float(value, -1.0)
        if score >= 0:
            return round(max(0.0, min(score, 0.95)), 2)
    return 0.25 if analysis else 0.0


def _analysis_component_count(analysis: Dict[str, Any]) -> int:
    summary = analysis.get("detection_summary") if isinstance(analysis.get("detection_summary"), dict) else {}
    detections = analysis.get("detections") if isinstance(analysis.get("detections"), list) else []
    return _safe_int(summary.get("total_components"), len(detections))


def _analysis_connector_count(analysis: Dict[str, Any]) -> int:
    connection = analysis.get("machine_connection_map") if isinstance(analysis.get("machine_connection_map"), dict) else {}
    count = _safe_int(connection.get("connector_count"), 0)
    detections = analysis.get("detections") if isinstance(analysis.get("detections"), list) else []
    for detection in detections:
        if not isinstance(detection, dict):
            continue
        label = str(detection.get("class_name") or detection.get("label") or "").lower()
        if "connector" in label or label.startswith("j"):
            count += 1
    return count


def _analysis_findings(analysis: Dict[str, Any]) -> List[Dict[str, str]]:
    findings: List[Dict[str, str]] = []
    ledger = analysis.get("certainty_ledger") if isinstance(analysis.get("certainty_ledger"), dict) else {}
    for missing in (ledger.get("missing_evidence") or [])[:12]:
        findings.append(
            _issue(
                "medium",
                "evidence_gap",
                str(missing),
                "Attach the missing capture, reference, measurement, or review to the board session.",
            )
        )
    production_aoi = analysis.get("production_aoi") if isinstance(analysis.get("production_aoi"), dict) else {}
    for blocker in (production_aoi.get("blockers") or [])[:12]:
        findings.append(
            _issue(
                "high",
                "production_aoi",
                str(blocker),
                "Resolve the AOI blocker before using this board result as a release decision.",
            )
        )
    for evidence in (production_aoi.get("required_evidence") or [])[:8]:
        findings.append(
            _issue(
                "medium",
                "required_evidence",
                str(evidence),
                "Collect the required evidence and rerun board intelligence.",
            )
        )
    return findings[:50]


def _visual_board_summary(
    analysis: Dict[str, Any],
    *,
    board_id: str = "session_board",
    board_name: str = "Session board",
    source: str = "session_analysis",
) -> Dict[str, Any]:
    role = _analysis_role(analysis)
    confidence = _analysis_confidence(analysis)
    component_count = _analysis_component_count(analysis)
    connector_count = _analysis_connector_count(analysis)
    findings = _analysis_findings(analysis)
    production_aoi = analysis.get("production_aoi") if isinstance(analysis.get("production_aoi"), dict) else {}
    hard_findings = [row for row in findings if row.get("severity") in {"critical", "error", "high"}]
    if confidence >= 0.7 and not hard_findings:
        disposition = "actionable"
    elif confidence >= 0.35 or component_count or connector_count:
        disposition = "needs_review"
    else:
        disposition = "insufficient_evidence"

    controller_count = 1 if _is_controller_role(role) else 0
    connection = analysis.get("machine_connection_map") if isinstance(analysis.get("machine_connection_map"), dict) else {}
    required_measurements = ((connection.get("splice_plan") or {}).get("required_measurements") or []) if isinstance(connection.get("splice_plan"), dict) else []
    action_plan = [
        {
            "stage": "ground_visual_evidence",
            "title": finding["message"],
            "action": finding["action"],
            "expected": "The claim has capture, measurement, review, or reference support in the session.",
        }
        for finding in findings
    ]
    for measurement in required_measurements[:8]:
        action_plan.append(
            {
                "stage": "measurement_gate",
                "title": str(measurement),
                "action": "Record the measurement in the board session before wiring or powering dependent outputs.",
                "expected": "Measurement supports the extracted board role and connection map.",
            }
        )
    if production_aoi.get("operator_checklist"):
        for item in (production_aoi.get("operator_checklist") or [])[:6]:
            action_plan.append(
                {
                    "stage": "operator_check",
                    "title": str(item),
                    "action": "Complete and record the operator check.",
                    "expected": "The production or repair decision is traceable to human-reviewed evidence.",
                }
            )

    connectors = [
        {"ref": f"connector_{index}", "evidence": "machine_connection_map"}
        for index in range(1, min(connector_count, 12) + 1)
    ]
    return {
        "board_id": board_id,
        "board_name": board_name,
        "source": source,
        "primary_role": role,
        "disposition": disposition,
        "confidence": confidence,
        "confidence_band": _confidence_band(confidence),
        "summary": {
            "component_count": component_count,
            "connector_count": connector_count,
            "power_rail_count": 0,
            "source": source,
        },
        "controller": {
            "count": controller_count,
            "controllers": ["visual_controller_candidate"] if controller_count else [],
            "programming_paths": [],
            "firmware_status": None,
            "buses": [],
        },
        "power": {"rails": [], "regulators": [], "summary": {}},
        "connectors": connectors,
        "findings": findings,
        "action_plan": action_plan[:80],
        "raw_structure": {
            "source": source,
            "analysis_keys": sorted(str(key) for key in analysis.keys())[:40],
            "machine_connection_map": connection,
        },
    }


def _boards_from_existing_intelligence(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    if analysis.get("mode") != "circuit_ai_board_intelligence":
        return []
    boards = analysis.get("boards") if isinstance(analysis.get("boards"), list) else []
    return [row for row in boards if isinstance(row, dict)]


def _boards_from_circuit_graph(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    if analysis.get("mode") != "circuit_ai_circuit_graph":
        return []
    boards = []
    for row in analysis.get("boards") or []:
        if not isinstance(row, dict):
            continue
        raw = dict(row.get("raw_structure") or {})
        if not raw:
            raw = {
                "board_id": row.get("board_id"),
                "board_name": row.get("board_name"),
                "source": row.get("source") or {"kind": "circuit_graph"},
                "summary": (row.get("graph") or {}).get("summary", {}),
                "primary_role": row.get("primary_role"),
                "connectors": [],
                "power": {},
                "active_components": [],
                "categories": {},
            }
        raw["_circuit_model"] = {key: value for key, value in row.items() if key != "raw_structure"}
        boards.append(_board_summary(raw))
    return boards


def _functional_salvage_summary(boards: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not any(isinstance(board.get("functional_salvage"), dict) for board in boards):
        return {}
    return aggregate_functional_salvage(boards)


def _board_reasoning_context(
    boards: List[Dict[str, Any]],
    functional_salvage: Dict[str, Any],
    readiness: Dict[str, Any],
    coverage: Dict[str, Any],
    tasks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    reports = [
        board.get("functional_salvage")
        for board in boards
        if isinstance(board.get("functional_salvage"), dict)
    ]
    context = {
        "mode": "board_intelligence_reasoning_context",
        "board_count": len(boards),
        "overall_readiness": readiness.get("level"),
        "workflow_state": "board_intelligence",
        "boards": [
            {
                "board_id": board.get("board_id"),
                "board_name": board.get("board_name"),
                "primary_role": board.get("primary_role"),
                "readiness": board.get("disposition"),
                "graph": (board.get("circuit") or {}).get("graph_summary") or {},
                "functional_salvage": board.get("functional_salvage"),
            }
            for board in boards
        ],
        "functional_salvage": functional_salvage,
        "evidence_coverage": {
            "score": coverage.get("score"),
            "blockers": coverage.get("blockers") or [],
        },
        "next_evidence_tasks": tasks[:12],
    }
    if reports:
        context["functional_reports"] = reports
    return context


def _task_type_for_text(text: str) -> str:
    lower = text.lower()
    if any(term in lower for term in ["voltage", "continuity", "resistance", "current", "measure", "logic level"]):
        return "measurement"
    if any(term in lower for term in ["photo", "scan", "capture", "close-up", "image", "marking"]):
        return "capture"
    if any(term in lower for term in ["golden", "reference", "netlist", "gerber", "kicad", "schematic"]):
        return "reference"
    if any(term in lower for term in ["review", "confirm", "verify", "operator"]):
        return "review"
    return "evidence"


def _make_gate(
    gate_id: str,
    label: str,
    passed: bool,
    *,
    weight: float,
    severity: str,
    action: str,
    evidence: Optional[List[str]] = None,
    required: bool = True,
    applicable: bool = True,
) -> Dict[str, Any]:
    if not applicable:
        status = "not_applicable"
    elif passed:
        status = "pass"
    else:
        status = "missing"
    return {
        "gate_id": gate_id,
        "label": label,
        "status": status,
        "passed": bool(passed) if applicable else True,
        "applicable": applicable,
        "required": required,
        "weight": weight,
        "severity": severity,
        "evidence": evidence or [],
        "action": action,
    }


def _board_has_source(board: Dict[str, Any]) -> bool:
    source = board.get("source")
    raw = board.get("raw_structure") if isinstance(board.get("raw_structure"), dict) else {}
    return bool(source or raw.get("source"))


def _board_component_count(board: Dict[str, Any]) -> int:
    summary = board.get("summary") if isinstance(board.get("summary"), dict) else {}
    return _safe_int(summary.get("component_count"), 0)


def _board_connector_count(board: Dict[str, Any]) -> int:
    summary = board.get("summary") if isinstance(board.get("summary"), dict) else {}
    return max(_safe_int(summary.get("connector_count"), 0), len(board.get("connectors") or []))


def _board_power_rail_count(board: Dict[str, Any]) -> int:
    summary = board.get("summary") if isinstance(board.get("summary"), dict) else {}
    power = board.get("power") if isinstance(board.get("power"), dict) else {}
    return max(_safe_int(summary.get("power_rail_count"), 0), len(power.get("rails") or []))


def _board_controller_count(board: Dict[str, Any]) -> int:
    controller = board.get("controller") if isinstance(board.get("controller"), dict) else {}
    return _safe_int(controller.get("count"), 0)


def _board_programming_path_count(board: Dict[str, Any]) -> int:
    controller = board.get("controller") if isinstance(board.get("controller"), dict) else {}
    return len(controller.get("programming_paths") or [])


def _evidence_coverage(boards: List[Dict[str, Any]], session: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    counts = _session_counts(session)
    has_boards = bool(boards)
    primary = boards[0] if boards else {}
    controller_applicable = _is_controller_role(primary.get("primary_role")) or _board_controller_count(primary) > 0
    visual_capture = counts["capture_count"] > 0 or any(
        str(board.get("source") or "").startswith(("session", "visual", "scan"))
        for board in boards
    )
    gates = [
        _make_gate(
            "design_or_scan_source",
            "Board source evidence",
            has_boards and any(_board_has_source(board) for board in boards),
            weight=1.0,
            severity="high",
            evidence=[str(board.get("source")) for board in boards if board.get("source")],
            action="Attach at least one design file, scan analysis, or reviewed board session.",
        ),
        _make_gate(
            "board_role",
            "Board role classification",
            has_boards and any(str(board.get("primary_role") or "unknown_board") != "unknown_board" for board in boards),
            weight=0.9,
            severity="high",
            evidence=[str(board.get("primary_role")) for board in boards if board.get("primary_role")],
            action="Classify the board role from design evidence, markings, component inventory, or operator review.",
        ),
        _make_gate(
            "component_inventory",
            "Component inventory",
            any(_board_component_count(board) > 0 for board in boards),
            weight=0.8,
            severity="medium",
            evidence=[f"{_board_component_count(board)} component(s)" for board in boards if _board_component_count(board) > 0],
            action="Provide scan, netlist, or detection evidence with component candidates.",
        ),
        _make_gate(
            "connector_map",
            "Connector and I/O map",
            any(_board_connector_count(board) > 0 for board in boards),
            weight=0.8,
            severity="high",
            evidence=[f"{_board_connector_count(board)} connector(s)" for board in boards if _board_connector_count(board) > 0],
            action="Identify external connectors, headers, harness points, or test pads before wiring integration.",
        ),
        _make_gate(
            "power_model",
            "Power rail model",
            any(_board_power_rail_count(board) > 0 for board in boards),
            weight=0.9,
            severity="high",
            evidence=[f"{_board_power_rail_count(board)} rail(s)" for board in boards if _board_power_rail_count(board) > 0],
            action="Extract or measure board power rails, polarity, grounds, regulators, and safe input limits.",
        ),
        _make_gate(
            "controller_identity",
            "Controller identity",
            any(_board_controller_count(board) > 0 for board in boards),
            weight=0.8,
            severity="high",
            evidence=[str(item) for board in boards for item in ((board.get("controller") or {}).get("controllers") or [])],
            action="Identify the controller/module and its critical boot/runtime requirements.",
            applicable=controller_applicable,
        ),
        _make_gate(
            "programming_path",
            "Programming or debug path",
            any(_board_programming_path_count(board) > 0 for board in boards),
            weight=0.7,
            severity="high",
            evidence=[str(path) for board in boards for path in ((board.get("controller") or {}).get("programming_paths") or [])[:4]],
            action="Confirm USB, UART, SWD, JTAG, or module-native programming access before firmware bring-up.",
            applicable=controller_applicable,
        ),
        _make_gate(
            "visual_capture",
            "Visual capture or reviewed scan",
            visual_capture,
            weight=0.6,
            severity="medium",
            evidence=[f"{counts['capture_count']} capture(s)"] if counts["capture_count"] else [],
            action="Attach top/bottom board photos or reviewed scan analysis to ground the design extraction.",
            required=False,
        ),
        _make_gate(
            "measurement_evidence",
            "Electrical measurements",
            counts["measurement_count"] > 0,
            weight=0.6,
            severity="medium",
            evidence=[f"{counts['measurement_count']} measurement(s)"] if counts["measurement_count"] else [],
            action="Record voltage, continuity, resistance, or logic-level measurements for power and connector claims.",
            required=False,
        ),
        _make_gate(
            "human_review",
            "Human review",
            counts["review_count"] > 0 or counts["resolved_task_count"] > 0,
            weight=0.5,
            severity="medium",
            evidence=[f"{counts['review_count']} review(s)", f"{counts['resolved_task_count']} resolved task(s)"],
            action="Resolve the highest-priority evidence task or operator review before treating weak claims as strong.",
            required=False,
        ),
        _make_gate(
            "outcome_feedback",
            "Outcome feedback",
            counts["outcome_count"] > 0,
            weight=0.4,
            severity="low",
            evidence=[f"{counts['outcome_count']} outcome(s)"] if counts["outcome_count"] else [],
            action="Record the repair, reuse, AOI, or bring-up outcome so future decisions can be calibrated.",
            required=False,
        ),
    ]
    applicable = [gate for gate in gates if gate["applicable"]]
    denominator = sum(float(gate["weight"]) for gate in applicable) or 1.0
    numerator = sum(float(gate["weight"]) for gate in applicable if gate["status"] == "pass")
    blockers = [
        {
            "gate_id": gate["gate_id"],
            "label": gate["label"],
            "severity": gate["severity"],
            "action": gate["action"],
        }
        for gate in applicable
        if gate["status"] != "pass" and gate["required"] and gate["severity"] in {"critical", "high"}
    ]
    return {
        "score": round(max(0.0, min(numerator / denominator, 1.0)), 3),
        "passed_gate_count": len([gate for gate in applicable if gate["status"] == "pass"]),
        "applicable_gate_count": len(applicable),
        "blockers": blockers,
        "gates": gates,
    }


def _next_evidence_tasks(
    boards: List[Dict[str, Any]],
    coverage: Dict[str, Any],
    session: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    seen = set()

    def add(prompt: str, *, task_type: Optional[str] = None, priority: int = 3, source: str = "board_intelligence", gate_id: Optional[str] = None) -> None:
        text = str(prompt or "").strip()
        key = (task_type or _task_type_for_text(text), text.lower())
        if not text or key in seen:
            return
        seen.add(key)
        tasks.append(
            {
                "task_type": key[0],
                "prompt": text,
                "priority": priority,
                "source": source,
                "gate_id": gate_id,
                "usable_for": ["board_intelligence", "bringup", "repair", "reuse", "training"],
            }
        )

    for gate in coverage.get("gates") or []:
        if not isinstance(gate, dict) or gate.get("status") in {"pass", "not_applicable"}:
            continue
        priority = 1 if gate.get("severity") in {"critical", "high"} else 2 if gate.get("severity") == "medium" else 3
        add(str(gate.get("action") or gate.get("label")), priority=priority, gate_id=str(gate.get("gate_id") or ""))

    for board in boards:
        for finding in (board.get("findings") or [])[:12]:
            if not isinstance(finding, dict):
                continue
            priority = 1 if finding.get("severity") in {"critical", "error", "high"} else 2
            add(str(finding.get("action") or finding.get("message") or ""), priority=priority, source=f"board_finding:{finding.get('topic')}")

    if isinstance(session, dict):
        for task in (session.get("evidence_tasks") or [])[:12]:
            if not isinstance(task, dict) or str(task.get("status") or "open") != "open":
                continue
            add(
                str(task.get("prompt") or ""),
                task_type=str(task.get("type") or "evidence"),
                priority=_safe_int(task.get("priority"), 3),
                source=str(task.get("source") or "session_task"),
            )

    return tasks[:30]


def _readiness(
    boards: List[Dict[str, Any]],
    coverage: Dict[str, Any],
    session: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    counts = _session_counts(session)
    score = float(coverage.get("score") or 0.0)
    blockers = coverage.get("blockers") or []
    dispositions = {str(board.get("disposition") or "") for board in boards}
    if not boards:
        level = "insufficient_evidence"
        reason = "No board-level design, scan, or session analysis is available."
    elif "insufficient_evidence" in dispositions or score < 0.35:
        level = "insufficient_evidence"
        reason = "Board identity or core electrical evidence is too weak."
    elif blockers:
        level = "evidence_review_required"
        reason = "One or more required high-severity board gates are still missing."
    elif counts["outcome_count"] > 0 and score >= 0.72:
        level = "calibrated_case"
        reason = "The board decision has source evidence plus recorded outcome feedback."
    elif counts["measurement_count"] > 0 and (counts["review_count"] > 0 or counts["resolved_task_count"] > 0):
        level = "operator_workflow_ready"
        reason = "The board has source evidence, measurements, and reviewed session evidence."
    elif counts["measurement_count"] > 0:
        level = "bringup_ready"
        reason = "Core design gates pass and at least one electrical measurement is recorded."
    else:
        level = "design_review_ready"
        reason = "Core design gates pass, but session measurements/reviews are still thin."
    return {
        "level": level,
        "score": score,
        "confidence_band": _confidence_band(score),
        "reason": reason,
        "blocker_count": len(blockers),
        "blockers": blockers,
    }


def _operator_summary(
    boards: List[Dict[str, Any]],
    coverage: Dict[str, Any],
    tasks: List[Dict[str, Any]],
    session: Optional[Dict[str, Any]],
) -> Dict[str, List[str]]:
    counts = _session_counts(session)
    known: List[str] = []
    for board in boards[:4]:
        name = board.get("board_name") or board.get("board_id") or "board"
        role = str(board.get("primary_role") or "unknown_board").replace("_", " ")
        confidence = board.get("confidence")
        known.append(f"{name}: role={role}, confidence={confidence}")
        if _board_controller_count(board):
            known.append(f"{name}: {_board_controller_count(board)} controller candidate(s)")
        if _board_power_rail_count(board):
            known.append(f"{name}: {_board_power_rail_count(board)} power rail(s)")
        if _board_connector_count(board):
            known.append(f"{name}: {_board_connector_count(board)} connector/I/O candidate(s)")
    if counts["measurement_count"]:
        known.append(f"{counts['measurement_count']} electrical measurement(s) are recorded")
    if counts["review_count"] or counts["resolved_task_count"]:
        known.append(f"{counts['review_count']} review(s) and {counts['resolved_task_count']} resolved task(s) are recorded")
    if counts["outcome_count"]:
        known.append(f"{counts['outcome_count']} outcome(s) are recorded")

    unknown = [
        str(gate.get("label") or gate.get("gate_id"))
        for gate in coverage.get("gates") or []
        if isinstance(gate, dict) and gate.get("status") == "missing"
    ]
    next_steps = [str(task.get("prompt") or "") for task in tasks[:8]]
    return {
        "known": _dedupe_text(known, limit=12),
        "unknown": _dedupe_text(unknown, limit=12),
        "next": _dedupe_text(next_steps, limit=8),
    }


def _certainty_ledger_from_readiness(coverage: Dict[str, Any], readiness: Dict[str, Any]) -> Dict[str, Any]:
    score = float(readiness.get("score") or coverage.get("score") or 0.0)
    level = {
        "calibrated_case": "certain",
        "operator_workflow_ready": "likely",
        "bringup_ready": "likely",
        "design_review_ready": "possible",
        "evidence_review_required": "possible",
        "insufficient_evidence": "unknown",
    }.get(str(readiness.get("level") or ""), "unknown")
    items = []
    missing = []
    for gate in coverage.get("gates") or []:
        if not isinstance(gate, dict) or not gate.get("applicable", True):
            continue
        status = str(gate.get("status") or "missing")
        certainty = "likely" if status == "pass" else "unknown"
        if status == "missing":
            missing.append(str(gate.get("action") or gate.get("label") or "missing board evidence"))
        items.append(
            {
                "item_id": f"board_gate_{gate.get('gate_id')}",
                "claim_type": "board_intelligence_gate",
                "claim": str(gate.get("label") or gate.get("gate_id")),
                "certainty": certainty,
                "score": 1.0 if status == "pass" else 0.0,
                "next_actions": [] if status == "pass" else [str(gate.get("action") or "")],
                "usable_for": ["board_intelligence", "bringup", "repair", "reuse"],
            }
        )
    return {
        "overall": {
            "score": round(max(0.0, min(score, 1.0)), 3),
            "level": level,
            "summary": str(readiness.get("reason") or ""),
        },
        "counts": {
            "total": len(items),
            "certain": 1 if level == "certain" else 0,
            "likely": len([item for item in items if item["certainty"] == "likely"]),
            "possible": 1 if level == "possible" else 0,
            "unknown": len([item for item in items if item["certainty"] == "unknown"]),
        },
        "missing_evidence": _dedupe_text(missing, limit=20),
        "items": items[:60],
        "training_queue": {
            "should_capture": bool(missing),
            "candidate_labels": [item["claim"] for item in items if item["certainty"] == "unknown"][:12],
        },
    }


def _payload_analyses(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    analyses: List[Dict[str, Any]] = []
    for key in ["analysis", "results", "scan_analysis", "visual_analysis", "intelligence"]:
        value = payload.get(key)
        if isinstance(value, dict):
            analyses.append(value)
    for row in payload.get("analyses") or []:
        if isinstance(row, dict):
            if isinstance(row.get("results"), dict):
                analyses.append(row["results"])
            else:
                analyses.append(row)
    session = payload.get("session") if isinstance(payload.get("session"), dict) else {}
    latest = _latest_session_analysis(session) if session else {}
    if latest:
        analyses.append(latest)
    return analyses


def _boards_from_payload(payload: Dict[str, Any]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    boards_raw: List[Dict[str, Any]] = []
    boards: List[Dict[str, Any]] = []
    topology: Optional[Dict[str, Any]] = None
    if _payload_has_design_paths(payload):
        boards_raw = _extract_boards(payload)
        boards.extend(_board_summary(board) for board in boards_raw)
        if len(boards_raw) > 1 or bool(payload.get("machine_name")):
            topology = synthesize_machine_topology(
                boards_raw,
                machine_name=str(payload.get("machine_name") or "board_intelligence_machine"),
            )

    for index, analysis in enumerate(_payload_analyses(payload), start=1):
        existing_boards = _boards_from_existing_intelligence(analysis)
        if existing_boards:
            boards.extend(existing_boards)
            if topology is None and isinstance(analysis.get("machine_topology"), dict):
                topology = analysis.get("machine_topology")
            continue
        circuit_boards = _boards_from_circuit_graph(analysis)
        if circuit_boards:
            boards.extend(circuit_boards)
            if topology is None and isinstance(analysis.get("machine_topology"), dict):
                topology = analysis.get("machine_topology")
            continue
        if any(
            key in analysis
            for key in [
                "board_understanding",
                "detections",
                "detection_summary",
                "machine_connection_map",
                "production_aoi",
                "certainty_ledger",
            ]
        ):
            boards.append(
                _visual_board_summary(
                    analysis,
                    board_id=str(payload.get("board_id") or f"session_board_{index}"),
                    board_name=str(payload.get("board_name") or payload.get("title") or f"Session Board {index}"),
                    source=str(payload.get("source") or "session_analysis"),
                )
            )
    return boards_raw, boards, topology


def _session_artifacts(session: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(session, dict):
        return {}
    graph = BoardEvidenceGraphBuilder().build(session)
    dossier = BoardDossierBuilder().build(session)
    return {
        "evidence_graph": {
            "summary": graph.get("summary", {}),
            "grounded_claims": graph.get("grounded_claims", [])[:6],
            "weak_claims": graph.get("weak_claims", [])[:6],
            "next_grounding_actions": graph.get("next_grounding_actions", [])[:6],
        },
        "dossier": {
            "status": dossier.get("status"),
            "executive_summary": dossier.get("executive_summary"),
            "identity": dossier.get("identity", {}),
            "known": dossier.get("known", [])[:8],
            "uncertain": dossier.get("uncertain", [])[:8],
            "next_actions": dossier.get("next_actions", [])[:8],
            "confirmed_findings": dossier.get("confirmed_findings", [])[:8],
        },
    }


def _session_context(session: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(session, dict):
        return None
    latest = _latest_session_analysis(session)
    return {
        "session_id": session.get("session_id"),
        "title": session.get("title"),
        "route": session.get("route"),
        "status": session.get("status"),
        "device_hint": session.get("device_hint"),
        "latest_analysis_mode": latest.get("mode"),
        **_session_counts(session),
    }


def _overall_disposition(boards: List[Dict[str, Any]], readiness: Dict[str, Any]) -> str:
    level = str(readiness.get("level") or "")
    if level == "insufficient_evidence":
        return "insufficient_evidence"
    if readiness.get("blockers"):
        return "needs_review"
    dispositions = {str(row.get("disposition") or "") for row in boards}
    if "insufficient_evidence" in dispositions:
        return "insufficient_evidence"
    if "needs_review" in dispositions and level not in {"operator_workflow_ready", "calibrated_case"}:
        return "needs_review"
    return "actionable"


def _assemble_intelligence(
    *,
    boards: List[Dict[str, Any]],
    boards_raw: Optional[List[Dict[str, Any]]] = None,
    topology: Optional[Dict[str, Any]] = None,
    session: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    coverage = _evidence_coverage(boards, session)
    readiness = _readiness(boards, coverage, session)
    tasks = _next_evidence_tasks(boards, coverage, session)
    operator_summary = _operator_summary(boards, coverage, tasks, session)
    certainty = _certainty_ledger_from_readiness(coverage, readiness)
    artifacts = _session_artifacts(session)
    result = {
        "mode": "circuit_ai_board_intelligence",
        "overall_disposition": _overall_disposition(boards, readiness),
        "readiness": readiness,
        "evidence_coverage": coverage,
        "operator_summary": operator_summary,
        "next_evidence_tasks": tasks,
        "certainty_ledger": certainty,
        "board_count": len(boards),
        "boards": boards,
        "machine_topology": topology,
        "session_context": _session_context(session),
        "downstream_capabilities": assess_downstream_capabilities(),
    }
    functional_salvage = _functional_salvage_summary(boards)
    if functional_salvage:
        result["functional_salvage"] = functional_salvage
    reasoning_context = _board_reasoning_context(boards, functional_salvage, readiness, coverage, tasks)
    circuit_reasoning = CircuitAIReasoner(enable_llm=False).assess(
        {
            "goal": "reason about board function, reuse readiness, missing evidence, and safe downstream integration",
            "analysis": reasoning_context,
        }
    )
    result["circuit_reasoning"] = circuit_reasoning
    if circuit_reasoning.get("proof_summary"):
        result["circuit_proof"] = {
            "summary": circuit_reasoning.get("proof_summary") or {},
            "recommended_first_action": circuit_reasoning.get("recommended_first_action") or {},
            "top_candidates": (circuit_reasoning.get("proof_matrix") or [])[:5],
        }
    if boards_raw:
        result["machine_board_count"] = len(boards_raw)
    result.update(artifacts)
    return result


def assess_downstream_capabilities() -> Dict[str, Any]:
    root = _repo_root()
    mecha_root = Path(os.getenv("MECHA_SPLICER_ROOT") or root / "apps" / "mecha-splicer")
    splicer3d_root = root / "apps" / "3d-splicer"
    return {
        "mecha_splicer": {
            "status": "available" if (mecha_root / "src" / "mecha_splicer" / "runner.py").exists() else "missing",
            "role": "downstream mechanical packaging and OpenSCAD bundle generation",
            "root": str(mecha_root),
            "can_run_from_circuit_ai_bridge": (mecha_root / "src" / "mecha_splicer" / "runner.py").exists(),
            "current_limitations": [
                "Works best from structured machine/mechanism specs.",
                "Mechanical simulation is feasibility/DFM oriented, not certified FEA.",
            ],
        },
        "splicer3d": {
            "status": "available" if (splicer3d_root / "src" / "api" / "main.py").exists() else "missing",
            "role": "optional parametric enclosure/script/STL service",
            "root": str(splicer3d_root),
            "cadquery_installed": importlib.util.find_spec("cadquery") is not None,
            "current_limitations": [
                "True STL rendering requires CadQuery in the runtime.",
                "Without CadQuery, the useful path is script generation or fallback.",
            ],
        },
    }


def analyze_board_intelligence(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    session = payload.get("session") if isinstance(payload.get("session"), dict) else None
    boards_raw, boards, topology = _boards_from_payload(payload)
    if not boards:
        raise ValueError("payload must include board design paths, scan analysis, prior board intelligence, or session evidence")
    return _assemble_intelligence(boards=boards, boards_raw=boards_raw, topology=topology, session=session)


def analyze_board_session_intelligence(
    session: Dict[str, Any],
    *,
    design_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not isinstance(session, dict):
        raise ValueError("session must be an object")
    payload: Dict[str, Any] = {"session": session}
    if isinstance(design_payload, dict):
        payload.update(design_payload)
    boards_raw, boards, topology = _boards_from_payload(payload)
    if not boards:
        analysis = _latest_session_analysis(session)
        if analysis:
            boards.append(
                _visual_board_summary(
                    analysis,
                    board_id=str(session.get("session_id") or "session_board"),
                    board_name=str(session.get("title") or session.get("device_hint") or "Session board"),
                    source="session_latest_analysis",
                )
            )
    if not boards:
        boards.append(
            _visual_board_summary(
                {},
                board_id=str(session.get("session_id") or "session_board"),
                board_name=str(session.get("title") or session.get("device_hint") or "Session board"),
                source="session_without_analysis",
            )
        )
    return _assemble_intelligence(boards=boards, boards_raw=boards_raw, topology=topology, session=session)
