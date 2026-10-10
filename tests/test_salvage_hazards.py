"""Audit regressions for file and typed salvage plans; no HTTP or library lookup."""

from pathlib import Path

import pytest

from hardware_splicer.assembly_plan import _classify
from hardware_splicer.donor_capture import build_donor_salvage_plan
from hardware_splicer.salvage_plan import build_salvage_plan


@pytest.fixture(autouse=True)
def no_library(monkeypatch):
    monkeypatch.setattr("hardware_splicer.part_lookup.libraries_available", lambda: False)


def typed(kind, package, marking, ref="Z1"):
    return {"ref": ref, "kind": kind, "package": package, "marking": marking, "x_mm": 10, "y_mm": 10}


def donor(*parts):
    return build_donor_salvage_plan({"name": "Donor", "board": {"width_mm": 40, "length_mm": 30}, "parts": list(parts)})


def board(ref, footprint, value=""):
    return build_salvage_plan(
        '(kicad_pcb (version 20240108) (general (thickness 1.6))'
        '(gr_rect (start 0 0) (end 40 30) (layer "Edge.Cuts"))'
        f'(footprint "{footprint}" (layer "F.Cu") (at 10 10) (attr through_hole)'
        f'(property "Reference" "{ref}") (property "Value" "{value}")'
        '(fp_rect (start -1 -1) (end 1 1) (layer "F.CrtYd"))))'
    )


def advice(plan):
    return plan["parts"][0]["salvage"]


@pytest.mark.parametrize("marking", ["2kV", "0.1kV", "330WV", "330 WV", "HV", "high voltage", "microwave", "flash"])
def test_a2_a3_b2_b3_capacitor_markings_leave_the_part_in_place(marking):
    for plan in (donor(typed("capacitor", "film box", marking, "C1")), board("C1", "Capacitor_THT:C_Rect_L18", marking)):
        got = advice(plan)
        assert got["verdict"] == "skip" and got["hazards"]
        assert got["tool"] == "" and all("C1" not in s["refs"] for s in plan["steps"] if s["kind"] == "salvage")


@pytest.mark.parametrize("ref", ["X1", "CX1"])
def test_a1_file_capacitors_are_not_connectors_or_unclassified_parts(ref):
    plan = board(ref, "Capacitor_THT:C_Rect_L18", "275VAC X2")
    assert plan["parts"][0]["kind"] == "passive"
    assert advice(plan)["verdict"] == "skip" and advice(plan)["hazards"]


@pytest.mark.parametrize("package,marking", [("film box", "1uF"), ("ceramic disc", "222M"), ("ceramic disc", "")])
def test_a3_b6_unreadable_voltage_is_a_warning_not_a_guessed_rating(package, marking):
    got = advice(donor(typed("capacitor", package, marking, "C1")))
    assert got["verdict"] == "optional"
    assert "might be a mains safety capacitor" in " ".join(got["hazards"])
    assert "do not reuse" in " ".join(got["hazards"])


@pytest.mark.parametrize("marking,warning", [
    ("magnetron", "radiation"), ("CRT flyback", "charge"), ("anode", "charge"),
    ("CCFL", "mercury"), ("backlight", "lamp"), ("lamp", "break"),
    ("heater", "cool"), ("fuser", "cool"), ("thermal fuse", "bypass"),
    ("TCO", "bypass"), ("microwave", "capacitor"), ("HV diode", "high voltage"),
    ("MOT", "microwave"), ("high voltage", "high voltage"),
])
def test_a6_a7_b1_b2_b5_b7_b14_typed_hazards_override_other_and_wrong_kinds(marking, warning):
    for kind, package in [("other", "something else"), ("ic", "DIP"), ("connector", "USB")]:
        plan = donor(typed(kind, package, marking))
        got = advice(plan)
        assert got["verdict"] == "skip" and warning in " ".join(got["hazards"])
        assert got["tool"] == "" and [s["kind"] for s in plan["steps"]] == ["prepare", "finish"]


@pytest.mark.parametrize("ref,footprint,value,kind,warning,verdict", [
    ("T1", "MyLib:Flyback_EE25", "EE25", "other", "charge", "skip"),
    ("T1", "MyLib:EE16", "CCFL 1500V", "other", "mercury", "skip"),
    ("F1", "Fuse:ThermalFuse_L13", "10A 250V", "passive", "bypass", "skip"),
    ("Z1", "MyLib:Thermal_Cut-Off", "", "passive", "bypass", "skip"),
    ("K1", "MyLib:SRD-05VDC-SL-C", "", "other", "mains", "optional"),
    ("K1", "MyLib:Thing", "SONGLE SRD-05VDC-SL-C", "other", "mains", "optional"),
])
def test_a7_b7_b16_file_appliance_parts_get_their_kind_and_hazard(ref, footprint, value, kind, warning, verdict):
    plan = board(ref, footprint, value)
    assert plan["parts"][0]["kind"] == kind
    assert advice(plan)["verdict"] == verdict and warning in " ".join(advice(plan)["hazards"])


