"""
Multi-board machine requirements compiler.

This module adds a first-class "machine" layer on top of existing single-board
requirements functions. It compiles multiple board specs, validates board-to-
board integration wiring, and emits artifacts that can drive EE+ME workflows.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .requirements_intake import (
    DESIGN_INTENTS,
    LANES,
    build_questions_and_assumptions,
    compile_to_circuit_ai_hints,
    evaluate_requirements,
    render_sow,
    run_lane_checks,
    template_for_lane,
)


_DEFAULT_INTERFACES = {
    "i2c": ["SCL", "SDA", "GND"],
    "spi": ["SCLK", "MOSI", "MISO", "CS", "GND"],
    "uart": ["TX", "RX", "GND"],
    "can": ["CANH", "CANL", "GND"],
    "usb2": ["D+", "D-", "VBUS", "GND"],
    "power": ["V+", "GND"],
    "gpio": ["SIG", "GND"],
}


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _normalize_board_requirements(
    board: Dict[str, Any], machine_name: str, machine_lane: str, machine_intent: str, idx: int
) -> Tuple[str, str, str, Dict[str, Any], Dict[str, Any]]:
    board_id = str(board.get("board_id") or f"board_{idx + 1}").strip()
    if not board_id:
        board_id = f"board_{idx + 1}"

    lane = str(board.get("lane") or machine_lane or "generic").strip() or "generic"
    if lane not in LANES:
        lane = "generic"
    design_intent = str(board.get("design_intent") or machine_intent or "prototype").strip() or "prototype"
    if design_intent not in DESIGN_INTENTS:
        design_intent = "prototype"

    req = board.get("requirements")
    if not isinstance(req, dict):
        req = template_for_lane(lane)
    else:
        req = dict(req)

    meta = req.get("meta")
    if not isinstance(meta, dict):
        meta = {}
        req["meta"] = meta
    meta["lane"] = lane
    meta["design_intent"] = design_intent
    if not str(meta.get("project_name") or "").strip():
        board_name = str(board.get("name") or board_id).strip() or board_id
        meta["project_name"] = f"{machine_name}::{board_name}"

    board_view = {
        "board_id": board_id,
        "name": str(board.get("name") or board_id),
        "role": str(board.get("role") or ""),
        "lane": lane,
        "design_intent": design_intent,
        "pcb_outline_mm": board.get("pcb_outline_mm"),
        "mounts": board.get("mounts") or [],
        "ports": board.get("ports") or [],
    }
    return board_id, lane, design_intent, req, board_view


def _build_harness_bom(interconnects: List[Dict[str, Any]]) -> str:
    lines = ["from_board,to_board,interface,connector,signal_count,length_cm,notes"]
    for c in interconnects:
        interface = str(c.get("interface") or "custom").strip().lower()
        signals = c.get("signals")
        signal_count = len(signals) if isinstance(signals, list) and signals else len(_DEFAULT_INTERFACES.get(interface, ["SIG", "GND"]))
        connector = str(c.get("connector") or ("JST-XH" if interface in ("i2c", "uart", "gpio", "power") else "custom")).strip()
        length_cm = int(_as_float(c.get("length_cm"), 20.0))
        notes = str(c.get("notes") or "")
        lines.append(
            f"\"{c.get('from_board','')}\",\"{c.get('to_board','')}\",\"{interface}\",\"{connector}\",{signal_count},{length_cm},\"{notes}\""
        )
    return "\n".join(lines) + "\n"


def _machine_readiness(board_levels: List[str], blockers: List[str]) -> str:
    if blockers:
        return "draft"
    if any(level == "draft" for level in board_levels):
        return "draft"
    if any(level == "reviewable" for level in board_levels):
        return "reviewable"
    return "ready"


def _to_mecha_anchor(board: Dict[str, Any]) -> Dict[str, Any] | None:
    outline = board.get("pcb_outline_mm")
    if not isinstance(outline, list) or len(outline) < 2:
        return None
    w = _as_float(outline[0], 0.0)
    h = _as_float(outline[1], 0.0)
    t = _as_float(outline[2], 1.6) if len(outline) >= 3 else 1.6
    if w <= 0.0 or h <= 0.0:
        return None
    return {
        "device": board.get("name") or board.get("board_id") or "board",
        "pcb_w_mm": w,
        "pcb_h_mm": h,
        "pcb_t_mm": t,
        "mounts": board.get("mounts") or [],
        "ports": board.get("ports") or [],
    }


def render_machine_sow(
    machine_name: str,
    board_reports: List[Dict[str, Any]],
    system_questions: List[str],
    system_risks: List[str],
) -> str:
    lines: List[str] = []
    lines.append(f"# System SOW — {machine_name}")
    lines.append("")
    lines.append("## Board Scope")
    for b in board_reports:
        quality = b.get("quality") or {}
        q = f"{quality.get('grade')}:{quality.get('score')}" if isinstance(quality, dict) else "n/a"
        lines.append(
            f"- `{b.get('board_id')}` ({b.get('lane')}/{b.get('design_intent')}): readiness `{b.get('readiness_level')}`, quality `{q}`."
        )
    lines.append("")
    lines.append("## System Open Questions")
    if system_questions:
        for q in system_questions:
            lines.append(f"- {q}")
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## System Risks")
    if system_risks:
        for r in system_risks:
            lines.append(f"- {r}")
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## Acceptance")
    lines.append("- Each board has explicit requirements + readiness + unresolved questions.")
    lines.append("- Inter-board interfaces are listed with connector and signal assumptions.")
    lines.append("- Mechanical enclosure anchors are generated for boards that provide outlines.")
    return "\n".join(lines).rstrip() + "\n"


def compile_machine_requirements(machine: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(machine, dict):
        raise ValueError("machine JSON object required")

    machine_name = str(machine.get("machine_name") or machine.get("name") or "machine").strip() or "machine"
    machine_lane = str(machine.get("lane") or "generic").strip() or "generic"
    if machine_lane not in LANES:
        machine_lane = "generic"
    machine_intent = str(machine.get("design_intent") or "prototype").strip() or "prototype"
    if machine_intent not in DESIGN_INTENTS:
        machine_intent = "prototype"

    raw_boards = machine.get("boards")
    if not isinstance(raw_boards, list) or not raw_boards:
        raise ValueError("boards[] is required (at least 1 board)")

    board_reports: List[Dict[str, Any]] = []
    board_ids: set[str] = set()
    machine_blockers: List[str] = []
    machine_questions: List[str] = []
    machine_risks: List[str] = []
    mecha_anchors: List[Dict[str, Any]] = []

    for idx, raw in enumerate(raw_boards):
        if not isinstance(raw, dict):
            machine_blockers.append(f"boards[{idx}] must be an object.")
            continue

        board_id, lane, design_intent, req, board_view = _normalize_board_requirements(
            raw, machine_name, machine_lane, machine_intent, idx
        )
        if board_id in board_ids:
            machine_blockers.append(f"Duplicate board_id: {board_id}")
            continue
        board_ids.add(board_id)

        readiness = evaluate_requirements(req)
        lane_checks = run_lane_checks(req)
        hints = compile_to_circuit_ai_hints(req)
        questions, assumptions, risks = build_questions_and_assumptions(req)
        sow_md = render_sow(req, questions, assumptions, risks)

        quality = (lane_checks.get("quality") or {}) if isinstance(lane_checks, dict) else {}
        board_report = {
            "board_id": board_id,
            "name": board_view["name"],
            "role": board_view["role"],
            "lane": lane,
            "design_intent": design_intent,
            "pcb_outline_mm": board_view["pcb_outline_mm"],
            "mounts": board_view["mounts"],
            "ports": board_view["ports"],
            "readiness_level": readiness.get("readiness_level"),
            "blockers": readiness.get("blockers") or [],
            "quality": quality,
            "questions": questions,
            "assumptions": assumptions,
            "risks": risks,
            "hints": hints,
            "sow_md": sow_md,
        }
        board_reports.append(board_report)
        machine_blockers.extend([f"{board_id}: {x}" for x in (board_report["blockers"] or [])])

        anchor = _to_mecha_anchor(raw)
        if anchor:
            mecha_anchors.append(anchor)

    interconnects = machine.get("interconnects")
    if not isinstance(interconnects, list):
        interconnects = []
    normalized_interconnects: List[Dict[str, Any]] = []
    for i, raw in enumerate(interconnects):
        if not isinstance(raw, dict):
            machine_blockers.append(f"interconnects[{i}] must be an object.")
            continue
        from_board = str(raw.get("from_board") or "").strip()
        to_board = str(raw.get("to_board") or "").strip()
        if from_board not in board_ids or to_board not in board_ids:
            machine_blockers.append(f"interconnects[{i}] references unknown board(s): {from_board} -> {to_board}")
            continue
        interface = str(raw.get("interface") or "custom").strip().lower()
        from_v = raw.get("from_voltage_v")
        to_v = raw.get("to_voltage_v")
        if from_v is not None and to_v is not None and abs(_as_float(from_v, 0.0) - _as_float(to_v, 0.0)) > 0.35:
            machine_risks.append(
                f"Voltage mismatch on {from_board}->{to_board} ({interface}): {from_v}V vs {to_v}V. Add level-shifting/isolation."
            )
        normalized_interconnects.append(
            {
                "from_board": from_board,
                "to_board": to_board,
                "interface": interface,
                "signals": raw.get("signals") if isinstance(raw.get("signals"), list) else [],
                "connector": raw.get("connector") or "",
                "length_cm": _as_float(raw.get("length_cm"), 20.0),
                "notes": raw.get("notes") or "",
            }
        )

    if not normalized_interconnects and len(board_reports) > 1:
        machine_questions.append("Define interconnects[] between boards (protocol, connector, and length).")

    power_tree = machine.get("power_tree")
    if not isinstance(power_tree, list):
        power_tree = []
    normalized_power: List[Dict[str, Any]] = []
    for i, raw in enumerate(power_tree):
        if not isinstance(raw, dict):
            machine_blockers.append(f"power_tree[{i}] must be an object.")
            continue
        board_id = str(raw.get("board_id") or "").strip()
        if board_id and board_id not in board_ids:
            machine_blockers.append(f"power_tree[{i}] references unknown board_id: {board_id}")
            continue
        normalized_power.append(
            {
                "source": str(raw.get("source") or ""),
                "board_id": board_id,
                "rail": str(raw.get("rail") or ""),
                "voltage_v": raw.get("voltage_v"),
                "max_current_a": raw.get("max_current_a"),
                "notes": str(raw.get("notes") or ""),
            }
        )
    if not normalized_power:
        machine_questions.append("Provide power_tree[] so total system current and connector ratings can be verified.")

    board_levels = [str(b.get("readiness_level") or "draft") for b in board_reports]
    system_readiness = _machine_readiness(board_levels, machine_blockers)

    board_hint_map = [{"board_id": b.get("board_id"), "hints": b.get("hints")} for b in board_reports]
    system_hints = {
        "machine_name": machine_name,
        "boards": board_hint_map,
        "interconnects": normalized_interconnects,
        "power_tree": normalized_power,
        "mecha_electronics_anchors": mecha_anchors,
    }
    machine_sow_md = render_machine_sow(machine_name, board_reports, machine_questions, machine_risks)

    return {
        "machine": {
            "machine_name": machine_name,
            "lane": machine_lane,
            "design_intent": machine_intent,
            "board_count": len(board_reports),
            "interconnect_count": len(normalized_interconnects),
            "readiness_level": system_readiness,
            "blockers": machine_blockers,
        },
        "boards": board_reports,
        "system": {
            "questions": machine_questions,
            "risks": machine_risks,
            "interconnects": normalized_interconnects,
            "power_tree": normalized_power,
            "harness_bom_csv": _build_harness_bom(normalized_interconnects),
            "mecha_electronics_anchors": mecha_anchors,
            "sow_md": machine_sow_md,
        },
        "hints": system_hints,
    }
