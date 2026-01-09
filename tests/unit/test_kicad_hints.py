from src.engines.kicad_hints import generate_hints_template


def test_kicad_hints_template_fallback_source_prefers_vin():
    payload = generate_hints_template("tests/data/kicad_divider.net")

    assert payload["ground_net"] == "GND"
    assert any(c["net"] == "VIN" for c in payload["net_candidates"])

    # No rails in this fixture; fallback should pick VIN as source
    sources = payload["hints"]["sources"]
    assert sources
    assert sources[0]["net"] == "VIN"
