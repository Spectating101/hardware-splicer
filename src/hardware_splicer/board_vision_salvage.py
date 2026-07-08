"""Donor board vision → functional_salvage.v1 for splice intake (no static fixture required)."""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Sequence, Tuple

SCHEMA_VERSION = "hardware_splicer.donor_board_vision_report.v1"
FUNCTIONAL_SALVAGE_SCHEMA = "functional_salvage.v1"
BOARD_EVIDENCE_SCHEMA = "board_evidence.v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
CIRCUIT_AI_ROOT = REPO_ROOT / "apps" / "circuit-ai"

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic"}


def _slug(text: str, *, limit: int = 48) -> str:
    safe = re.sub(r"[^a-z0-9]+", "_", str(text or "").lower()).strip("_")
    return (safe[:limit] or "block")


def _dedupe_strings(items: Sequence[str]) -> List[str]:
    kept: List[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        kept.append(text)
    return kept


def _gate_type_from_prompt(prompt: str) -> str:
    text = prompt.lower()
    if "continuity" in text or "short" in text:
        return "continuity"
    if "current" in text:
        return "current"
    if "thermal" in text or "temperature" in text:
        return "thermal"
    if "polarity" in text:
        return "polarity"
    return "voltage"


def _capabilities_for_item(label: str, kind: str) -> Tuple[str, List[str], str]:
    text = f"{label} {kind}".lower()
    if any(token in text for token in ("h-bridge", "hbridge", "motor driver", "motor_driver", "tb6612", "l298")):
        return (
            "actuator_driver",
            ["actuator_driver", "motor_or_load", "connector"],
            "connector_reuse",
        )
    if any(token in text for token in ("motor", "gearbox", "wheel")):
        return (
            "mechanical_motion",
            ["motor_or_load", "wheel_or_drive", "connector"],
            "connector_reuse",
        )
    if any(token in text for token in ("stepper", "a4988", "tmc", "drv")):
        return (
            "actuator_driver",
            ["actuator_driver", "motor_or_load", "connector"],
            "connector_reuse",
        )
    if any(token in text for token in ("regulator", "buck", "boost", "ldo", "power")):
        return (
            "power_regulation",
            ["power", "connector"],
            "board_section_cut_candidate",
        )
    if any(token in text for token in ("esp32", "esp8266", "mcu", "microcontroller", "arduino", "stm32")):
        return (
            "controller_core",
            ["controller", "connector"],
            "whole_board_reuse",
        )
    if any(token in text for token in ("usb", "uart", "serial", "ch340", "cp210")):
        return (
            "usb_serial_bridge",
            ["usb_serial", "connector"],
            "whole_board_reuse",
        )
    if any(token in kind for token in ("connector", "header", "port", "socket", "terminal")):
        return ("connector_harness", ["connector"], "connector_reuse")
    return ("unknown_function", ["connector"], "connector_reuse")


def _string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _rows(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _gates_from_prompts(prompts: Sequence[str], *, prefix: str) -> List[Dict[str, Any]]:
    gates: List[Dict[str, Any]] = []
    for index, prompt in enumerate(prompts):
        text = str(prompt).strip()
        if not text:
            continue
        gates.append(
            {
                "gate_id": f"{prefix}_{index + 1}",
                "gate_type": _gate_type_from_prompt(text),
                "prompt": text,
                "status": "open",
            }
        )
    return gates


def _item_to_block(
    item: Mapping[str, Any],
    *,
    board_id: str,
    index: int,
    default_kind: str,
) -> Dict[str, Any]:
    label = str(
        item.get("label")
        or item.get("name")
        or item.get("function")
        or item.get("kind")
        or f"vision_block_{index}"
    ).strip()
    kind = str(item.get("kind") or item.get("type") or default_kind).strip()
    function_type, capabilities, extract_class = _capabilities_for_item(label, kind)
    connector_refs = _string_list(item.get("connector_refs") or item.get("connectors"))
    if not connector_refs and kind in {"connector", "header", "port"}:
        connector_refs = [label]
    missing = _dedupe_strings(
        [
            *_string_list(item.get("missing_evidence")),
            *_string_list(item.get("recommended_checks")),
            *_string_list(item.get("required_tests")),
            *_string_list(item.get("warnings")),
        ]
    )
    if function_type == "actuator_driver" and not missing:
        missing = [
            f"Measure primary supply rail for {label} before interconnect",
            f"Confirm {label} outputs are not shorted to ground",
        ]
    gates = _gates_from_prompts(missing, prefix=f"vision_{_slug(label)}")
    block_id = f"{board_id}_{_slug(label)}"
    return {
        "block_id": block_id,
        "board_id": board_id,
        "name": label,
        "function_type": function_type,
        "capabilities": capabilities,
        "source": "board_vision",
        "source_refs": _dedupe_strings(_string_list(item.get("source_refs") or item.get("id") or label)),
        "connector_refs": connector_refs,
        "confidence": float(item.get("confidence") or 0.65),
        "extractability": {
            "class": extract_class,
            "action": "Reuse after vision-identified function is confirmed with bench measurements.",
            "requires_layout_confirmation": extract_class == "board_section_cut_candidate",
        },
        "status": "reuse_candidate",
        "reuse_value_score": round(min(0.9, max(0.45, float(item.get("confidence") or 0.65))), 2),
        "suggested_uses": _string_list(item.get("suggested_uses")) or ["salvage splice block"],
        "rationale": str(item.get("notes") or item.get("rationale") or "Derived from donor board photo evidence (candidate)."),
        "evidence_gates": gates,
        "missing_evidence": missing,
    }


def board_evidence_to_functional_salvage(
    board_evidence: Mapping[str, Any],
    *,
    board_id: str,
    board_name: str = "",
    goal: str = "",
    source_artifact: str = "",
) -> Dict[str, Any]:
    """Convert board_evidence.v1 into functional_salvage.v1 for splice planning."""
    evidence = dict(board_evidence)
    blocks: List[Dict[str, Any]] = []
    index = 0
    for row in _rows(evidence.get("salvage_candidates")):
        blocks.append(_item_to_block(row, board_id=board_id, index=index, default_kind="salvage_candidate"))
        index += 1
    for row in _rows(evidence.get("connectors")):
        blocks.append(_item_to_block(row, board_id=board_id, index=index, default_kind="connector"))
        index += 1
    for row in _rows(evidence.get("components")):
        blocks.append(_item_to_block(row, board_id=board_id, index=index, default_kind="component"))
        index += 1

    top_gates = _gates_from_prompts(_string_list(evidence.get("recommended_checks")), prefix=f"vision_{_slug(board_id)}")
    for block in blocks:
        for gate in block.get("evidence_gates") or []:
            gate_id = str(gate.get("gate_id") or "")
            if gate_id and not any(str(row.get("gate_id")) == gate_id for row in top_gates):
                top_gates.append(gate)

    extractability_summary: Dict[str, int] = {}
    for block in blocks:
        extract_class = str((block.get("extractability") or {}).get("class") or "unknown")
        extractability_summary[extract_class] = extractability_summary.get(extract_class, 0) + 1

    return {
        "schema_version": FUNCTIONAL_SALVAGE_SCHEMA,
        "mode": "functional_salvage_assessment",
        "board_id": board_id,
        "board_name": board_name or board_id,
        "verdict": "ready_after_measurements",
        "source": "board_vision",
        "source_artifact": source_artifact,
        "goal": goal,
        "reusable_blocks": blocks,
        "evidence_gates": top_gates,
        "extractability_summary": extractability_summary,
        "safety_policy": {
            "reuse_ready_requires": [
                "bench measurements attached",
                "vision-derived blocks treated as candidates until gates close",
            ],
            "default_for_unknowns": "blocked_until_evidence",
        },
    }


def _vision_config(intake: Mapping[str, Any]) -> Dict[str, Any]:
    top = intake.get("donor_board_vision") if isinstance(intake.get("donor_board_vision"), dict) else {}
    assist = intake.get("vision_assistance") if isinstance(intake.get("vision_assistance"), dict) else {}
    enabled = bool(top.get("enabled", assist.get("enabled", False)))
    if intake.get("attachments") or _donor_board_rows(intake):
        enabled = bool(top.get("enabled", assist.get("enabled", True)))
    return {
        "enabled": enabled,
        "live": bool(top.get("live", assist.get("live", False))),
        "merge_with_fixture": bool(top.get("merge_with_fixture", True)),
        "provider": str(top.get("provider") or assist.get("provider") or "qwen"),
        "device_hint": str(top.get("device_hint") or ""),
    }


def _donor_board_rows(intake: Mapping[str, Any]) -> List[Dict[str, Any]]:
    circuit = intake.get("circuit") if isinstance(intake.get("circuit"), dict) else {}
    boards = [row for row in (circuit.get("boards") or []) if isinstance(row, dict)]
    return boards


def _resolve_image_path(path_text: str, *, base_dir: Path | None) -> Path | None:
    raw = str(path_text or "").strip()
    if not raw:
        return None
    candidate = Path(raw)
    if not candidate.is_absolute() and base_dir is not None:
        candidate = (base_dir / candidate).resolve()
    elif not candidate.is_absolute():
        candidate = (REPO_ROOT / candidate).resolve()
    if candidate.is_file() and candidate.suffix.lower() in _IMAGE_EXTENSIONS:
        return candidate
    return None


def _inline_image_payload(source: Mapping[str, Any]) -> tuple[bytes, str] | None:
    data_b64 = str(source.get("image_base64") or source.get("data_base64") or "").strip()
    url = str(source.get("url") or source.get("data_url") or "").strip()
    if url.startswith("data:image/"):
        _, _, data_b64 = url.partition(",")
    if not data_b64:
        return None
    try:
        raw = base64.b64decode(data_b64, validate=False)
    except (ValueError, binascii.Error):
        return None
    if not raw:
        return None
    filename = str(source.get("filename") or source.get("name") or "donor_board.jpg")
    return raw, filename


def _materialize_inline_image(source: Mapping[str, Any]) -> Path | None:
    payload = _inline_image_payload(source)
    if payload is None:
        return None
    raw, filename = payload
    suffix = Path(filename).suffix.lower()
    if suffix not in _IMAGE_EXTENSIONS:
        suffix = ".jpg"
    fd, path_str = tempfile.mkstemp(suffix=suffix, prefix="hs_donor_")
    try:
        os.write(fd, raw)
    finally:
        os.close(fd)
    return Path(path_str)


def _donor_attachment_paths(intake: Mapping[str, Any], board_id: str) -> List[Path]:
    base_dir = Path(str(intake.get("source_file") or "")).parent if intake.get("source_file") else REPO_ROOT
    paths: List[Path] = []
    for attachment in intake.get("attachments") or []:
        if not isinstance(attachment, dict):
            continue
        kind = str(attachment.get("kind") or attachment.get("type") or "").lower()
        if kind not in {"image", "photo", "board_photo", "donor_board"}:
            continue
        board_ref = str(attachment.get("board_id") or attachment.get("donor_board_id") or "").strip()
        if board_ref and board_ref != board_id:
            continue
        inline = _materialize_inline_image(attachment)
        if inline is not None:
            paths.append(inline)
            continue
        resolved = _resolve_image_path(str(attachment.get("path") or attachment.get("file") or ""), base_dir=base_dir)
        if resolved is not None:
            paths.append(resolved)
    return paths


def _analyze_board_image_path(
    image_path: Path,
    *,
    goal: str,
    live: bool,
    device_hint: str,
    symptoms: Sequence[str] = (),
) -> Dict[str, Any]:
    if not CIRCUIT_AI_ROOT.is_dir():
        return {"ok": False, "error": "circuit_ai_app_not_found", "path": str(image_path)}
    import sys

    root_str = str(CIRCUIT_AI_ROOT)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    try:
        from src.vision.qwen_board_vision import analyze_board_image_with_qwen
    except ImportError as exc:
        return {"ok": False, "error": f"qwen_board_vision_import_failed: {exc}", "path": str(image_path)}

    image_bytes = image_path.read_bytes()
    result = analyze_board_image_with_qwen(
        image_bytes,
        filename=image_path.name,
        goal=goal,
        device_hint=device_hint,
        symptoms=symptoms,
        live=live,
    )
    result["ok"] = bool(result.get("board_evidence"))
    result["image_path"] = str(image_path)
    return result


def _merge_functional_salvage(
    existing: Mapping[str, Any] | None,
    generated: Mapping[str, Any],
    *,
    merge_with_fixture: bool,
) -> Dict[str, Any]:
    if not existing or not merge_with_fixture:
        return dict(generated)
    merged = dict(existing)
    old_blocks = list(merged.get("reusable_blocks") or [])
    new_blocks = list(generated.get("reusable_blocks") or [])
    seen = {str(row.get("block_id") or "") for row in old_blocks}
    for row in new_blocks:
        block_id = str(row.get("block_id") or "")
        if block_id and block_id in seen:
            continue
        old_blocks.append(row)
        if block_id:
            seen.add(block_id)
    merged["reusable_blocks"] = old_blocks
    old_gates = list(merged.get("evidence_gates") or [])
    new_gates = list(generated.get("evidence_gates") or [])
    gate_seen = {str(row.get("gate_id") or "") for row in old_gates}
    for row in new_gates:
        gate_id = str(row.get("gate_id") or "")
        if gate_id and gate_id in gate_seen:
            continue
        old_gates.append(row)
        if gate_id:
            gate_seen.add(gate_id)
    merged["evidence_gates"] = old_gates
    merged["vision_augmented"] = True
    merged["vision_source"] = generated.get("source")
    return merged


def _resolve_refs(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("@"):
        rel = value[1:].lstrip("/")
        path = (REPO_ROOT / rel).resolve()
        if not path.is_file():
            raise ValueError(f"board vision fixture not found: {value} -> {path}")
        return _resolve_refs(json.loads(path.read_text(encoding="utf-8")))
    if isinstance(value, list):
        return [_resolve_refs(item) for item in value]
    if isinstance(value, dict):
        return {key: _resolve_refs(item) for key, item in value.items()}
    return value


def _board_vision_row(
    board: Mapping[str, Any],
    intake: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    goal: str,
) -> Dict[str, Any]:
    board_id = str(board.get("board_id") or board.get("id") or "donor_board")
    board_name = str(board.get("board_name") or board.get("name") or board_id)
    source_artifact = ""

    if isinstance(board.get("board_evidence"), dict):
        evidence = _resolve_refs(board["board_evidence"])
        source_artifact = "intake.board_evidence"
        functional = board_evidence_to_functional_salvage(
            evidence,
            board_id=board_id,
            board_name=board_name,
            goal=goal,
            source_artifact=source_artifact,
        )
        return {
            "board_id": board_id,
            "mode": "embedded_board_evidence",
            "ok": True,
            "source_artifact": source_artifact,
            "board_evidence": evidence,
            "functional_salvage": functional,
        }

    image_path: Path | None = None
    vision_source = board.get("vision_source") if isinstance(board.get("vision_source"), dict) else {}
    if vision_source:
        image_path = _materialize_inline_image(vision_source)
        if image_path is not None:
            source_artifact = str(vision_source.get("filename") or vision_source.get("name") or "inline_upload")
    if image_path is None and vision_source.get("path"):
        base_dir = Path(str(intake.get("source_file") or "")).parent if intake.get("source_file") else REPO_ROOT
        image_path = _resolve_image_path(str(vision_source["path"]), base_dir=base_dir)
        source_artifact = str(vision_source.get("path") or "")
    if image_path is None:
        attachments = _donor_attachment_paths(intake, board_id)
        if attachments:
            image_path = attachments[0]
            source_artifact = str(image_path)

    if image_path is None:
        return {"board_id": board_id, "mode": "skipped", "ok": False, "reason": "no_donor_board_image"}

    live = bool(vision_source.get("live", config.get("live")))
    repair_ctx = intake.get("repair_intake_context") if isinstance(intake.get("repair_intake_context"), dict) else {}
    symptoms = _dedupe_strings(
        [
            *_string_list(vision_source.get("symptoms")),
            *_string_list(config.get("symptoms")),
            *_string_list(repair_ctx.get("symptoms")),
        ]
    )
    device_hint = str(
        vision_source.get("device_hint")
        or config.get("device_hint")
        or repair_ctx.get("device_hint")
        or ""
    )
    analysis = _analyze_board_image_path(
        image_path,
        goal=goal,
        live=live,
        device_hint=device_hint,
        symptoms=symptoms,
    )
    evidence = analysis.get("board_evidence") if isinstance(analysis.get("board_evidence"), dict) else {}
    if not evidence:
        return {
            "board_id": board_id,
            "mode": analysis.get("mode") or "analyze_failed",
            "ok": False,
            "source_artifact": source_artifact,
            "analysis": analysis,
        }
    functional = board_evidence_to_functional_salvage(
        evidence,
        board_id=board_id,
        board_name=board_name,
        goal=goal,
        source_artifact=source_artifact,
    )
    return {
        "board_id": board_id,
        "mode": analysis.get("mode") or "analyzed",
        "ok": True,
        "source_artifact": source_artifact,
        "board_evidence": evidence,
        "functional_salvage": functional,
        "analysis": analysis,
    }


def enrich_intake_with_donor_board_vision(intake: Mapping[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Attach vision-derived functional_salvage to donor boards when photos or board_evidence are present."""
    body: Dict[str, Any] = dict(intake)
    config = _vision_config(body)
    goal = str(body.get("goal") or body.get("intent") or "").strip()
    boards = _donor_board_rows(body)
    report: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "enabled": config["enabled"],
        "live": config["live"],
        "merge_with_fixture": config["merge_with_fixture"],
        "boards": [],
        "applied_board_count": 0,
    }

    if not config["enabled"] or not boards:
        report["skipped"] = True
        report["reason"] = "disabled_or_no_circuit_boards"
        return body, report

    circuit = dict(body.get("circuit") or {})
    updated_boards: List[Dict[str, Any]] = []
    for board in boards:
        row = dict(board)
        if not (
            isinstance(row.get("board_evidence"), dict)
            or isinstance(row.get("vision_source"), dict)
            or _donor_attachment_paths(body, str(row.get("board_id") or ""))
        ):
            updated_boards.append(row)
            continue
        vision_row = _board_vision_row(row, body, config, goal=goal)
        report["boards"].append(vision_row)
        if not vision_row.get("ok"):
            updated_boards.append(row)
            continue
        generated = vision_row.get("functional_salvage") if isinstance(vision_row.get("functional_salvage"), dict) else {}
        existing = row.get("functional_salvage") if isinstance(row.get("functional_salvage"), dict) else None
        row["functional_salvage"] = _merge_functional_salvage(
            existing,
            generated,
            merge_with_fixture=bool(config["merge_with_fixture"]),
        )
        row["board_evidence"] = vision_row.get("board_evidence")
        row["donor_board_vision"] = {
            "mode": vision_row.get("mode"),
            "source_artifact": vision_row.get("source_artifact"),
        }
        updated_boards.append(row)
        report["applied_board_count"] += 1

    if report["applied_board_count"]:
        circuit["boards"] = updated_boards
        body["circuit"] = circuit
    return body, report
