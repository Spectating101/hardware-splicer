from __future__ import annotations

import socket
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from hardware_splicer.bom_generator import enrich_bom_with_jlcsearch
from hardware_splicer.parts_intel import (
    JlcEnrichProvider,
    LOOKUP_EXECUTOR_WORKERS,
    LOOKUP_THREAD_PREFIX,
    OfflineCatalogProvider,
    _catalog_match,
    build_bom,
    clear_lookup_cache,
    enrich_bom,
    extract_components,
    parts_providers_from_env,
    set_parts_intel_clock,
)

REPO = Path(__file__).resolve().parents[1]
SCH = REPO / "hardware" / "reference_designs" / "spi_flash_adapter_v1" / "spi_flash_adapter_v1.kicad_sch"

EXPECTED_REFS = [
    "J1",
    "U1",
    "U2",
    "U3",
    "R1",
    "R2",
    "R3",
    "R4",
    "R5",
    "R6",
    "R7",
    "JP1",
    "C1",
    "C2",
    "C3",
    "C4",
    "C5",
    "C6",
    "TP1",
    "TP2",
    "TP3",
    "TP4",
    "TP5",
    "TP6",
    "TP7",
    "TP8",
    "TP9",
    "TP10",
    "TP11",
    "TP12",
    "TP13",
    "TP14",
    "TP15",
    "TP16",
    "TP17",
    "TP18",
    "#FLG01",
    "#FLG02",
    "#FLG03",
    "#FLG04",
]

EXPECTED_BY_REF = {
    "J1": ("HOST_SPI_1x06", "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical"),
    "U1": ("TXU0304PWR", "Package_SO:TSSOP-14_4.4x5mm_P0.65mm"),
    "U2": ("W25Q128JWSIQ", "Package_SO:SOIC-8_5.3x5.3mm_P1.27mm"),
    "U3": ("TLV75518PDBVR", "Package_TO_SOT_SMD:SOT-23-5"),
    "R1": ("0R", "Resistor_SMD:R_0603_1608Metric"),
    "R2": ("10k", "Resistor_SMD:R_0603_1608Metric"),
    "R3": ("10k", "Resistor_SMD:R_0603_1608Metric"),
    "R4": ("0R", "Resistor_SMD:R_0603_1608Metric"),
    "R5": ("10k", "Resistor_SMD:R_0603_1608Metric"),
    "R6": ("10k", "Resistor_SMD:R_0603_1608Metric"),
    "R7": ("10k", "Resistor_SMD:R_0603_1608Metric"),
    "JP1": ("ENABLE_AFTER_RAIL_CHECK", "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"),
    "C1": ("1uF 10V X7R", "Capacitor_SMD:C_0603_1608Metric"),
    "C2": ("4.7uF 6.3V X5R", "Capacitor_SMD:C_0603_1608Metric"),
    "C3": ("100nF 16V X7R", "Capacitor_SMD:C_0603_1608Metric"),
    "C4": ("100nF 16V X7R", "Capacitor_SMD:C_0603_1608Metric"),
    "C5": ("100nF 16V X7R", "Capacitor_SMD:C_0603_1608Metric"),
    "C6": ("1uF 10V X7R", "Capacitor_SMD:C_0603_1608Metric"),
    "TP1": ("HOST_3V3", "TestPoint:TestPoint_Pad_D1.5mm"),
    "TP10": ("DUT_CS_N", "TestPoint:TestPoint_Pad_D1.5mm"),
    "#FLG01": ("PWR_FLAG", None),
}


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _blocked(self: socket.socket, *args: Any, **kwargs: Any) -> None:
        raise OSError("network disabled in parts intelligence tests")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    clear_lookup_cache()


def _sch() -> str:
    return SCH.read_text(encoding="utf-8")


def test_reference_schematic_component_count_refs_values_footprints() -> None:
    components = extract_components(_sch())
    assert len(components) == 40
    assert [row["ref"] for row in components] == EXPECTED_REFS
    by_ref = {row["ref"]: row for row in components}
    for ref, (value, footprint) in EXPECTED_BY_REF.items():
        assert by_ref[ref]["value"] == value
        assert by_ref[ref]["footprint"] == footprint
    assert by_ref["R1"]["dnp"] is True
    assert by_ref["R4"]["dnp"] is True
    assert by_ref["R2"]["dnp"] is False
    assert by_ref["R2"]["in_bom"] is True
    assert by_ref["TP1"]["in_bom"] is False
    assert by_ref["TP1"]["on_board"] is True
    assert by_ref["U1"]["lib_id"] == "HardwareSplicer:TXU0304PW"
    assert by_ref["U1"]["uuid"] == "7e272ad8-21c3-43f2-9c57-c27614fcbb47"


