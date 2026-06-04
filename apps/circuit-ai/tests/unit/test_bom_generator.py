from pathlib import Path

from src.engines.bom_generator import BOMGenerator


def test_bom_parses_fields_and_normalizes_values():
    net_path = Path("tests/data/kicad_bom_fields.net")
    gen = BOMGenerator()

    comps = gen.parse_kicad_netlist(str(net_path))
    assert comps, "expected components"
    comp_by_ref = {c["reference"]: c for c in comps}

    assert "fields" in comp_by_ref["R1"]
    assert comp_by_ref["R1"]["fields"].get("Manufacturer") == "Yageo"
    assert comp_by_ref["R1"]["fields"].get("MPN") == "RC0603FR-0710KL"

    bom = gen.generate_bom(str(net_path), include_pricing=False)
    assert bom["status"] == "success"
    assert bom["schema_version"] == 2
    assert "items" in bom

    # Value normalization: C1 0.1uF -> 100nF
    items = bom["items"]
    c_items = [i for i in items if (i.get("category") == "capacitor" and i.get("footprint", "").endswith("C_0603"))]
    assert any(i.get("value") == "100nF" for i in c_items)


def test_bom_groups_passives_without_identity_fields():
    net_path = Path("tests/data/kicad_bom_fields.net")
    gen = BOMGenerator()
    bom = gen.generate_bom(str(net_path), include_pricing=False)

    # R2 and R3 should group together (same footprint, normalized value, no identity fields)
    r_group = [
        i
        for i in bom["items"]
        if i.get("category") == "resistor"
        and i.get("footprint", "").endswith("R_0603")
        and i.get("manufacturer") in (None, "")
        and i.get("mpn") in (None, "")
    ]
    assert len(r_group) == 1
    assert r_group[0]["quantity"] == 2
    assert r_group[0]["value"] == "10K"

