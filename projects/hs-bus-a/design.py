"""HS-BUS-A: USB to DYNAMIXEL TTL bus adapter with 12 V distribution for HS-ARM-A (replaces the U2D2 and its power hub).

The half-duplex interface follows ROBOTIS's published TTL circuit (two tri-state buffers sharing one data line, the
direction set by a transmit-enable line, 10 kOhm pull-ups at 5 V), with one change: ROBOTIS draws a 74LVC2G241,
whose inputs need 0.7 x VCC (3.5 V at 5 V) for a high, and the FT232R only guarantees 3.2 V out at 5 V VCCIO. TI's
74AHCT1G125/126 take TTL levels (2.0 V high) at the same supply, so the margin is guaranteed by the datasheets.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.kicad_component_board import Design, Part  # noqa: E402

R0603 = "Resistor_SMD:R_0603_1608Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
LED0603 = "LED_SMD:LED_0603_1608Metric"
JST_EH3 = "Connector_JST:JST_EH_B3B-EH-A_1x03_P2.50mm_Vertical"

DS = {
    "ft232r": "https://ftdichip.com/wp-content/uploads/2020/08/DS_FT232R.pdf",
    "ahct125": "https://www.ti.com/lit/ds/symlink/sn74ahct1g125.pdf",
    "ahct126": "https://www.ti.com/lit/ds/symlink/sn74ahct1g126.pdf",
    "tpd2e2u06": "https://www.ti.com/lit/ds/symlink/tpd2e2u06.pdf",
    "smbj": "https://www.vishay.com/docs/88392/smbj.pdf",
    "mfmsmf": "https://www.bourns.com/docs/Product-Datasheets/mfmsmf.pdf",
    "jst_eh": "https://www.jst-mfg.com/product/pdf/eng/eEH.pdf",
}


def P(ref, lib_id, value, footprint, sch, pcb=None, rot=0.0, mpn="", ds="", **extra):
    fields = {"MPN": mpn} if mpn else {}
    if ds:
        fields["Datasheet"] = ds
    fields.update(extra)
    return Part(ref=ref, lib_id=lib_id, value=value, footprint=footprint, sch_xy=sch, pcb_xy=pcb, pcb_rot=rot, fields=fields)


# Board origin (100, 100) mm; outline 100..170 x 100..156. Logic on the left, 12 V on the right.
PARTS = [
    P("J1", "Connector:USB_C_Receptacle_USB2.0_16P", "USB-C", "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12",
      (40, 90), (103.6, 124), 270, mpn="HRO TYPE-C-31-M-12", LCSC="C165948"),
    P("U4", "Power_Protection:TPD2E2U06DCK", "TPD2E2U06DCK", "Package_TO_SOT_SMD:SOT-323_SC-70", (100, 70), (113, 124), 90,
      mpn="TPD2E2U06QDCKRQ1", ds=DS["tpd2e2u06"], LCSC="C915089"),
    P("R1", "Device:R", "5.1k", R0603, (95, 125), (111, 133), 90, mpn="0603 5.1k 1%"),
    P("R2", "Device:R", "5.1k", R0603, (110, 125), (114, 133), 90, mpn="0603 5.1k 1%"),
    P("U1", "Interface_USB:FT232RL", "FT232RL", "Package_SO:SSOP-28_5.3x10.2mm_P0.65mm", (175, 110), (126, 125), 180,
      mpn="FT232RL-REEL", ds=DS["ft232r"], LCSC="C8690"),
    P("C1", "Device:C", "4.7u", C0805, (40, 200), (119, 112), 90, mpn="0805 4.7uF 16V X5R"),
    P("C2", "Device:C", "100n", C0603, (55, 200), (122, 112), 90, mpn="0603 100nF 50V X7R"),
    P("C3", "Device:C", "100n", C0603, (70, 200), (118, 118), 90, mpn="0603 100nF 50V X7R"),
    P("C4", "Device:C", "100n", C0603, (85, 200), (131, 134), 90, mpn="0603 100nF 50V X7R"),
    P("U2", "74xGxx:74AHCT1G126", "74AHCT1G126", "Package_TO_SOT_SMD:SOT-23-5", (255, 80), (138.5, 117), 0,
      mpn="SN74AHCT1G126DBVR", ds=DS["ahct126"], LCSC="C163712"),
    P("U3", "74xGxx:74AHCT1G125", "74AHCT1G125", "Package_TO_SOT_SMD:SOT-23-5", (255, 150), (138.5, 131), 0,
      mpn="SN74AHCT1G125DBVR", ds=DS["ahct125"], LCSC="C7484"),
    P("C5", "Device:C", "100n", C0603, (100, 200), (138.5, 112), 0, mpn="0603 100nF 50V X7R"),
    P("C6", "Device:C", "100n", C0603, (115, 200), (138.5, 136), 0, mpn="0603 100nF 50V X7R"),
    P("R3", "Device:R", "10k", R0603, (290, 150), (134, 138), 90, mpn="0603 10k 1%"),
    P("R4", "Device:R", "10k", R0603, (290, 80), (134, 124), 90, mpn="0603 10k 1%"),
    P("R5", "Device:R", "10k", R0603, (225, 200), (134, 119), 90, mpn="0603 10k 1%"),
    P("R6", "Device:R", "1k", R0603, (150, 235), (116, 145), 0, mpn="0603 1k 1%"),
    P("D2", "Device:LED", "TX green", LED0603, (180, 245), (110, 145), 0, mpn="KT-0603G", LCSC="C12624"),
    P("R7", "Device:R", "1k", R0603, (210, 235), (116, 149), 0, mpn="0603 1k 1%"),
    P("D3", "Device:LED", "RX yellow", LED0603, (240, 245), (110, 149), 0, mpn="KT-0603Y", LCSC="C2287"),
    # 12 V side
    # Data-line protection, after Pollen Robotics' production DYNAMIXEL converter (elec_grabette, Apache-2.0): a cable
    # that puts 12 V on the data pin meets 150 ohm + a resettable PTC, and a 5.1 V Zener holds the buffer side.
    P("R9", "Device:R", "150", R0603, (300, 110), (142.5, 121), 90, mpn="0603 150R 1%"),
    P("D5", "Device:D_Zener", "5V1", "Diode_SMD:D_SOD-323", (320, 125), (142.5, 125.5), 90, mpn="BZT52C5V1S", LCSC="C2903905"),
    P("TH1", "Device:Thermistor_PTC", "100R PTC", R0603, (300, 140), (142.5, 137), 90, mpn="PRG18BB101MB1RB", LCSC="C913703"),
    P("J2", "Connector:Screw_Terminal_01x02", "12V IN",
      "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal", (320, 45), (152, 107), 180,
      mpn="WJ500V-5.08-2P", LCSC="C8465"),
    P("D1", "Device:D_TVS", "SMBJ15CA", "Diode_SMD:D_SMB", (345, 60), (148, 117), 0, mpn="SMBJ15CA", ds=DS["smbj"], LCSC="C169449"),
    P("C7", "Device:C_Polarized", "220u 25V", "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm", (365, 60), (147, 128), 0,
      mpn="220uF 25V radial 8 mm", LCSC="C160162"),
    P("C8", "Device:C", "100n 50V", "Capacitor_SMD:C_1206_3216Metric", (385, 60), (147, 136), 0, mpn="1206 100nF 50V X7R"),
    P("R8", "Device:R", "4.7k", "Resistor_SMD:R_1206_3216Metric", (400, 60), (147, 144), 0, mpn="1206 4.7k 1%"),
    P("D4", "Device:LED", "12V red", LED0603, (400, 95), (147, 148), 0, mpn="KT-0603R", LCSC="C2286"),
    P("F1", "Device:Polyfuse", "2.5A hold", "Fuse:Fuse_1812_4532Metric", (330, 140), (159, 113.5), 0,
      mpn="MF-MSMF250/16X", ds=DS["mfmsmf"], LCSC="C210838"),
    P("F2", "Device:Polyfuse", "2.5A hold", "Fuse:Fuse_1812_4532Metric", (330, 180), (159, 126.5), 0,
      mpn="MF-MSMF250/16X", ds=DS["mfmsmf"], LCSC="C210838"),
    P("F3", "Device:Polyfuse", "2.5A hold", "Fuse:Fuse_1812_4532Metric", (330, 220), (159, 139.5), 0,
      mpn="MF-MSMF250/16X", ds=DS["mfmsmf"], LCSC="C210838"),
    P("J3", "Connector_Generic:Conn_01x03", "DXL 1", JST_EH3, (375, 140), (166, 111), 270, mpn="JST B3B-EH-A", ds=DS["jst_eh"], LCSC="C160259"),
    P("J4", "Connector_Generic:Conn_01x03", "DXL 2", JST_EH3, (375, 180), (166, 124), 270, mpn="JST B3B-EH-A", ds=DS["jst_eh"], LCSC="C160259"),
    P("J5", "Connector_Generic:Conn_01x03", "DXL 3", JST_EH3, (375, 220), (166, 137), 270, mpn="JST B3B-EH-A", ds=DS["jst_eh"], LCSC="C160259"),
    P("H1", "Mechanical:MountingHole", "M3", "MountingHole:MountingHole_3.2mm_M3", (300, 250), (103.5, 103.5)),
    P("H2", "Mechanical:MountingHole", "M3", "MountingHole:MountingHole_3.2mm_M3", (315, 250), (103.5, 152.5)),
    P("H3", "Mechanical:MountingHole", "M3", "MountingHole:MountingHole_3.2mm_M3", (330, 250), (166.5, 103.5)),
    P("H4", "Mechanical:MountingHole", "M3", "MountingHole:MountingHole_3.2mm_M3", (345, 250), (166.5, 152.5)),
]

NETS = {
    "VBUS_5V": ["J1.A4", "J1.A9", "J1.B4", "J1.B9", "U1.20", "U1.4", "C1.1", "C2.1", "C4.1", "U2.5", "U3.5", "C5.1",
                "C6.1", "R3.1", "R4.1", "D2.2", "D3.2"],
    "GND": ["J1.A1", "J1.A12", "J1.B1", "J1.B12", "J1.S1", "U1.7", "U1.18", "U1.21", "U1.25", "U1.26", "U2.3", "U3.3",
            "U4.3", "R1.2", "R2.2", "R5.2", "C1.2", "C2.2", "C3.2", "C4.2", "C5.2", "C6.2", "J2.2", "D1.2", "C7.2",
            "C8.2", "D4.1", "J3.1", "J4.1", "J5.1", "D5.2"],
    "USB_DP": ["J1.A6", "J1.B6", "U4.1", "U1.15"],
    "USB_DM": ["J1.A7", "J1.B7", "U4.2", "U1.16"],
    "CC1": ["J1.A5", "R1.1"],
    "CC2": ["J1.B5", "R2.1"],
    "FT_3V3OUT": ["U1.17", "C3.1"],
    "TXD": ["U1.1", "U2.2"],
    "TXDEN": ["U1.13", "U2.1", "U3.1", "R5.1"],
    "DXL_DATA_BUF": ["U2.4", "U3.2", "R4.2", "R9.1"],
    "DXL_DATA_CLAMP": ["R9.2", "D5.1", "TH1.1"],
    "DXL_DATA": ["TH1.2", "J3.3", "J4.3", "J5.3"],
    "RXD": ["U3.4", "U1.5", "R3.2"],
    "TXLED_N": ["U1.23", "R6.2"],
    "TXLED_K": ["R6.1", "D2.1"],
    "RXLED_N": ["U1.22", "R7.2"],
    "RXLED_K": ["R7.1", "D3.1"],
    "VIN_12V": ["J2.1", "D1.1", "C7.1", "C8.1", "F1.1", "F2.1", "F3.1", "R8.1"],
    "PWR_LED_A": ["R8.2", "D4.2"],
    "DXL_VDD1": ["F1.2", "J3.2"],
    "DXL_VDD2": ["F2.2", "J4.2"],
    "DXL_VDD3": ["F3.2", "J5.2"],
}

UNUSED = ["J1.A8", "J1.B8", "U1.3", "U1.11", "U1.2", "U1.9", "U1.10", "U1.6", "U1.14", "U1.12", "U1.19", "U1.27",
          "U1.28"]

DESIGN = Design(name="hs_bus_a", title="HS-BUS-A USB to DYNAMIXEL TTL bus, 12 V distribution", parts=PARTS, nets=NETS,
                unused=UNUSED, power_flag_nets=["VBUS_5V", "GND", "VIN_12V"])
