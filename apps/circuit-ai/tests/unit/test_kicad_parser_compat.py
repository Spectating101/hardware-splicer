from __future__ import annotations

from pathlib import Path

from src.engines.kicad_parser import KiCadParser
from src.engines.system_structure_extractor import extract_board_structure


VERSION_D_NETLIST = """
(export (version D)
  (components
    (comp (ref U1)
      (value STM32F446R(C-E)Tx)
      (footprint Housings_QFP:LQFP-64))
    (comp (ref J1)
      (value Conn_01x04)
      (footprint Connector_PinHeader_2.54mm:PinHeader_1x04))
  )
  (nets
    (net (code 1) (name +5V)
      (node (ref J1) (pin 1))
      (node (ref U1) (pin 1)))
    (net (code 2) (name GND)
      (node (ref J1) (pin 2))
      (node (ref U1) (pin 2)))
    (net (code 3) (name UART_TX)
      (node (ref J1) (pin 3))
      (node (ref U1) (pin 3)))
    (net (code 4) (name UART_RX)
      (node (ref J1) (pin 4))
      (node (ref U1) (pin 4)))
  )
)
""".strip()


LEGACY_V11_NETLIST = """
# EESchema Netlist Version 1.1 created  10.03.2013 00:14:50
(
 ( /ABCDEF01 $noname  IC1 ATMEGA644P {Lib=ATMEGA}
  (    1 +5V )
  (    2 GND )
  (    3 /TXD )
  (    4 /RXD )
 )
 ( /ABCDEF02 $noname  P1 UART_HDR {Lib=CONN_4}
  (    1 +5V )
  (    2 GND )
  (    3 /TXD )
  (    4 /RXD )
 )
)
""".strip()


def _write(path: Path, contents: str) -> Path:
    path.write_text(contents + "\n", encoding="utf-8")
    return path


def test_kicad_parser_supports_version_d_unquoted_netlists(tmp_path):
    netlist_path = _write(tmp_path / "version_d.net", VERSION_D_NETLIST)

    parsed = KiCadParser(str(netlist_path)).parse()

    assert "U1" in parsed["components"]
    assert parsed["components"]["U1"]["value"] == "STM32F446R(C-E)Tx"
    assert "+5V" in parsed["nets"]
    assert any(node["ref"] == "J1" for node in parsed["nets"]["UART_TX"]["nodes"])


def test_kicad_parser_supports_legacy_v11_netlists(tmp_path):
    netlist_path = _write(tmp_path / "legacy_v11.net", LEGACY_V11_NETLIST)

    parsed = KiCadParser(str(netlist_path)).parse()

    assert parsed["components"]["IC1"]["value"] == "ATMEGA644P"
    assert parsed["components"]["P1"]["footprint"] == "CONN_4"
    assert "/TXD" in parsed["nets"]
    assert any(node["ref"] == "P1" for node in parsed["nets"]["/RXD"]["nodes"])


def test_extract_board_structure_works_on_legacy_v11_netlists(tmp_path):
    netlist_path = _write(tmp_path / "legacy_v11.net", LEGACY_V11_NETLIST)

    result = extract_board_structure(str(netlist_path), board_id="legacy_ctrl", kind="netlist")

    assert result["connectors"]
    assert result["controller_runtime"]["controllers"]
    assert result["primary_role"] in {"controller", "interface_board"}
