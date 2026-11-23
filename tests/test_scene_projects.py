"""Each committed scene project's parts sidecar is what the builder produces from its model."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from hardware_splicer.part_scene import build_parts_sidecar_for

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = {
    "hs3g-b-drone": ("b", {"custom": 6, "envelope": 24, "unknown": 2}),
    "esp32-servo-board": ("a", {"custom": 1, "envelope": 11, "copper": 15}),
    "spi-flash-adapter-board": ("a", {"custom": 1, "envelope": 36, "copper": 20}),
}


@pytest.mark.parametrize("project_id", sorted(PROJECTS))
def test_committed_sidecar_is_reproducible(project_id):
    revision_id, expected = PROJECTS[project_id]
    project = ROOT / "projects" / project_id
    manifest = json.loads((project / "scene.json").read_text())
    revision = next(row for row in manifest["revisions"] if row["id"] == revision_id)
    built = build_parts_sidecar_for(ROOT / revision["glb"], project, revision_id,
                                    glb_native_units=revision.get("glb_native_units"))
    committed = json.loads((ROOT / revision["parts"]).read_text())
    assert built == committed
    assert Counter(part["geometry_basis"] for part in built["parts"]) == expected


def test_basis_rules_cite_their_source():
    for project_id in PROJECTS:
        rules = json.loads((ROOT / "projects" / project_id / "geometry-basis.json").read_text())
        assert rules["source"]
        assert all(rule["basis"] in {"custom", "vendor_step", "envelope", "proxy", "unknown", "copper"} for rule in rules["rules"])


def test_board_heights_are_recorded_as_assumptions():
    for project_id in ("esp32-servo-board", "spi-flash-adapter-board"):
        heights = json.loads((ROOT / "projects" / project_id / "footprint-heights.json").read_text())["heights"]
        assert heights and all(row["state"] == "assumed" and row["why"] for row in heights.values())


def test_board_scenes_carry_each_nets_copper_and_fit_skips_it():
    from hardware_splicer import scene_fit
    for project in ("esp32-servo-board", "spi-flash-adapter-board"):
        parts = json.loads((ROOT / "projects" / project / "parts.json").read_text())["parts"]
        copper = [part for part in parts if part["geometry_basis"] == "copper"]
        assert copper and all(part["part_id"].startswith("net-") for part in copper)
        assert any(part["part_id"] == "net-gnd" for part in copper)
    # Copper belongs to KiCad's DRC; the body fit engine leaves it out.
    assert "copper" in Path(scene_fit.__file__).read_text()
