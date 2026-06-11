#!/usr/bin/env python3
"""Score plant-watering intake briefs across tiers (brief → vision → evidence → tier5)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS_DIR = (ROOT / "scripts").resolve()
sys.path = [str(SRC)] + [p for p in sys.path if Path(p).resolve() != SCRIPTS_DIR]

from hardware_splicer.project_intake import load_project_intake, run_project_intake, splice_and_build_from_intake  # noqa: E402
from hardware_splicer.scoring_summary import scorecard_from_artifacts  # noqa: E402
TIERS = [
    ("tier1_brief", "examples/intakes/plant_watering_brief.json", False),
    ("tier2_vision", "examples/intakes/plant_watering_vision_brief.json", False),
    ("tier2_5_annotated", "examples/intakes/plant_watering_vision_annotated_brief.json", False),
    ("tier3_evidence", "examples/intakes/plant_watering_evidence_pack.json", False),
    ("tier5_full_stack", "examples/intakes/plant_watering_tier5_brief.json", True),
]


def _load_env_local() -> None:
    env_file = ROOT / ".env.local"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip("'\"")


def main() -> int:
    _load_env_local()
    out_root = Path(os.environ.get("HARDWARE_SPLICER_TIER_SCORE_OUT", "/tmp/hardware_splicer_tier_scores"))
    out_root.mkdir(parents=True, exist_ok=True)
    rows = []

    for tier_id, brief_rel, run_splice in TIERS:
        brief = ROOT / brief_rel
        intake = load_project_intake(brief)
        if os.getenv("HARDWARE_SPLICER_SKIP_VISION_LIVE", "").strip().lower() in {"1", "true", "yes", "on"}:
            vision = dict(intake.get("vision_assistance") or {})
            if vision:
                vision["live"] = False
                intake["vision_assistance"] = vision
        tier_dir = out_root / tier_id
        intake_result = run_project_intake(intake, out_dir=tier_dir / "intake", start_splicer=False)
        splice_score = None
        if run_splice:
            splice = splice_and_build_from_intake(intake, out_dir=tier_dir / "splice_build", export_gerber=True)
            splice_score = splice.get("functional_delivery")
        card = scorecard_from_artifacts(tier_dir / "intake")
        card["tier_id"] = tier_id
        card["brief"] = str(brief)
        card["intake_ok"] = intake_result.get("ok")
        if splice_score:
            card["splice_functional_delivery_score"] = splice_score.get("functional_delivery_score")
            card["splice_functional_delivery_grade"] = splice_score.get("grade")
        rows.append(card)

    report = {
        "schema_version": "hardware_splicer.intake_tier_scores.v1",
        "out_root": str(out_root),
        "rows": rows,
    }
    report_path = out_root / "INTAKE_TIER_SCORES.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
