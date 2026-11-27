"""Checking parts against distributor records, with a fake distributor so no test touches the network."""

from __future__ import annotations

import pytest

from hardware_splicer.distributor_check import _package, _value, check_components

RECORDS = {
    "C25905": {"code": "C25905", "found": True, "model": "0402WGF5101TCE", "package": "0402", "name": "RES 5.1kΩ ±1% 62.5mW 0402",
               "stock": 2161600, "params": {"Resistance": "5.1kΩ"}, "fetched": "2026-11-26"},
    "C25804": {"code": "C25804", "found": True, "model": "0603WAF1002T5E", "package": "0603", "name": "RES 10kΩ ±1% 100mW 0603",
               "stock": 0, "params": {"Resistance": "10kΩ"}, "fetched": "2026-11-26"},
    "C82942": {"code": "C82942", "found": True, "model": "ME6211C33M5G-N", "package": "SOT-23-5", "name": "LDO", "stock": 5,
               "params": {}, "fetched": "2026-11-26"},
    "C1": {"code": "C1", "found": False, "model": None, "package": None, "name": None, "stock": None, "params": {}, "fetched": "2026-11-26"},
}


def comp(value, footprint, **fields):
    return {"value": value, "footprint": footprint, "fields": fields}


def rules(components):
    return sorted((f["rule"], f["components"][0]) for f in check_components(components, RECORDS.get)["findings"])


def test_a_part_that_matches_its_record_passes():
    assert rules({"R14": comp("5.1k", "Resistor_SMD:R_0402_1005Metric", **{"LCSC Part": "C25905"}),
                  "U1": comp("ME6211C33", "Package_TO_SOT_SMD:SOT-23-5", LCSC="C82942")}) == []


def test_a_code_for_another_package_or_value_is_caught():
    """The class of mistake Nihil.sh reports catching: a code that resolves to an 0603 part on 0402 pads."""
    found = rules({"R1": comp("5.1k", "Resistor_SMD:R_0402_1005Metric", LCSC="C25804")})
    assert found == [("out_of_stock", "R1"), ("package_mismatch", "R1"), ("value_mismatch", "R1")]


def test_unknown_codes_and_other_mpns_are_reported_and_parts_without_codes_skipped():
    report = check_components({"R2": comp("10k", "Resistor_SMD:R_0603_1608Metric", LCSC="C1"),
                               "U1": comp("LDO", "Package_TO_SOT_SMD:SOT-23-5", LCSC="C82942", MPN="AP2112K-3.3TRG1"),
                               "J1": comp("USB_C", "Connector_USB:USB_C_Receptacle_GCT_USB4105")}, RECORDS.get)
    assert sorted(f["rule"] for f in report["findings"]) == ["code_not_found", "mpn_differs"]
    assert report["parts_with_codes"] == 2 and report["parts_without_codes"] == 1


def test_package_and_value_vocabulary():
    assert _package("Package_SO:SOIC-8_3.9x4.9mm_P1.27mm") == _package("SOP-8") == "SOIC-8"
    assert _package("Package_DFN_QFN:QFN-56-1EP_7x7mm_P0.4mm") == _package("LQFN-56(7x7)") == "QFN-56"
    assert _package("Package_TO_SOT_SMD:SOT-23") == _package("SOT-23-3") == "SOT-23"
    assert _package("SMD") is None and _package("Connector_USB:USB_C_Receptacle_GCT_USB4105") is None
    assert _value("4k7", "") == pytest.approx(4700) and _value("0.1u", "F") == pytest.approx(_value("100nF", "F"))
    assert _value("2u2", "F") == pytest.approx(2.2e-6)
    assert _value("DNP", "") is None
    assert _value("22 µF", "F") == pytest.approx(22e-6) and _value("100 nF", "F") == pytest.approx(1e-7)  # amachronic/echoplayer
    assert _value("4.7 μH", "H") == pytest.approx(4.7e-6)


def test_one_outline_under_several_names_is_not_a_mismatch():
    """LCSC writes SOT-23-6L for USBLC6-2SC6 (C7519) and SC-70-6 for INA186 (C2058245); KiCad names SOT-23-6 and SOT-363."""
    assert _package("Package_TO_SOT_SMD:SOT-23-6") == _package("SOT-23-6L") == "SOT-23-6"
    assert _package("lib:SOT-363_SC-70-6") == _package("SC-70-6") == _package("SC-88") == "SOT-363"
    assert _package("SOT-23-6L") != _package("SOT-23")


def test_a_listing_that_contradicts_itself_is_a_note_not_an_error():
    """C552486 lists package SC-70 while its name says SOT-23; the board's SOT-23 footprint is not judged on it."""
    record = {"code": "C552486", "found": True, "model": "PESD2CANFD24V-TR", "package": "SC-70", "name": "ESD DIODE 24VWM 42VC SOT-23",
              "stock": 10, "params": {}, "fetched": "2026-11-26"}
    report = check_components({"D8": comp("PESD2CANFD24V", "Package_TO_SOT_SMD:SOT-23", LCSC="C552486")}, {"C552486": record}.get)
    assert [(f["rule"], f["severity"]) for f in report["findings"]] == [("listing_inconsistent", "info")]
