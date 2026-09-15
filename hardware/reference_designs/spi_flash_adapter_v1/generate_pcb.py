#!/usr/bin/env python3
"""Generate the placed, net-assigned KiCad PCB used as the routing input."""

from __future__ import annotations

import argparse
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pcbnew


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "spi_flash_adapter_v1_unrouted.kicad_pcb"
FP_ROOT = Path("/usr/share/kicad/footprints")
MM = pcbnew.FromMM


FOOTPRINTS = {
    "J1": ("Connector_PinHeader_2.54mm.pretty", "PinHeader_1x06_P2.54mm_Vertical", "HOST_SPI_1x06", (105, 80), 0),
    "U1": ("Package_SO.pretty", "TSSOP-14_4.4x5mm_P0.65mm", "TXU0304PWR", (145, 88), 0),
    "U2": ("Package_SO.pretty", "SOIC-8_5.3x5.3mm_P1.27mm", "W25Q128JWSIQ", (170, 88), 0),
    "U3": ("Package_TO_SOT_SMD.pretty", "SOT-23-5", "TLV75518PDBVR", (125, 68), 0),
    "R1": ("Resistor_SMD.pretty", "R_0603_1608Metric", "0R", (114, 78), 0),
    "R2": ("Resistor_SMD.pretty", "R_0603_1608Metric", "10k", (162, 94), 0),
    "R3": ("Resistor_SMD.pretty", "R_0603_1608Metric", "10k", (181, 88), 0),
    "R4": ("Resistor_SMD.pretty", "R_0603_1608Metric", "0R", (134, 74), 0),
    "C1": ("Capacitor_SMD.pretty", "C_0603_1608Metric", "1uF", (120.5, 67.05), 180),
    "C2": ("Capacitor_SMD.pretty", "C_0603_1608Metric", "4.7uF", (129, 67.05), 0),
    "C3": ("Capacitor_SMD.pretty", "C_0603_1608Metric", "100nF", (139.3, 86.05), 180),
    "C4": ("Capacitor_SMD.pretty", "C_0603_1608Metric", "100nF", (150.5, 86.05), 0),
    "C5": ("Capacitor_SMD.pretty", "C_0603_1608Metric", "100nF", (176.5, 86.095), 0),
    "C6": ("Capacitor_SMD.pretty", "C_0603_1608Metric", "1uF", (176, 82.5), 0),
    "H1": ("MountingHole.pretty", "MountingHole_3.2mm_M3", "M3", (104, 64), 0),
    "H2": ("MountingHole.pretty", "MountingHole_3.2mm_M3", "M3", (186, 64), 0),
    "H3": ("MountingHole.pretty", "MountingHole_3.2mm_M3", "M3", (104, 106), 0),
    "H4": ("MountingHole.pretty", "MountingHole_3.2mm_M3", "M3", (186, 106), 0),
}


TEST_POSITIONS = {
    "HOST_3V3": (110, 65),
    "3V3": (116, 65),
    "1V8": (135, 65),
    "GND": (143, 65),
    "HOST_SCLK": (118, 84),
    "DUT_SCLK": (155, 80),
    "HOST_MOSI": (123, 90),
    "DUT_MOSI": (160, 82),
    "HOST_CS_N": (118, 96),
    "DUT_CS_N": (155, 94),
    "HOST_MISO": (128, 101),
    "DUT_MISO": (160, 98),
    "DUT_IO2_WP_N": (172, 98),
    "DUT_IO3_HOLD_N": (181, 96),
    "DUT_1V8": (143, 74),
}


