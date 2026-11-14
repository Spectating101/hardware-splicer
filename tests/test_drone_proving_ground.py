"""HS-3G drone proving-ground package: regenerate it and check CAD, numbers and README.

The package lives in examples/drone_proving_ground/. These tests rebuild the
frame in a temporary directory, so they never touch the committed files, and
fail if the committed README or results.json drift from a fresh regeneration.
"""
from __future__ import annotations

import json
import math
import re
import shutil
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
    rho = res["carbon_density_g_cm3"]
    # the cutter's 0.06 lb/in^3, converted
    assert rho == pytest.approx(0.06 * 453.59237 / 16.387064, abs=1e-4)
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
    assert m["motor_bolt_pcd_counts"] == {f"{F['motor_pcd_mm']:g}": 16}
    prop_d = next(p for p in res["parts"] if p["id"] == "prop")["diameter_mm"]
    a = res["assumptions"]
    assert m["adjacent_motor_spacing_mm"][0] - prop_d >= a["min_adjacent_tip_gap_mm"]["value"]
    assert res["clearance"]["min_radial_mm"] >= a["min_prop_clearance_mm"]["value"]


def test_drone_checks_pass_except_the_documented_full_throttle_c_rating(regen):
    _, res = regen
    failing = {k for k, v in res["checks"].items() if not v}
    assert failing == {"battery_continuous_covers_full_throttle", "cutter_rules_met_everywhere"}
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
    assert first < text.index("## 2. What this package adds") < text.index("## 3. Corrections from the 2026-11-13 audit") \
        < text.index("## 4. Corrections from the pre-purchase review")
    strategies = json.loads((PKG / "inputs" / "strategies.json").read_text())["strategies"]
    external = {s["url"] for st in strategies for s in st["sources"] if s["url"].startswith("https://")}
    assert len(strategies) >= 3 and len({st["id"] for st in strategies if any(
        s["url"].startswith("https://") for s in st["sources"])}) >= 3
    for url in external:
        assert url in text
    for ref in ("276-13", "291-2", "291-4", "291-6", "291-11", "291-10", "276-38", "276-30", "276-18",
                "276-17", "276-6", "276-10", "230-20", "230-21"):
        assert ref in text, ref
    phys = text[text.index("## 11. What only physical testing can prove"):text.index("## 12.")]
    assert len(re.findall(r"^\d+\. \*\*", phys, flags=re.M)) >= 10


def test_drone_package_has_no_local_paths_or_personal_details():
    for path in PKG.rglob("*"):
        if path.is_file() and path.suffix in {".md", ".json", ".py"}:
            text = path.read_text(encoding="utf-8")
            assert "/home/" not in text and "@gmail" not in text, path


def test_drone_review_corrections_are_applied(regen):
    _, res = regen
    parts = {p["id"]: p for p in res["parts"]}
    st = parts["stack"]
    assert sum(st["component_masses_g"].values()) == pytest.approx(16.8)
    assert next(r for r in res["mass"]["rows"] if r["id"] == "stack")["total_g"] == pytest.approx(16.8)
    assert st["unit_price_usd"] == 64.99 and parts["camera"]["unit_price_usd"] == 17.99
    assert "8 MB flash" in st["identity"] and "16 MB" not in st["identity"]
    assert st["uarts_hw"] - len(st["uarts_reserved"]) == 4
    assert st["uarts_hw"] - len(st["uarts_reserved"]) - len(st["uart_needs"]) == 1
    assert "Matek" not in parts["gps"]["identity"]
    for pid in ("stack", "camera", "gps", "frame_cut"):
        assert all(s.get("accessed") == "2026-11-14" for s in parts[pid]["sources"]), pid
    # the lighter density stays as sensitivity; the payload allowance uses the heaviest case
    assert res["mass_density_high"]["density"] == 1.6
    assert res["auw_heavy_case_g"] == max(res["mass"]["auw_g"], res["mass_density_high"]["auw_g"])
    assert res["payload_allowance_g"] == pytest.approx(
        res["mass_limit_g"] - res["mass_design_margin_g"] - res["auw_heavy_case_g"], abs=0.051)


def test_drone_frame_meets_cutter_rules_except_at_motor_pads(regen):
    _, res = regen
    rules = res["cutter_rules"]
    for plate, d in res["manufacturability"].items():
        for k, v in d["smallest_hole_by_feature_mm"].items():
            if not k.startswith("motor_"):
                assert v >= rules["min_hole_d_mm"] - 1e-6, (plate, k)
        for k, v in d["smallest_web_by_pair_mm"].items():
            if "motor_" not in k:
                assert v >= rules["min_web_over_t"] * d["thickness_mm"] - 1e-6, (plate, k)
    # the reviewed 0.65 mm web is gone
    assert res["manufacturability"]["bottom_plate"]["smallest_web_mm"] >= 1.0
    assert res["checks"]["cutter_rules_met_away_from_motor_pads"]