def test_a4_a5_b17_prepare_names_leftover_charge_before_iron_work():
    plan = donor(typed("capacitor", "electrolytic can", "47uF 400V", "C1"), typed("connector", "USB", "", "J1"))
    prep = plan["steps"][0]
    text = prep["instruction"]
    assert "C1" in text and "meter" in text and "prove" in text and "zero" in text
    assert "leave a resistor across" in text.lower() and "re-measure after a wait" in text and "come back" in text
    assert "do not wear a wrist strap near high voltage" in text
    assert "Use an anti-static strap" not in text
    assert any("J1" in s["refs"] and "iron" in s["instruction"] for s in plan["steps"][1:])
    assert "safe" not in prep["title"].lower()


@pytest.mark.parametrize("part", [
    typed("mains or power part", "relay", "", "K1"), typed("other", "something else", "HV", "Z1"),
    typed("capacitor", "film box", "", "C1"), typed("capacitor", "ceramic disc", "222M", "C1"),
    typed("capacitor", "electrolytic can", "330uF", "C1"),
])
def test_a5_mains_and_hv_context_also_remove_the_strap_suggestion(part):
    text = donor(part)["steps"][0]["instruction"]
    assert part["ref"] in text and "do not wear a wrist strap near high voltage" in text


def test_a9_mains_parts_point_at_capacitors_for_stored_charge():
    text = " ".join(advice(donor(typed("mains or power part", "transformer", "")))["hazards"])
    assert "capacitors" in text and "transformers and filter parts can hold energy" not in text.lower()


def test_a10_rating_is_a_leave_in_place_policy_not_a_claim_of_present_voltage():
    got = advice(donor(typed("capacitor", "electrolytic can", "400V", "C1")))
    assert "policy" in " ".join(got["reasons"])
    assert "not the voltage now present" in " ".join(got["reasons"])
    assert "if you decide to take it" in " ".join(got["hazards"])
    assert "prove zero" in " ".join(got["hazards"])


def test_a8_wide_terminal_is_never_worth_taking():
    got = advice(donor(typed("connector", "terminal block", "")))
    assert got["verdict"] == "optional" and "mains" in " ".join(got["hazards"])


@pytest.mark.parametrize("pitch", ["5.00", "6.35", "8.00", "12.00"])
def test_a8_explicit_pitch_above_the_documented_cutoff_is_not_a_keeper(pitch):
    got = advice(board("J1", f"TerminalBlock:TerminalBlock_Custom_P{pitch}mm"))
    assert got["verdict"] == "optional" and "mains" in " ".join(got["hazards"])


def test_a11_docs_and_file_limits_include_the_capture_path():
    root = Path(__file__).resolve().parents[1]
    text = (root / "docs/SALVAGE_PLAN.md").read_text()
    assert "no capture path yet" not in text and "/engineering/donor" in text
    assert any("typed capture" in limit for limit in board("R1", "Resistor:R_0805")["limits"])


def test_a12_aa_holder_does_not_claim_lithium():
    got = advice(board("BT1", "Battery:BatteryHolder_Keystone_2460_1xAA"))
    assert "lithium" not in " ".join(got["hazards"])
    assert "cell" in " ".join(got["hazards"]) and "heat" in " ".join(got["hazards"])


@pytest.mark.parametrize("marking", ["lithium pouch", "swollen Li-ion", "vape battery", "tool battery pack"])
def test_b4_cells_marked_as_other_are_never_heated(marking):
    got = advice(donor(typed("other", "something else", marking)))
    assert got["verdict"] == "skip"
    text = " ".join(got["hazards"])
    assert "tape" in text and "do not puncture" in text and "do not solder" in text


def test_b4_xt60_means_the_pack_may_still_be_live():
    for plan in (donor(typed("connector", "other connector", "XT60", "J1")), board("J1", "Connector_AMASS:XT60")):
        assert "pack may still be live" in " ".join(advice(plan)["hazards"])
        assert "disconnect" in plan["steps"][0]["instruction"].lower()


