#!/usr/bin/env python3
"""Generate the editable KiCad schematic for the SPI flash adapter reference design.

Generation requires ``kicad-sch-api==0.5.6`` and the KiCad 9 symbol libraries.  The
checked-in schematic remains the review artifact; this generator documents how it was
constructed and makes the connectivity reproducible.
"""

from __future__ import annotations

from pathlib import Path
import re

import kicad_sch_api as ksa


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "spi_flash_adapter_v1.kicad_sch"


PARTS = [
    (
        "Connector_Generic:Conn_01x06",
        "J1",
        "HOST_SPI_1x06",
        (35, 95),
        "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical",
        {"Manufacturer": "Samtec", "MPN": "TSW-106-07-T-S"},
    ),
    ("HardwareSplicer:TXU0304PW", "U1", "TXU0304PWR", (105, 95), "Package_SO:TSSOP-14_4.4x5mm_P0.65mm", {"Manufacturer": "Texas Instruments", "MPN": "TXU0304PWR"}),
    ("HardwareSplicer:W25Q128JWS", "U2", "W25Q128JWSIQ", (160, 95), "Package_SO:SOIC-8_5.3x5.3mm_P1.27mm", {"Manufacturer": "Winbond Electronics", "MPN": "W25Q128JWSIQ"}),
    ("Regulator_Linear:TLV75518PDBV", "U3", "TLV75518PDBVR", (75, 45), "Package_TO_SOT_SMD:SOT-23-5", {"Manufacturer": "Texas Instruments", "MPN": "TLV75518PDBVR"}),
    ("Device:R", "R1", "0R", (48, 45), "Resistor_SMD:R_0603_1608Metric", {"Manufacturer": "Yageo", "MPN": "RC0603JR-070RL", "Purpose": "removable host-power/current-measurement link"}),
    ("Device:R", "R2", "10k", (185, 82), "Resistor_SMD:R_0603_1608Metric", {"Manufacturer": "Yageo", "MPN": "RC0603FR-0710KL", "Purpose": "IO2/WP defined-high bias"}),
    ("Device:R", "R3", "10k", (200, 82), "Resistor_SMD:R_0603_1608Metric", {"Manufacturer": "Yageo", "MPN": "RC0603FR-0710KL", "Purpose": "IO3/HOLD defined-high bias"}),
    ("Device:R", "R4", "0R", (125, 45), "Resistor_SMD:R_0603_1608Metric", {"Manufacturer": "Yageo", "MPN": "RC0603JR-070RL", "Purpose": "removable DUT-domain isolation/current-measurement link"}),
    ("Device:R", "R5", "10k", (145, 145), "Resistor_SMD:R_0603_1608Metric", {"Manufacturer": "Yageo", "MPN": "RC0603FR-0710KL", "Purpose": "host CS high when host is high impedance"}),
    ("Device:R", "R6", "10k", (175, 145), "Resistor_SMD:R_0603_1608Metric", {"Manufacturer": "Yageo", "MPN": "RC0603FR-0710KL", "Purpose": "DUT CS tracks DUT rail while translator disabled"}),
    ("Device:R", "R7", "10k", (205, 145), "Resistor_SMD:R_0603_1608Metric", {"Manufacturer": "Yageo", "MPN": "RC0603FR-0710KL", "Purpose": "OE default low; JP1 must be deliberately bridged"}),
    ("Connector_Generic:Conn_01x02", "JP1", "ENABLE_AFTER_RAIL_CHECK", (230, 145), "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", {"Manufacturer": "Samtec", "MPN": "TSW-102-07-T-S", "Purpose": "normally open enable header; no shunt fitted"}),
    ("Device:C", "C1", "1uF 10V X7R", (55, 60), "Capacitor_SMD:C_0603_1608Metric", {"Manufacturer": "Murata", "MPN": "GRM188R71A105KA61D", "Purpose": "LDO input bypass"}),
    ("Device:C", "C2", "4.7uF 6.3V X5R", (92, 57), "Capacitor_SMD:C_0603_1608Metric", {"Manufacturer": "Murata", "MPN": "GRM188R60J475KE19D", "Purpose": "LDO output bypass"}),
    ("Device:C", "C3", "100nF 16V X7R", (70, 120), "Capacitor_SMD:C_0603_1608Metric", {"Manufacturer": "Murata", "MPN": "GRM188R71C104KA01D", "Purpose": "TXU0304 VCCA bypass"}),
    ("Device:C", "C4", "100nF 16V X7R", (120, 120), "Capacitor_SMD:C_0603_1608Metric", {"Manufacturer": "Murata", "MPN": "GRM188R71C104KA01D", "Purpose": "TXU0304 VCCB bypass"}),
    ("Device:C", "C5", "100nF 16V X7R", (175, 120), "Capacitor_SMD:C_0603_1608Metric", {"Manufacturer": "Murata", "MPN": "GRM188R71C104KA01D", "Purpose": "flash high-frequency bypass"}),
    ("Device:C", "C6", "1uF 10V X7R", (195, 120), "Capacitor_SMD:C_0603_1608Metric", {"Manufacturer": "Murata", "MPN": "GRM188R71A105KA61D", "Purpose": "flash local bulk bypass"}),
]


