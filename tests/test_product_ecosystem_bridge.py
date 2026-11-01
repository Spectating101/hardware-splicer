"""Verify HS product external adapters do not invent physical correctness."""
import copy
import json
from pathlib import Path

import pytest
from hardware_splicer.product_ecosystem_bridge import (
    backend_readiness, to_blueprint_spec, to_decad_odbom, load_product,
)

ROOT=Path(__file__).resolve().parents[1]
PRODUCT=ROOT/"examples/products/clearbench_s1_product.json"


def sample():
    return json.loads(PRODUCT.read_text()), {"product_spec_sha256":"a"*64}


def test_blueprint_is_one_complete_offline_product_not_parts_catalog():
    product, receipt=sample()
    spec=to_blueprint_spec(product, receipt)
    assert spec["meta"]["id"]=="clearbench-s1"
    assert "NON-POTABLE" in spec["meta"]["subtitle"]
    assert spec["meta"]["researched"] is False
    assert spec["bounds"]=={"length":450,"width":260,"height":740}
    assert len(spec["parts"])>=10
    assert {"tray","panel","housing","service","sample","p_in","p_out","sample_valve"} <= {
        item["id"] for item in spec["parts"]}
    assert spec["explode"]["driver"]=="apart"
    assert {"front","side","top","iso"} == {v["id"] for v in spec["views"]}
    assert len(spec["annotations"]["callouts"])>=8
    housing=next(p for p in spec["parts"] if p["id"]=="housing")
    assert housing["shape"]["r"]==59
    assert housing["shape"]["h"]==308
    assert "not real manufacturer CAD" in housing["note"]
    assert not any("MEASURED" in str(p.get("note","")) for p in spec["parts"])


def test_disassembly_does_not_fabricate_unknown_fasteners_or_safe_order():
    product,receipt=sample()
    odbom=to_decad_odbom(product,receipt)
    assert len(odbom["nodes"])==11
    assert odbom["disassembly_execution_plan"]==[]
    assert all(not rows for rows in odbom["graph_edges"].values())
    assert odbom["metadata"]["x-hs-source-spec-sha256"]==receipt["product_spec_sha256"]
    assert odbom["metadata"]["x-hs-physical_authority"] is False
    assert {n["id"] for n in odbom["nodes"]} == {
        "node_"+r["ref"].lower() for r in product["product_bom"]}


def test_backend_readiness_strictly_distinguishes_execution_from_discovery():
    product,receipt=sample()
    b=backend_readiness(product,receipt)
    assert len(b["backends"])==8
    assert all(not x["executed_in_this_export"] for x in b["backends"])
    assert all(x["status"].startswith(("BLOCKED","NOT_APPLICABLE","EXPORT_READY"))
               for x in b["backends"])
    assert b["all_physical_authorities"] is False
    assert b["cross_tool_handoff_preserves_source_hash"] is True
    assert {"CADCLAW","MARB","Teardown","SolidCraft","FieldCraft","re:trace",
            "DeCAD","blueprint-3d-sheet"}=={x["name"] for x in b["backends"]}


def test_product_revisions_are_visible_to_both_backend_contracts():
    product,receipt=sample()
    other=copy.deepcopy(product)
    other["product_bom"][0]["engineering_status"]="UNQUALIFIED"
    assert to_decad_odbom(other,receipt)!=to_decad_odbom(product,receipt)
    other=copy.deepcopy(product)
    other["layout"]["filter_housing"]["height_mm"]=298
    assert to_blueprint_spec(other,receipt)!=to_blueprint_spec(product,receipt)
