"""Independent acceptance contracts; no CAD generator or pcbnew dependency."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET


RECEIPT_INPUTS = {
    "schematic": "spi_flash_adapter_v1.kicad_sch",
    "pcb": "spi_flash_adapter_v1.kicad_pcb",
    "project_rules": "spi_flash_adapter_v1.kicad_pro",
    "symbol_library": "HardwareSplicer.kicad_sym",
    "symbol_library_table": "sym-lib-table",
    "bom": "BOM.csv",
    "design_manifest": "design_manifest.json",
    "verifier": "verify_design.py",
    "electrical_contract": "design_checks.py",
}

# Acceptance requirements are deliberately checked against the exported
# schematic, independently of the generator's PIN_NETS implementation.
REQUIRED_PIN_NETS = {
    "J1": {"1": "HOST_3V3", "2": "GND", "3": "HOST_SCLK", "4": "HOST_MOSI", "5": "HOST_CS_N", "6": "HOST_MISO"},
    "JP1": {"1": "DUT_1V8", "2": "TRANSLATOR_OE"},
    "U1": {"1": "3V3", "2": "HOST_SCLK", "3": "HOST_MOSI", "4": "HOST_CS_N", "5": "HOST_MISO", "7": "GND", "8": "TRANSLATOR_OE", "10": "DUT_MISO", "11": "DUT_CS_N", "12": "DUT_MOSI", "13": "DUT_SCLK", "14": "DUT_1V8"},
    "U2": {"1": "DUT_CS_N", "2": "DUT_MISO", "3": "DUT_IO2_WP_N", "4": "GND", "5": "DUT_MOSI", "6": "DUT_SCLK", "7": "DUT_IO3_HOLD_N", "8": "DUT_1V8"},
    "U3": {"1": "3V3", "2": "GND", "3": "3V3", "5": "1V8"},
    "R1": {"1": "HOST_3V3", "2": "3V3"},
    "R2": {"1": "DUT_IO2_WP_N", "2": "DUT_1V8"},
    "R3": {"1": "DUT_IO3_HOLD_N", "2": "DUT_1V8"},
    "R4": {"1": "1V8", "2": "DUT_1V8"},
    "R5": {"1": "HOST_CS_N", "2": "HOST_3V3"},
    "R6": {"1": "DUT_CS_N", "2": "DUT_1V8"},
    "R7": {"1": "TRANSLATOR_OE", "2": "GND"},
    "C1": {"1": "3V3", "2": "GND"},
    "C2": {"1": "1V8", "2": "GND"},
    "C3": {"1": "3V3", "2": "GND"},
    "C4": {"1": "DUT_1V8", "2": "GND"},
    "C5": {"1": "DUT_1V8", "2": "GND"},
    "C6": {"1": "DUT_1V8", "2": "GND"},
    **{f"TP{i}": {"1": net} for i, net in enumerate((
        "HOST_3V3", "3V3", "1V8", "GND", "HOST_SCLK", "DUT_SCLK",
        "HOST_MOSI", "DUT_MOSI", "HOST_CS_N", "DUT_CS_N", "HOST_MISO",
        "DUT_MISO", "DUT_IO2_WP_N", "DUT_IO3_HOLD_N", "DUT_1V8",
        "TRANSLATOR_OE", "GND", "GND",
    ), start=1)},
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def report_entries(value: object, label: str) -> list[dict]:
    require(isinstance(value, list), f"{label}: missing or invalid report array")
    for item in value:
        require(isinstance(item, dict), f"{label}: malformed report entry")
        require(isinstance(item.get("type"), str) and bool(item["type"]), f"{label}: missing violation type")
        require(item.get("severity") in {"error", "warning"}, f"{label}: unknown/excluded severity")
        require(isinstance(item.get("description"), str), f"{label}: missing description")
        require(isinstance(item.get("items"), list), f"{label}: missing affected items")
    return value


def reported_count(stdout: str, category: str) -> int:
    counts = re.findall(rf"^Found (\d+) {re.escape(category)}$", stdout, re.MULTILINE)
    require(len(counts) == 1, f"missing/ambiguous KiCad {category} summary")
    return int(counts[0])


def validate_erc(report: dict, stdout: str) -> None:
    require(report.get("$schema") == "https://schemas.kicad.org/erc.v1.json", "unsupported ERC schema")
    require(report.get("source") == "spi_flash_adapter_v1.kicad_sch", "wrong ERC source")
    sheets = report.get("sheets")
    require(isinstance(sheets, list) and len(sheets) == 1, "expected one ERC sheet")
    entries = report_entries(sheets[0].get("violations"), "ERC")
    require(reported_count(stdout, "violations") == len(entries), "ERC report/summary disagree")
    require(not entries, f"ERC violations: {entries}")


def validate_drc(report: dict, stdout: str, compatible_footprint_uuids: set[str]) -> list[dict]:
    require(report.get("$schema") == "https://schemas.kicad.org/drc.v1.json", "unsupported DRC schema")
    require(report.get("source") == "spi_flash_adapter_v1.kicad_pcb", "wrong DRC source")
    violations = report_entries(report.get("violations"), "DRC")
    unconnected = report_entries(report.get("unconnected_items"), "unconnected_items")
    parity = report_entries(report.get("schematic_parity"), "schematic_parity")
    for category, entries in (("violations", violations), ("unconnected items", unconnected), ("schematic parity issues", parity)):
        require(reported_count(stdout, category) == len(entries), f"DRC {category} report/summary disagree")
    require(not unconnected and not parity, "unconnected pads or schematic parity issues")
    advisories = []
    for entry in violations:
        items = entry["items"]
        compatible = (
            entry["type"] == "lib_footprint_mismatch"
            and entry["severity"] == "warning"
            and bool(items)
            and all(isinstance(item, dict) and item.get("uuid") in compatible_footprint_uuids for item in items)
        )
        require(compatible, f"actionable DRC violation: {entry}")
        advisories.append(entry)
    return advisories


def validate_rules(project: dict) -> None:
    settings = project["board"]["design_settings"]
    require(settings.get("drc_exclusions") == [], "DRC exclusions are not allowed")
    minimums = {
        "min_clearance": 0.2, "min_track_width": 0.15,
        "min_copper_edge_clearance": 0.5, "min_through_hole_diameter": 0.3,
        "min_via_diameter": 0.6, "min_via_annular_width": 0.1,
    }
    for name, value in minimums.items():
        require(settings["rules"].get(name) == value, f"unreviewed design rule: {name}")
    ignored = {name for name, severity in settings["rule_severities"].items() if severity == "ignore"}
    require(ignored <= {
        "footprint_filters_mismatch", "footprint_type_mismatch", "missing_courtyard",
        "npth_inside_courtyard", "pth_inside_courtyard",
    }, f"critical DRC categories ignored: {ignored}")


def netlist_components(root: ET.Element) -> dict[str, ET.Element]:
    items = root.findall("./components/comp")
    components = {item.attrib["ref"]: item for item in items}
    require(len(items) == len(components), "duplicate schematic references")
    return components


def validate_topology(root: ET.Element) -> dict[tuple[str, str], str]:
    components = netlist_components(root)
    require(set(components) == set(REQUIRED_PIN_NETS), "missing/extra schematic components")
    actual = {}
    for net in root.findall("./nets/net"):
        nodes = net.findall("node")
        for node in nodes:
            key = (node.attrib["ref"], node.attrib["pin"])
            require(key not in actual, f"duplicate net assignment: {key}")
            actual[key] = net.attrib["name"]
            if node.attrib.get("pintype") == "no_connect":
                require(len(nodes) == 1 and net.attrib["name"].startswith("unconnected-"), f"NC pin connected: {key}")
    for reference, pins in REQUIRED_PIN_NETS.items():
        for pin, net in pins.items():
            require(actual.get((reference, pin)) == f"/{net}", f"required topology violated: {reference}.{pin} must be {net}")
    expected_nc = {("U1", "6"), ("U1", "9"), ("U3", "4")}
    expected = {(ref, pin) for ref, pins in REQUIRED_PIN_NETS.items() for pin in pins} | expected_nc
    require(set(actual) == expected, "unexpected or missing pins in exported netlist")
    for reference in ("R2", "R3", "R5", "R6", "R7"):
        require(components[reference].findtext("value") == "10k", f"wrong bias resistor value: {reference}")
    for reference in ("R1", "R4"):
        require(components[reference].findtext("value") == "0R", f"wrong rail link value: {reference}")
    for reference, mpn in {"U1": "TXU0304PWR", "U2": "W25Q128JWSIQ", "U3": "TLV75518PDBVR"}.items():
        require(components[reference].findtext("fields/field[@name='MPN']") == mpn, f"unreviewed IC identity: {reference}")
    dnp = {ref for ref, comp in components.items() if comp.find("property[@name='dnp']") is not None}
    require(dnp == {"R1", "R4"}, "initial assembly must leave only R1/R4 DNP")
    u1 = root.find("./libparts/libpart[@lib='HardwareSplicer'][@part='TXU0304PW']")
    require(u1 is not None, "manufacturer-specific translator symbol missing")
    pin_types = {p.attrib["num"]: p.attrib["type"] for p in u1.findall("./pins/pin")}
    require(all(pin_types.get(p) == "input" for p in ("2", "3", "4", "8", "10")), "TXU input pin semantics incorrect")
    require(all(pin_types.get(p) == "tri_state" for p in ("5", "11", "12", "13")), "TXU output pin semantics incorrect")
    flash_symbol = components["U2"].find("libsource")
    require(flash_symbol is not None and flash_symbol.get("lib") == "HardwareSplicer" and flash_symbol.get("part") == "W25Q128JWS", "wrong flash symbol identity")
    return actual


def validate_bom(root: ET.Element, rows: list[dict]) -> None:
    components = netlist_components(root)
    required = {ref: comp for ref, comp in components.items() if comp.find("property[@name='exclude_from_bom']") is None}
    seen = set()
    for row in rows:
        references = row["References"].split()
        require(int(row["Quantity"]) == len(references) and bool(references), "BOM quantity/reference mismatch")
        for reference in references:
            require(reference in required and reference not in seen, f"extra/duplicate BOM reference: {reference}")
            seen.add(reference)
            component = required[reference]
            for column, path in {
                "Value": "value", "Footprint": "footprint", "Manufacturer": "fields/field[@name='Manufacturer']",
                "Manufacturer Part Number": "fields/field[@name='MPN']",
            }.items():
                require(bool(row[column]) and row[column] == component.findtext(path), f"BOM/schematic mismatch: {reference} {column}")
            assembly = "DNP" if component.find("property[@name='dnp']") is not None else "FIT"
            require(row["Initial Assembly"] == assembly, f"BOM assembly mismatch: {reference}")
    require(seen == set(required), "missing BOM references")


def validate_timing(manifest: dict) -> None:
    timing = manifest["timing_budget"]
    residual = (timing["half_period_ns"] - timing["translator_a_to_b_max_ns"]
                - timing["flash_clock_low_to_output_valid_max_ns"] - timing["translator_b_to_a_max_ns"])
    require(timing["known_read_return_residual_ns"] == residual, "read-return timing omits a path segment")
    require(manifest["bringup_controls"]["min_vcc_to_cs_low_us"] >= 20, "flash startup wait too short")
    require(manifest["bringup_controls"]["enable_shunt_initially_fitted"] is False, "enable shunt must be initially absent")