def test_mpn_only_from_explicit_properties_never_from_value() -> None:
    original = extract_components(_sch())
    by_ref = {row["ref"]: row for row in original}
    assert by_ref["U1"]["mpn"] == "TXU0304PWR"
    assert by_ref["U1"]["mpn_source"] == "property:MPN"
    assert by_ref["U1"]["manufacturer"] == "Texas Instruments"
    assert by_ref["TP1"]["mpn"] is None
    assert by_ref["TP1"]["mpn_source"] is None

    stripped = _sch().replace('\t\t(property "MPN" "TXU0304PWR"', '\t\t(property "KiCadValue" "not-an-mpn"', 1)
    without = {row["ref"]: row for row in extract_components(stripped)}
    assert without["U1"]["value"] == "TXU0304PWR"
    assert without["U1"]["mpn"] is None
    assert without["U1"]["mpn_source"] is None

    injected = stripped.replace(
        '\t\t(uuid "216011bc-1323-4701-9051-f4001b15eefb")\n'
        '\t\t(property "Reference" "#FLG01"',
        '\t\t(uuid "216011bc-1323-4701-9051-f4001b15eefb")\n'
        '\t\t(property "MPN" "TXU0304PWR"\n\t\t\t(at 0 0 0)\n\t\t)\n'
        '\t\t(property "Reference" "#FLG01"',
        1,
    )
    added = {row["ref"]: row for row in extract_components(injected)}
    assert added["#FLG01"]["mpn"] == "TXU0304PWR"
    assert added["#FLG01"]["mpn_source"] == "property:MPN"
    assert added["#FLG01"]["value"] == "PWR_FLAG"


def test_dnp_and_in_bom_from_text_replace() -> None:
    edited = _sch().replace(
        '\t\t(uuid "b7db2b3d-a7bd-4166-951c-4a75126f75bc")\n'
        '\t\t(property "Reference" "R2"',
        '\t\t(uuid "b7db2b3d-a7bd-4166-951c-4a75126f75bc")\n'
        '\t\t(property "Reference" "R2"',
        1,
    )
    edited = edited.replace(
        '\t\t(lib_id "Device:R")\n'
        "\t\t(at 185.42 82.55 0)\n"
        "\t\t(unit 1)\n"
        "\t\t(exclude_from_sim no)\n"
        "\t\t(in_bom yes)\n"
        "\t\t(on_board yes)\n"
        "\t\t(dnp no)",
        '\t\t(lib_id "Device:R")\n'
        "\t\t(at 185.42 82.55 0)\n"
        "\t\t(unit 1)\n"
        "\t\t(exclude_from_sim no)\n"
        "\t\t(in_bom no)\n"
        "\t\t(on_board yes)\n"
        "\t\t(dnp yes)",
        1,
    )
    by_ref = {row["ref"]: row for row in extract_components(edited)}
    assert by_ref["R2"]["dnp"] is True
    assert by_ref["R2"]["in_bom"] is False
    assert by_ref["R3"]["dnp"] is False
    assert by_ref["R3"]["in_bom"] is True


