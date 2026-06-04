from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterable, List


MAX_BOARD_FILE_BYTES = int(os.getenv("HARDWARE_SPLICER_MAX_BOARD_FILE_BYTES", str(50 * 1024 * 1024)))


def _issue(severity: str, code: str, message: str, *, field: str = "") -> Dict[str, str]:
    row = {"severity": severity, "code": code, "message": message}
    if field:
        row["field"] = field
    return row


def _board_ids(machine: Dict[str, Any]) -> List[str]:
    ids: List[str] = []
    for board in machine.get("boards") or []:
        if isinstance(board, dict):
            ids.append(str(board.get("board_id") or "").strip())
    return ids


def _positive_number(value: Any) -> bool:
    try:
        return float(value) > 0
    except Exception:
        return False


def validate_compile_spec(spec: Any, *, check_files: bool = True) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    machine = spec.machine if isinstance(getattr(spec, "machine", None), dict) else {}
    boards = machine.get("boards")

    if not str(getattr(spec, "project_name", "") or "").strip():
        issues.append(_issue("error", "project_name_required", "project_name must not be blank.", field="project_name"))

    if not isinstance(boards, list) or not boards:
        issues.append(_issue("error", "boards_required", "machine.boards must contain at least one board.", field="machine.boards"))
        boards = []

    seen: set[str] = set()
    for index, board in enumerate(boards):
        if not isinstance(board, dict):
            issues.append(_issue("error", "board_object_required", "Each machine board must be an object.", field=f"machine.boards[{index}]"))
            continue
        board_id = str(board.get("board_id") or "").strip()
        if not board_id:
            issues.append(_issue("error", "board_id_required", "Each board must have a non-empty board_id.", field=f"machine.boards[{index}].board_id"))
        elif board_id in seen:
            issues.append(_issue("error", "duplicate_board_id", f"Duplicate board_id: {board_id}.", field=f"machine.boards[{index}].board_id"))
        seen.add(board_id)

        outline = board.get("pcb_outline_mm")
        if outline is not None:
            if not isinstance(outline, list) or len(outline) < 2 or not all(_positive_number(v) for v in outline[:2]):
                issues.append(
                    _issue(
                        "error",
                        "invalid_pcb_outline",
                        "pcb_outline_mm must contain positive width and height values.",
                        field=f"machine.boards[{index}].pcb_outline_mm",
                    )
                )

        capabilities = board.get("capabilities")
        if capabilities is not None and not isinstance(capabilities, dict):
            issues.append(
                _issue(
                    "error",
                    "invalid_capabilities",
                    "board.capabilities must be an object when present.",
                    field=f"machine.boards[{index}].capabilities",
                )
            )

        requirements = board.get("requirements")
        if requirements is None:
            issues.append(
                _issue(
                    "warning",
                    "requirements_missing",
                    f"Board {board_id or index} has no explicit requirements; downstream readiness may stay draft.",
                    field=f"machine.boards[{index}].requirements",
                )
            )
        elif not isinstance(requirements, dict):
            issues.append(
                _issue(
                    "error",
                    "invalid_requirements",
                    "board.requirements must be an object when present.",
                    field=f"machine.boards[{index}].requirements",
                )
            )

    valid_board_ids = {board_id for board_id in _board_ids(machine) if board_id}
    files = getattr(spec, "board_design_files", {}) or {}
    if not isinstance(files, dict):
        issues.append(_issue("error", "invalid_board_design_files", "board_design_files must be an object.", field="board_design_files"))
        files = {}

    for board_id, meta in files.items():
        field = f"board_design_files.{board_id}"
        if str(board_id) not in valid_board_ids:
            issues.append(_issue("error", "unknown_board_design_file", f"Board design file references unknown board_id: {board_id}.", field=field))
        if not isinstance(meta, dict):
            issues.append(_issue("error", "invalid_board_design_file", "Each board design file entry must be an object.", field=field))
            continue
        path_text = str(meta.get("path") or "").strip()
        kind = str(meta.get("kind") or "").strip().lower()
        if not path_text:
            issues.append(_issue("error", "board_design_path_required", "Board design file path must not be blank.", field=f"{field}.path"))
            continue
        if kind and kind not in {"netlist", "pcb"}:
            issues.append(_issue("error", "invalid_board_design_kind", "Board design file kind must be 'netlist' or 'pcb'.", field=f"{field}.kind"))
        if check_files:
            path = Path(path_text)
            if not path.exists():
                issues.append(_issue("error", "board_design_file_missing", f"Board design file does not exist: {path}.", field=f"{field}.path"))
            elif not path.is_file():
                issues.append(_issue("error", "board_design_file_not_file", f"Board design path is not a file: {path}.", field=f"{field}.path"))
            elif path.stat().st_size > MAX_BOARD_FILE_BYTES:
                issues.append(
                    _issue(
                        "error",
                        "board_design_file_too_large",
                        f"Board design file exceeds {MAX_BOARD_FILE_BYTES} bytes: {path}.",
                        field=f"{field}.path",
                    )
                )

    if bool(getattr(spec, "render_stl", False)) and not bool(getattr(spec, "use_3d_splicer", False)):
        issues.append(_issue("warning", "render_stl_without_3d", "render_stl is ignored when use_3d_splicer is false.", field="render_stl"))

    return issues


def validation_errors(issues: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    return [issue for issue in issues if str(issue.get("severity") or "").lower() == "error"]


def raise_for_validation_errors(issues: Iterable[Dict[str, str]]) -> None:
    errors = validation_errors(issues)
    if not errors:
        return
    summary = "; ".join(str(issue.get("message") or issue.get("code")) for issue in errors[:5])
    if len(errors) > 5:
        summary += f"; and {len(errors) - 5} more error(s)"
    raise ValueError(f"Hardware compile spec validation failed: {summary}")
