from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple


SCHEMA_VERSION = "hardware_splicer.evidence_extraction_report.v1"

EVIDENCE_FIELDS = {
    "board_design_files",
    "mechanical_measurement_capture",
    "mechanical_simulation_capture",
    "mechanical_bench_capture",
    "robotics_bench_capture",
    "integrated_bench_capture",
    "field_validation",
    "release_review",
    "releases",
}

BOARD_EXTENSIONS = {
    ".net": "netlist",
    ".xml": "netlist",
    ".kicad_pcb": "pcb",
    ".pcb": "pcb",
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
PASS_WORDS = {"pass", "passed", "ok", "verified", "accepted", "closed", "true", "mitigated"}
FAIL_WORDS = {"fail", "failed", "blocked", "block", "error", "critical", "unsafe", "rejected", "false"}


def enrich_intake_with_extracted_evidence(intake: Mapping[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Promote declared evidence notes/files into structured intake evidence.

    The extractor is intentionally conservative: it only consumes explicitly
    provided notes, JSON evidence patches, and file attachments. It indexes
    image/video artifacts as pending vision evidence, but it does not turn a
    photo into measurements or pass/fail rows by itself.
    """

    body = dict(intake)
    report = build_evidence_extraction_report(body)
    extracted = _dict(report.get("extracted_evidence"))
    if not extracted:
        return body, report

    evidence = _dict(body.get("evidence"))
    _merge_evidence(evidence, extracted)
    body["evidence"] = evidence
    return body, report


def build_evidence_extraction_report(intake: Mapping[str, Any]) -> Dict[str, Any]:
    body = dict(intake)
    base_dir = _base_dir(body)
    sources = _source_rows(body)
    extracted: Dict[str, Any] = {}
    accepted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    pending_vision: List[Dict[str, Any]] = []

    for source in sources:
        kind = str(source.get("kind") or "").strip().lower()
        source_id = str(source.get("id") or source.get("path") or source.get("label") or f"source_{len(accepted) + len(rejected)}")
        if source.get("inline_text") is not None:
            _extract_notes(
                str(source.get("inline_text") or ""),
                extracted=extracted,
                accepted=accepted,
                rejected=rejected,
                source_id=source_id,
                artifact_uri=_artifact_uri(source, base_dir),
            )
            continue

        path_text = str(source.get("path") or source.get("file") or "").strip()
        if not path_text:
            rejected.append(_reject(source_id, "source_missing_path_or_text", "Evidence source did not include a path or inline text."))
            continue
        path = Path(path_text)
        if not path.is_absolute():
            path = base_dir / path
        path = path.resolve()
        suffix = path.suffix.lower()
        if not path.exists():
            rejected.append(_reject(source_id, "source_path_missing", f"Evidence source path does not exist: {path}"))
            continue

        if kind in {"json", "evidence_json", "patch"} or suffix == ".json":
            _extract_json_patch(path, extracted=extracted, accepted=accepted, rejected=rejected, source_id=source_id)
        elif kind in {"notes", "text", "markdown", "md", "txt"} or suffix in {".md", ".txt"}:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = path.read_text(encoding="utf-8", errors="replace")
            _extract_notes(text, extracted=extracted, accepted=accepted, rejected=rejected, source_id=source_id, artifact_uri=str(path))
        elif suffix in BOARD_EXTENSIONS or kind in {"netlist", "pcb", "kicad_pcb"}:
            board_id = str(source.get("board_id") or "main_ctrl")
            board_kind = str(source.get("board_kind") or kind or BOARD_EXTENSIONS.get(suffix) or "netlist")
            _add_board_file(extracted, board_id, str(path), _normalize_board_kind(board_kind))
            accepted.append(_accepted(source_id, "evidence.board_design_files", "board_file", board_id, 0.95))
        elif suffix in IMAGE_EXTENSIONS or suffix in VIDEO_EXTENSIONS or kind in {"image", "photo", "vision", "video"}:
            pending_vision.append(
                {
                    "source_id": source_id,
                    "path": str(path),
                    "reason": "Visual artifact is indexed but not promoted to trusted measurements without vision/human extraction.",
                }
            )
            field = _evidence_field_from_source(source)
            if field:
                _add_artifacts(extracted.setdefault(field, {}), [str(path)])
                accepted.append(_accepted(source_id, f"evidence.{field}", "artifact_only", str(path), 0.3))
        else:
            rejected.append(_reject(source_id, "unsupported_source_kind", f"Unsupported evidence source kind or extension: {kind or suffix}"))

    return {
        "schema_version": SCHEMA_VERSION,
        "source_count": len(sources),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "pending_vision_count": len(pending_vision),
        "accepted": accepted,
        "rejected": rejected,
        "pending_vision": pending_vision,
        "extracted_evidence": extracted,
        "extracted_evidence_summary": _evidence_summary(extracted),
    }


def _source_rows(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for key in ["evidence_sources", "attachments"]:
        value = body.get(key)
        if isinstance(value, Mapping):
            value = [value]
        if isinstance(value, str):
            value = [value]
        if isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, Mapping):
                    row = dict(item)
                else:
                    row = {"path": str(item)}
                row.setdefault("id", f"{key}_{index}")
                rows.append(row)
    for key in ["evidence_notes", "observation_notes", "bench_notes"]:
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            rows.append({"id": key, "kind": "notes", "inline_text": value})
        elif isinstance(value, list):
            text = "\n".join(str(item) for item in value if str(item).strip())
            if text.strip():
                rows.append({"id": key, "kind": "notes", "inline_text": text})
    return rows


def _extract_json_patch(
    path: Path,
    *,
    extracted: Dict[str, Any],
    accepted: List[Dict[str, Any]],
    rejected: List[Dict[str, Any]],
    source_id: str,
) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        rejected.append(_reject(source_id, "json_parse_failed", str(exc)))
        return
    if not isinstance(data, Mapping):
        rejected.append(_reject(source_id, "json_not_object", "Evidence JSON must be an object."))
        return
    patch = _dict(data.get("evidence"))
    if not patch:
        patch = {key: data[key] for key in EVIDENCE_FIELDS if key in data}
    if not patch:
        rejected.append(_reject(source_id, "json_no_evidence_fields", "JSON did not contain recognized evidence fields."))
        return
    recognized = False
    for key, value in patch.items():
        if key not in EVIDENCE_FIELDS:
            continue
        _merge_evidence(extracted, {key: value})
        accepted.append(_accepted(source_id, f"evidence.{key}", "json_patch", key, 0.95))
        recognized = True
    if not recognized:
        rejected.append(_reject(source_id, "json_no_recognized_evidence_fields", "JSON evidence patch used unsupported keys."))


def _extract_notes(
    text: str,
    *,
    extracted: Dict[str, Any],
    accepted: List[Dict[str, Any]],
    rejected: List[Dict[str, Any]],
    source_id: str,
    artifact_uri: str | None,
) -> None:
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = _clean_line(raw_line)
        if not line:
            continue
        if ":" not in line:
            continue
        prefix, content = line.split(":", 1)
        prefix = _normalize_key(prefix)
        content = content.strip()
        if not prefix or not content:
            continue
        parsed = _parse_content(content)
        line_id = f"{source_id}:{line_number}"
        artifacts = _artifacts_from(parsed)
        if artifact_uri:
            artifacts.append(artifact_uri)

        if prefix in {"board", "boardfile", "board_file", "netlist", "pcb", "kicad"}:
            path = parsed["values"].get("path") or parsed["values"].get("file")
            if not path:
                rejected.append(_reject(line_id, "board_source_missing_path", "Board evidence line needs path=... or file=..."))
                continue
            board_id = str(parsed["values"].get("board_id") or parsed["values"].get("id") or "main_ctrl")
            kind = _normalize_board_kind(str(parsed["values"].get("kind") or parsed["values"].get("type") or "netlist"))
            _add_board_file(extracted, board_id, str(path), kind)
            accepted.append(_accepted(line_id, "evidence.board_design_files", "note_board_file", board_id, 0.86))
            continue

        if prefix in {"measure", "measurement", "dimension", "dimensions"}:
            row = _measurement_row(parsed)
            _append_capture_row(extracted, "mechanical_measurement_capture", "dimensions", row, artifacts)
            accepted.append(_accepted(line_id, "evidence.mechanical_measurement_capture.dimensions", "note_measurement", row["target"], 0.84))
            continue

        if prefix in {"clearance", "clearances"}:
            row = _generic_row(parsed)
            if parsed["values"].get("clearance_mm") is not None:
                row["clearance_mm"] = _number(parsed["values"]["clearance_mm"])
            _append_capture_row(extracted, "mechanical_measurement_capture", "clearances", row, artifacts)
            accepted.append(_accepted(line_id, "evidence.mechanical_measurement_capture.clearances", "note_clearance", row["target"], 0.84))
            continue

        if prefix in {"simulation", "sim", "fit_load", "load_simulation", "mechanical_simulation"}:
            row = _generic_row(parsed, default_status="pass")
            _append_capture_row(extracted, "mechanical_simulation_capture", "simulation", row, artifacts)
            accepted.append(_accepted(line_id, "evidence.mechanical_simulation_capture.simulation", "note_simulation", row["target"], 0.82))
            continue

        if prefix in {"mechanical_bench", "fit_check", "load_test", "mechanical_motion"}:
            list_key = "fit_checks" if "fit" in prefix else "load_tests" if "load" in prefix else "motion_tests"
            row = _generic_row(parsed, default_status="pass")
            _append_capture_row(extracted, "mechanical_bench_capture", list_key, row, artifacts)
            accepted.append(_accepted(line_id, f"evidence.mechanical_bench_capture.{list_key}", "note_mechanical_bench", row["target"], 0.82))
            continue

        if prefix in {"robotics_bench", "motion_test", "robotics_motion", "robotics_current", "current_test", "cycle_test"}:
            if "current" in prefix:
                list_key = "current_tests"
            elif "cycle" in prefix:
                list_key = "cycle_tests"
            else:
                list_key = "motion_tests"
            row = _generic_row(parsed, default_status="pass")
            if parsed["values"].get("current_a") is not None:
                row["current_a"] = _number(parsed["values"]["current_a"])
            _append_capture_row(extracted, "robotics_bench_capture", list_key, row, artifacts)
            accepted.append(_accepted(line_id, f"evidence.robotics_bench_capture.{list_key}", "note_robotics_bench", row["target"], 0.82))
            continue

        if prefix in {"integrated_bench", "system_bench", "integrated_electrical", "integrated_motion", "integrated_packaging", "integrated_thermal"}:
            if "electrical" in prefix:
                list_key = "electrical_tests"
            elif "motion" in prefix:
                list_key = "motion_tests"
            elif "packaging" in prefix:
                list_key = "packaging_tests"
            elif "thermal" in prefix:
                list_key = "thermal_tests"
            else:
                list_key = "tests"
            row = _generic_row(parsed, default_status="pass")
            _append_capture_row(extracted, "integrated_bench_capture", list_key, row, artifacts)
            accepted.append(_accepted(line_id, f"evidence.integrated_bench_capture.{list_key}", "note_integrated_bench", row["target"], 0.82))
            continue

        if prefix in {"field", "field_validation", "mission", "mission_test"}:
            list_key = "mission_tests" if "mission" in prefix else "field_tests"
            row = _generic_row(parsed, default_status="pass")
            _append_capture_row(extracted, "field_validation", list_key, row, artifacts)
            accepted.append(_accepted(line_id, f"evidence.field_validation.{list_key}", "note_field_validation", row["target"], 0.8))
            continue

        if prefix in {"release", "release_review"}:
            values = parsed["values"]
            scope = str(values.get("scope") or values.get("scope_statement") or parsed["target"] or "").strip()
            if not scope:
                rejected.append(_reject(line_id, "release_scope_missing", "Release note needs scope=... or scope_statement=..."))
                continue
            release = {
                "scope_statement": scope,
                "artifact_uris": artifacts or ["evidence://extracted/release-review"],
                "acceptance_reviewed": _bool(values.get("accepted") or values.get("acceptance_reviewed") or values.get("reviewed")),
            }
            _merge_evidence(extracted, {"release_review": release})
            accepted.append(_accepted(line_id, "evidence.release_review", "note_release_review", "release_review", 0.86))
            continue

        rejected.append(_reject(line_id, "unsupported_note_prefix", f"Unsupported evidence note prefix: {prefix}"))


def _parse_content(content: str) -> Dict[str, Any]:
    try:
        tokens = shlex.split(content)
    except ValueError:
        tokens = content.split()
    values: Dict[str, Any] = {}
    target_tokens: List[str] = []
    status = ""
    for token in tokens:
        if "=" in token:
            key, value = token.split("=", 1)
            values[_normalize_key(key)] = value
            continue
        normalized = token.strip().lower()
        if normalized in PASS_WORDS or normalized in FAIL_WORDS:
            status = normalized
            continue
        target_tokens.append(token)
    if values.get("status") or values.get("result") or values.get("decision"):
        status = str(values.get("status") or values.get("result") or values.get("decision"))
    target = str(values.get("target") or " ".join(target_tokens)).strip()
    return {"target": target, "values": values, "status": status}


def _measurement_row(parsed: Dict[str, Any]) -> Dict[str, Any]:
    row = _generic_row(parsed, default_status="verified")
    values = _dict(parsed.get("values"))
    for key in ["value_mm", "width_mm", "height_mm", "depth_mm", "diameter_mm", "thickness_mm"]:
        if values.get(key) is not None:
            row["value_mm"] = _number(values[key])
            if key != "value_mm" and key not in row["target"]:
                row["target"] = f"{row['target']} {key.replace('_mm', '').replace('_', ' ')}".strip()
            break
    if values.get("material") is not None:
        row["material"] = str(values["material"])
    if values.get("tolerance_mm") is not None:
        row["tolerance_mm"] = _number(values["tolerance_mm"])
    return row


def _generic_row(parsed: Dict[str, Any], *, default_status: str = "") -> Dict[str, Any]:
    values = _dict(parsed.get("values"))
    row = {
        "target": str(parsed.get("target") or values.get("target") or "extracted evidence").strip(),
        "status": str(parsed.get("status") or default_status or values.get("status") or "observed").strip(),
    }
    for key in ["message", "notes", "detail"]:
        if values.get(key) is not None:
            row["message"] = str(values[key])
            break
    return row


def _append_capture_row(extracted: Dict[str, Any], field: str, list_key: str, row: Dict[str, Any], artifacts: List[str]) -> None:
    capture = extracted.setdefault(field, {})
    capture.setdefault(list_key, []).append(row)
    _add_artifacts(capture, artifacts)


def _add_board_file(extracted: Dict[str, Any], board_id: str, path: str, kind: str) -> None:
    files = extracted.setdefault("board_design_files", {})
    files[str(board_id)] = {"path": path, "kind": kind}


def _add_artifacts(capture: Dict[str, Any], artifacts: List[str]) -> None:
    values = [str(item).strip() for item in artifacts if str(item).strip()]
    if not values:
        return
    existing = capture.setdefault("artifact_uris", [])
    if not isinstance(existing, list):
        capture["artifact_uris"] = existing = [str(existing)]
    for value in values:
        if value not in existing:
            existing.append(value)


def _artifacts_from(parsed: Dict[str, Any]) -> List[str]:
    values = _dict(parsed.get("values"))
    artifacts: List[str] = []
    for key in ["artifact", "artifact_uri", "uri", "log", "photo", "video"]:
        if values.get(key):
            artifacts.append(str(values[key]))
    return artifacts


def _artifact_uri(source: Dict[str, Any], base_dir: Path) -> str | None:
    value = source.get("artifact_uri") or source.get("uri")
    if value:
        return str(value)
    path = str(source.get("path") or "").strip()
    if not path:
        return None
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = base_dir / resolved
    return str(resolved.resolve())


def _evidence_field_from_source(source: Dict[str, Any]) -> str:
    value = str(source.get("evidence_field") or source.get("field") or "").strip()
    if value.startswith("evidence."):
        value = value.split(".", 1)[1]
    return value if value in EVIDENCE_FIELDS else ""


def _merge_evidence(target: Dict[str, Any], patch: Mapping[str, Any]) -> None:
    for key, value in patch.items():
        if key not in target:
            target[key] = value
            continue
        existing = target[key]
        if isinstance(existing, dict) and isinstance(value, Mapping):
            _merge_evidence(existing, value)
        elif isinstance(existing, list) and isinstance(value, list):
            for item in value:
                if item not in existing:
                    existing.append(item)


def _evidence_summary(evidence: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "board_design_file_count": len(_dict(evidence.get("board_design_files"))),
        "has_measurements": bool(_dict(evidence.get("mechanical_measurement_capture"))),
        "has_mechanical_simulation": bool(_dict(evidence.get("mechanical_simulation_capture"))),
        "has_mechanical_bench": bool(_dict(evidence.get("mechanical_bench_capture"))),
        "has_robotics_bench": bool(_dict(evidence.get("robotics_bench_capture"))),
        "has_integrated_bench": bool(_dict(evidence.get("integrated_bench_capture"))),
        "has_field_validation": bool(_dict(evidence.get("field_validation"))),
        "has_release_review": bool(_dict(evidence.get("release_review"))),
    }


def _clean_line(line: str) -> str:
    text = line.strip()
    while text.startswith(("-", "*")):
        text = text[1:].strip()
    return text


def _normalize_key(value: str) -> str:
    out = []
    previous_underscore = False
    for char in str(value).strip().lower():
        if char.isalnum():
            out.append(char)
            previous_underscore = False
        elif not previous_underscore:
            out.append("_")
            previous_underscore = True
    return "".join(out).strip("_")


def _normalize_board_kind(kind: str) -> str:
    value = str(kind).strip().lower()
    if value in {"pcb", "kicad_pcb", "board"}:
        return "pcb"
    return "netlist"


def _number(value: Any) -> float:
    text = str(value)
    kept = "".join(char for char in text if char.isdigit() or char in {".", "-"})
    try:
        return float(kept)
    except ValueError:
        return 0.0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "yes", "true", "pass", "passed", "accepted", "reviewed", "closed"}


def _accepted(source_id: str, field: str, method: str, target: str, confidence: float) -> Dict[str, Any]:
    return {
        "source_id": source_id,
        "field": field,
        "method": method,
        "target": target,
        "confidence": round(confidence, 2),
    }


def _reject(source_id: str, reason: str, message: str) -> Dict[str, Any]:
    return {"source_id": source_id, "reason": reason, "message": message}


def _base_dir(body: Dict[str, Any]) -> Path:
    source_file = str(body.get("source_file") or "").strip()
    if source_file:
        return Path(source_file).resolve().parent
    return Path.cwd()


def _dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, Iterable) and not isinstance(value, (Mapping, bytes)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value)]