PIN_NETS = {
    "J1": {"1": "HOST_3V3", "2": "GND", "3": "HOST_SCLK", "4": "HOST_MOSI", "5": "HOST_CS_N", "6": "HOST_MISO"},
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
    "JP1": {"1": "DUT_1V8", "2": "TRANSLATOR_OE"},
    "C1": {"1": "3V3", "2": "GND"},
    "C2": {"1": "1V8", "2": "GND"},
    "C3": {"1": "3V3", "2": "GND"},
    "C4": {"1": "DUT_1V8", "2": "GND"},
    "C5": {"1": "DUT_1V8", "2": "GND"},
    "C6": {"1": "DUT_1V8", "2": "GND"},
}


TEST_NETS = [
    "HOST_3V3", "3V3", "1V8", "GND", "HOST_SCLK", "DUT_SCLK",
    "HOST_MOSI", "DUT_MOSI", "HOST_CS_N", "DUT_CS_N", "HOST_MISO",
    "DUT_MISO", "DUT_IO2_WP_N", "DUT_IO3_HOLD_N", "DUT_1V8",
    "TRANSLATOR_OE", "GND", "GND",
]


def add_pin_label(schematic: ksa.Schematic, reference: str, pin: str, net: str) -> None:
    position = schematic.get_component_pin_position(reference, pin)
    if position is None:
        raise RuntimeError(f"missing {reference} pin {pin}")
    component = schematic.components.get(reference)
    if component is None:
        raise RuntimeError(f"missing {reference}")
    dx = position.x - component.position.x
    dy = position.y - component.position.y
    stub = 5.08
    if abs(dx) >= abs(dy):
        direction = -1 if dx < 0 else 1
        end = (position.x + direction * stub, position.y)
        justification = "right" if direction < 0 else "left"
    elif reference.startswith("U"):
        direction = -1 if dy < 0 else 1
        side = -1 if dx < 0 else 1
        bend = (position.x, position.y + direction * 2.54)
        end = (bend[0] + side * stub, bend[1])
        schematic.add_wire((position.x, position.y), bend)
        schematic.add_wire(bend, end)
        justification = "right" if side < 0 else "left"
    else:
        direction = -1 if dy < 0 else 1
        end = (position.x, position.y + direction * stub)
        justification = "left"
    if abs(dx) >= abs(dy):
        schematic.add_wire((position.x, position.y), end)
    elif not reference.startswith("U"):
        schematic.add_wire((position.x, position.y), end)
    schematic.labels.add(net, end, rotation=0, size=1.0, justify_h=justification)


