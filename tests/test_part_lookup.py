"""Looking a marking up in KiCad's own libraries: real data, honest tiers, and checked against an independent reading of the same files."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from hardware_splicer import part_lookup as pl
from hardware_splicer.kicad_diff import parse_kicad_sexp

pytestmark = pytest.mark.skipif(not pl.libraries_available(), reason="KiCad's libraries are not installed")


def _props(tree) -> dict[str, str]:
    out: dict[str, str] = {}
    for child in tree:
        if isinstance(child, list) and child and child[0] == "property" and len(child) > 2:
            out.setdefault(str(child[1]), str(child[2]))
    return out


def test_the_index_agrees_with_an_independent_reading_of_the_same_symbols() -> None:
    index = pl._index()
    sample = index.rows[:: max(1, len(index.rows) // 400)]
    assert len(sample) >= 300
    for row in sample:
        text = Path(row.path).read_text(encoding="utf-8")[row.start : row.end]
        tree = None
        for candidate in (text, text.rstrip()[:-1]):
            try:
                tree = parse_kicad_sexp(candidate)
                break
            except Exception:
                continue
        assert tree is not None, row.name
        props = _props(tree)
        assert tree[1] == row.name
        assert row.description == pl._clean(props.get("Description", ""), 200), (row.library, row.name)
        assert row.datasheet == pl._clean(props.get("Datasheet", ""), 300), (row.library, row.name)
        assert row.footprint == pl._clean(props.get("Footprint", ""), 120), (row.library, row.name)


def test_a_part_gets_its_own_datasheet_and_footprint_not_its_neighbours() -> None:
    by_name = {m["name"]: m for m in pl.lookup_part("NE555")["matches"]}
    assert by_name["NE555D"]["footprint"] == "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"
    assert by_name["NE555P"]["footprint"] == "Package_DIP:DIP-8_W7.62mm"
    assert by_name["NE555P"]["datasheet"] == "http://www.ti.com/lit/ds/symlink/ne555.pdf"


def test_a_marking_is_matched_in_three_honest_tiers_and_says_what_each_means() -> None:
    exact = pl.lookup_part("LM358")["matches"]
    assert exact[0]["tier"] == "exact" and exact[0]["name"] == "LM358" and "exactly this name" in exact[0]["tier_text"]
    variant = pl.lookup_part("TLV75518PDBVR")["matches"]
    assert variant[0]["tier"] == "variant" and variant[0]["name"] == "TLV75518PDBV"
    assert "plus a code" in variant[0]["tier_text"] and "a package, a grade or a different chip" in variant[0]["tier_text"]
    assert "different package or grade" not in variant[0]["tier_text"]
    family = pl.lookup_part("W25Q128JWSIQ")["matches"]
    assert family and {m["tier"] for m in family} == {"family"} and all(m["name"].startswith("W25Q128J") for m in family)
    assert all("not this one" in m["tier_text"] for m in family)
    assert all(m["description"] for m in family)


def test_what_the_library_does_not_know_is_an_empty_answer_not_a_guess() -> None:
    nothing = pl.lookup_part("L9110S")
    assert nothing["matches"] == [] and nothing["source"]["name"] == "KiCad symbol library"
    assert pl.lookup_part("QZXJ7")["matches"] == []
    short = pl.lookup_part("ab")
    assert short["matches"] == [] and "at least 3 characters" in short["reason"]


@pytest.mark.parametrize("bad", ["x" * 41, "NE‮555", "NE​555", "a\u0000b"])
def test_a_marking_that_cannot_be_looked_up_is_refused(bad: str) -> None:
    with pytest.raises(pl.PartLookupError):
        pl.lookup_part(bad)


@pytest.mark.parametrize("bad", [None, 5, ["NE555"], {"a": 1}, b"NE555"])
def test_something_that_is_not_text_is_refused(bad) -> None:
    with pytest.raises(pl.PartLookupError, match="must be text"):
        pl.lookup_part(bad)


def test_only_web_links_come_back_as_datasheets_and_every_answer_names_its_source() -> None:
    result = pl.lookup_part("NE555")
    assert result["source"]["version"] == "9.0" and result["source"]["symbols"] > 20000 and "not proof" in result["source"]["note"]
    for match in result["matches"]:
        assert match["datasheet"] is None or match["datasheet"].startswith(("http://", "https://"))
    assert pl._safe_url("javascript:alert(1)") is None and pl._safe_url("file:///etc/passwd") is None and pl._safe_url("~") is None
    assert pl._safe_url("https://example.com/a b") is None and pl._safe_url("https://example.com/ds.pdf") == "https://example.com/ds.pdf"


def test_a_symbols_pins_are_read_with_their_names_and_types_including_for_derived_symbols() -> None:
    pins = pl.symbol_pins("Timer", "NE555P")
    assert pins["pins_total"] == 8
    by_number = {p["number"]: p for p in pins["pins"]}
    assert by_number["8"]["name"] == "VCC" and by_number["8"]["type"] == "power_in" and by_number["1"]["name"] == "GND"
    derived = next(r for r in pl._index().rows if r.extends)
    assert pl.symbol_pins(derived.library, derived.name)["pins_total"] > 0
    with pytest.raises(pl.PartLookupError):
        pl.symbol_pins("Timer", "NOT_A_PART")


def test_the_measurements_to_make_come_from_the_pins_and_never_claim_what_the_reading_should_be() -> None:
    gates = pl.power_gates("Timer", "NE555P", "Package_DIP:DIP-8_W7.62mm")
    kinds = [g["kind"] for g in gates]
    assert kinds == ["diode", "isolation", "voltage"]          # power-off first; the old voltage-then-ohms order told people to power the board
    assert "pin 8 (VCC)" in gates[0]["instruction"] and "pin 1 (GND)" in gates[0]["instruction"]
    assert "dot or notch marks the pin-1 end" in gates[0]["instruction"]
    assert "datasheet" in gates[-1]["expect"] and not any(ch.isdigit() for g in gates for ch in g["expect"])     # no invented range
    assert all("write down" in g["expect"] for g in gates)
    assert "near zero" not in gates[1]["expect"] and "pass" not in "".join(g["expect"] for g in gates).lower()
    assert "pin-1 end" not in pl.power_gates("Timer", "NE555P", None)[0]["instruction"]        # only said where the package is known
    assert pl.power_gates("Timer", "NOT_A_PART", None) == []


def test_package_sizes_are_the_libraries_courtyards_and_a_name_cannot_walk_out_of_the_library() -> None:
    soic = pl.footprint_size("Package_SO:SOIC-8_3.9x4.9mm_P1.27mm")
    assert (soic["width_mm"], soic["length_mm"]) == (7.4, 5.4) and "courtyard" in soic["source"]
    assert pl.footprint_size("Package_DIP:DIP-8_W7.62mm")["width_mm"] > 9
    for bad in ("../../etc:passwd", "Package_SO:../../../../etc/passwd", "Nope:Nope", "", "no colon", "a:b/../c"):
        assert pl.footprint_size(bad) is None


def test_it_is_deterministic_and_fast_after_the_first_look() -> None:
    first = pl.lookup_part("74HC595")
    start = time.perf_counter()
    for _ in range(50):
        again = pl.lookup_part("74HC595")
    assert again == first and (time.perf_counter() - start) / 50 < 0.02


def test_without_libraries_it_says_so_instead_of_pretending(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_KICAD_DIR", str(tmp_path))
    pl.clear_cache()
    try:
        result = pl.lookup_part("NE555")
        assert result["matches"] == [] and "not installed" in result["reason"]
    finally:
        monkeypatch.undo()
        pl.clear_cache()


# --- review findings (Grok), each reproduced before it was fixed -----------------------------------------------------------------


def test_a_negative_supply_is_a_supply_not_the_ground() -> None:
    gates = pl.power_gates("Audio", "AS3310", None)
    assert gates and "pin 14 (GND)" in gates[0]["to"] and "VEE" not in gates[0]["to"]            # GND is the reference, though VEE was listed first
    assert any("VEE" in g["from"] for g in gates), gates                                          # and VEE is measured as a supply of its own
    assert all("PGND" not in g["to"] for g in gates)


def test_an_exposed_pad_is_never_measured_as_a_supply() -> None:
    gates = pl.power_gates("MCU_Microchip_PIC16", "PIC16F15356-xML", "Package_DFN_QFN:QFN-28-1EP_6x6mm_P0.65mm_EP4.25x4.25mm")
    assert gates and not any("PAD" in g["from"] or "PAD" in g["to"] for g in gates)
    assert [g["from"] for g in gates if g["kind"] == "voltage"] == ["pin 17 (VDD)"]
    assert "pin 5 (VSS)" in gates[0]["to"]


def test_a_part_with_several_supply_pins_of_one_name_is_measured_once_per_name() -> None:
    names = [g["from"] for g in pl.power_gates("MCU_ST_STM32F1", "STM32F103C8Tx", "Package_QFP:LQFP-48_7x7mm_P0.5mm") if g["kind"] == "voltage"]
    assert len(names) == len(set(names)) and len(names) <= 3


# --- the second review (Grok): tiers, supplies, big parts, hostile libraries ------------------------------------------------------


@pytest.mark.parametrize(
    ("marking", "expected"),
    [
        ("74HC", []), ("NE55", []), ("74HC0", []),                                  # the start of many parts: nothing is offered
        ("LM35", ["LM35-D", "LM35-LP", "LM35-NEB"]),                                 # real grade codes after a separator; LM358 and LM3578 are other chips
        ("NE555", ["NE555D", "NE555P"]),
        ("SN74LVC1G00", ["SN74LVC1G00DBV", "SN74LVC1G00DCK", "SN74LVC1G00DRL"]),    # not G14 or G125: a different function
        ("STM32F103C8T6", ["STM32F103C8Tx"]),                                        # KiCad's trailing x stands for any character
    ],
)
def test_a_variant_differs_only_by_a_package_or_grade_code_never_by_a_function(marking: str, expected: list[str]) -> None:
    result = pl.lookup_part(marking)
    assert [m["name"] for m in result["matches"] if m["tier"] in {"exact", "variant"}][: len(expected)] == expected
    assert not [m for m in result["matches"] if m["tier"] == "variant" and m["name"] not in expected] or not expected
    if not expected:
        assert result["matches"] == [] and "start of many different parts" in (result["reason"] or "")


def test_a_family_member_never_differs_in_a_digit_from_the_marking() -> None:
    for marking in ("SN74LVC1G00", "74HC595", "LM358", "NE555"):
        for match in pl.lookup_part(marking)["matches"]:
            if match["tier"] == "family":
                common = next((i for i in range(min(len(match["name"]), len(marking))) if match["name"].lower()[i] != marking.lower()[i]), 0)
                assert not any(ch.isdigit() for ch in marking[common:] + match["name"][common:]), (marking, match["name"])


def test_only_the_supply_pins_are_measured_and_the_main_one_comes_first() -> None:
    reg = pl.power_gates("Regulator_Linear", "uA7805", "Package_TO_SOT_THT:TO-220-3_Vertical")
    assert [g["from"] for g in reg if g["kind"] == "voltage"] == ["pin 1 (IN)"]                    # the output pin is not what the chip is supplied by
    assert all("OUT" not in g["from"] and "VO)" not in g["from"] for g in pl.power_gates("Regulator_Linear", "AP1117-33", None))
    stm = pl.power_gates("MCU_ST_STM32F1", "STM32F103C8Tx", "Package_QFP:LQFP-48_7x7mm_P0.5mm")
    volts = [g for g in stm if g["kind"] == "voltage"]
    assert volts[0]["from"] == "pin 24 (VDD)"                  # not the battery-backup pin that happens to come first


def test_a_part_with_hundreds_of_pins_gets_no_guessed_measurements() -> None:
    assert pl.symbol_pins("FPGA_Lattice", "LFE5U-85F-8BG756x", limit=None)["pins_total"] == 756
    assert pl.power_gates("FPGA_Lattice", "LFE5U-85F-8BG756x", None) == []
    assert len(pl.symbol_pins("FPGA_Lattice", "LFE5U-85F-8BG756x")["pins"]) == pl.MAX_PINS        # the displayed list is still capped


def test_a_negative_supply_and_a_pad_check_use_the_ranked_ground() -> None:
    assert [g["to"] for g in pl.power_gates("Timer", "NE555P", None)] == ["pin 1 (GND)"] * 3


def test_one_unreadable_library_file_does_not_stop_the_others(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    symbols = tmp_path / "symbols"
    symbols.mkdir()
    (symbols / "aa.kicad_sym").write_bytes(b"\xff\xfe not utf-8 \xff")
    (symbols / "bb.kicad_sym").write_text('(kicad_symbol_lib (generator_version "9.0")\n\t(symbol "FOO123"\n\t\t(property "Value" "FOO123"\n\t\t)\n\t\t(property "Description" "A test part"\n\t\t)\n\t)\n)\n', encoding="utf-8")
    monkeypatch.setenv("HARDWARE_SPLICER_KICAD_DIR", str(tmp_path))
    pl.clear_cache()
    try:
        result = pl.lookup_part("FOO123")
        assert [m["name"] for m in result["matches"]] == ["FOO123"] and result["source"]["skipped_files"] == 1
    finally:
        monkeypatch.undo()
        pl.clear_cache()


def test_a_symbol_name_with_an_escaped_quote_is_still_indexed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    symbols = tmp_path / "symbols"
    symbols.mkdir()
    (symbols / "q.kicad_sym").write_text('(kicad_symbol_lib (generator_version "9.0")\n\t(symbol "FOO\\"BAR1"\n\t\t(property "Description" "Quoted"\n\t\t)\n\t)\n)\n', encoding="utf-8")
    monkeypatch.setenv("HARDWARE_SPLICER_KICAD_DIR", str(tmp_path))
    pl.clear_cache()
    try:
        assert [m["name"] for m in pl.lookup_part('FOO"BAR1')["matches"]] == ['FOO"BAR1']
    finally:
        monkeypatch.undo()
        pl.clear_cache()


# --- the third review (Grok): measurement order, package-aware pins, missing pairs ----------------------------------------------


def _kinds(gates: list[dict]) -> list[str]:
    return [g["kind"] for g in gates]


def _blob(gates: list[dict]) -> str:
    return " ".join(f"{g['instruction']} {g['expect']}" for g in gates)


def test_power_off_diode_and_ohms_come_before_any_voltage_and_never_power_the_board() -> None:
    gates = pl.power_gates("Regulator_Controller", "UC3842_DIP8", "Package_DIP:DIP-8_W7.62mm")
    assert _kinds(gates)[:2] == ["diode", "isolation"] and "voltage" in _kinds(gates)
    assert _kinds(gates).index("diode") < _kinds(gates).index("isolation") < _kinds(gates).index("voltage")
    text = _blob(gates)
    assert "powered the way it was originally" not in text
    assert "board's own supply" in text and "bench supply with a current limit" in text
    assert "mains-derived" not in text
    assert "not anything connected to the mains without isolation" in text
    assert "diode mode" in text.lower() or "in diode mode" in text
    assert "both ways" in text
    volt = next(g for g in gates if g["kind"] == "voltage")
    assert "Only after writing down the power-off readings" in volt["instruction"]
    assert not any(ch.isdigit() for ch in volt["expect"])


def test_ohms_does_not_call_a_low_reading_a_short() -> None:
    iso = next(g for g in pl.power_gates("Timer", "NE555P", "Package_DIP:DIP-8_W7.62mm") if g["kind"] == "isolation")
    text = iso["instruction"] + " " + iso["expect"]
    assert "near zero" not in text
    assert "every path in parallel" in text
    assert "both ways" in text
    assert "datasheet" in text or "known-good" in text


def test_package_aware_pick_uses_the_footprint_family_the_person_chose() -> None:
    matches = pl.lookup_part("ATMEGA328P")["matches"]
    picked = pl.pick_named_match(matches, "Package_DIP:DIP-8_W7.62mm")
    assert picked is not None and picked["name"] == "ATmega328P-P"
    assert pl.footprint_fits_user(picked["footprint"], "Package_DIP:DIP-8_W7.62mm")
    gates = pl.power_gates(picked["library"], picked["name"], picked["footprint"])
    assert any(g["from"] == "pin 7 (VCC)" for g in gates) and all(g["to"] == "pin 8 (GND)" for g in gates)
    wrong = pl.pick_named_match(matches, "Package_BGA:BGA-64_9.0x9.0mm_Layout10x10_P0.8mm")
    assert wrong is not None and not pl.footprint_fits_user(wrong["footprint"], "Package_BGA:BGA-64_9.0x9.0mm_Layout10x10_P0.8mm")
    lm = pl.pick_named_match(pl.lookup_part("LM317")["matches"], "Package_TO_SOT_THT:TO-220-3_Vertical")
    assert lm is not None and lm["name"] == "LM317_TO-220"
    mcp = pl.pick_named_match(pl.lookup_part("MCP73831")["matches"], "Package_TO_SOT_SMD:SOT-23")
    assert mcp is not None and mcp["name"].endswith("-OT")


def test_dual_supply_named_grounds_and_internal_pins() -> None:
    tl = pl.power_gates("Amplifier_Operational", "TL072", None)
    assert tl and all("V+" in g["from"] and "V-" in g["to"] for g in tl)
    assert pl.power_gates("Amplifier_Operational", "LM358", None)
    mcp = pl.power_gates("Battery_Management", "MCP73831-2-OT", "Package_TO_SOT_SMD:SOT-23-5")
    assert mcp and any("V_{DD}" in g["from"] and "V_{SS}" in g["to"] for g in mcp)
    lm = pl.power_gates("Regulator_Linear", "LM317_TO-220", "Package_TO_SOT_THT:TO-220-3_Vertical")
    assert lm and any("VI" in g["from"] and "VO" in g["to"] for g in lm)
    l298 = [g["from"] for g in pl.power_gates("Driver_Motor", "L298N", None) if g["kind"] == "voltage"]
    assert any("Vs" in f for f in l298) and any("Vss" in f for f in l298)
    assert all("SENSE" not in f for f in l298)
    tb = [g["from"] for g in pl.power_gates("Driver_Motor", "TB6612FNG", None) if g["kind"] == "voltage"]
    assert any("VCC" in f for f in tb) and any("VM" in f for f in tb)
    assert all("PGND" not in f for f in tb)
    drv = [g["from"] for g in pl.power_gates("Driver_Motor", "DRV8833PW", None) if g["kind"] == "voltage"]
    assert any("VM" in f for f in drv) and all("VINT" not in f for f in drv)


def test_pin_one_sentence_follows_jedec_and_names_packages_it_does_not_cover() -> None:
    dip = pl.power_gates("Timer", "NE555P", "Package_DIP:DIP-8_W7.62mm")[0]["instruction"]
    assert "dot or notch marks the pin-1 end" in dip
    assert "counter-clockwise" in dip and "underside" in dip
    assert "corner with the dot or notch" not in dip
    assert "pin-1 end" not in pl.power_gates("Timer", "NE555P", None)[0]["instruction"]
    to220 = _blob(pl.power_gates("Regulator_Linear", "uA7805", "Package_TO_SOT_THT:TO-220-3_Vertical"))
    assert "datasheet's package drawing" in to220 and "7805 vs LM317" in to220
    sot = _blob(pl.power_gates("Regulator_Linear", "TLV75518PDBV", "Package_TO_SOT_SMD:SOT-23-5"))
    assert "datasheet's package drawing" in sot
    module = _blob(pl.power_gates("RF_Module", "ESP32-WROOM-32", "RF_Module:ESP32-WROOM-32"))
    assert "numbered contacts" in module.lower() and "pin-1 mark" in module
    assert "row and column" not in module
    bga = _blob(pl.power_gates("Logic_LevelTranslator", "TXB0102YZP", "Package_BGA:Texas_DSBGA-8_0.9x1.9mm_Layout2x4_P0.5mm"))
    assert "row and column" in bga and "numbered contacts" not in bga.lower()


def test_courtyard_source_does_not_claim_it_is_a_little_larger_than_the_part() -> None:
    soic = pl.footprint_size("Package_SO:SOIC-8_3.9x4.9mm_P1.27mm")
    assert "courtyard" in soic["source"] and "may not be your exact package" in soic["source"]
    assert "a little larger" not in soic["source"]
    assert "a little larger" not in (pl.footprint_size.__doc__ or "")


def test_regulator_input_is_not_enough_and_enable_and_tab_are_mentioned() -> None:
    reg = pl.power_gates("Regulator_Linear", "uA7805", "Package_TO_SOT_THT:TO-220-3_Vertical")
    assert [g["from"] for g in reg if g["kind"] == "voltage"] == ["pin 1 (IN)"]
    assert "does not show what the output is doing" in _blob(reg)
    assert "metal tab is a terminal" in _blob(reg)
    tlv = _blob(pl.power_gates("Regulator_Linear", "TLV75518PDBV", "Package_TO_SOT_SMD:SOT-23-5"))
    assert "enable pin (EN)" in tlv


def test_split_rails_get_an_isolation_check_each_and_vref_is_not_a_supply() -> None:
    txb = pl.power_gates("Logic_LevelTranslator", "TXB0108PW", "Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm")
    iso = [g for g in txb if g["kind"] == "isolation"]
    assert len(iso) == 2
    assert any("V_{CCA}" in g["from"] for g in iso) and any("V_{CCB}" in g["from"] for g in iso)
    assert "must not be joined" not in _blob(iso)
    assert "separate pins to check each on its own" in _blob(iso)
    pca_pins = pl.symbol_pins("Interface", "PCA9306", limit=None)["pins"]
    assert any(pl._pin_token(p["name"]).startswith("VREF") and p["type"] == "power_in" for p in pca_pins)
    pca = pl.power_gates("Interface", "PCA9306", None)
    assert pca == []          # VREF pins are excluded by design: a part whose only supplies are VREF gets no gates


def test_cautions_sit_on_the_gates_they_belong_to() -> None:
    stm = _blob(pl.power_gates("MCU_ST_STM32F1", "STM32F103C8Tx", "Package_QFP:LQFP-48_7x7mm_P0.5mm"))
    assert "coin-cell backup" in stm
    vcap_pins = pl.symbol_pins("MCU_ST_STM32F4", "STM32F401CCFx", limit=None)["pins"]
    assert any(pl._pin_token(p["name"]) in {"VCAP", "VCAP1", "VCAP2"} for p in vcap_pins)
    assert all("VCAP" not in g["from"] for g in pl.power_gates("MCU_ST_STM32F4", "STM32F401CCFx", None))
    chg = _blob(pl.power_gates("Battery_Management", "TP4056-42-ESOP8", None))
    assert "Do not charge a cell" in chg
    motor = _blob(pl.power_gates("Driver_Motor", "DRV8833PW", None))
    assert "Motor drivers read low" not in motor
    assert "Windings attached to the outputs" in motor and "output stage's own diodes" in motor
    volt = next(g for g in pl.power_gates("Timer", "NE555P", None) if g["kind"] == "voltage")
    assert "Reversing the probes" not in volt["instruction"]
    assert "Connect a supply the right way round" in volt["instruction"]
    assert "reversing the supply on a chip can destroy it" in volt["instruction"]


def test_vregin_is_kept_and_exact_internal_names_are_dropped() -> None:
    pins = pl.symbol_pins("Interface_USB", "CP2102N-Axx-xQFN20", limit=None)["pins"]
    assert any(pl._pin_token(p["name"]) == "VREGIN" and p["type"] == "power_in" for p in pins)
    volts = [g["from"] for g in pl.power_gates("Interface_USB", "CP2102N-Axx-xQFN20", None) if g["kind"] == "voltage"]
    assert any("VREGIN" in f for f in volts) and any("VDD" in f for f in volts)
    drv = [g["from"] for g in pl.power_gates("Driver_Motor", "DRV8833PW", None) if g["kind"] == "voltage"]
    assert all("VINT" not in f for f in drv)


def test_isolated_domains_pair_each_supply_with_its_own_ground() -> None:
    gates = pl.power_gates("Isolator", "ISO1540", None)
    pairs = {(g["from"], g["to"]) for g in gates}
    assert ("pin 1 (VCC1)", "pin 4 (GND1)") in pairs
    assert ("pin 8 (VCC2)", "pin 5 (GND2)") in pairs
    assert all(g["to"] != "pin 4 (GND1)" or "VCC2" not in g["from"] for g in gates)


def test_numbered_duplicate_rails_collapse_and_six_voltage_gates_are_allowed() -> None:
    tb = [g["from"] for g in pl.power_gates("Driver_Motor", "TB6612FNG", None) if g["kind"] == "voltage"]
    assert any("VCC" in f for f in tb)
    vm = [f for f in tb if "VM" in f]
    assert len(vm) == 1
    esp = [g["from"] for g in pl.power_gates("MCU_Espressif", "ESP32-C3", None) if g["kind"] == "voltage"]
    assert any("VDDA" in f for f in esp)
    assert any("VDD3P3)" in f or f.endswith("VDD3P3)") for f in esp)
    assert len(esp) <= 6 and len(esp) >= 4


def test_a_prefix_match_does_not_claim_the_code_is_a_package_or_grade() -> None:
    matches = pl.lookup_part("ESP32")["matches"]
    names = {m["name"] for m in matches if m["tier"] == "variant"}
    assert {"ESP32-C3", "ESP32-S2"} <= names
    for match in matches:
        if match["tier"] == "variant":
            assert "a package, a grade or a different chip" in match["tier_text"]
            assert "different package or grade" not in match["tier_text"]


def test_resolve_lookup_gates_follows_the_chosen_package_and_warns_without_a_footprint() -> None:
    atmega = pl.lookup_part("ATMEGA328P")["matches"]
    dip = pl.resolve_lookup_gates(atmega, "DIP")
    assert dip["gates_from"] == "ATmega328P-P"
    assert any(g["from"] == "pin 7 (VCC)" for g in dip["gates"])
    assert dip["package_note"] is None
    unaware = pl.resolve_lookup_gates(atmega, None)
    assert unaware["gates_from"] == "ATmega328P-A"
    assert any(g["from"] == "pin 4 (VCC)" for g in unaware["gates"])
    tl = pl.resolve_lookup_gates(pl.lookup_part("TL071H")["matches"], "SOT-23")
    assert tl["gates_from"] == "TL071" and tl["gates"]
    assert tl["package_note"] and "does not say which package" in tl["package_note"]
    assert all("does not say which package" in g["instruction"] for g in tl["gates"])
    assert any("V+" in g["from"] for g in tl["gates"])


# --- sourced part-caution table -------------------------------------------------------------------------------------------


def _cautions(*args, **kwargs) -> str:
    return " ".join(pl.part_cautions(*args, **kwargs))


def test_mcp73831_cautions_name_the_charger_pins_and_skip_a_different_digit() -> None:
    text = _cautions("MCP73831-2-OT", tier="exact", library="Battery_Management")
    assert "Li-Ion" in text or "Li-Polymer" in text
    assert "VBAT" in text and "positive terminal" in text
    assert "STAT" in text and "status" in text
    assert "PROG" in text and "floating" in text
    assert "no cell connected" in text
    assert "Microchip MCP73831/2 datasheet DS20001984H" in text
    assert "General practice, not from the datasheet." in text
    assert "Li-Ion" not in _cautions("MCP73833", tier="exact")
    assert "PROG" not in _cautions("MCP73833", tier="exact")
    assert "Li-Ion" not in _cautions("MCP73831-2-OT", tier="family", library="Battery_Management")


def test_tb6612_cautions_keep_the_two_supplies_apart() -> None:
    text = _cautions("TB6612FNG", tier="exact", library="Driver_Motor")
    assert "Vcc" in text and "VM" in text
    assert "own range" in text
    assert "neither is fed from the other" in text or "do not feed one from the other" in text
    assert "Toshiba TB6612FNG datasheet" in text
    assert "Vcc" not in _cautions("TB6612FNG", tier="family")


def test_l298_cautions_say_sense_is_not_a_supply() -> None:
    text = _cautions("L298N", tier="exact", library="Driver_Motor")
    assert "SENSE" in text and "not supplies" in text
    assert "logic" in text.lower()
    assert "diode" in text.lower() and "inductive" in text.lower()
    assert "STMicroelectronics L298 datasheet" in text
    assert "SENSE" not in _cautions("L297", tier="exact")


def test_2n7002_cautions_name_the_body_diode_and_sot23_and_skip_2n7000() -> None:
    text = _cautions("2N7002", tier="exact")
    assert "body diode" in text.lower()
    assert "source" in text.lower() and "drain" in text.lower()
    assert "gate" in text.lower()
    assert "Diodes Incorporated 2N7002 datasheet DS11303" in text
    blob = _cautions("2N7000", tier="exact")
    assert "body diode" not in blob.lower()
    assert "DS11303" not in blob


def test_tip120_cautions_name_the_darlington_and_skip_a_different_digit() -> None:
    text = _cautions("TIP120", tier="exact")
    assert "Darlington" in text
    assert "shunt" in text.lower() or "resistor" in text.lower()
    assert "onsemi TIP120/121/122 datasheet" in text
    assert "Darlington" not in _cautions("TIP125", tier="exact")
    assert "Darlington" in _cautions("TIP122", tier="exact")


def test_irf840_cautions_name_the_body_diode() -> None:
    text = _cautions("IRF840", tier="exact")
    assert "body diode" in text.lower()
    assert "Vishay IRF840 datasheet" in text
    assert "body diode" not in _cautions("IRF840", tier="family").lower()


def test_nrf24l01_cautions_name_the_plus_document_and_power_outputs() -> None:
    text = _cautions("nRF24L01", tier="exact")
    assert "nRF24L01+" in text
    assert "chip actually in hand" in text or "chip in hand" in text
    assert "VDD_PA" in text and "DVDD" in text
    assert "power" in text.lower() and "output" in text.lower()
    assert "ANT1" in text and "ANT2" in text and "VDD_PA" in text
    assert "Nordic nRF24L01+ preliminary product specification" in text
    assert "VDD_PA" not in _cautions("nRF24L01", tier="family")


def test_every_datasheet_caution_has_quote_url_label_and_as_of() -> None:
    for entry in pl.load_part_cautions():
        assert entry["names"] and all(isinstance(pattern, str) for pattern in entry["names"])
        for caution in entry["cautions"]:
            assert caution["text"].strip()
            if caution["basis"] == "datasheet":
                assert caution["quote"].strip()
                source = caution["source"]
                assert source["url"].startswith(("http://", "https://"))
                assert source["label"].strip()
                assert source["as_of"] == "2026-10-11"


@pytest.mark.parametrize(
    "payload",
    [
        [{"names": ["^X"], "cautions": [{"basis": "general practice", "source": {"label": "x", "url": "https://example.com/x", "as_of": "2026-10-11"}}]}],
        [{"names": ["^X"], "cautions": [{"text": "x", "basis": "datasheet", "source": {"label": "x", "url": "https://example.com/x", "as_of": "2026-10-11"}}]}],
        [{"names": ["^X"], "cautions": [{"text": "x", "basis": "datasheet", "quote": "q", "source": {"url": "https://example.com/x", "as_of": "2026-10-11"}}]}],
        [{"names": ["^X"], "cautions": [{"text": "x", "basis": "datasheet", "quote": "q", "source": {"label": "x", "as_of": "2026-10-11"}}]}],
        [{"names": ["("], "cautions": [{"text": "x", "basis": "general practice"}]}],
        [{"names": ["^X"], "cautions": [{"text": "x", "basis": "general practice", "extra": 1}]}],
        [{"names": ["^X"], "oops": 1, "cautions": [{"text": "x", "basis": "general practice"}]}],
    ],
)
def test_the_caution_loader_rejects_each_malformed_shape(tmp_path: Path, payload: list) -> None:
    path = tmp_path / "part_cautions.json"
    path.write_text(__import__("json").dumps({"entries": payload}), encoding="utf-8")
    with pytest.raises(RuntimeError):
        pl.load_part_cautions(path)


def test_ball_grid_cautions_and_no_dip_style_pin_count() -> None:
    footprint = "Package_BGA:Texas_DSBGA-8_0.9x1.9mm_Layout2x4_P0.5mm"
    pins = [{"number": "A1", "name": "VCCA", "type": "power_in"}, {"number": "B2", "name": "GND", "type": "power_in"}]
    text = _cautions("TXB0102YZP", tier="exact", footprint=footprint, pins=pins)
    assert "cannot be probed" in text or "can't be probed" in text
    assert "DIP" in text
    assert "accessible pads" in text or "test points" in text
    assert "General practice, not from the datasheet." in text
    dip = _cautions("NE555P", tier="exact", footprint="Package_DIP:DIP-8_W7.62mm")
    assert "cannot be probed" not in dip and "can't be probed" not in dip
    bga = _blob(pl.power_gates("Logic_LevelTranslator", "TXB0102YZP", footprint))
    assert "dot or notch marks the pin-1 end" not in bga
    assert "first leg counter-clockwise" not in bga
    assert "row and column" in bga


def test_three_lead_sot23_uses_the_drawing_not_dip_wording() -> None:
    footprint = "Package_TO_SOT_SMD:SOT-23"
    text = _cautions("2N7002", tier="exact", footprint=footprint)
    assert "pin 1" in text.lower() and "left" in text
    assert "pin 2" in text.lower() and "right" in text
    assert "pin 3" in text.lower() or "single lead" in text
    assert "datasheet drawing" in text or "package drawing" in text
    three = pl._orientation(footprint)
    assert "dot or notch marks the pin-1 end" not in three
    assert "counter-clockwise" not in three
    assert "7805 vs LM317" not in three
    assert "pin 1" in three.lower() and "left" in three
    five = _blob(pl.power_gates("Regulator_Linear", "TLV75518PDBV", "Package_TO_SOT_SMD:SOT-23-5"))
    assert "dot or notch marks the pin-1 end" not in five
    assert "round the package" in five or "around the package" in five
    assert "datasheet's package drawing" in five
    assert "7805 vs LM317" not in five


def test_battery_management_outside_the_table_gets_the_generic_cell_caution() -> None:
    text = _cautions("TP4056-42-ESOP8", tier="exact", library="Battery_Management")
    assert "no cell connected" in text
    assert "fire" in text.lower()
    assert "General practice, not from the datasheet." in text
    named = _cautions("MCP73831-2-OT", tier="exact", library="Battery_Management")
    assert "fire" not in named.lower()          # the curated charger has its own no-cell line, not this generic


def test_separate_supply_pins_get_a_pointer_only_caution() -> None:
    pins = [
        {"number": "1", "name": "VDD", "type": "power_in"},
        {"number": "2", "name": "VDDA", "type": "power_in"},
        {"number": "3", "name": "VBAT", "type": "power_in"},
        {"number": "4", "name": "VDDIO", "type": "power_in"},
        {"number": "5", "name": "GND", "type": "power_in"},
    ]
    text = _cautions("STM32F103C8Tx", tier="exact", library="MCU_ST_STM32F1", pins=pins)
    assert "separate supply" in text
    assert "datasheet" in text.lower()
    assert "General practice, not from the datasheet." in text
    plain = _cautions("NE555P", tier="exact", library="Timer", pins=[{"number": "8", "name": "VCC", "type": "power_in"}, {"number": "1", "name": "GND", "type": "power_in"}])
    assert "separate supply" not in plain


def test_lookup_attaches_cautions_only_to_a_named_match() -> None:
    named = pl.lookup_part("MCP73831")
    assert named["cautions"]
    assert any("PROG" in row for row in named["cautions"])
    family = pl.lookup_part("W25Q128JWSIQ")
    assert family["matches"] and {m["tier"] for m in family["matches"]} == {"family"}
    assert family.get("cautions") in (None, [])
    resolved = pl.resolve_lookup_gates(named["matches"], None)
    assert resolved["cautions"]
    assert any("PROG" in row for row in resolved["cautions"])
    family_resolved = pl.resolve_lookup_gates(family["matches"], None)
    assert family_resolved.get("cautions") in (None, [])
