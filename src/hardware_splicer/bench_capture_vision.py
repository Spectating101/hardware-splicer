"""Camera-assisted bench capture template drafting.

Vision suggests test points and attaches photos to BENCH_CAPTURE_TEMPLATE rows.
It does **not** close splice bench gates — operators must submit instrument-backed
``bench_topology_capture.v1`` readings via ``submit_bench_capture``.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

from .bench_capture_bridge import (
    BENCH_CAPTURE_SCHEMA,
    TEMPLATE_FILE,
    load_bench_capture_template,
    sync_bench_session_template,
)
from .board_vision_salvage import _analyze_board_image_path, _resolve_image_path
from .splice_bench import bench_status

SCHEMA_VERSION = "hardware_splicer.bench_capture_vision.v1"
DRAFT_FILE = "BENCH_CAPTURE_VISION_DRAFT.json"
REPORT_FILE = "BENCH_CAPTURE_VISION_REPORT.json"

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic"}

_KIND_HINTS: Dict[str, List[str]] = {
    "continuity": [
        "Probe donor GND to load connector shell with DMM continuity.",
        "Verify harness pairs before energizing — photo shows connector orientation.",
    ],
    "voltage": [
        "Measure rail at the connector visible in the photo before attaching the load.",
        "Confirm polarity at the labeled motor/supply header.",
    ],
    "current": [
        "Series-insert DMM on the supply lead shown at the board edge.",
    ],
    "psu_ramp": [
        "Attach current-limited bench supply to the donor VMOTOR rail connector.",
        "Ramp slowly while watching the driver region in the photo for hotspots.",
    ],
    "thermal": [
        "Capture a thermal baseline of the driver IC region after a short idle ramp.",
        "Compare hotspot against the motor driver area visible in the board photo.",
    ],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text or "").strip().lower()).strip("_") or "bench"


def _rows(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _materialize_inline_image(source: Mapping[str, Any], *, build_dir: Path) -> Path | None:
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
    filename = str(source.get("filename") or source.get("name") or "bench_photo.jpg")
    suffix = Path(filename).suffix.lower()
    if suffix not in _IMAGE_EXTENSIONS:
        suffix = ".jpg"
    target = build_dir / f"vision_inline_{_slug(filename)}{suffix}"
    target.write_bytes(raw)
    return target


def resolve_bench_image_paths(
    build_dir: str | Path,
    attachments: Sequence[Mapping[str, Any]] | None = None,
) -> List[Path]:
    """Resolve image paths from attachment dicts relative to build_dir / repo."""
    root = Path(build_dir).resolve()
    paths: List[Path] = []
    seen: set[str] = set()
    for attachment in attachments or []:
        if not isinstance(attachment, dict):
            continue
        kind = str(attachment.get("kind") or attachment.get("type") or "image").lower()
        if kind not in {"image", "photo", "board_photo", "thermal_image", "bench_photo"}:
            continue
        inline = _materialize_inline_image(attachment, build_dir=root)
        if inline is not None:
            key = str(inline.resolve())
            if key not in seen:
                paths.append(inline)
                seen.add(key)
            continue
        resolved = _resolve_image_path(
            str(attachment.get("path") or attachment.get("file") or attachment.get("uri") or ""),
            base_dir=root,
        )
        if resolved is None:
            continue
        key = str(resolved.resolve())
        if key in seen:
            continue
        paths.append(resolved)
        seen.add(key)
    return paths


def _artifact_rows(image_paths: Sequence[Path], *, build_dir: Path) -> List[Dict[str, Any]]:
    artifacts: List[Dict[str, Any]] = []
    for index, image_path in enumerate(image_paths, start=1):
        try:
            rel = image_path.resolve().relative_to(build_dir.resolve())
            uri = str(rel)
        except ValueError:
            uri = str(image_path)
        artifacts.append(
            {
                "kind": "photo",
                "uri": uri,
                "notes": f"Bench vision assist source #{index}: {image_path.name}",
                "source": "bench_capture_vision_assist",
            }
        )
    return artifacts


def _offline_measurement_suggestion(
    row: Mapping[str, Any],
    *,
    image_paths: Sequence[Path],
) -> Dict[str, Any]:
    kind = str(row.get("kind") or "voltage")
    target = str(row.get("target") or row.get("notes") or "")
    target_lower = target.lower()
    hints = list(_KIND_HINTS.get(kind, _KIND_HINTS["voltage"]))
    if "vmotor" in target_lower or "motor" in target_lower:
        hints.insert(0, "Focus DMM on the motor supply connector visible in the donor photo.")
    if "ground" in target_lower or "gnd" in target_lower:
        hints.insert(0, "Use continuity between donor GND pour and connector shell.")
    if "gpio" in target_lower or "driver" in target_lower:
        hints.append("Dry-run driver enable with bench leads — do not rely on photo alone.")
    photo_names = [path.name for path in image_paths]
    return {
        "mode": "offline_heuristic",
        "gate_id": row.get("gate_id"),
        "kind": kind,
        "suggested_actions": hints[:3],
        "photo_refs": photo_names,
        "confidence": "low",
        "operator_must_confirm": True,
    }


def _live_measurement_suggestions(
    analysis: Mapping[str, Any],
    template: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    evidence = analysis.get("board_evidence") if isinstance(analysis.get("board_evidence"), dict) else {}
    blocks = _rows(evidence.get("reusable_blocks"))
    connectors = _rows(evidence.get("connectors"))
    suggestions: List[Dict[str, Any]] = []
    for row in _rows(template.get("measurements")):
        gate_id = str(row.get("gate_id") or "")
        kind = str(row.get("kind") or "")
        target = str(row.get("target") or "").lower()
        matched_blocks = [
            block
            for block in blocks
            if any(
                token in str(block.get("block_id") or "").lower()
                or token in str(block.get("label") or "").lower()
                for token in ("motor", "driver", "supply", "logic")
                if token in target or token in kind
            )
        ]
        matched_connectors = [
            conn
            for conn in connectors
            if any(token in str(conn.get("name") or "").lower() for token in ("motor", "j_", "conn"))
        ]
        actions: List[str] = []
        for block in matched_blocks[:2]:
            label = str(block.get("label") or block.get("block_id") or "block")
            actions.append(f"Inspect {label} region from vision before probing.")
        for conn in matched_connectors[:2]:
            actions.append(f"Probe connector {conn.get('name') or conn.get('connector_id')} with DMM.")
        if not actions:
            actions = _offline_measurement_suggestion(row, image_paths=[]).get("suggested_actions") or []
        suggestions.append(
            {
                "mode": "live_board_vision",
                "gate_id": gate_id,
                "kind": kind,
                "suggested_actions": actions[:4],
                "vision_blocks": [str(b.get("block_id") or "") for b in matched_blocks[:4]],
                "confidence": "medium" if matched_blocks or matched_connectors else "low",
                "operator_must_confirm": True,
            }
        )
    return suggestions


def build_vision_assisted_capture_draft(
    template: Mapping[str, Any],
    *,
    image_paths: Sequence[Path],
    build_dir: Path,
    vision_report: Mapping[str, Any] | None = None,
    operator_id: str = "",
) -> Dict[str, Any]:
    """Merge template + photo artifacts + suggestions; measurements stay open."""
    draft = dict(template)
    draft["schema_version"] = BENCH_CAPTURE_SCHEMA
    draft["source"] = "hardware_splicer.bench_capture_vision_assist"
    draft["operator_id"] = operator_id or draft.get("operator_id") or ""
    draft["recorded_at"] = draft.get("recorded_at") or ""
    draft["vision_assisted"] = True
    draft["vision_assist_at"] = _now()

    artifacts = _rows(draft.get("artifacts"))
    artifacts.extend(_artifact_rows(image_paths, build_dir=build_dir))
    draft["artifacts"] = artifacts

    live_analyses = [
        row
        for row in _rows((vision_report or {}).get("image_analyses"))
        if isinstance(row, dict) and row.get("ok")
    ]
    if live_analyses:
        suggestions = _live_measurement_suggestions(live_analyses[0], template)
    else:
        suggestions = [
            _offline_measurement_suggestion(row, image_paths=image_paths)
            for row in _rows(template.get("measurements"))
        ]

    enriched: List[Dict[str, Any]] = []
    suggestion_by_gate = {str(s.get("gate_id") or ""): s for s in suggestions}
    for row in _rows(template.get("measurements")):
        item = dict(row)
        item["status"] = "open"
        item.pop("value", None)
        gate_id = str(item.get("gate_id") or "")
        suggestion = suggestion_by_gate.get(gate_id)
        if suggestion:
            item["vision_assist"] = suggestion
            hint = (suggestion.get("suggested_actions") or [""])[0]
            if hint and not str(item.get("notes") or "").strip():
                item["notes"] = hint
        enriched.append(item)
    draft["measurements"] = enriched

    policy = dict(draft.get("policy") or {})
    draft["policy"] = {
        **policy,
        "vision_alone_is_not_evidence": True,
        "fill_status_pass_fail_after_physical_measurement": True,
        "draft_from_vision_assist": True,
        "submit_via": "hs_splice_bench_submit_capture or POST /v1/splice-bench/submit-capture",
    }
    return draft


def assist_bench_capture_vision(
    build_dir: str | Path,
    *,
    attachments: Sequence[Mapping[str, Any]] | None = None,
    live: bool = False,
    operator_id: str = "",
    device_hint: str = "",
    goal: str = "",
) -> Dict[str, Any]:
    """Attach bench photos and draft measurement hints without closing gates."""
    root = Path(build_dir).resolve()
    if not root.is_dir():
        raise ValueError(f"build_dir not found: {root}")

    session_before = bench_status(root)
    template_sync = sync_bench_session_template(root)
    template = dict(template_sync.get("template") or load_bench_capture_template(root))
    image_paths = resolve_bench_image_paths(root, attachments)
    if not image_paths:
        raise ValueError("no_bench_images_resolved: pass attachments with kind=image and path or image_base64")

    project_goal = goal or str(session_before.get("project_name") or template.get("project_name") or "bench bring-up")
    image_analyses: List[Dict[str, Any]] = []
    for image_path in image_paths:
        if live:
            analysis = _analyze_board_image_path(
                image_path,
                goal=f"{project_goal} — suggest DMM/PSU test points for open bench gates (do not assert pass/fail)",
                live=True,
                device_hint=device_hint,
                symptoms=(),
            )
        else:
            analysis = {
                "ok": True,
                "mode": "offline",
                "image_path": str(image_path),
                "note": "Offline assist — heuristic suggestions only; set live=true for Qwen board vision.",
            }
        image_analyses.append(analysis)

    vision_report: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "assisted_at": _now(),
        "build_dir": str(root),
        "live": bool(live),
        "image_count": len(image_paths),
        "image_paths": [str(path) for path in image_paths],
        "image_analyses": image_analyses,
        "open_gate_count": session_before.get("open_gate_count"),
        "policy": "Vision assist drafts capture rows — instrument readings required to close gates.",
    }

    draft = build_vision_assisted_capture_draft(
        template,
        image_paths=image_paths,
        build_dir=root,
        vision_report=vision_report,
        operator_id=operator_id,
    )
    draft_path = root / DRAFT_FILE
    draft_path.write_text(json.dumps(draft, indent=2), encoding="utf-8")
    draft["draft_path"] = str(draft_path)

    report_path = root / REPORT_FILE
    vision_report["draft_path"] = str(draft_path)
    vision_report["template_path"] = str(root / TEMPLATE_FILE)
    vision_report["measurement_count"] = len(draft.get("measurements") or [])
    vision_report["suggestion_count"] = sum(1 for row in _rows(draft.get("measurements")) if row.get("vision_assist"))
    report_path.write_text(json.dumps(vision_report, indent=2), encoding="utf-8")

    session_after = bench_status(root)
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "build_dir": str(root),
        "draft": draft,
        "draft_path": str(draft_path),
        "vision_report_path": str(report_path),
        "vision_report": vision_report,
        "bench_session": {
            "readiness": session_after.get("readiness"),
            "open_gate_count": session_after.get("open_gate_count"),
            "power_on_authorized": session_after.get("power_on_authorized"),
            "bench_capture_template": session_after.get("bench_capture_template"),
        },
        "policy": {
            "vision_alone_is_not_evidence": True,
            "gates_unchanged": session_before.get("open_gate_count") == session_after.get("open_gate_count"),
        },
    }
