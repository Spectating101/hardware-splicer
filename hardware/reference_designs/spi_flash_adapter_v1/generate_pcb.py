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
    "R5": ("Resistor_SMD.pretty", "R_0603_1608Metric", "10k", (133, 94), 0),
    "R6": ("Resistor_SMD.pretty", "R_0603_1608Metric", "10k", (161, 85), 0),
    "R7": ("Resistor_SMD.pretty", "R_0603_1608Metric", "10k", (151, 100), 0),
    "JP1": ("Connector_PinHeader_2.54mm.pretty", "PinHeader_1x02_P2.54mm_Vertical", "ENABLE_AFTER_RAIL_CHECK", (147, 98), 0),
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


TEST_POSITIONS = [
    ("HOST_3V3", (110, 65)),
    ("3V3", (116, 65)),
    ("1V8", (135, 65)),
    ("GND", (143, 65)),
    ("HOST_SCLK", (118, 84)),
    ("DUT_SCLK", (155, 80)),
    ("HOST_MOSI", (123, 90)),
    ("DUT_MOSI", (160, 82)),
    ("HOST_CS_N", (118, 96)),
    ("DUT_CS_N", (155, 94)),
    ("HOST_MISO", (128, 101)),
    ("DUT_MISO", (160, 98)),
    ("DUT_IO2_WP_N", (172, 98)),
    ("DUT_IO3_HOLD_N", (181, 96)),
    ("DUT_1V8", (143, 74)),
    ("TRANSLATOR_OE", (155, 101)),
    ("GND", (146, 93)),
    ("GND", (175, 101)),
]

# Local ground escape vias are routed before the signal autorouter. Each IC and
# bypass capacitor gets a direct, short connection to the back ground reference.
GROUND_ESCAPES = {
    ("U1", "7"): (140.6, 89.95),
    ("U2", "4"): (164.9, 89.905),
    ("U3", "2"): (122.8, 68),
    ("C1", "2"): (119.725, 65.8),
    ("C2", "2"): (129.775, 65.8),
    ("C3", "2"): (138.525, 84.8),
    ("C4", "2"): (151.275, 84.8),
    ("C5", "2"): (178.5, 86.095),
    ("C6", "2"): (178, 82.5),
    ("R7", "2"): (151.775, 101.2),
    ("TP4", "1"): (143, 66.5),
    ("TP17", "1"): (146, 94.5),
    ("TP18", "1"): (175, 102.5),
}


def add_ground_reference(board: pcbnew.BOARD) -> None:
    ground = board.FindNet("/GND")
    for (reference, number), position in GROUND_ESCAPES.items():
        ground_pad = pad(board, reference, number)
        if ground_pad.GetNetname() != "/GND":
            raise RuntimeError(f"ground escape targets non-ground pad {reference}.{number}")
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(point(*position))
        via.SetWidth(pcbnew.F_Cu, MM(0.6))
        via.SetDrill(MM(0.3))
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        via.SetNet(ground)
        via.SetLocked(True)
        board.Add(via)
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(ground_pad.GetPosition())
        track.SetEnd(via.GetPosition())
        track.SetWidth(MM(0.25))
        track.SetLayer(pcbnew.F_Cu)
        track.SetNet(ground)
        track.SetLocked(True)
        board.Add(track)
    for position in ((110, 70), (110, 100), (135, 100), (155, 104), (180, 100), (180, 70), (150, 70)):
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(point(*position))
        via.SetWidth(pcbnew.F_Cu, MM(0.6))
        via.SetDrill(MM(0.3))
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        via.SetNet(ground)
        via.SetLocked(True)
        board.Add(via)
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        zone = pcbnew.ZONE(board)
        zone.SetZoneName(f"GND reference {board.GetLayerName(layer)}")
        zone.SetLayer(layer)
        zone.SetNet(ground)
        zone.SetLocalClearance(MM(0.2))
        zone.SetMinThickness(MM(0.2))
        zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        zone.Outline().NewOutline()
        for x, y in ((100.5, 60.5), (189.5, 60.5), (189.5, 109.5), (100.5, 109.5)):
            zone.Outline().Append(MM(x), MM(y))
        board.Add(zone)
    board.BuildConnectivity()


def point(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(MM(x), MM(y))


def add_footprint(board: pcbnew.BOARD, reference: str, spec: tuple) -> pcbnew.FOOTPRINT:
    library, name, value, position, angle = spec
    footprint = pcbnew.FootprintLoad(str(FP_ROOT / library), name)
    if footprint is None:
        raise RuntimeError(f"unable to load {library}:{name}")
    footprint.SetReference(reference)
    footprint.SetFPIDAsString(f"{library.removesuffix('.pretty')}:{name}")
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
        footprint.SetDNP(component.find("property[@name='dnp']") is not None)
        for field_name in ("Manufacturer", "MPN"):
            value = component.findtext(f"fields/field[@name='{field_name}']", default="")
            if value:
                field = pcbnew.PCB_FIELD(footprint, footprint.GetNextFieldId(), field_name)
                field.SetText(value)
                field.SetVisible(False)
                footprint.AddField(field)

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
    for index, (net_name, position) in enumerate(TEST_POSITIONS, start=1):
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
        ("HS SPI FLASH ADAPTER v1 REV 0.2", (145, 108), 1.0),
        ("MODELED - NOT POWER AUTHORIZED", (145, 105), 0.9),
        ("J1: 3V3 GND CLK MOSI CS# MISO", (116, 107), 0.8),
        ("JP1 OPEN AT POWER UP/DOWN", (168, 104), 0.8),
        ("ENABLE AFTER RAIL CHECK + CS HIGH", (160, 62), 0.8),
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

    add_ground_reference(board)
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
