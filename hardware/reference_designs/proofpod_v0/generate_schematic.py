#!/usr/bin/env python3
"""Generate ProofPod v0 schematic candidate for Product Factory run PF-001."""

from __future__ import annotations

from pathlib import Path

import kicad_sch_api as ksa


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "proofpod_v0.kicad_sch"


PARTS = [
    ("Connector:USB_C_Receptacle_USB2.0_16P", "J1", "USB_C", (25, 55), "", {"Purpose": "USB-C 5V + USB2 device"}),
    ("HardwareSplicer:RP2040QFN56", "U1", "RP2040", (105, 85), "Package_DFN_QFN:QFN-56-1EP_7x7mm_P0.4mm_EP3.2x3.2mm", {"Manufacturer": "Raspberry Pi", "MPN": "RP2040"}),
    ("Memory_Flash:W25Q32JVSS", "U2", "W25Q32JVSSIQ", (165, 45), "Package_SO:SOIC-8_5.3x5.3mm_P1.27mm", {"Manufacturer": "Winbond Electronics", "MPN": "W25Q32JVSSIQ"}),
    ("HardwareSplicer:TXU0304PW", "U3", "TXU0304PWR", (185, 95), "Package_SO:TSSOP-14_4.4x5mm_P0.65mm", {"Manufacturer": "Texas Instruments", "MPN": "TXU0304PWR"}),
    ("Interface:PCA9306DC", "U4", "PCA9306DCTR", (185, 145), "Package_SO:VSSOP-8_3x3mm_P0.65mm", {"Manufacturer": "Texas Instruments", "MPN": "PCA9306DCTR"}),
    ("HardwareSplicer:INA219DCN", "U5", "INA219AIDCNR", (120, 155), "Package_TO_SOT_SMD:SOT-23-8", {"Manufacturer": "Texas Instruments", "MPN": "INA219AIDCNR"}),
    ("Regulator_Linear:TLV75533PDBV", "U6", "TLV75533PDBVR", (55, 35), "Package_TO_SOT_SMD:SOT-23-5", {"Manufacturer": "Texas Instruments", "MPN": "TLV75533PDBVR"}),
    ("Regulator_Linear:TLV75518PDBV", "U7", "TLV75518PDBVR", (80, 35), "Package_TO_SOT_SMD:SOT-23-5", {"Manufacturer": "Texas Instruments", "MPN": "TLV75518PDBVR"}),
    ("HardwareSplicer:TPS2553DBV", "U8", "TPS2553DBVR", (120, 125), "Package_TO_SOT_SMD:SOT-23-6", {"Manufacturer": "Texas Instruments", "MPN": "TPS2553DBVR"}),
    ("Device:Crystal", "Y1", "12MHz", (105, 35), "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm", {"Purpose": "exact MPN/load capacitance pending"}),
    ("Connector_Generic:Conn_02x04_Odd_Even", "J2", "TARGET", (235, 120), "Connector_PinHeader_2.54mm:PinHeader_2x04_P2.54mm_Vertical", {"Purpose": "target power + SPI + I2C"}),
    ("Connector_Generic:Conn_01x04", "J3", "SWD", (65, 100), "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical", {"Purpose": "SWD programming/debug"}),
    ("Switch:SW_SPDT", "SW1", "TARGET_1V8_3V3_SELECT", (85, 125), "", {"Purpose": "physical target-rail selection"}),
    ("Switch:SW_SPST", "SW2", "WRITE_ARM", (70, 155), "", {"Purpose": "physical write authorization input"}),
]

