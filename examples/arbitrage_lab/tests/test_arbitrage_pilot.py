"""Tests for prototype generation and disclosed scenario economics."""
from __future__ import annotations

import importlib.util
import json
import math
import struct
from pathlib import Path

import pytest
from pydantic import ValidationError
from mecha_splicer.bundle import generate_bundle

HERE=Path(__file__).resolve().parents[1]
SPEC=HERE/"router3_indoor_mount.json"


def _profit_module():
    s=importlib.util.spec_from_file_location("hs_arbitrage_profit",HERE/"profit_screen.py")
    m=importlib.util.module_from_spec(s)
    assert s.loader
    s.loader.exec_module(m)
    return m


def test_native_hs_bundle_generates_two_piece_real_part():
    spec=json.loads(SPEC.read_text())
    bundle=generate_bundle(spec)
    assert bundle["blockers"] is False
    assert "indoor_router_mount.scad" in bundle["outputs"]
    assert any(line["qty"]==2 and line["category"]=="printed" for line in bundle["bom"])
    assert any("UNVERIFIED" in i["message"] for i in bundle["dfm"])


def test_depth_parameter_changes_native_geometry():
    a=generate_bundle({**json.loads(SPEC.read_text()),"indoor_router_mount":{"device_depth_mm":42}})
    b=generate_bundle({**json.loads(SPEC.read_text()),"indoor_router_mount":{"device_depth_mm":55}})
    assert a["outputs"]==b["outputs"]
    from mecha_splicer.engines.indoor_router_mount import generate_indoor_router_mount_scad
    from mecha_splicer.spec import IndoorRouterMountSpec
    assert generate_indoor_router_mount_scad(IndoorRouterMountSpec(device_depth_mm=42)) != generate_indoor_router_mount_scad(IndoorRouterMountSpec(device_depth_mm=55))


@pytest.mark.parametrize("bad",[-1,0,150])
def test_bad_device_depth_fails(bad):
    from mecha_splicer.spec import IndoorRouterMountSpec
    with pytest.raises(ValidationError):
        IndoorRouterMountSpec(device_depth_mm=bad)


def test_market_snapshots_retain_comparable_sources_and_hypotheses():
    j=json.loads((HERE/"market_snapshot_20261105.json").read_text())
    assert len(j["candidates"])>=6
    assert all(c["listing_source"].startswith("https://") for c in j["candidates"])
    assert all(c["grams_per_sale_assumption"]>0 for c in j["candidates"])
    assert "shipping_excluded" in j["outsourced_petg"]


def test_contribution_formula_and_minimum_order():
    m=_profit_module()
    a=json.loads((HERE/"market_snapshot_20261105.json").read_text())["assumptions"]
    result=m.unit_contribution(100000,3,a)
    assert result["supplier_billed_mass_g"]==10
    assert result["print_cost_idr"]==10000
    assert result["marketplace_fees_idr"]==20000
    assert result["contribution_idr"] == 100000-10000-20000-result["fixed_expenses_and_reserves_idr"]
    assert result["break_even_price_idr"] > 0


def test_stress_and_fee_gate_are_not_sales_proof():
    m=_profit_module()
    j=json.loads((HERE/"market_snapshot_20261105.json").read_text())
    c=j["candidates"][0]
    out=m.evaluate_candidate(c,j)
    assert out["reported_cumulative_sales"]==182
    assert out["stress"]["contribution_idr"]<out["base"]["contribution_idr"]
    assert out["release_status"].startswith("HS native")
    assert not out["passes_stress_nonnegative"]


def test_negative_price_or_mass_rejected():
    m=_profit_module()
    j=json.loads((HERE/"market_snapshot_20261105.json").read_text())
    with pytest.raises(ValueError):
        m.unit_contribution(-1,10,j["assumptions"])
    with pytest.raises(ValueError):
        m.unit_contribution(1,-2,j["assumptions"])


def test_committed_native_stl_is_a_binary_triangulated_mesh():
    # CI regenerates outputs/ (needs OpenSCAD); a fresh clone has only the committed evidence/ copy.
    candidates=[HERE/"outputs/native_router3/indoor_router_mount.stl",HERE/"evidence/indoor_router_mount.stl"]
    p=next((c for c in candidates if c.is_file()),None)
    assert p is not None,"neither generated nor committed native STL exists"
    blob=p.read_bytes()
    n=struct.unpack_from("<I",blob,80)[0]
    assert n>100
    assert len(blob)==84+n*50
    audit=json.loads((p.parent/"native_mesh_audit.json").read_text())
    assert audit["non_2_manifold_edges"]==0
    assert audit["assumed_solid_PETG_grams_for_pair"]>50
