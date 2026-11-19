import hashlib
import json
from pathlib import Path

import pytest
from hardware_splicer.mechanical_fixture_handoff import (
    EVIDENCE_SCHEMA, MechanicalDesignError, REQUEST_SCHEMA, build, load_spec, strategies,
)


def example(source, **changes):
    base = {
        "schema": REQUEST_SCHEMA,
        "project_id": "test-novel-fixture",
        "revision": 1,
        "objective": "Inspect a removable source-backed PCB without guessed mounting holes",
        "source": {"filename": "original.ref", "url": "https://example.org/design",
                   "sha256": hashlib.sha256(source).hexdigest(),
                   "geometry_basis": "manufacturer_nominal_dimensions",
                   "reproduction_rights": "external_reference_not_redistributed"},
        "board": {"width_mm": 21, "depth_mm": 17.8, "thickness_mm": 1,
                  "thickness_basis": "unverified_assumption", "outline_xy_mm": None,
                  "mounting_holes": [], "mounting_holes_status": "unverified", "unknown_contacts": True},
        "interface": {"usb_corridor_width_mm": 9, "usb_corridor_depth_mm": 6,
                      "antenna_geometry_status": "unknown", "edge_contacts_status": "unknown"},
        "requirements": {"min_nominal_edge_gap_mm": .4, "max_base_width_mm": 50,
                         "max_base_depth_mm": 40, "stationary_unpowered_only": True},
    }
    base.update(changes)
    return base


def test_unknown_holes_select_gravity_and_reject_assumed_holes():
    original = b"fixed manufacturer source"
    spec = example(original)
    assert strategies(load_spec(json.dumps(spec).encode(), original))["selected"] == "holeless_gravity_support"
    spec["board"]["mounting_holes"] = [{"x_mm": -5, "y_mm": -5, "diameter_mm": 2.5, "source_anchor": "design-1"}]*4
    with pytest.raises(MechanicalDesignError, match="assumed mounting holes"):
        load_spec(json.dumps(spec).encode(), original)


def test_source_drift_bad_fields_and_physical_operation_rejected():
    s = b"original source"
    spec = example(s)
    with pytest.raises(MechanicalDesignError, match="pinned SHA"):
        load_spec(json.dumps(spec).encode(), b"altered source")
    spec["physical_authority_granted"] = True
    with pytest.raises(MechanicalDesignError, match="unsupported"):
        load_spec(json.dumps(spec).encode(), s)
    spec.pop("physical_authority_granted")
    spec["requirements"]["stationary_unpowered_only"] = False
    with pytest.raises(MechanicalDesignError, match="unpowered"):
        load_spec(json.dumps(spec).encode(), s)


def test_repeat_keys_and_nonfinite_values_rejected():
    s=b"original source"
    raw=json.dumps(example(s)).replace('"revision": 1,','"revision": 1, "revision": 2,')
    with pytest.raises(MechanicalDesignError,match="Duplicate"):
        load_spec(raw.encode(),s)
    spec=example(s)
    spec["board"]["width_mm"]=float("nan")
    with pytest.raises(MechanicalDesignError,match="finite"):
        load_spec(json.dumps(spec).encode(),s)


def test_unverified_source_geometry_cannot_claim_mounting_holes():
    s=b"original source"
    spec=example(s)
    spec["board"]["mounting_holes_status"]="verified_source_geometry"
    with pytest.raises(MechanicalDesignError,match="four sourced"):
        load_spec(json.dumps(spec).encode(),s)


def test_real_cad_adhoc_geometry_and_revision_receipt(tmp_path):
    original=b"fixture source only; no holes"
    src=tmp_path/"original.ref"
    src.write_bytes(original)
    request=tmp_path/"request.json"
    request.write_text(json.dumps(example(original)))
    result=build(request,src,tmp_path/"revision1")
    assert result["strategy"]=="holeless_gravity_support"
    assert result["digital_checks_passed"] is True
    v=json.loads((tmp_path/"revision1/verification.json").read_text())
    assert v["geometry"]["nominal_board_collision_mm3"]==0
    assert v["geometry"]["usb_corridor_collision_mm3"]==0
    assert v["geometry"]["negative_control_collision_mm3"]>0
    assert v["physical_status"]=="UNVERIFIED"
    e=json.loads((tmp_path/"revision1/mechanical-evidence.json").read_text())
    assert e["schema"]==EVIDENCE_SCHEMA
    assert e["implementation_sha256"] == hashlib.sha256((Path(__file__).resolve().parents[1]/"src/hardware_splicer/mechanical_fixture_handoff.py").read_bytes()).hexdigest()
    assert e["physical_authority_granted"] is False
    assert e["artifacts"]["fixture.step"]["sha256"] == hashlib.sha256((tmp_path/"revision1/fixture.step").read_bytes()).hexdigest()
    with pytest.raises(MechanicalDesignError,match="already exists"):
        build(request,src,tmp_path/"revision1")
    # Legitimate changed requirements cause a different, separately retained result.
    req=example(original,revision=2)
    req["requirements"]["min_nominal_edge_gap_mm"]=.9
    request.write_text(json.dumps(req))
    new=build(request,src,tmp_path/"revision2")
    assert result["evidence_sha256"] != new["evidence_sha256"]
    assert json.loads((tmp_path/"revision2/mechanical-evidence.json").read_text())["revision"]==2
    assert json.loads((tmp_path/"revision1/mechanical-evidence.json").read_text())["revision"]==1


def test_verified_original_eagle_holes_choose_standoffs(tmp_path):
    xml = b'''<eagle><drawing><board><libraries><library name="L"><packages><package name="M"><hole x="0" y="0" drill="2.5"/></package></packages></library></libraries><elements>
    <element name="H1" library="L" package="M" x="2" y="2"/><element name="H2" library="L" package="M" x="18" y="2"/>
    <element name="H3" library="L" package="M" x="2" y="18"/><element name="H4" library="L" package="M" x="18" y="18"/>
    </elements></board></drawing></eagle>'''
    src=tmp_path/"mounts.brd"
    src.write_bytes(xml)
    spec=example(xml)
    spec["source"]["filename"]="mounts.brd"
    spec["source"]["geometry_basis"]="reviewed_source_geometry"
    spec["board"]["width_mm"]=20
    spec["board"]["depth_mm"]=20
    spec["board"]["source_center_mm"]=[10,10]
    spec["board"]["mounting_holes_status"]="verified_source_geometry"
    spec["board"]["mounting_holes"]=[
        {"x_mm":x,"y_mm":y,"diameter_mm":2.5,"source_anchor":anchor}
        for anchor,x,y in [("H1",-8,-8),("H2",8,-8),("H3",-8,8),("H4",8,8)]]
    request=tmp_path/"request.json"
    request.write_text(json.dumps(spec))
    loaded=load_spec(request.read_bytes(),xml)
    assert strategies(loaded)["selected"]=="source_hole_standoffs"
    result=build(request,src,tmp_path/"result")
    assert result["strategy"]=="source_hole_standoffs"
    assert result["digital_checks_passed"] is True
    assert json.loads((tmp_path/"result/verification.json").read_text())["physical_status"]=="UNVERIFIED"
    spec["board"]["mounting_holes"][0]["x_mm"]=-7.8
    with pytest.raises(MechanicalDesignError,match="Original EAGLE"):
        load_spec(json.dumps(spec).encode(),xml)
    spec["source"]["geometry_basis"]="manufacturer_nominal_dimensions"
    with pytest.raises(MechanicalDesignError,match="require an original EAGLE"):
        load_spec(json.dumps(spec).encode(),xml)