def main() -> None:
    schematic = ksa.create_schematic("SPI Flash Adapter Reference Design v1")
    schematic.library.add_library_path(HERE / "HardwareSplicer.kicad_sym")
    schematic.set_paper_size("A4")
    schematic.set_title_block(
        title="3.3 V host to 1.8 V W25Q128JW SPI adapter",
        date="2026-09-15",
        rev="0.2 MODELED",
        company="Hardware Splicer",
        comments={
            1: "Read-only JEDEC 0x9F first-use target; 5 MHz initial clock.",
            2: "No fabrication, power-on, or physical correctness authority is granted.",
            3: "W25Q128JW Rev G SHA-256 4d065361...70e275e.",
        },
    )

    for lib_id, ref, value, position, footprint, properties in PARTS:
        component = schematic.components.add(
            lib_id,
            ref,
            value,
            position=position,
            footprint=footprint,
            **properties,
        )
        component.hidden_properties.update(properties)
        if ref.startswith("U"):
            component.hidden_properties.add("Value")

    for index, net in enumerate(TEST_NETS, start=1):
        testpoint = schematic.components.add(
            "Connector:TestPoint",
            f"TP{index}",
            net,
            position=(25 + ((index - 1) % 3) * 40, 132 + ((index - 1) // 3) * 11),
            footprint="TestPoint:TestPoint_Pad_D1.5mm",
            DNP="yes",
            Purpose="bare copper measurement pad; exclude from BOM",
        )
        testpoint.in_bom = False
        testpoint.hidden_properties.update({"DNP", "Purpose"})
        testpoint.hidden_properties.add("Value")
        PIN_NETS[f"TP{index}"] = {"1": net}

    schematic.components.add("power:PWR_FLAG", "#FLG01", "PWR_FLAG", position=(35, 45))
    schematic.components.add("power:PWR_FLAG", "#FLG02", "PWR_FLAG", position=(35, 60))
    schematic.components.add("power:PWR_FLAG", "#FLG03", "PWR_FLAG", position=(55, 45))
    schematic.components.add("power:PWR_FLAG", "#FLG04", "PWR_FLAG", position=(75, 60))
    PIN_NETS["#FLG01"] = {"1": "HOST_3V3"}
    PIN_NETS["#FLG02"] = {"1": "GND"}
    PIN_NETS["#FLG03"] = {"1": "3V3"}
    PIN_NETS["#FLG04"] = {"1": "DUT_1V8"}

    for reference, pins in PIN_NETS.items():
        for pin, net in pins.items():
            add_pin_label(schematic, reference, pin, net)

    for reference, pin in (("U1", "6"), ("U1", "9"), ("U3", "4")):
        position = schematic.get_component_pin_position(reference, pin)
        if position is None:
            raise RuntimeError(f"missing no-connect target {reference} pin {pin}")
        schematic.no_connects.add((position.x, position.y))

    schematic.add_text(
        "U1 is TXU0304PWR; the project symbol encodes the actual fixed directions.\n"
        "Pins 2/3/4 A inputs -> pins 13/12/11 B outputs; pin 10 B input -> pin 5 A output.\n"
        "OE pin 8 accepts either supply domain; R7 holds it low until JP1 is bridged.",
        (105, 70),
        size=1.1,
        bold=True,
    )
    schematic.add_text(
        "POWER/SEQUENCING: U3 is TLV75518PDBVR. R1 is the host-power link; R4 isolates DUT_1V8.\n"
        "JP1 MUST BE OPEN at power-up/down. R5/R6 bias CS to its own domain rail.\n"
        "Enable only after DUT VCC >= 1.7 V for >=20 us, rail checks, and host CS=high.\n"
        "Open JP1 with CS high before power-down; change R1/R4 only with power off.",
        (105, 25),
        size=1.1,
    )
    schematic.add_text(
        "FLASH: W25Q128JWSIQ SOIC-8 208 mil. IQ has QE fixed high; IO2/IO3 bias\n"
        "is not hardware write protection. First transaction: read-only 0x9F at 5 MHz.\n"
        "Use SPI mode 0; no writes/erase. Physical correctness remains UNPROVEN.",
        (220, 68),
        size=1.1,
    )
    schematic.save(OUTPUT)
    # kicad-sch-api 0.5.6 does not expose symbol DNP. Apply the initial
    # assembly variant to its serialized top-level symbol blocks, with exact
    # match counts so a formatter change cannot silently fit the rail links.
    seen = set()
    def mark_initial_dnp(match: re.Match) -> str:
        block = match.group(0)
        reference = re.search(r'\(property "Reference" "([^"]+)"', block)
        if reference and reference[1] in {"R1", "R4"}:
            if block.count("(dnp no)") != 1:
                raise RuntimeError("unexpected DNP serialization")
            seen.add(reference[1])
            return block.replace("(dnp no)", "(dnp yes)")
        return block
    text = re.sub(r"(?ms)^\t\(symbol\n.*?^\t\)", mark_initial_dnp, OUTPUT.read_text())
    if seen != {"R1", "R4"}:
        raise RuntimeError(f"initial assembly DNP markers missing: {seen}")
    OUTPUT.write_text(text)
    print(OUTPUT)


if __name__ == "__main__":
    main()
