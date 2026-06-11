from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


def scorecard_from_artifacts(out_dir: str | Path) -> Dict[str, Any]:
    root = Path(out_dir)
    authority = _read_json(root / "PROJECT_AUTHORITY.json")
    metrics = _read_json(root / "PRODUCTION_RELEASE_METRICS.json")
    functional = _read_json(root / "FUNCTIONAL_DELIVERY.json")
    vision = _read_json(root / "VISION_EVIDENCE_REPORT.json")
    dashboard = authority.get("dashboard") if isinstance(authority.get("dashboard"), Mapping) else {}

    gates = metrics.get("weighted_gates") if isinstance(metrics.get("weighted_gates"), list) else []
    return {
        "schema_version": "hardware_splicer.scoring_summary.v1",
        "out_dir": str(root),
        "project_authority_level": authority.get("project_authority_level"),
        "authority_score": authority.get("authority_score"),
        "production_readiness_score": metrics.get("production_readiness_score", dashboard.get("production_readiness_score")),
        "production_ready": metrics.get("production_ready"),
        "gates_passed": metrics.get("gates_passed"),
        "gates_total": metrics.get("gates_total"),
        "gates": [
            {
                "id": row.get("id"),
                "passed": row.get("passed"),
                "score": row.get("score"),
                "blockers": row.get("blockers"),
            }
            for row in gates
            if isinstance(row, Mapping)
        ],
        "functional_delivery_score": functional.get("functional_delivery_score", dashboard.get("functional_delivery_score")),
        "functional_delivery_grade": functional.get("grade", dashboard.get("functional_delivery_grade")),
        "vision_candidate_count": vision.get("candidate_count"),
        "vision_applied_note_count": vision.get("applied_note_count"),
        "evidence_gap_ids": metrics.get("evidence_gap_ids"),
        "top_blockers": metrics.get("top_blockers"),
    }


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return dict(data) if isinstance(data, Mapping) else {}
    except (OSError, json.JSONDecodeError):
        return {}
