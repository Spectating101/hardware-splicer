"""Pinned live Qwen board_evidence golden artifact."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE_EVIDENCE = ROOT / "tests" / "data" / "golden" / "rc_toy_live_board_evidence.json"
LIVE_META = ROOT / "tests" / "data" / "golden" / "rc_toy_live_board_evidence.meta.json"


def test_live_board_evidence_pinned():
    evidence = json.loads(LIVE_EVIDENCE.read_text(encoding="utf-8"))
    assert evidence.get("schema_version") == "board_evidence.v1"
    assert "_golden_meta" not in evidence
    assert len(evidence.get("salvage_candidates") or []) >= 1
    meta = json.loads(LIVE_META.read_text(encoding="utf-8"))
    assert meta.get("mode") == "live"
    assert meta.get("provider") == "qwen"
    assert meta.get("image_sha256")


def test_golden_intake_uses_live_evidence():
    from hardware_splicer.board_vision_salvage import board_evidence_to_functional_salvage

    evidence = json.loads(LIVE_EVIDENCE.read_text(encoding="utf-8"))
    salvage = board_evidence_to_functional_salvage(
        evidence,
        board_id="donor_rc_car_ctrl",
        goal="robot drive base",
        source_artifact=str(LIVE_EVIDENCE),
    )
    assert salvage.get("source") == "board_vision"
    assert len(salvage.get("reusable_blocks") or []) >= 1
    labels = " ".join(str(row.get("name") or "") for row in salvage.get("reusable_blocks") or [])
    assert "motor" in labels.lower() or "driver" in labels.lower()
