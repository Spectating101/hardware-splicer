"""A maker's Eagle board file gives a planner entry its geometry; the electrical half is left as named gaps."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from hardware_splicer.eagle_board_import import EagleImportError, draft_entry, main

URL = "https://github.com/example/board/blob/0123456789abcdef0123456789abcdef01234567/board.brd"

# A 25 x 18 mm board with a 4-pin header near the top edge, rotated 180 degrees as Adafruit often places it, and two holes.
BOARD = b"""<?xml version="1.0"?><eagle version="9"><drawing><board>
<plain>
 <wire x1="0" y1="0" x2="25" y2="0" layer="20"/><wire x1="25" y1="0" x2="25" y2="18" layer="20"/>
 <wire x1="25" y1="18" x2="0" y2="18" layer="20"/><wire x1="0" y1="18" x2="0" y2="0" layer="20"/>
</plain>
<libraries><library name="lib"><packages>
 <package name="1X04_ROUND"><pad name="1" x="-3.81" y="0" drill="1"/><pad name="2" x="-1.27" y="0" drill="1"/>
  <pad name="3" x="1.27" y="0" drill="1"/><pad name="4" x="3.81" y="0" drill="1"/></package>
 <package name="MOUNTINGHOLE_2.5"><pad name="H" x="0" y="0" drill="2.5"/></package>
</packages></library></libraries>
<elements>
 <element name="JP1" library="lib" package="1X04_ROUND" x="12.5" y="15.46" rot="R180"/>
 <element name="H1" library="lib" package="MOUNTINGHOLE_2.5" x="2.54" y="2.54"/>
 <element name="H2" library="lib" package="MOUNTINGHOLE_2.5" x="22.46" y="2.54"/>
</elements>
<signals>
 <signal name="VIN"><contactref element="JP1" pad="1"/></signal><signal name="GND"><contactref element="JP1" pad="2"/></signal>
 <signal name="SCL"><contactref element="JP1" pad="3"/></signal><signal name="SDA"><contactref element="JP1" pad="4"/></signal>
</signals>
</board></drawing></eagle>"""


def test_geometry_comes_from_the_board_file_in_a_top_left_frame():
    entry = draft_entry(BOARD, module_id="example-sensor", url=URL)
    assert entry["pcb_mm"] == {"x": 25.0, "y": 18.0, "z": 1.6}
    pins = {p["id"]: p for p in entry["pins"]}
    # R180 puts pad 1 at the right: x = 12.5 + 3.81; the header row is 18 - 15.46 = 2.54 mm from the top edge.
    assert pins["VIN"]["x"] == 16.31 and pins["SDA"]["x"] == 8.69 and all(p["y"] == 2.54 for p in entry["pins"])
    assert pins["VIN"]["roles"] == ["power_in"] and pins["GND"]["roles"] == ["ground"]
    assert pins["SDA"]["roles"] == ["i2c_sda"] and pins["SCL"]["roles"] == ["i2c_scl"]
    assert "(2.54, 15.46)" in entry["dimension_basis"]["holes"]
    assert entry["sources"] == [{"label": "Maker's board file", "url": URL}]


def test_the_electrical_half_is_left_as_gaps_and_nothing_is_added_to_the_library():
    entry = draft_entry(BOARD, module_id="example-sensor", url=URL)
    assert entry["draft"]["status"] == "GEOMETRY_ONLY_DRAFT"
    assert {g["field"] for g in entry["draft"]["gaps"]} >= {"i2c.addresses", "electrical.supply_note", "engineering.loads"}
    assert "i2c" not in entry and "engineering" not in entry


def test_mirror_gives_the_front_view():
    plain = {p["id"]: p["x"] for p in draft_entry(BOARD, module_id="example-sensor", url=URL)["pins"]}
    flipped = {p["id"]: p["x"] for p in draft_entry(BOARD, module_id="example-sensor", url=URL, mirror=True)["pins"]}
    assert all(abs(plain[k] + flipped[k] - 25.0) < 0.01 for k in plain)


@pytest.mark.parametrize("data,kwargs,match", [
    (BOARD, {"url": "https://github.com/example/board/blob/main/board.brd"}, "pinned to a commit"),
    (BOARD, {"module_id": "Bad Id"}, "module id"),
    (b"<eagle><drawing><schematic/></drawing></eagle>", {}, "no <board>"),
    (b"not xml", {}, "not an Eagle XML"),
    (BOARD.replace(b'layer="20"', b'layer="21"'), {}, "no outline"),
])
def test_bad_input_is_refused(data, kwargs, match):
    args = {"module_id": "example-sensor", "url": URL, **kwargs}
    with pytest.raises(EagleImportError, match=match):
        draft_entry(data, **args)


REAL = os.environ.get("HS_ADAFRUIT_OLED_13_BRD")


@pytest.mark.skipif(not REAL or not Path(REAL).is_file(), reason="set HS_ADAFRUIT_OLED_13_BRD to Adafruit's 1.3in OLED STEMMA QT .brd")
def test_the_real_oled_board_reproduces_the_hand_built_library_entry():
    from hardware_splicer.device_plan import module_library

    entry = draft_entry(Path(REAL).read_bytes(), module_id="check-oled", url=URL, kind="display", mirror=True)
    library = next(m for m in module_library()["modules"] if m["id"] == "adafruit-oled-1.3-128x64-stemma-qt")
    assert entry["pcb_mm"] == library["pcb_mm"]
    assert [(p["x"], p["y"], p["roles"]) for p in entry["pins"]] == [(p["x"], p["y"], p["roles"]) for p in library["pins"]]


def test_cli(tmp_path, capsys):
    board = tmp_path / "b.brd"
    board.write_bytes(BOARD)
    assert main([str(board), "--url", URL, "--id", "example-sensor"]) == 0
    assert json.loads(capsys.readouterr().out)["id"] == "example-sensor"
    assert main([str(board), "--url", "https://example.com/x", "--id", "example-sensor"]) == 2
    capsys.readouterr()
