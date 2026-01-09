from src.engines.kicad_hints import generate_hints_template


def test_kicad_hints_suggests_esp32_load_current():
    payload = generate_hints_template("tests/data/kicad_with_esp32.net")

    hints = payload["hints"]
    loads = hints["loads_cc"]
    assert loads

    u1 = next((l for l in loads if l["name"] == "U1"), None)
    assert u1 is not None
    assert u1["net"] == "VIN"
    assert u1["amps"] >= 0.2
