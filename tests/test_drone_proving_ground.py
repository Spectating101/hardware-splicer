"""HS-3G drone proving-ground package: regenerate it and check CAD, numbers and README.

The package lives in examples/drone_proving_ground/. These tests rebuild the
frame in a temporary directory, so they never touch the committed files, and
fail if the committed README or results.json drift from a fresh regeneration.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import pytest

cq = pytest.importorskip("cadquery")

PKG = Path(__file__).resolve().parents[1] / "examples" / "drone_proving_ground"
sys.path.insert(0, str(PKG))

import build_hs3g_package  # noqa: E402
import hs3g_design as design  # noqa: E402
import hs3g_readme as render_readme  # noqa: E402


@pytest.fixture(scope="module")
def regen(tmp_path_factory):
    out = tmp_path_factory.mktemp("drone_proving_ground")
    res = build_hs3g_package.compute(out)
    return out, res


def test_drone_frame_step_and_stl_are_generated(regen):
    out, res = regen
    for key, name in res["cad_files"].items():
        path = out / name
        assert path.is_file() and path.stat().st_size > 1000, key


def test_drone_frame_step_reimports_as_one_solid_with_cad_volume(regen):
    out, res = regen
    for plate in ("bottom_plate", "top_plate"):
        shape = cq.importers.importStep(str(out / res["cad_files"][f"{plate}_step"])).val()
        assert len(shape.Solids()) == 1
        cad_v = res["cad_measured"][f"{plate.split('_')[0]}_volume_mm3"]
        assert shape.Volume() == pytest.approx(cad_v, rel=1e-4)


def test_drone_frame_stl_is_watertight_and_matches_cad_volume(regen):
    out, res = regen
    for plate in ("bottom_plate", "top_plate"):
        rep = design.mesh_report(out / res["cad_files"][f"{plate}_stl"])
        assert rep["degenerate_triangles"] == 0
        assert rep["non_manifold_edges"] == 0
        assert rep["inconsistently_oriented_edges"] == 0
        assert rep["watertight"]
        cad_v = res["cad_measured"][f"{plate.split('_')[0]}_volume_mm3"]
        assert rep["signed_volume_mm3"] == pytest.approx(cad_v, rel=2e-3)


def test_drone_frame_mass_follows_volume_and_density(regen):
    _, res = regen
    rho = res["materials"]["carbon_plate"]["density_g_cm3"]
    v = res["cad_measured"]["bottom_volume_mm3"] + res["cad_measured"]["top_volume_mm3"]
    assert res["mass"]["frame_g"] == pytest.approx(v * rho / 1000.0, abs=1e-3)
    assert res["mass"]["auw_g"] == pytest.approx(sum(r["total_g"] for r in res["mass"]["rows"]), abs=0.01)
    assert res["cg"]["mass_g"] == pytest.approx(res["mass"]["auw_g"], abs=0.05)


def test_drone_frame_motor_spacing_and_prop_clearance(regen):
    _, res = regen
    F = res["frame_parameters"]
    m = res["cad_measured"]
    assert m["motor_count"] == 4
    for d in m["diagonal_motor_spacing_mm"]:
        assert d == pytest.approx(F["wheelbase_mm"], abs=0.01)
    for d in m["adjacent_motor_spacing_mm"]:
        assert d == pytest.approx(F["wheelbase_mm"] / math.sqrt(2), abs=0.01)
    assert m["motor_bolt_pcd_counts"] == {"12": 16, "9": 16}
    prop_d = next(p for p in res["parts"] if p["id"] == "prop")["diameter_mm"]
    a = res["assumptions"]
    assert m["adjacent_motor_spacing_mm"][0] - prop_d >= a["min_adjacent_tip_gap_mm"]["value"]
    assert res["clearance"]["min_radial_mm"] >= a["min_prop_clearance_mm"]["value"]


def test_drone_checks_pass_except_the_documented_full_throttle_c_rating(regen):
    _, res = regen
    failing = {k for k, v in res["checks"].items() if not v}
    assert failing == {"battery_continuous_covers_full_throttle"}
    p = res["propulsion"]
    assert p["throttle_limit_current_a"] <= p["battery_cont_a"]
    assert res["mass_density_high"]["auw_g"] <= res["mass_limit_g"] - res["mass_design_margin_g"]


def test_drone_propulsion_numbers_follow_the_maker_table(regen):
    _, res = regen
    table = json.loads((PKG / "inputs" / "motor_f1404_3800kv_thrust.json").read_text())
    rows = table["props"]["HQ 3x3x3"]
    p = res["propulsion"]
    assert p["max_thrust_total_g"] == pytest.approx(4 * rows[-1][1], abs=0.05)
    assert p["tw_ratio_full"] == pytest.approx(4 * rows[-1][1] / res["mass"]["auw_g"], abs=0.005)
    # momentum-theory scaling from the first row must be the pessimistic branch used
    hover = res["mass"]["auw_g"] / 4
    assert p["hover_power_per_motor_n15_w"] == pytest.approx(rows[0][5] * (hover / rows[0][1]) ** 1.5, abs=0.01)
    assert p["hover_power_per_motor_used_w"] >= p["hover_power_per_motor_fit_w"]


def test_drone_audit_corrections_reproduce_the_audit(regen):
    _, res = regen
    bom = res["audit"]["bom"]
    geo = res["audit"]["geometry"]
    assert bom["pr291_build_min_twd"] == bom["pr291_committed_build_min_twd"] == 4036
    assert bom["corrected_build_min_twd"] == 526 + 4 * 416 + 2387 + 60 + 467 + 2 * 181 + 18 == 5484
    assert bom["corrected_if_1900_board_is_5in1_twd"] == 4997
    assert geo["auw_g"] == pytest.approx(38.0, abs=0.05)
    assert geo["rib_protrusion_mm"] == pytest.approx(1.0, abs=1e-6)
    assert geo["bbox_from_ribs_mm"] == pytest.approx(geo["bbox_committed_mm"], abs=1e-3)


def test_drone_readme_and_results_match_a_fresh_regeneration(regen):
    _, res = regen
    fresh = json.dumps(res, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    assert (PKG / "generated" / "results.json").read_text() == fresh, "rerun build_hs3g_package.py"
    assert (PKG / "README.md").read_text() == render_readme.render(res), "rerun build_hs3g_package.py"


def test_drone_readme_covers_strategies_corrections_and_physical_unknowns():
    text = (PKG / "README.md").read_text()
    assert text.startswith("# HS-3G")
    first = text.index("## 1. What the existing drone PRs already proved")
    assert first < text.index("## 2. What this package adds") < text.index("## 3. Corrections from the audit")
    strategies = json.loads((PKG / "inputs" / "strategies.json").read_text())["strategies"]
    external = {s["url"] for st in strategies for s in st["sources"] if s["url"].startswith("https://")}
    assert len(strategies) >= 3 and len({st["id"] for st in strategies if any(
        s["url"].startswith("https://") for s in st["sources"])}) >= 3
    for url in external:
        assert url in text
    for ref in ("276-13", "291-2", "291-4", "291-6", "291-11", "291-10", "276-38", "276-30", "276-18",
                "276-17", "276-6", "276-10", "230-20", "230-21"):
        assert ref in text, ref
    phys = text[text.index("## 9. What only physical testing can prove"):text.index("## 10.")]
    assert len(re.findall(r"^\d+\. \*\*", phys, flags=re.M)) >= 10


def test_drone_package_has_no_local_paths_or_personal_details():
    for path in PKG.rglob("*"):
        if path.is_file() and path.suffix in {".md", ".json", ".py"}:
            text = path.read_text(encoding="utf-8")
            assert "/home/" not in text and "@gmail" not in text, path