def point(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(MM(x), MM(y))


def add_footprint(board: pcbnew.BOARD, reference: str, spec: tuple) -> pcbnew.FOOTPRINT:
    library, name, value, position, angle = spec
    footprint = pcbnew.FootprintLoad(str(FP_ROOT / library), name)
    if footprint is None:
        raise RuntimeError(f"unable to load {library}:{name}")
    footprint.SetReference(reference)
    footprint.SetValue(value)
    footprint.SetPosition(point(*position))
    footprint.SetOrientationDegrees(angle)
    board.Add(footprint)
    return footprint


def pad(board: pcbnew.BOARD, reference: str, number: str) -> pcbnew.PAD:
    footprint = board.FindFootprintByReference(reference)
    found = footprint.FindPadByNumber(number) if footprint else None
    if found is None:
        raise RuntimeError(f"missing pad {reference}.{number}")
    return found


def apply_schematic_netlist(board: pcbnew.BOARD, netlist: Path) -> None:
    root = ET.parse(netlist).getroot()

    for component in root.findall("./components/comp"):
        reference = component.attrib["ref"]
        footprint = board.FindFootprintByReference(reference)
        if footprint is None:
            raise RuntimeError(f"schematic component {reference} has no board footprint")
        footprint.SetValue(component.findtext("value", default=""))
        footprint.SetFPIDAsString(component.findtext("footprint", default=""))
        footprint.SetPath(pcbnew.KIID_PATH(component.findtext("tstamps", default="")))

    for xml_net in root.findall("./nets/net"):
        name = xml_net.attrib["name"]
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
        for node in xml_net.findall("node"):
            pad(board, node.attrib["ref"], node.attrib["pin"]).SetNet(net)


def build_board(netlist: Path) -> pcbnew.BOARD:
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(2)
    settings = board.GetDesignSettings()
    settings.m_MinClearance = MM(0.2)
    # Freerouting necks down short TSSOP/SOIC fanout segments to 0.15 mm;
    # longer traces retain the 0.20 mm default netclass width.
    settings.m_TrackMinWidth = MM(0.15)
    settings.m_ViasMinSize = MM(0.6)
    settings.m_MinThroughDrill = MM(0.3)
    default_netclass = settings.m_NetSettings.GetDefaultNetclass()
    default_netclass.SetTrackWidth(MM(0.2))
    default_netclass.SetClearance(MM(0.2))

    for reference, spec in FOOTPRINTS.items():
        fp = add_footprint(board, reference, spec)
        if reference.startswith("H"):
            fp.SetAttributes(
                fp.GetAttributes()
                | pcbnew.FP_BOARD_ONLY
                | pcbnew.FP_EXCLUDE_FROM_BOM
                | pcbnew.FP_EXCLUDE_FROM_POS_FILES
            )
            fp.Reference().SetVisible(False)
    for index, (net_name, position) in enumerate(TEST_POSITIONS.items(), start=1):
        add_footprint(board, f"TP{index}", ("TestPoint.pretty", "TestPoint_Pad_D1.5mm", net_name, position, 0))

    apply_schematic_netlist(board, netlist)

    for start, end in (((100, 60), (190, 60)), ((190, 60), (190, 110)), ((190, 110), (100, 110)), ((100, 110), (100, 60))):
        edge = pcbnew.PCB_SHAPE(board)
        edge.SetShape(pcbnew.SHAPE_T_SEGMENT)
        edge.SetStart(point(*start))
        edge.SetEnd(point(*end))
        edge.SetLayer(pcbnew.Edge_Cuts)
        edge.SetWidth(MM(0.05))
        board.Add(edge)

    for value, pos, size in (
        ("HS SPI FLASH ADAPTER v1", (145, 108), 1.2),
        ("MODELED - NOT POWER AUTHORIZED", (145, 105), 0.9),
        ("J1: 3V3 GND CLK MOSI CS# MISO", (116, 107), 0.8),
    ):
        item = pcbnew.PCB_TEXT(board)
        item.SetText(value)
        item.SetPosition(point(*pos))
        item.SetLayer(pcbnew.F_SilkS)
        item.SetTextHeight(MM(size))
        item.SetTextWidth(MM(size))
        item.SetTextThickness(MM(0.15))
        item.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
        board.Add(item)

    return board


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="hs-spi-netlist-") as temporary:
        netlist = Path(temporary) / "spi_flash_adapter_v1.xml"
        subprocess.run(
            [
                "kicad-cli",
                "sch",
                "export",
                "netlist",
                str(HERE / "spi_flash_adapter_v1.kicad_sch"),
                "--format",
                "kicadxml",
                "-o",
                str(netlist),
            ],
            check=True,
        )
        board = build_board(netlist)
    pcbnew.SaveBoard(str(args.output), board)
    print(args.output)


if __name__ == "__main__":
    main()