def test_build_bom_groups_quantities_and_natural_ref_sort() -> None:
    result = build_bom(extract_components(_sch()))
    groups = result["groups"]
    ten_k = next(
        group
        for group in groups
        if group["value"] == "10k" and group["footprint"] == "Resistor_SMD:R_0603_1608Metric"
    )
    assert ten_k["quantity"] == 5
    assert ten_k["refs"] == ["R2", "R3", "R5", "R6", "R7"]
    assert ten_k["mpn"] == "RC0603FR-0710KL"
    assert ten_k["manufacturer"] == "Yageo"
    assert ten_k["missing_mpn"] is False
    assert ten_k["dnp"] is False

    dnp_zero = next(group for group in groups if group["value"] == "0R")
    assert dnp_zero["refs"] == ["R1", "R4"]
    assert dnp_zero["quantity"] == 2
    assert dnp_zero["dnp"] is True

    flags = next(group for group in groups if group["value"] == "PWR_FLAG")
    assert flags["refs"] == ["#FLG01", "#FLG02", "#FLG03", "#FLG04"]
    assert flags["missing_mpn"] is True
    assert flags["mpn"] is None
    assert flags["manufacturer"] is None

    u1 = next(group for group in groups if "U1" in group["refs"])
    assert u1["manufacturer"] == "Texas Instruments"

    tp_gnd = next(group for group in groups if group["value"] == "GND" and group["not_in_bom"] is True)
    assert tp_gnd["refs"] == ["TP4", "TP17", "TP18"]
    assert "R10" not in str(ten_k["refs"])

    mixed_order = build_bom(
        [
            {
                "ref": "R10",
                "uuid": "a",
                "value": "10k",
                "lib_id": "Device:R",
                "footprint": "R_0603",
                "datasheet": None,
                "dnp": False,
                "in_bom": True,
                "on_board": True,
                "properties": {},
                "mpn": None,
                "manufacturer": None,
                "lcsc": None,
                "mpn_source": None,
            },
            {
                "ref": "R2",
                "uuid": "b",
                "value": "10k",
                "lib_id": "Device:R",
                "footprint": "R_0603",
                "datasheet": None,
                "dnp": False,
                "in_bom": True,
                "on_board": True,
                "properties": {},
                "mpn": None,
                "manufacturer": None,
                "lcsc": None,
                "mpn_source": None,
            },
        ]
    )
    assert mixed_order["groups"][0]["refs"] == ["R2", "R10"]

    summary = result["summary"]
    assert summary["components"] == 40
    assert summary["groups"] == len(groups)
    assert summary["unique_mpns"] == 10
    assert summary["dnp_components"] == 2
    assert summary["excluded_components"] == 18
    assert summary["missing_mpn_groups"] >= 1
    tp_group = next(group for group in groups if "TP1" in group["refs"])
    assert tp_group["missing_mpn"] is True
    assert tp_group["not_in_bom"] is True


class _FakeProvider:
    def __init__(self, name: str, result: Any = None, *, error: Exception | None = None, delay_s: float = 0) -> None:
        self.name = name
        self.result = result
        self.error = error
        self.delay_s = delay_s
        self.calls: list[dict[str, Any]] = []

    def lookup(self, query: dict[str, Any], *, timeout_s: float) -> dict[str, Any] | None:
        self.calls.append({"query": dict(query), "timeout_s": timeout_s})
        if self.delay_s:
            time.sleep(self.delay_s)
        if self.error is not None:
            raise self.error
        return self.result


def test_enrich_success_no_data_exception_timeout_limit_and_cache() -> None:
    groups = [
        {
            "value": "TXU0304PWR",
            "footprint": "TSSOP-14",
            "mpn": "TXU0304PWR",
            "lcsc": None,
            "dnp": False,
            "quantity": 1,
            "refs": ["U1"],
            "missing_mpn": False,
            "not_in_bom": False,
        },
        {
            "value": "same",
            "footprint": "other",
            "mpn": "TXU0304PWR",
            "lcsc": None,
            "dnp": False,
            "quantity": 1,
            "refs": ["U99"],
            "missing_mpn": False,
            "not_in_bom": False,
        },
        {
            "value": "empty",
            "footprint": "x",
            "mpn": "NO-DATA-MPN",
            "lcsc": None,
            "dnp": False,
            "quantity": 1,
            "refs": ["R1"],
            "missing_mpn": False,
            "not_in_bom": False,
        },
        {
            "value": "boom",
            "footprint": "x",
            "mpn": "BOOM-MPN",
            "lcsc": None,
            "dnp": False,
            "quantity": 1,
            "refs": ["R2"],
            "missing_mpn": False,
            "not_in_bom": False,
        },
        {
            "value": "slow",
            "footprint": "x",
            "mpn": "SLOW-MPN",
            "lcsc": None,
            "dnp": False,
            "quantity": 1,
            "refs": ["R3"],
            "missing_mpn": False,
            "not_in_bom": False,
        },
        {
            "value": "limit",
            "footprint": "x",
            "mpn": "LIMIT-MPN",
            "lcsc": None,
            "dnp": False,
            "quantity": 1,
            "refs": ["R4"],
            "missing_mpn": False,
            "not_in_bom": False,
        },
    ]
    record = {
        "source": "fake-ok",
        "as_of": "2026-10-06T00:00:00+00:00",
        "lifecycle": "active",
        "stock": 12,
        "price_breaks": [{"qty": 1, "unit_price": 0.5, "currency": "USD"}],
        "datasheet_url": "https://example.test/txu.pdf",
        "alternates": [{"mpn": "TXU0304BQBR", "manufacturer": "TI", "reason": "same family"}],
        "package": "TSSOP-14",
    }

    def _route(query: dict[str, Any], *, timeout_s: float) -> dict[str, Any] | None:
        mpn = query.get("mpn")
        if mpn == "TXU0304PWR":
            return record
        if mpn == "NO-DATA-MPN":
            return None
        if mpn == "BOOM-MPN":
            raise RuntimeError("provider exploded")
        if mpn == "SLOW-MPN":
            time.sleep(0.25)
            return record
        return record

    class Router:
        name = "router"
        calls: list[str] = []

        def lookup(self, query: dict[str, Any], *, timeout_s: float) -> dict[str, Any] | None:
            mpn = str(query.get("mpn") or "")
            Router.calls.append(mpn)
            return _route(query, timeout_s=timeout_s)

    Router.calls = []
    enriched = enrich_bom(groups, [Router()], timeout_s=0.05, max_lookups=4)
    by_mpn = {group["mpn"]: group for group in enriched}
    ok = by_mpn["TXU0304PWR"]["availability"]
    assert ok["status"] == "checked"
    assert ok["records"][0]["source"] == "fake-ok"
    assert ok["records"][0]["as_of"] == "2026-10-06T00:00:00+00:00"
    assert ok["records"][0]["lifecycle"] == "active"
    assert ok["records"][0]["stock"] == 12
    assert Router.calls.count("TXU0304PWR") == 1

    assert by_mpn["NO-DATA-MPN"]["availability"]["status"] == "no_data"
    failed = by_mpn["BOOM-MPN"]["availability"]
    assert failed["status"] == "lookup_failed"
    assert "exploded" in str(failed.get("reason") or "")
    assert "/" not in str(failed.get("reason") or "")

    timed = by_mpn["SLOW-MPN"]["availability"]
    assert timed["status"] == "lookup_failed"
    assert "timeout" in str(timed.get("reason") or "").lower()

    limited = by_mpn["LIMIT-MPN"]["availability"]
    assert limited["status"] == "not_checked"
    assert limited.get("note") == "lookup limit reached"


