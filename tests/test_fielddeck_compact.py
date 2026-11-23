"""The proposed compact Fielddeck layout (revision 5c): reproducible records, no physical claims."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from hardware_splicer.part_scene import build_parts_sidecar

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projects" / "cyberdeck-real-trial-20261020"
GEOMETRY = json.loads((PROJECT / "compact" / "geometry.json").read_text())


def test_committed_sidecar_is_reproducible():
    committed = json.loads((PROJECT / "compact" / "parts.json").read_text())
    assert build_parts_sidecar(PROJECT, "5c") == committed
    assert committed["revision"] == "5c" and committed["missing_inputs"] == []
    assert committed["revision_diff"]["from_revision"] == "5"


def test_geometry_record_matches_its_build_and_model():
    sources = GEOMETRY["sources"]
    assert sources["build_sha256"] == hashlib.sha256((PROJECT / "compact" / "build.py").read_bytes()).hexdigest()
    assert sources["glb_sha256"] == hashlib.sha256((PROJECT / "compact" / "cad" / "FIELDDECK_5C.glb").read_bytes()).hexdigest()


def test_compact_layout_is_smaller_with_no_solid_overlaps():
    before, after = GEOMETRY["measured"]["5"], GEOMETRY["measured"]["5c"]
    assert after["overlaps"] == []
    assert after["case_height_mm"] == before["case_height_mm"] - GEOMETRY["drop_mm"]
    assert after["printable_volume_total_mm3"] < before["printable_volume_total_mm3"]


def test_the_proposal_claims_nothing_physical():
    assert GEOMETRY["physical_fit_verified"] is False
    assert GEOMETRY["status"].startswith("proposed_")
    sidecar = json.loads((PROJECT / "compact" / "parts.json").read_text())
    reasons = " ".join(row["reason"] for row in sidecar["blockers"])
    for open_question in ("cable access", "heat", "centre of mass", "retention"):
        assert open_question in reasons
    manifest = json.loads((PROJECT / "scene.json").read_text())
    label = next(row["label"] for row in manifest["revisions"] if row["id"] == "5c")
    assert "proposed" in label and not any(word in label.lower() for word in ("ready", "approved", "verified"))