def test_drone_frame_junctions_are_filleted(regen):
    import hs3g_frame as frame_mod
    _, res = regen
    assert res["cad_measured"]["bottom_sharp_concave_corners"] == 0
    sharp = dict(frame_mod.FRAME, junction_fillet_r_mm=0.0)
    # without the fillet the same check finds the 8 arm roots and 8 pad junctions
    assert frame_mod._sharp_concave_corners(frame_mod.bottom_outline(sharp).val()) == 16


def test_drone_battery_strap_check_tests_what_it_claims(regen):
    _, res = regen
    s = res["battery_strap"]
    lo, hi = s["slot_inner_edges_x_mm"]
    assert lo <= s["pack_x_extent_mm"][0] and s["pack_x_extent_mm"][1] <= hi
    assert s["strap_side_gap_to_stack_spacer_mm"] > 0 and s["strap_gap_under_esc_mm"] > 0
    assert s["slot_y_end_mm"] < res["frame_parameters"]["stack_pitch_mm"] / 2
    # the check fails when the pack is moved over a slot
    parts = res["parts"]
    bad = design.battery_strap(res["frame_parameters"], parts, 5.0, s["slot_y_end_mm"] * 2)
    assert not bad["slots_outside_pack"]
    # and when the strap is too wide to pass between the stack spacers
    wide = dict(res["frame_parameters"], strap_w_mm=20.0)
    assert not design.battery_strap(wide, parts, res["cg"]["battery_x_mm"], 21.0)["strap_clears_stack_spacers"]


def test_drone_arm_mode_is_reported_as_a_range(regen):
    _, res = regen
    cases = res["arm_cases"]
    f = [c["f1_hz"] for c in cases.values()]
    assert res["arm_range"]["f1_max_hz"] == max(f) == cases["on_axis_clamp_axis"]["f1_hz"]
    assert res["arm_range"]["f1_min_hz"] == min(f) == cases["bias_clamp_far_edge"]["f1_hz"]
    assert cases["on_axis_clamp_far_edge"]["free_length_mm"] > cases["on_axis_clamp_axis"]["free_length_mm"]
    assert 10.0 < res["arm_range"]["e_bias_gpa"] < 25.0


def test_drone_hardware_lists_stack_screws_and_motor_engagement(regen):
    _, res = regen
    hw = res["hardware"]
    ids = {it["id"]: it for it in hw["items"]}
    assert ids["stack_screw"]["qty"] == 4
    assert hw["stack_screw_len_mm"] >= hw["stack_screw_needed_mm"]
    F = res["frame_parameters"]
    assert hw["motor_thread_engagement_mm"] == pytest.approx(hw["motor_screw_len_mm"] - F["bottom_t_mm"])
    assert hw["motor_thread_depth_verified"] is False
    assert next(r for r in res["mass"]["rows"] if r["id"] == "hardware")["total_g"] == pytest.approx(hw["total_g"])


def test_drone_readme_states_review_gates(regen):
    text = (PKG / "README.md").read_text()
    assert "## 10. Order in two stages" in text and "measure before cutting" in text.lower()
    assert "law.moj.gov.tw" in text and "natural person" in text and "visual line of sight" in text
    assert "upper bound" in text and "Thrust-stand the hover point before quoting" in text
    assert "Bluejay" in text and "unverified" in text


def _copy_package(dst: Path) -> Path:
    (dst / "generated").mkdir(parents=True)
    shutil.copyfile(PKG / "README.md", dst / "README.md")
    for f in (PKG / "generated").iterdir():
        shutil.copyfile(f, dst / "generated" / f.name)
    return dst


def test_drone_check_passes_on_committed_copy_and_writes_nothing(tmp_path):
    pkg = _copy_package(tmp_path / "pkg")
    before = {f: f.read_bytes() for f in pkg.rglob("*") if f.is_file()}
    assert build_hs3g_package.main(["--check", "--pkg", str(pkg)]) == 0
    after = {f: f.read_bytes() for f in pkg.rglob("*") if f.is_file()}
    assert before == after


def test_drone_check_fails_on_hand_edited_results(tmp_path):
    pkg = _copy_package(tmp_path / "pkg")
    res_path = pkg / "generated" / "results.json"
    data = json.loads(res_path.read_text())
    data["mass"]["auw_g"] = 999.99
    edited = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    res_path.write_text(edited)
    assert build_hs3g_package.main(["--check", "--pkg", str(pkg)]) == 1
    assert res_path.read_text() == edited  # --check never restores or overwrites