def test_offline_catalog_provider_uses_repo_data_only() -> None:
    provider = OfflineCatalogProvider()
    hit = provider.lookup({"mpn": "INA219"}, timeout_s=1.0)
    assert hit is not None
    assert hit["source"] == "hardware-splicer-catalog"
    assert hit["as_of"]
    assert hit["datasheet_url"] == "https://learn.adafruit.com/adafruit-ina219-current-sensor-breakout/pinouts"
    missing = provider.lookup({"mpn": "NOT-A-REAL-CATALOG-PART"}, timeout_s=1.0)
    assert missing is None


def test_catalog_match_requires_mpn_or_lcsc(monkeypatch: pytest.MonkeyPatch) -> None:
    library = {
        "solo": {
            "id": "solo",
            "partNumber": "ABC123",
            "manufacturer": "Acme",
            "datasheetUrl": "https://example.test/acme.pdf",
            "lcsc": "C555",
        },
        "nomfr": {
            "id": "nomfr",
            "partNumber": "XYZ999",
            "datasheetUrl": "https://example.test/xyz.pdf",
        },
    }
    monkeypatch.setattr("hardware_splicer.parts_intel._load_library", lambda: library)
    monkeypatch.setattr("hardware_splicer.parts_intel._PART_HINTS", {})
    provider = OfflineCatalogProvider()

    assert _catalog_match(mpn=None, manufacturer="Acme", lcsc=None) is None
    assert _catalog_match(mpn="ABC123", manufacturer=None) is not None
    assert _catalog_match(mpn="ABC123", manufacturer="Acme") is not None
    assert _catalog_match(mpn="ABC123", manufacturer="Nexperia") is None
    assert _catalog_match(mpn="XYZ999", manufacturer=None) is not None
    assert _catalog_match(mpn="XYZ999", manufacturer="Acme") is None
    assert _catalog_match(mpn=None, manufacturer=None, lcsc="C555") is not None
    assert _catalog_match(mpn=None, manufacturer="Acme", lcsc="C555") is not None
    assert _catalog_match(mpn=None, manufacturer="Nexperia", lcsc="C555") is None

    assert provider.lookup({"manufacturer": "Acme"}, timeout_s=1.0) is None
    assert provider.lookup({"mpn": "ABC123"}, timeout_s=1.0) is not None
    assert provider.lookup({"mpn": "ABC123", "manufacturer": "Acme"}, timeout_s=1.0) is not None
    assert provider.lookup({"mpn": "ABC123", "manufacturer": "Nexperia"}, timeout_s=1.0) is None
    assert provider.lookup({"mpn": "XYZ999"}, timeout_s=1.0) is not None
    assert provider.lookup({"mpn": "XYZ999", "manufacturer": "Acme"}, timeout_s=1.0) is None
    assert provider.lookup({"lcsc": "C555"}, timeout_s=1.0) is not None
    assert provider.lookup({"lcsc": "C555", "manufacturer": "Acme"}, timeout_s=1.0) is not None
    assert provider.lookup({"lcsc": "C555", "manufacturer": "Nexperia"}, timeout_s=1.0) is None

    group = {
        "value": "x",
        "footprint": "x",
        "mpn": "NO-SUCH-MPN",
        "lcsc": None,
        "manufacturer": "Acme",
        "dnp": False,
        "quantity": 1,
        "refs": ["U1"],
        "missing_mpn": False,
        "not_in_bom": False,
    }
    enriched = enrich_bom([group], [provider], timeout_s=1.0)
    assert enriched[0]["availability"]["status"] == "no_data"