RESISTORS = [
    ("R1", "27R", "USB DP series"), ("R2", "27R", "USB DM series"),
    ("R3", "5.1k", "USB-C CC1 Rd"), ("R4", "5.1k", "USB-C CC2 Rd"),
    ("R5", "133k", "TPS2553 ILIM: nominal ~200 mA; max ~234 mA before resistor tolerance"),
    ("R6", "0.1R 1%", "target current shunt"),
    ("R7", "10k", "SPI OE default low"), ("R8", "200k", "PCA9306 enable bias"),
    ("R9", "4.7k", "host I2C SDA pull-up"), ("R10", "4.7k", "host I2C SCL pull-up"),
    ("R11", "4.7k", "target I2C SDA pull-up"), ("R12", "4.7k", "target I2C SCL pull-up"),
    ("R13", "100k", "WRITE_ARM default low"), ("R14", "100k", "target power default off"),
    ("R15", "10k", "TPS2553 FAULT pull-up"), ("R16", "100k", "RP2040 RUN pull-up"),
]
for idx, (ref, value, purpose) in enumerate(RESISTORS):
    PARTS.append(("Device:R", ref, value, (25 + (idx % 4) * 25, 195 + (idx // 4) * 12),
                  "Resistor_SMD:R_0603_1608Metric", {"Purpose": purpose}))

CAPS = [
    ("C1", "10uF", "USB input bulk"), ("C2", "4.7uF", "3V3 regulator output"),
    ("C3", "4.7uF", "1V8 regulator output"), ("C4", "100nF", "TPS2553 input bypass"),
    ("C5", "4.7uF", "target output bulk"), ("C6", "100nF", "RP2040 IOVDD decoupling"),
    ("C7", "100nF", "RP2040 IOVDD decoupling"), ("C8", "100nF", "RP2040 IOVDD decoupling"),
    ("C9", "100nF", "RP2040 IOVDD decoupling"), ("C10", "100nF", "RP2040 USB/ADC decoupling"),
    ("C11", "100nF", "RP2040 DVDD decoupling"), ("C12", "100nF", "RP2040 DVDD decoupling"),
    ("C13", "1uF", "RP2040 VREG output"), ("C14", "100nF", "QSPI flash bypass"),
    ("C15", "15pF", "12MHz crystal load provisional"), ("C16", "15pF", "12MHz crystal load provisional"),
]
for idx, (ref, value, purpose) in enumerate(CAPS):
    PARTS.append(("Device:C", ref, value, (140 + (idx % 4) * 24, 195 + (idx // 4) * 12),
                  "Capacitor_SMD:C_0603_1608Metric", {"Purpose": purpose}))


PIN_NETS: dict[str, dict[str, str]] = {
    "J1": {
        "A1": "GND", "A4": "VBUS_5V", "A5": "USB_CC1", "A6": "USB_DP_CONN", "A7": "USB_DM_CONN",
        "A9": "VBUS_5V", "A12": "GND", "B1": "GND", "B4": "VBUS_5V", "B5": "USB_CC2",
        "B6": "USB_DP_CONN", "B7": "USB_DM_CONN", "B9": "VBUS_5V", "B12": "GND", "S1": "GND",
    },
    "U1": {
        "1": "3V3", "2": "SPI_SCLK_HOST", "3": "SPI_MOSI_HOST", "4": "SPI_CS_HOST",
        "5": "SPI_MISO_HOST", "6": "I2C_SDA_HOST", "7": "I2C_SCL_HOST", "8": "SPI_OE",
        "9": "TARGET_POWER_EN", "10": "3V3", "11": "TARGET_FAULT_N", "12": "WRITE_ARM",
        "19": "GND", "20": "XIN", "21": "XOUT", "22": "3V3", "23": "1V1",
        "24": "SWCLK", "25": "SWDIO", "26": "RUN", "33": "3V3", "42": "3V3",
        "43": "3V3", "44": "3V3", "45": "1V1", "46": "USB_DM_MCU", "47": "USB_DP_MCU",
        "48": "3V3", "49": "3V3", "50": "1V1", "51": "QSPI_SD3", "52": "QSPI_SCLK",
        "53": "QSPI_SD0", "54": "QSPI_SD2", "55": "QSPI_SD1", "56": "QSPI_CS_N", "57": "GND",
    },
    "U2": {"1": "QSPI_CS_N", "2": "QSPI_SD1", "3": "QSPI_SD2", "4": "GND", "5": "QSPI_SD0", "6": "QSPI_SCLK", "7": "QSPI_SD3", "8": "3V3"},
    "U3": {"1": "3V3", "2": "SPI_SCLK_HOST", "3": "SPI_MOSI_HOST", "4": "SPI_CS_HOST", "5": "SPI_MISO_HOST", "7": "GND", "8": "SPI_OE", "10": "SPI_MISO_TARGET", "11": "SPI_CS_TARGET", "12": "SPI_MOSI_TARGET", "13": "SPI_SCLK_TARGET", "14": "VTARGET"},
    "U4": {"1": "GND", "2": "3V3", "3": "I2C_SCL_HOST", "4": "I2C_SDA_HOST", "5": "I2C_SDA_TARGET", "6": "I2C_SCL_TARGET", "7": "VTARGET", "8": "I2C_EN"},
    "U5": {"1": "TARGET_SWITCHED", "2": "VTARGET", "3": "GND", "4": "3V3", "5": "I2C_SCL_HOST", "6": "I2C_SDA_HOST", "7": "GND", "8": "GND"},
    "U6": {"1": "VBUS_5V", "2": "GND", "3": "VBUS_5V", "5": "3V3"},
    "U7": {"1": "3V3", "2": "GND", "3": "3V3", "5": "1V8"},
    "U8": {"1": "TARGET_SOURCE", "2": "GND", "3": "TARGET_POWER_EN", "4": "TARGET_FAULT_N", "5": "ILIM_SET", "6": "TARGET_SWITCHED"},
    "Y1": {"1": "XIN", "2": "XOUT"},
    "J2": {"1": "VTARGET", "2": "GND", "3": "SPI_SCLK_TARGET", "4": "SPI_MOSI_TARGET", "5": "SPI_MISO_TARGET", "6": "SPI_CS_TARGET", "7": "I2C_SCL_TARGET", "8": "I2C_SDA_TARGET"},
    "J3": {"1": "3V3", "2": "GND", "3": "SWCLK", "4": "SWDIO"},
    "SW1": {"1": "1V8", "2": "TARGET_SOURCE", "3": "3V3"},
    "SW2": {"1": "3V3", "2": "WRITE_ARM"},
    "R1": {"1": "USB_DP_MCU", "2": "USB_DP_CONN"},
    "R2": {"1": "USB_DM_MCU", "2": "USB_DM_CONN"},
    "R3": {"1": "USB_CC1", "2": "GND"}, "R4": {"1": "USB_CC2", "2": "GND"},
    "R5": {"1": "ILIM_SET", "2": "GND"}, "R6": {"1": "TARGET_SWITCHED", "2": "VTARGET"},
    "R7": {"1": "SPI_OE", "2": "GND"}, "R8": {"1": "I2C_EN", "2": "VTARGET"},
    "R9": {"1": "I2C_SDA_HOST", "2": "3V3"}, "R10": {"1": "I2C_SCL_HOST", "2": "3V3"},
    "R11": {"1": "I2C_SDA_TARGET", "2": "VTARGET"}, "R12": {"1": "I2C_SCL_TARGET", "2": "VTARGET"},
    "R13": {"1": "WRITE_ARM", "2": "GND"}, "R14": {"1": "TARGET_POWER_EN", "2": "GND"},
    "R15": {"1": "TARGET_FAULT_N", "2": "3V3"}, "R16": {"1": "RUN", "2": "3V3"},
    "C1": {"1": "VBUS_5V", "2": "GND"}, "C2": {"1": "3V3", "2": "GND"},
    "C3": {"1": "1V8", "2": "GND"}, "C4": {"1": "TARGET_SOURCE", "2": "GND"},
    "C5": {"1": "VTARGET", "2": "GND"}, "C6": {"1": "3V3", "2": "GND"},
    "C7": {"1": "3V3", "2": "GND"}, "C8": {"1": "3V3", "2": "GND"},
    "C9": {"1": "3V3", "2": "GND"}, "C10": {"1": "3V3", "2": "GND"},
    "C11": {"1": "1V1", "2": "GND"}, "C12": {"1": "1V1", "2": "GND"},
    "C13": {"1": "1V1", "2": "GND"}, "C14": {"1": "3V3", "2": "GND"},
    "C15": {"1": "XIN", "2": "GND"}, "C16": {"1": "XOUT", "2": "GND"},
}

NO_CONNECTS = {
    "J1": ["A8", "B8"],
    "U1": [str(pin) for pin in list(range(13, 19)) + list(range(27, 33)) + list(range(34, 42))],
    "U3": ["6", "9"],
    "U6": ["4"],
    "U7": ["4"],
}


def add_pin_label(schematic: ksa.Schematic, reference: str, pin: str, net: str) -> None:
    position = schematic.get_component_pin_position(reference, pin)
    if position is None:
        raise RuntimeError(f"missing {reference} pin {pin}")
    component = schematic.components.get(reference)
    if component is None:
        raise RuntimeError(f"missing {reference}")
    dx = position.x - component.position.x
    dy = position.y - component.position.y
    # Two-pin vertical passives can have pins only 3.81 mm apart. A 5.08 mm
    # label stub from each side overlaps through the symbol and electrically
    # shorts the nets. Keep their stubs below half that separation.
    # The USB-C symbol has densely packed and stacked pins. Long label stubs can
    # cross neighboring symbol geometry and merge nets in the serialized KiCad
    # schematic even when the logical PIN_NETS map is correct. Keep J1 short too.
    stub = 1.27 if reference == "J1" or reference.startswith(("R", "C", "Y")) else 5.08
    if abs(dx) >= abs(dy):
        direction = -1 if dx < 0 else 1
        end = (position.x + direction * stub, position.y)
        justification = "right" if direction < 0 else "left"
        schematic.add_wire((position.x, position.y), end)
    else:
        direction = -1 if dy < 0 else 1
        end = (position.x, position.y + direction * stub)
        justification = "left"
        schematic.add_wire((position.x, position.y), end)
    schematic.labels.add(net, end, rotation=0, size=1.0, justify_h=justification)


def main() -> None:
    schematic = ksa.create_schematic("ProofPod v0 Product Factory Run PF-001")
    schematic.library.add_library_path(HERE / "HardwareSplicer.kicad_sym")
    schematic.set_paper_size("A3")
    schematic.set_title_block(
        title="ProofPod v0 protected SPI/I2C validation pod",
        date="2026-09-23",
        rev="0.1 SCHEMATIC CANDIDATE",
        company="Hardware Splicer Product Factory PF-001",
        comments={
            1: "Target power and signal outputs default disabled; physical correctness UNPROVEN.",
            2: "TPS2553 current-limit target <=250 mA; WRITE_ARM is firmware authorization, not opcode firewall.",
            3: "USB-C exact MPN, crystal MPN/load, ESD selection, PCB and physical proof remain blocked.",
        },
    )

    for lib_id, ref, value, position, footprint, properties in PARTS:
        kwargs = dict(properties)
        if footprint:
            kwargs["footprint"] = footprint
        component = schematic.components.add(lib_id, ref, value, position=position, **kwargs)
        component.hidden_properties.update(properties)
        component.hidden_properties.add("Value")

    for reference, pins in PIN_NETS.items():
        for pin, net in pins.items():
            add_pin_label(schematic, reference, pin, net)

    for reference, pins in NO_CONNECTS.items():
        for pin in pins:
            position = schematic.get_component_pin_position(reference, pin)
            if position is None:
                raise RuntimeError(f"missing no-connect target {reference} pin {pin}")
            schematic.no_connects.add((position.x, position.y))

    for index, net in enumerate(("VBUS_5V", "3V3", "1V8", "GND"), start=1):
        ref = f"#FLG0{index}"
        schematic.components.add("power:PWR_FLAG", ref, "PWR_FLAG", position=(25 + index * 15, 15))
        PIN_NETS[ref] = {"1": net}
        add_pin_label(schematic, ref, "1", net)

    schematic.add_text(
        "FACTORY GATE: this is a schematic candidate only. No PCB, fabrication, power-on or commercial superiority authority.\n"
        "The first-use product policy keeps target power OFF and TXU0304 OE LOW until software checks + explicit user action.",
        (125, 15), size=1.2, bold=True,
    )
    schematic.add_text(
        "TARGET POWER: physical SW1 selects 1.8V or 3.3V. TPS2553 is active-high and defaults OFF via R14.\n"
        "R5=133k targets ~201mA nominal and ~234mA datasheet-max before resistor tolerance. R6/INA219 measure target current.",
        (155, 120), size=1.0,
    )
    schematic.add_text(
        "EXTERNAL TARGET MODE: keep TARGET_POWER_EN low. External VTARGET may power translator B-side; TPS2553 reverse protection\n"
        "is relied upon to block backfeed. This topology still requires independent EE review before PCB release.",
        (155, 170), size=1.0,
    )
    schematic.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