def test_b8_supercapacitor_short_and_jewellery_warning():
    text = " ".join(advice(board("C1", "Capacitor_SMD:C_EDLC_D10mm", "100F 2.7V"))["hazards"])
    assert "remove jewellery" in text and "do not short" in text


@pytest.mark.parametrize("marking,warning", [("supercapacitor 100F 2.7V", "remove jewellery"), ("tantalum 47uF 16V", "reverse polarity destroys it")])
def test_b8_b9_typed_capacitor_words_also_work_without_a_package_menu_entry(marking, warning):
    got = advice(donor(typed("other", "something else", marking)))
    assert got["verdict"] == "test_first" and warning in " ".join(got["hazards"])


def test_b9_tantalum_wrong_polarity_destroys_it():
    text = " ".join(advice(donor(typed("capacitor", "tantalum", "47uF 16V")))["hazards"])
    assert "reverse polarity destroys it" in text


def test_b10_electrolytic_damage_is_a_discard_condition():
    text = " ".join(advice(donor(typed("capacitor", "electrolytic can", "1000uF 25V")))["hazards"])
    assert "bulged or leaking" in text and "discard" in text
    got = advice(donor(typed("capacitor", "electrolytic can", "bulged 25V")))
    assert got["verdict"] == "skip" and "discard" in " ".join(got["reasons"])


@pytest.mark.parametrize("marking", ["PC817", "VO617A", "LTV817"])
def test_b11_optocoupler_verdict_has_no_isolation_claim(marking):
    got = advice(donor(typed("ic", "DIP", marking)))
    assert got["verdict"] == "keep"
    text = " ".join(got["hazards"])
    assert "isolation barrier only within its ratings" in text and "used one is not known" in text


def test_b12_varistor_is_not_advice_to_put_it_back_on_mains():
    text = " ".join(advice(donor(typed("mains or power part", "varistor", "")))["hazards"])
    assert "do not put" in text and "back on mains" in text


@pytest.mark.parametrize("ref,footprint", [("RT1", "Thermistor:Thermistor_NTC"), ("TH1", "Device:R_NTC_0805")])
def test_b13_thermistors_get_a_generic_hot_surface_note(ref, footprint):
    text = " ".join(advice(board(ref, footprint))["hazards"])
    assert "hot" in text and "cool" in text


@pytest.mark.parametrize("marking", ["IRF840", "LNK304P", "TNY267", "TOP223", "VIPer22A", "UC3842", "MOSFET 600V", "NCP1200", "ICE2A165"])
def test_b15_mains_side_silicon_keeps_verdict_with_generic_context(marking):
    got = advice(donor(typed("ic", "TO-220", marking)))
    assert got["verdict"] == ("identify" if " " in marking else "keep")
    assert "may have sat on a mains primary" in " ".join(got["hazards"])


def test_b18_surge_parts_get_only_a_generic_protection_note():
    text = " ".join(advice(board("GDT1", "Spark_Gap:Gas_Discharge_Tube_2pin"))["hazards"])
    assert "used surge protector" in text and "do not rely" in text


def test_no_test_instruction_invents_a_capacitor_reading():
    plan = donor(typed("capacitor", "electrolytic can", "470uF 16V"))
    checks = [c for s in plan["steps"] for c in s["checks"] if c["check"] == "test"]
    assert all("close to the printed value" not in c["expect"] for c in checks)


def test_classification_preserves_an_x_connector_without_capacitor_footprint():
    assert _classify("X1", "Connector:PinHeader") == "connector"


def test_a3_b6_each_removal_group_keeps_its_own_hazards():
    plan = donor(typed("capacitor", "film box", "16V", "C1"), typed("capacitor", "film box", "", "C2"))
    step = next(s for s in plan["steps"] if s["kind"] == "salvage" and "C2" in s["refs"])
    assert "might be a mains safety capacitor" in step["instruction"].lower()
    assert "C1" not in step["refs"]


def test_a5_design_omissions_do_not_add_fitted_hazards():
    from hardware_splicer.salvage_plan import plan_from_assembly
    plan = board("C1", "Capacitor_THT:CP_Radial", "400V")
    plan["parts"][0]["do_not_populate"] = True
    plan["not_fitted"] = ["C1"]
    result = plan_from_assembly(plan)
    assert "Use an anti-static strap" in result["steps"][0]["instruction"]
    assert "C1" not in result["steps"][0]["instruction"]


def test_b3_unmarked_polarised_can_names_possible_flash_charge():
    text = " ".join(advice(donor(typed("capacitor", "electrolytic can", "330uF")))["hazards"])
    assert "could be a photoflash" in text and "prove zero with a meter" in text