def test_provider_record_without_source_or_as_of_is_dropped() -> None:
    note = "provider returned a record without source and date"

    class Fake:
        def __init__(self, name: str, payload: dict[str, Any]) -> None:
            self.name = name
            self.payload = payload

        def lookup(self, query: dict[str, Any], *, timeout_s: float) -> dict[str, Any] | None:
            return dict(self.payload)

    def _group(mpn: str) -> dict[str, Any]:
        return {
            "value": mpn,
            "footprint": "x",
            "mpn": mpn,
            "lcsc": None,
            "manufacturer": None,
            "dnp": False,
            "quantity": 1,
            "refs": ["U1"],
            "missing_mpn": False,
            "not_in_bom": False,
        }

    base = {
        "lifecycle": "active",
        "stock": 1,
        "price_breaks": None,
        "datasheet_url": None,
        "alternates": [],
        "package": None,
    }
    no_source = enrich_bom(
        [_group("NO-SOURCE-MPN")],
        [Fake("no-source", {**base, "as_of": "2026-10-06T00:00:00+00:00"})],
        timeout_s=1.0,
    )[0]
    assert no_source["availability"]["status"] == "lookup_failed"
    assert no_source["availability"]["note"] == note
    assert no_source["availability"]["records"] == []
    assert no_source["availability"].get("source") != "no-source"

    no_as_of = enrich_bom(
        [_group("NO-ASOF-MPN")],
        [Fake("no-asof", {**base, "source": "fake"})],
        timeout_s=1.0,
    )[0]
    assert no_as_of["availability"]["status"] == "lookup_failed"
    assert no_as_of["availability"]["note"] == note

    bad_as_of = enrich_bom(
        [_group("BAD-ASOF-MPN")],
        [Fake("bad-asof", {**base, "source": "fake", "as_of": "not-a-date"})],
        timeout_s=1.0,
    )[0]
    assert bad_as_of["availability"]["status"] == "lookup_failed"
    assert bad_as_of["availability"]["note"] == note
    assert "T" not in str(bad_as_of["availability"].get("as_of") or "")


