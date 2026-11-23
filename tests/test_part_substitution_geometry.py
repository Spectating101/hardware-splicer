"""Nominal CAD follows declared dimensions/holes without granting fit approval."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest

from hardware_splicer.part_substitution import evaluate_substitution
from hardware_splicer.part_substitution_geometry import generate_substitution_geometry, _prepare

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples/part_substitution"


def specification(name="display"):
    return json.loads((EXAMPLES / f"cyberdeck-{name}-replacement.json").read_text())


def report(name="display"):
    return evaluate_substitution(specification(name))


@pytest.mark.parametrize("name", ["display", "controller", "power"])
def test_three_declared_fixture_patterns_resolve_without_invented_dimensions(name):
    result = report(name)
    prepared = _prepare(result)
    adapter = prepared["adapters"][0]
    assert adapter["status"] == "nominal_geometry_generated"
    assert adapter["structural_fit_verified"] is False
    assert adapter["thickness_mm"] == 3
    assert adapter["edge_margin_mm"] == 6
    assert adapter["parameter_basis"] == "explicit_declared_mount_adapter"
    expected = result["geometry"]["adapter_requirements"][0]
    assert {tuple(h["local_xy_mm"]) for h in adapter["holes"]} == {
        tuple(p) for p in expected["base_holes_mm"] + expected["replacement_holes_mm"]}


def test_missing_replacement_envelope_produces_unknown_without_invoking_native(tmp_path):
    spec = specification()
    spec["candidate"]["dimensions_mm"] = None
    result = generate_substitution_geometry(evaluate_substitution(spec), tmp_path / "out", interpreter="/no/python")
    assert result["status"] == "unknown"
    assert result["files"] == {}
    assert result["assembly_complete"] is False
    assert result["physical_fit_unverified"] is True


def test_missing_plate_assumptions_are_not_silently_defaulted():
    spec = specification()
    spec.pop("mount_adapter")
    prepared = _prepare(evaluate_substitution(spec))
    assert prepared["adapters"][0]["status"] == "not_generated"
    assert "explicit" in prepared["adapters"][0]["reason"]


@pytest.mark.parametrize("mutation,reason", [
    ("overlap", "web"), ("edge", "ligament"), ("nonrectangular", "rectangular"),
    ("plane", "bottom-face"), ("different_diameter", "different bore"),
])
def test_unmakeable_or_unsupported_adapters_are_blocked(mutation, reason):
    spec = specification()
    mount = spec["candidate"]["mount"]
    if mutation == "overlap":
        mount["holes_mm"] = [[5, 4], [147, 4], [5, 86], [147, 86]]
    elif mutation == "edge":
        spec["mount_adapter"]["edge_margin_mm"] = 2
    elif mutation == "nonrectangular":
        mount["holes_mm"][0][0] = 11
    elif mutation == "plane":
        mount["plane_z_mm"] = 2
        next(p for p in spec["parts"] if p["part_id"] == spec["replace_part_id"])["mount"]["plane_z_mm"] = 2
    elif mutation == "different_diameter":
        mount["holes_mm"] = deepcopy(next(p for p in spec["parts"] if p["part_id"] == spec["replace_part_id"])["mount"]["holes_mm"])
        mount["hole_diameter_mm"] = 3.2
    prepared = _prepare(evaluate_substitution(spec))
    assert prepared["adapters"][0]["status"] == "blocked"
    assert reason in prepared["adapters"][0]["reason"]


def test_adapter_cannot_intersect_unchanged_nominal_body():
    spec = specification()
    other = next(p for p in spec["parts"] if p["part_id"] == "board@west.17")
    other["position_mm"] = [30, 105, 16]
    prepared = _prepare(evaluate_substitution(spec))
    assert prepared["adapters"][0]["status"] == "blocked"
    assert "collides" in prepared["adapters"][0]["reason"]


def test_report_cannot_relabel_stale_envelope_or_drill_geometry():
    value = report()
    value["geometry"]["envelopes"][0]["dimensions_mm"][0] += 1
    with pytest.raises(ValueError, match="differs"):
        _prepare(value)
    value = report()
    value["geometry"]["adapter_requirements"][0]["replacement_holes_mm"] = [[11, 10], [151, 10], [11, 82], [151, 82]]
    assert _prepare(value)["adapters"][0]["status"] == "blocked"


def test_output_is_create_only_and_symlinks_are_rejected(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    original = out / "nominal_assembly.step"
    original.write_text("original")
    with pytest.raises(ValueError, match="fresh"):
        generate_substitution_geometry(report(), out)
    assert original.read_text() == "original"
    alias = tmp_path / "alias"
    alias.symlink_to(out, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        generate_substitution_geometry(report(), alias / "nested")


def test_unavailable_native_interpreter_has_no_plausible_partial_exports(tmp_path):
    value = report()
    before = deepcopy(value)
    result = generate_substitution_geometry(value, tmp_path / "out", interpreter="/no/python")
    assert result["status"] == "unavailable"
    assert result["files"] == {}
    assert list((tmp_path / "out").iterdir()) == []
    assert value == before
    assert result["construction_ready"] is False
    assert result["adapter_results"][0]["status"] == "nominal_geometry_supported"
    assert result["core_status"] == value["status"]
    assert result["specification_sha256"] == value["specification_sha256"]


NATIVE = os.environ.get("HS_SUBSTITUTION_NATIVE_PYTHON")


@pytest.mark.skipif(not NATIVE, reason="Set HS_SUBSTITUTION_NATIVE_PYTHON for bounded native CAD proof.")
def test_native_reimports_declared_drills_and_new_geometry_without_approving_fit(tmp_path):
    first = report()
    result = generate_substitution_geometry(first, tmp_path / "first", interpreter=NATIVE)
    assert result["status"] == "generated", result.get("reason")
    assert len(result["files"]) == 6
    assert result["native_verification"]["nominal_assembly"]["solid_count"] == 5
    adapter = result["native_verification"]["adapter_plate"]
    assert adapter["through_drill_volume_verified"] is True
    assert len(adapter["reimported_bores_mm"]) == 8
    assert adapter["stl_watertight"] is True
    assert result["physical_fit_unverified"] is True
    assert result["core_status"] == "requires_adaptation"
    for name, entry in result["files"].items():
        raw = (tmp_path / "first" / name).read_bytes()
        assert entry == {"sha256": "sha256:" + hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}
    # Fresh declared placement/size and new hole locations must propagate into
    # actual reopened STEP, not merely change a JSON digest or a canned model.
    spec = specification()
    target = next(p for p in spec["parts"] if p["part_id"] == spec["replace_part_id"])
    target["position_mm"] = [32, 104, 21]
    spec["candidate"]["dimensions_mm"] = [164, 96, 11]
    spec["candidate"]["mount"]["holes_mm"] = [[12, 12], [152, 12], [12, 80], [152, 80]]
    revised = generate_substitution_geometry(evaluate_substitution(spec), tmp_path / "second", interpreter=NATIVE)
    assert revised["status"] == "generated", revised.get("reason")
    assert revised["native_verification"]["replacement_envelope"]["bounds_mm"] == pytest.approx([32, 104, 21, 196, 200, 32])
    bores = revised["native_verification"]["adapter_plate"]["reimported_bores_mm"]
    assert [44.0, 116.0, 2.7] in bores
    assert [40.0, 115.0, 2.7] not in bores
    assert revised["report_sha256"] != result["report_sha256"]
    assert revised["files"]["replacement_envelope.step"]["sha256"] != result["files"]["replacement_envelope.step"]["sha256"]
