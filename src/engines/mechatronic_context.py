from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .layout_advisor import find_mounting_holes, summarize_board
from .prototype3d_generator import build_prototype3d_artifacts
from .system_structure_extractor import extract_board_structure, synthesize_machine_topology


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _board_file_map(machine: Dict[str, Any], board_design_files: Optional[Dict[str, Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if isinstance(board_design_files, dict):
        for board_id, meta in board_design_files.items():
            if not isinstance(meta, dict):
                continue
            path = str(meta.get("path") or "").strip()
            kind = str(meta.get("kind") or "").strip().lower()
            if not path:
                continue
            if kind not in ("netlist", "pcb"):
                kind = "netlist" if path.lower().endswith(".net") else "pcb"
            out[str(board_id)] = {"path": path, "kind": kind}
    for row in machine.get("boards") or []:
        if not isinstance(row, dict):
            continue
        board_id = str(row.get("board_id") or "").strip()
        if not board_id or board_id in out:
            continue
        net_path = str(row.get("netlist_path") or "").strip()
        pcb_path = str(row.get("pcb_path") or "").strip()
        if net_path:
            out[board_id] = {"path": net_path, "kind": "netlist"}
        elif pcb_path:
            out[board_id] = {"path": pcb_path, "kind": "pcb"}
    return out


def _normalize_mounts(mounts: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not isinstance(mounts, list):
        return rows
    for mount in mounts:
        if not isinstance(mount, dict):
            continue
        x = mount.get("x_mm", mount.get("x"))
        y = mount.get("y_mm", mount.get("y"))
        if x is None or y is None:
            continue
        rows.append(
            {
                "x_mm": round(_as_float(x), 3),
                "y_mm": round(_as_float(y), 3),
                "d_mm": round(_as_float(mount.get("d_mm", mount.get("diameter_mm", mount.get("diameter", 2.2))), 2.2), 3),
            }
        )
    return rows


def _normalize_existing_ports(ports: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not isinstance(ports, list):
        return rows
    for port in ports:
        if not isinstance(port, dict):
            continue
        kind = str(port.get("kind") or "rect").strip().lower()
        if kind == "circle":
            circle = port.get("circle")
            if not isinstance(circle, dict):
                circle = {
                    "x_mm": port.get("x_mm", 0.0),
                    "y_mm": port.get("y_mm", 0.0),
                    "d_mm": port.get("d_mm", port.get("diameter_mm", 4.0)),
                }
            rows.append(
                {
                    "kind": "circle",
                    "circle": {
                        "x_mm": round(_as_float(circle.get("x_mm")), 3),
                        "y_mm": round(_as_float(circle.get("y_mm")), 3),
                        "d_mm": round(max(_as_float(circle.get("d_mm"), 4.0), 1.0), 3),
                    },
                    "label": str(port.get("label") or port.get("name") or "port"),
                    "face": str(port.get("face") or "front"),
                }
            )
            continue
        rect = port.get("rect")
        if not isinstance(rect, dict):
            rect = {
                "x_mm": port.get("x_mm", 0.0),
                "y_mm": port.get("y_mm", 0.0),
                "w_mm": port.get("w_mm", port.get("width_mm", 8.0)),
                "h_mm": port.get("h_mm", port.get("height_mm", 4.0)),
            }
        rows.append(
            {
                "kind": "rect",
                "rect": {
                    "x_mm": round(_as_float(rect.get("x_mm")), 3),
                    "y_mm": round(_as_float(rect.get("y_mm")), 3),
                    "w_mm": round(max(_as_float(rect.get("w_mm"), 8.0), 1.0), 3),
                    "h_mm": round(max(_as_float(rect.get("h_mm"), 4.0), 1.0), 3),
                },
                "label": str(port.get("label") or port.get("name") or "port"),
                "face": str(port.get("face") or "front"),
            }
        )
    return rows


def _connector_port_dims(connector: Dict[str, Any]) -> tuple[float, float]:
    value = str(connector.get("value") or "").upper()
    footprint = str(connector.get("footprint") or "").upper()
    interfaces = {str(row.get("interface") or "").lower() for row in (connector.get("interfaces") or []) if isinstance(row, dict)}
    pin_count = max(len(connector.get("pin_nets") or {}), 1)
    if "USB" in value or "USB" in footprint or "usb2" in interfaces:
        return 10.5, 4.5
    if "RJ45" in value or "RJ45" in footprint:
        return 16.0, 14.0
    if "TERMINAL" in value or "TERMINAL" in footprint or "power" in interfaces:
        return min(18.0, 4.0 + 2.2 * pin_count), 6.0
    return min(20.0, 4.0 + 1.9 * pin_count), 4.5


def _ports_from_connectors(connectors: List[Dict[str, Any]], board_w_mm: float, board_h_mm: float) -> List[Dict[str, Any]]:
    if not connectors:
        return []
    sorted_connectors = sorted((connector for connector in connectors if isinstance(connector, dict)), key=lambda row: str(row.get("ref") or ""))
    if not sorted_connectors:
        return []
    usable_span = max(board_w_mm - 12.0, 8.0)
    n = len(sorted_connectors)
    x_positions = [0.0] if n == 1 else [(-usable_span / 2.0) + (usable_span * idx / max(n - 1, 1)) for idx in range(n)]
    y_edge = -max(board_h_mm / 2.0 - 2.5, 0.0)

    rows: List[Dict[str, Any]] = []
    for index, connector in enumerate(sorted_connectors):
        width_mm, height_mm = _connector_port_dims(connector)
        interface_labels = [str(row.get("interface") or "").upper() for row in (connector.get("interfaces") or []) if row.get("interface")]
        label_bits = [str(connector.get("ref") or "PORT")]
        if interface_labels:
            label_bits.append("/".join(interface_labels[:2]))
        rows.append(
            {
                "kind": "rect",
                "rect": {
                    "x_mm": round(x_positions[index], 3),
                    "y_mm": round(y_edge, 3),
                    "w_mm": round(width_mm, 3),
                    "h_mm": round(height_mm, 3),
                },
                "label": " ".join(label_bits),
                "face": "front",
            }
        )
    return rows


def _board_outline(board: Dict[str, Any], board_summary: Dict[str, Any]) -> List[float]:
    outline = board.get("pcb_outline_mm")
    if isinstance(outline, list) and len(outline) >= 2:
        return [
            max(_as_float(outline[0], 50.0), 5.0),
            max(_as_float(outline[1], 40.0), 5.0),
            max(_as_float(outline[2], 1.6), 0.4) if len(outline) >= 3 else 1.6,
        ]
    width_mm = max(_as_float(board_summary.get("width_mm"), 50.0), 5.0)
    height_mm = max(_as_float(board_summary.get("height_mm"), 40.0), 5.0)
    return [width_mm, height_mm, 1.6]


def _infer_geometry(board: Dict[str, Any], design_meta: Dict[str, Any]) -> Dict[str, Any]:
    board_summary: Dict[str, Any] = {}
    mounting_holes: List[Dict[str, Any]] = []
    path = str(design_meta.get("path") or "").strip()
    kind = str(design_meta.get("kind") or "").strip().lower()
    if path and kind == "pcb":
        pcb_path = Path(path)
        if pcb_path.exists():
            try:
                board_summary = (summarize_board(pcb_path) or {}).get("board") or {}
            except Exception:
                board_summary = {}
            try:
                mounting_holes = find_mounting_holes(pcb_path)
            except Exception:
                mounting_holes = []
    outline_mm = _board_outline(board, board_summary)
    if not mounting_holes:
        mounting_holes = _normalize_mounts(board.get("mounts"))
    return {
        "outline_mm": outline_mm,
        "board_summary": board_summary,
        "mounting_holes": mounting_holes,
    }


def _safe_extract_structure(board: Dict[str, Any], design_meta: Dict[str, Any]) -> Dict[str, Any]:
    path = str(design_meta.get("path") or "").strip()
    kind = str(design_meta.get("kind") or "").strip().lower()
    if not path or kind not in ("pcb", "netlist"):
        return {}
    design_path = Path(path)
    if not design_path.exists():
        return {"error": "design_file_not_found"}
    try:
        return extract_board_structure(
            str(design_path),
            board_id=str(board.get("board_id") or design_path.stem),
            board_name=str(board.get("name") or board.get("board_id") or design_path.stem),
            kind=kind,
        )
    except Exception as exc:
        return {"error": str(exc)}


def _safe_prototype3d(board: Dict[str, Any], design_meta: Dict[str, Any]) -> Dict[str, Any]:
    path = str(design_meta.get("path") or "").strip()
    kind = str(design_meta.get("kind") or "").strip().lower()
    if not path or kind != "pcb":
        return {}
    pcb_path = Path(path)
    if not pcb_path.exists():
        return {}
    try:
        return build_prototype3d_artifacts(pcb_path, requirements=board.get("requirements") if isinstance(board.get("requirements"), dict) else None)
    except Exception as exc:
        return {"error": str(exc)}


def _build_electronics_anchor(board: Dict[str, Any], geometry: Dict[str, Any], structure: Dict[str, Any]) -> Dict[str, Any]:
    outline = geometry.get("outline_mm") or [50.0, 40.0, 1.6]
    board_w_mm = max(_as_float(outline[0], 50.0), 5.0)
    board_h_mm = max(_as_float(outline[1], 40.0), 5.0)
    board_t_mm = max(_as_float(outline[2], 1.6), 0.4)
    mounts = geometry.get("mounting_holes") or _normalize_mounts(board.get("mounts"))
    ports = _normalize_existing_ports(board.get("ports"))
    if not ports:
        ports = _ports_from_connectors(structure.get("connectors") or [], board_w_mm, board_h_mm)
    return {
        "device": str(board.get("name") or board.get("board_id") or "board"),
        "pcb_w_mm": round(board_w_mm, 3),
        "pcb_h_mm": round(board_h_mm, 3),
        "pcb_t_mm": round(board_t_mm, 3),
        "mounts": mounts,
        "ports": ports,
    }


def _primary_anchor_score(board_context: Dict[str, Any]) -> float:
    score = 0.0
    structure = board_context.get("structure") or {}
    role = str(structure.get("primary_role") or "")
    if role == "controller":
        score += 5.0
    elif role == "power_board":
        score += 4.0
    elif role == "motor_control":
        score += 4.0
    runtime = structure.get("controller_runtime") or {}
    score += 1.5 * len(runtime.get("controllers") or [])
    score += 0.3 * len(runtime.get("programming_paths") or [])
    if board_context.get("prototype3d"):
        score += 1.0
    anchor = board_context.get("electronics_anchor") or {}
    area = _as_float(anchor.get("pcb_w_mm"), 0.0) * _as_float(anchor.get("pcb_h_mm"), 0.0)
    score += min(area / 2500.0, 2.5)
    return score


def build_mechatronic_context(machine: Dict[str, Any], board_design_files: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    machine_name = str(machine.get("machine_name") or machine.get("name") or "machine").strip() or "machine"
    design_map = _board_file_map(machine, board_design_files)
    board_contexts: List[Dict[str, Any]] = []
    extracted_structures: List[Dict[str, Any]] = []
    questions: List[str] = []

    for board in machine.get("boards") or []:
        if not isinstance(board, dict):
            continue
        board_id = str(board.get("board_id") or "").strip()
        if not board_id:
            continue
        design_meta = dict(design_map.get(board_id) or {})
        geometry = _infer_geometry(board, design_meta)
        structure = _safe_extract_structure(board, design_meta)
        if structure and not structure.get("error"):
            extracted_structures.append(structure)
            questions.extend(structure.get("questions") or [])
        prototype3d = _safe_prototype3d(board, design_meta)
        electronics_anchor = _build_electronics_anchor(board, geometry, structure if isinstance(structure, dict) else {})
        board_contexts.append(
            {
                "board_id": board_id,
                "board_name": str(board.get("name") or board_id),
                "design_source": design_meta,
                "geometry": geometry,
                "structure": structure,
                "controller_runtime": (structure.get("controller_runtime") or {}) if isinstance(structure, dict) else {},
                "bring_up_plan": (structure.get("bring_up_plan") or []) if isinstance(structure, dict) else [],
                "electronics_anchor": electronics_anchor,
                "prototype3d": prototype3d,
            }
        )

    topology: Dict[str, Any] = {}
    if extracted_structures:
        topology = synthesize_machine_topology(extracted_structures, machine_name=machine_name)
        questions.extend(topology.get("questions") or [])

    primary_board = None
    if board_contexts:
        primary_board = max(board_contexts, key=_primary_anchor_score)

    return {
        "machine_name": machine_name,
        "board_count": len(board_contexts),
        "boards": board_contexts,
        "primary_board_id": primary_board.get("board_id") if isinstance(primary_board, dict) else None,
        "primary_electronics_anchor": (primary_board.get("electronics_anchor") if isinstance(primary_board, dict) else None) or {},
        "electronics_bundle": [row.get("electronics_anchor") or {} for row in board_contexts if isinstance(row.get("electronics_anchor"), dict)],
        "machine_topology": topology,
        "machine_bring_up_sequence": topology.get("machine_bring_up_sequence") if isinstance(topology, dict) else [],
        "questions": sorted(dict.fromkeys(question for question in questions if question)),
    }