def test_jlc_lcsc_only_result_is_on_records_not_group(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_JLC_ENRICH", "1")

    def _lcsc_only(bom: Any, *, client: Any = None) -> dict[str, Any]:
        lines = [dict(row) for row in bom.get("lines") or []]
        for line in lines:
            line["jlc_lcsc"] = "C99999"
        return {"lines": lines, "jlc_enriched": True}

    monkeypatch.setattr("hardware_splicer.parts_intel.enrich_bom_with_jlcsearch", _lcsc_only)
    provider = JlcEnrichProvider()
    record = provider.lookup({"mpn": "UNKNOWN-MPN"}, timeout_s=1.0)
    assert record is not None
    assert record["source"] == "jlcsearch"
    assert record["lcsc"] == "C99999"
    assert record.get("mpn_returned") is None

    groups = [
        {
            "value": "10k",
            "footprint": "R_0603",
            "mpn": "UNKNOWN-MPN",
            "lcsc": None,
            "manufacturer": None,
            "dnp": False,
            "quantity": 1,
            "refs": ["R2"],
            "missing_mpn": False,
            "not_in_bom": False,
        }
    ]
    enriched = enrich_bom(groups, [provider], timeout_s=1.0)
    assert enriched[0]["lcsc"] is None
    assert enriched[0]["mpn"] == "UNKNOWN-MPN"
    assert enriched[0]["availability"]["status"] == "checked"
    assert enriched[0]["availability"]["records"][0]["lcsc"] == "C99999"
    assert enriched[0]["availability"]["records"][0]["source"] == "jlcsearch"


def test_jlc_enrich_provider_maps_existing_function(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_JLC_ENRICH", "1")
    captured: dict[str, Any] = {}

    def _fake_enrich(bom: Any, *, client: Any = None) -> dict[str, Any]:
        captured["bom"] = bom
        captured["client"] = client
        lines = [dict(row) for row in bom.get("lines") or []]
        for line in lines:
            line["jlc_lcsc"] = "C123"
            line["jlc_mpn"] = "RC0603FR-0710KL"
            line["jlc_cpl_footprint"] = "R0603"
            line["lifecycle"] = "active"
            line["stock"] = 42
        return {"lines": lines, "jlc_enriched": True}

    monkeypatch.setattr("hardware_splicer.bom_generator.enrich_bom_with_jlcsearch", _fake_enrich)
    monkeypatch.setattr("hardware_splicer.parts_intel.enrich_bom_with_jlcsearch", _fake_enrich)
    provider = JlcEnrichProvider()
    record = provider.lookup({"mpn": "RC0603FR-0710KL"}, timeout_s=1.0)
    assert record is not None
    assert record["source"] == "jlcsearch"
    assert record["as_of"]
    assert record["lifecycle"] == "active"
    assert record["stock"] == 42
    assert record["package"] == "R0603"
    assert record["lcsc"] == "C123"
    assert record["mpn_returned"] == "RC0603FR-0710KL"
    assert captured["bom"]["lines"]

    def _boom(bom: Any, *, client: Any = None) -> dict[str, Any]:
        raise RuntimeError("network")

    monkeypatch.setattr("hardware_splicer.parts_intel.enrich_bom_with_jlcsearch", _boom)
    assert provider.lookup({"mpn": "RC0603FR-0710KL"}, timeout_s=1.0) is None


def test_jlc_enrich_flag_only_is_no_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_JLC_ENRICH", "1")

    def _flag_only(bom: Any, *, client: Any = None) -> dict[str, Any]:
        return {"lines": [dict(row) for row in bom.get("lines") or []], "jlc_enriched": True}

    monkeypatch.setattr("hardware_splicer.parts_intel.enrich_bom_with_jlcsearch", _flag_only)
    provider = JlcEnrichProvider()
    assert provider.lookup({"mpn": "RC0603FR-0710KL"}, timeout_s=1.0) is None
    groups = [
        {
            "value": "10k",
            "footprint": "R_0603",
            "mpn": "RC0603FR-0710KL",
            "lcsc": None,
            "manufacturer": "Yageo",
            "dnp": False,
            "quantity": 1,
            "refs": ["R2"],
            "missing_mpn": False,
            "not_in_bom": False,
        }
    ]
    enriched = enrich_bom(groups, [provider], timeout_s=1.0)
    assert enriched[0]["availability"]["status"] == "no_data"


def test_parts_providers_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARDWARE_SPLICER_JLC_ENRICH", raising=False)
    names = [provider.name for provider in parts_providers_from_env()]
    assert names == ["hardware-splicer-catalog"]

    monkeypatch.setenv("HARDWARE_SPLICER_JLC_ENRICH", "")
    assert [provider.name for provider in parts_providers_from_env()] == ["hardware-splicer-catalog"]

    monkeypatch.setenv("HARDWARE_SPLICER_JLC_ENRICH", "0")
    assert [provider.name for provider in parts_providers_from_env()] == ["hardware-splicer-catalog"]

    monkeypatch.setenv("HARDWARE_SPLICER_JLC_ENRICH", "1")
    enabled = [provider.name for provider in parts_providers_from_env()]
    assert enabled == ["hardware-splicer-catalog", JlcEnrichProvider().name]

    monkeypatch.setenv("HARDWARE_SPLICER_JLC_ENRICH", "TRUE")
    assert JlcEnrichProvider().name in [provider.name for provider in parts_providers_from_env()]
    monkeypatch.setenv("HARDWARE_SPLICER_JLC_ENRICH", "Yes")
    assert JlcEnrichProvider().name in [provider.name for provider in parts_providers_from_env()]


def test_enrich_passes_manufacturer_and_cache_key_includes_it() -> None:
    class Spy:
        name = "spy"
        calls: list[dict[str, Any]] = []

        def lookup(self, query: dict[str, Any], *, timeout_s: float) -> dict[str, Any] | None:
            Spy.calls.append(dict(query))
            return {
                "source": "spy",
                "as_of": "2026-10-06T00:00:00+00:00",
                "lifecycle": "active",
                "stock": 1,
                "price_breaks": None,
                "datasheet_url": None,
                "alternates": [],
                "package": None,
            }

    Spy.calls = []
    groups = [
        {
            "value": "TXU0304PWR",
            "footprint": "TSSOP-14",
            "mpn": "TXU0304PWR",
            "lcsc": None,
            "manufacturer": "Texas Instruments",
            "dnp": False,
            "quantity": 1,
            "refs": ["U1"],
            "missing_mpn": False,
            "not_in_bom": False,
        },
        {
            "value": "clone",
            "footprint": "other",
            "mpn": "TXU0304PWR",
            "lcsc": None,
            "manufacturer": "Texas Instruments",
            "dnp": False,
            "quantity": 1,
            "refs": ["U99"],
            "missing_mpn": False,
            "not_in_bom": False,
        },
        {
            "value": "alt-mfr",
            "footprint": "other",
            "mpn": "TXU0304PWR",
            "lcsc": None,
            "manufacturer": "Nexperia",
            "dnp": False,
            "quantity": 1,
            "refs": ["U2"],
            "missing_mpn": False,
            "not_in_bom": False,
        },
    ]
    enrich_bom(groups, [Spy()], timeout_s=1.0)
    assert Spy.calls[0]["manufacturer"] == "Texas Instruments"
    assert Spy.calls[0]["mpn"] == "TXU0304PWR"
    assert len(Spy.calls) == 2
    assert Spy.calls[1]["manufacturer"] == "Nexperia"


def test_enrich_cache_includes_ordered_provider_set() -> None:
    class FakeJlc:
        name = "jlcsearch"

        def __init__(self) -> None:
            self.calls = 0

        def lookup(self, query: dict[str, Any], *, timeout_s: float) -> dict[str, Any] | None:
            self.calls += 1
            return {
                "source": "jlcsearch",
                "as_of": "2026-10-06T12:00:00+00:00",
                "lifecycle": "active",
                "stock": 7,
                "price_breaks": None,
                "datasheet_url": None,
                "alternates": [],
                "package": None,
            }

    group = {
        "value": "x",
        "footprint": "x",
        "mpn": "CACHE-PROVIDER-SET-MPN",
        "lcsc": None,
        "manufacturer": "Acme",
        "dnp": False,
        "quantity": 1,
        "refs": ["U1"],
        "missing_mpn": False,
        "not_in_bom": False,
    }
    offline = OfflineCatalogProvider()
    first = enrich_bom([group], [offline], timeout_s=1.0)
    assert first[0]["availability"]["status"] == "no_data"
    assert first[0]["availability"]["records"] == []

    fake = FakeJlc()
    second = enrich_bom([group], [offline, fake], timeout_s=1.0)
    assert fake.calls == 1
    assert second[0]["availability"]["status"] == "checked"
    assert second[0]["availability"]["records"][0]["source"] == "jlcsearch"
    assert second[0]["availability"]["records"][0]["stock"] == 7

    third = enrich_bom([group], [offline, fake], timeout_s=1.0)
    assert fake.calls == 1
    assert third[0]["availability"]["status"] == "checked"


def test_timed_out_lookups_never_exceed_executor_workers() -> None:
    peak = 0

    class Slow:
        def __init__(self, name: str) -> None:
            self.name = name

        def lookup(self, query: dict[str, Any], *, timeout_s: float) -> dict[str, Any] | None:
            time.sleep(0.8)
            return None

    for index in range(20):
        group = {
            "value": f"v{index}",
            "footprint": "x",
            "mpn": f"SLOW-BOUND-{index}",
            "lcsc": None,
            "manufacturer": None,
            "dnp": False,
            "quantity": 1,
            "refs": [f"R{index}"],
            "missing_mpn": False,
            "not_in_bom": False,
        }
        enrich_bom([group], [Slow(f"slow-bound-{index}")], timeout_s=0.03)
        live = sum(1 for thread in threading.enumerate() if (thread.name or "").startswith(LOOKUP_THREAD_PREFIX))
        peak = max(peak, live)
    assert peak <= LOOKUP_EXECUTOR_WORKERS


def test_provider_breaker_opens_and_recovers_with_injectable_clock() -> None:
    clock = {"t": 1000.0}
    set_parts_intel_clock(lambda: clock["t"])

    class Flaky:
        name = "flaky"
        calls = 0

        def lookup(self, query: dict[str, Any], *, timeout_s: float) -> dict[str, Any] | None:
            Flaky.calls += 1
            if Flaky.calls <= 3:
                raise RuntimeError("fail")
            return {
                "source": "flaky",
                "as_of": "2026-10-06T00:00:00+00:00",
                "lifecycle": "active",
                "stock": 1,
                "price_breaks": None,
                "datasheet_url": None,
                "alternates": [],
                "package": None,
            }

    Flaky.calls = 0
    provider = Flaky()

    def _group(mpn: str) -> dict[str, Any]:
        return {
            "value": mpn,
            "footprint": "x",
            "mpn": mpn,
            "lcsc": None,
            "manufacturer": None,
            "dnp": False,
            "quantity": 1,
            "refs": ["U1"],
            "missing_mpn": False,
            "not_in_bom": False,
        }

    for mpn in ("A", "B", "C"):
        row = enrich_bom([_group(mpn)], [provider], timeout_s=1.0)[0]
        assert row["availability"]["status"] == "lookup_failed"
    assert Flaky.calls == 3

    skipped = enrich_bom([_group("D")], [provider], timeout_s=1.0)[0]
    assert skipped["availability"]["status"] == "lookup_failed"
    assert skipped["availability"]["reason"] == "provider temporarily skipped after repeated failures"
    assert Flaky.calls == 3

    clock["t"] += 60.0
    recovered = enrich_bom([_group("E")], [provider], timeout_s=1.0)[0]
    assert Flaky.calls == 4
    assert recovered["availability"]["status"] == "checked"


def test_mpn_manufacturer_lcsc_accept_common_property_names() -> None:
    text = """(kicad_sch (version 20211123) (generator eeschema)
  (symbol (lib_id "Device:R") (at 1 1 0) (unit 1)
    (in_bom yes) (on_board yes) (dnp no)
    (uuid a1)
    (property "Reference" "R1")
    (property "Value" "10k")
    (property "Footprint" "R_0603")
    (property "Manufacturer_Part_Number" "RC0603FR-0710KL")
    (property "MFR" "Yageo")
    (property "LCSC Part" "C17414")
  )
  (symbol (lib_id "Device:C") (at 2 2 0) (unit 1)
    (in_bom yes) (on_board yes) (dnp no)
    (uuid a2)
    (property "Reference" "C1")
    (property "Value" "100n")
    (property "Footprint" "C_0603")
    (property "Manufacturer Part Number" "GRM188R71C104KA01D")
    (property "JLCPCB Part" "C14663")
  )
)
"""
    by_ref = {row["ref"]: row for row in extract_components(text)}
    assert by_ref["R1"]["mpn"] == "RC0603FR-0710KL"
    assert by_ref["R1"]["mpn_source"] == "property:Manufacturer_Part_Number"
    assert by_ref["R1"]["manufacturer"] == "Yageo"
    assert by_ref["R1"]["lcsc"] == "C17414"
    assert by_ref["C1"]["mpn"] == "GRM188R71C104KA01D"
    assert by_ref["C1"]["mpn_source"] == "property:Manufacturer Part Number"
    assert by_ref["C1"]["lcsc"] == "C14663"


def test_datasheet_only_url_or_filename() -> None:
    text = """(kicad_sch (version 20211123) (generator eeschema)
  (symbol (lib_id "Device:R") (at 1 1 0) (unit 1)
    (in_bom yes) (on_board yes) (dnp no)
    (uuid aaaa)
    (property "Reference" "R1")
    (property "Value" "10k")
    (property "Footprint" "R_0603")
    (property "Datasheet" "~")
  )
  (symbol (lib_id "Device:C") (at 2 2 0) (unit 1)
    (in_bom yes) (on_board yes) (dnp no)
    (uuid bbbb)
    (property "Reference" "C1")
    (property "Value" "100n")
    (property "Footprint" "C_0603")
    (property "Datasheet" "https://example.test/c.pdf")
  )
  (symbol (lib_id "Device:R") (at 3 3 0) (unit 1)
    (in_bom yes) (on_board yes) (dnp no)
    (uuid cccc)
    (property "Reference" "R2")
    (property "Value" "1k")
    (property "Footprint" "R_0603")
    (property "Datasheet" "part.pdf")
  )
)
"""
    by_ref = {row["ref"]: row for row in extract_components(text)}
    assert by_ref["R1"]["datasheet"] is None
    assert by_ref["C1"]["datasheet"] == "https://example.test/c.pdf"
    assert by_ref["R2"]["datasheet"] == "part.pdf"


def test_enrich_bom_with_jlcsearch_still_imported() -> None:
    assert callable(enrich_bom_with_jlcsearch)
