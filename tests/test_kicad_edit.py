from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from hardware_splicer.kicad_diff import diff_kicad_text
from hardware_splicer.kicad_edit import KicadEditError, apply_edit_ops

REPO = Path(__file__).resolve().parents[1]
REF = REPO / "hardware" / "reference_designs" / "spi_flash_adapter_v1"
SCH = REF / "spi_flash_adapter_v1.kicad_sch"
PCB = REF / "spi_flash_adapter_v1.kicad_pcb"

R2_SCH_UUID = "b7db2b3d-a7bd-4166-951c-4a75126f75bc"
R2_PCB_UUID = "f9870e73-0956-4b59-80c4-abad9daa11b3"
R3_PCB_UUID = "031d0661-2bd1-460a-80a0-ce2fcebe1b77"
R1_SCH_UUID = "d26e3840-9536-4b27-9356-9fdd6c271b8b"
WIRE_UUID = "56c7e1f9-ded6-43f5-8417-8d308fb4226b"
LABEL_UUID = "21c6d8b8-1b4e-4d42-b8c6-443533fa7537"
SEGMENT_UUID = "0abb31d8-7d09-4cf1-9b15-9cb8ff1c70fb"
VIA_UUID = "22b157e5-11d4-498e-9e5e-c23412c1fe0c"
UNKNOWN_UUID = "00000000-0000-4000-8000-000000000000"

K6_SCH = """(kicad_sch (version 20211123) (generator eeschema)
  (paper "A4")
  (symbol (lib_id "Device:R") (at 50 50 0) (unit 1)
    (in_bom yes) (on_board yes)
    (tstamp a1b2c3d4-e5f6-7890-abcd-ef1234567890)
    (property "Reference" "R1" (id 0) (at 52 50 0))
    (property "Value" "10k" (id 1) (at 50 50 0))
  )
)
"""

CRLF_TAB_SCH = (
    "(kicad_sch\r\n"
    "\t(version 20211123)\r\n"
    '\t(symbol (lib_id "Device:R") (at 10 20 0) (unit 1)\r\n'
    "\t\t(in_bom yes) (on_board yes)\r\n"
    "\t\t(tstamp a1b2c3d4-e5f6-7890-abcd-ef1234567890)\r\n"
    '\t\t(property "Reference" "R1" (at 12 20 0))\r\n'
    '\t\t(property "Value" "10k" (at 10 20 0))\r\n'
    "\t)\r\n"
    ")\r\n"
)

_ITEM_HEADS = frozenset(
    {
        "symbol",
        "wire",
        "bus",
        "junction",
        "label",
        "global_label",
        "hierarchical_label",
        "no_connect",
        "footprint",
        "module",
        "segment",
        "via",
    }
)


def _sch() -> str:
    return SCH.read_text(encoding="utf-8")


def _pcb() -> str:
    return PCB.read_text(encoding="utf-8")


def _only_change(report: dict, *, change: str, item_type: str, ref: str | None = None):
    total = report["summary"]["added"] + report["summary"]["removed"] + report["summary"]["changed"]
    assert total == 1, report["changes"]
    assert len(report["changes"]) == 1
    row = report["changes"][0]
    assert row["change"] == change
    assert row["item_type"] == item_type
    if ref is not None:
        assert row["ref"] == ref
    return row


def _changed_region(before: str, after: str) -> tuple[int, int]:
    prefix = 0
    limit = min(len(before), len(after))
    while prefix < limit and before[prefix] == after[prefix]:
        prefix += 1
    suffix = 0
    while (
        suffix < len(before) - prefix
        and suffix < len(after) - prefix
        and before[len(before) - 1 - suffix] == after[len(after) - 1 - suffix]
    ):
        suffix += 1
    return prefix, len(before) - suffix


def _item_span(text: str, uuid: str) -> tuple[int, int]:
    pos = -1
    for needle in (f'(uuid "{uuid}")', f"(tstamp {uuid})", f'(tstamp "{uuid}")'):
        pos = text.find(needle)
        if pos != -1:
            break
    assert pos != -1, uuid
    depth = 0
    starts: list[int] = []
    index = pos
    while index >= 0:
        char = text[index]
        if char == ")":
            depth += 1
        elif char == "(":
            if depth == 0:
                starts.append(index)
            else:
                depth -= 1
        index -= 1
    for start in starts:
        head = text[start + 1 : start + 48].strip().split(None, 1)[0].split("\n", 1)[0].strip('"')
        if head not in _ITEM_HEADS:
            continue
        nested = 0
        cursor = start
        while cursor < len(text):
            char = text[cursor]
            if char == "(":
                nested += 1
            elif char == ")":
                nested -= 1
                if nested == 0:
                    return start, cursor + 1
            cursor += 1
    raise AssertionError(f"no item span for {uuid}")


def _assert_span_local(before: str, after: str, window: tuple[int, int], *, slack: int = 96) -> None:
    changed_start, changed_end = _changed_region(before, after)
    start, end = window
    assert start - slack <= changed_start <= changed_end <= end + slack, (
        changed_start,
        changed_end,
        start,
        end,
    )


def _oracle(kind: str, before: str, result: dict, *, change: str, item_type: str, ref: str | None = None):
    after = result["text"]
    report = diff_kicad_text(kind, before, after)
    row = _only_change(report, change=change, item_type=item_type, ref=ref)
    uuid = row.get("uuid") or (result["applied"][0]["target"].get("uuid") if result["applied"] else None)
    if change == "added":
        prefix, _end = _changed_region(before, after)
        _assert_span_local(before, after, (prefix, min(len(before), prefix + 8)))
    elif uuid:
        _assert_span_local(before, after, _item_span(before, uuid))
    return row, report


def test_schematic_set_property_value_and_idempotence() -> None:
    before = _sch()
    op = {"op": "set_property", "ref": "R2", "name": "Value", "value": "4.7k"}
    result = apply_edit_ops("schematic", before, [op])
    row, _report = _oracle("schematic", before, result, change="changed", item_type="symbol", ref="R2")
    assert "value 10k -> 4.7k" in row["details"]
    assert result["applied"][0]["index"] == 0
    assert result["applied"][0]["op"] == "set_property"
    assert result["applied"][0]["target"]["uuid"] == R2_SCH_UUID
    second = apply_edit_ops("schematic", result["text"], [op])
    assert second["text"] == result["text"]
    idle = diff_kicad_text("schematic", result["text"], second["text"])
    assert idle["summary"]["added"] == idle["summary"]["removed"] == idle["summary"]["changed"] == 0


def test_schematic_set_property_creates_custom_field() -> None:
    before = _sch()
    result = apply_edit_ops(
        "schematic",
        before,
        [{"op": "set_property", "uuid": R2_SCH_UUID, "name": "EditNote", "value": "splice-test"}],
    )
    row, _report = _oracle("schematic", before, result, change="changed", item_type="symbol", ref="R2")
    assert any("property EditNote" in detail and "splice-test" in detail for detail in row["details"])
    second = apply_edit_ops(
        "schematic",
        result["text"],
        [{"op": "set_property", "ref": "R2", "name": "EditNote", "value": "splice-test"}],
    )
    assert second["text"] == result["text"]


def test_schematic_move_symbol_shifts_properties() -> None:
    before = _sch()
    result = apply_edit_ops(
        "schematic",
        before,
        [{"op": "move", "ref": "R2", "x_mm": 187.96, "y_mm": 82.55}],
    )
    row, _report = _oracle("schematic", before, result, change="changed", item_type="symbol", ref="R2")
    assert any("moved from (185.42,82.55) to (187.96,82.55)" in detail for detail in row["details"])
    assert before.count("187.452") == 1
    assert "187.452" not in result["text"]
    assert "189.992" in result["text"]


def test_schematic_move_label() -> None:
    before = _sch()
    result = apply_edit_ops(
        "schematic",
        before,
        [{"op": "move", "uuid": LABEL_UUID, "x_mm": 30.48, "y_mm": 90.17}],
    )
    row, _report = _oracle(
        "schematic",
        before,
        result,
        change="changed",
        item_type="label",
        ref="HOST_3V3",
    )
    assert any("moved from (25.4,90.17) to (30.48,90.17)" in detail for detail in row["details"])


def test_schematic_rotate() -> None:
    before = _sch()
    result = apply_edit_ops("schematic", before, [{"op": "rotate", "ref": "R2", "degrees": 90}])
    row, _report = _oracle("schematic", before, result, change="changed", item_type="symbol", ref="R2")
    assert any("rotation 0.0 -> 90.0" in detail for detail in row["details"])


def test_schematic_set_flag_and_idempotence() -> None:
    before = _sch()
    op = {"op": "set_flag", "ref": "R2", "flag": "dnp", "value": True}
    result = apply_edit_ops("schematic", before, [op])
    row, _report = _oracle("schematic", before, result, change="changed", item_type="symbol", ref="R2")
    assert "dnp no -> yes" in row["details"]
    second = apply_edit_ops("schematic", result["text"], [op])
    assert second["text"] == result["text"]
    idle = diff_kicad_text("schematic", result["text"], second["text"])
    assert idle["summary"]["changed"] == 0


def test_schematic_add_local_label() -> None:
    before = _sch()
    op = {
        "op": "add_label",
        "text": "EDIT_NET",
        "x_mm": 10,
        "y_mm": 12,
        "label_kind": "local",
        "uuid_seed": "seed-local",
    }
    result = apply_edit_ops("schematic", before, [op])
    row, _report = _oracle("schematic", before, result, change="added", item_type="label", ref="EDIT_NET")
    assert any(detail == "at (10,12)" for detail in row["details"])
    assert result["applied"][0]["target"]["ref"] is None
    assert "EDIT_NET" in result["applied"][0]["detail"]
    again = apply_edit_ops("schematic", before, [op])
    assert again["text"] == result["text"]
    assert result["applied"][0]["target"]["uuid"] == again["applied"][0]["target"]["uuid"]


def test_schematic_add_global_label() -> None:
    before = _sch()
    result = apply_edit_ops(
        "schematic",
        before,
        [
            {
                "op": "add_label",
                "text": "EDIT_GLOBAL",
                "x_mm": 11,
                "y_mm": 13,
                "label_kind": "global",
                "uuid_seed": "seed-global",
            }
        ],
    )
    row, _report = _oracle(
        "schematic",
        before,
        result,
        change="added",
        item_type="global_label",
        ref="EDIT_GLOBAL",
    )
    assert any(detail == "at (11,13)" for detail in row["details"])
    assert result["applied"][0]["target"]["ref"] is None
    assert "EDIT_GLOBAL" in result["applied"][0]["detail"]
    assert '(shape input)' in result["text"]


def test_schematic_delete_wire_and_symbol() -> None:
    before = _sch()
    wire = apply_edit_ops("schematic", before, [{"op": "delete", "uuid": WIRE_UUID}])
    row, _report = _oracle("schematic", before, wire, change="removed", item_type="wire")
    assert row["uuid"] == WIRE_UUID
    symbol = apply_edit_ops("schematic", before, [{"op": "delete", "uuid": R1_SCH_UUID}])
    row, _report = _oracle("schematic", before, symbol, change="removed", item_type="symbol", ref="R1")
    assert row["uuid"] == R1_SCH_UUID


def test_pcb_move_footprint_and_via() -> None:
    before = _pcb()
    moved = apply_edit_ops("pcb", before, [{"op": "move", "ref": "R2", "x_mm": 164, "y_mm": 94}])
    row, _report = _oracle("pcb", before, moved, change="changed", item_type="footprint", ref="R2")
    assert any("moved from (162,94) to (164,94)" in detail for detail in row["details"])
    via = apply_edit_ops("pcb", before, [{"op": "move", "uuid": VIA_UUID, "x_mm": 165, "y_mm": 90}])
    row, _report = _oracle("pcb", before, via, change="changed", item_type="via")
    assert any("moved from (164.9,89.905) to (165,90)" in detail for detail in row["details"])


def _footprint_block(text: str, uuid: str) -> str:
    start, end = _item_span(text, uuid)
    return text[start:end]


def _pad_at_sources(text: str, uuid: str) -> list[str]:
    block = _footprint_block(text, uuid)
    sources: list[str] = []
    pos = 0
    while True:
        pad = block.find("(pad ", pos)
        if pad < 0:
            break
        at = block.find("(at ", pad)
        close = block.find(")", at)
        assert at != -1 and close != -1
        sources.append(block[at : close + 1])
        pos = close
    return sources


def _pad_angles(text: str, uuid: str) -> list[float]:
    angles: list[float] = []
    for source in _pad_at_sources(text, uuid):
        nums = [part for part in source[4:-1].split() if part not in {"unlocked", "locked"}]
        angles.append(float(nums[2]) if len(nums) >= 3 else 0.0)
    return angles


def test_pcb_rotate_footprint() -> None:
    before = _pcb()
    result = apply_edit_ops("pcb", before, [{"op": "rotate", "uuid": R2_PCB_UUID, "degrees": 90}])
    row, _report = _oracle("pcb", before, result, change="changed", item_type="footprint", ref="R2")
    assert any("rotation 0.0 -> 90.0" in detail for detail in row["details"])
    before_angles = _pad_angles(before, R2_PCB_UUID)
    after_angles = _pad_angles(result["text"], R2_PCB_UUID)
    assert before_angles and len(before_angles) == len(after_angles)
    for old, new in zip(before_angles, after_angles):
        assert abs(((new - old) % 360) - 90) < 1e-9
    fp_after = _footprint_block(result["text"], R2_PCB_UUID)
    assert "(xyz 0 0 0)" in fp_after
    assert "(at -0.825 0 90)" in fp_after
    assert "(at 0.825 0 90)" in fp_after


def test_pcb_rotate_four_times_restores_pad_angles() -> None:
    before = _pcb()
    original_angles = _pad_angles(before, R2_PCB_UUID)
    text = before
    for _ in range(4):
        text = apply_edit_ops("pcb", text, [{"op": "rotate", "uuid": R2_PCB_UUID, "degrees": 90}])["text"]
    assert _pad_angles(text, R2_PCB_UUID) == original_angles
    idle = diff_kicad_text("pcb", before, text)
    assert idle["summary"]["added"] == idle["summary"]["removed"] == idle["summary"]["changed"] == 0


def test_pcb_rotate_kicad_cli_load(tmp_path: Path) -> None:
    if shutil.which("kicad-cli") is None:
        pytest.skip("kicad-cli is missing")
    edited = apply_edit_ops("pcb", _pcb(), [{"op": "rotate", "uuid": R2_PCB_UUID, "degrees": 90}])["text"]
    pcb_path = tmp_path / "rotated.kicad_pcb"
    pcb_path.write_text(edited, encoding="utf-8")
    drc_out = tmp_path / "drc.json"
    completed = subprocess.run(
        [
            "kicad-cli",
            "pcb",
            "drc",
            "--format",
            "json",
            "--output",
            str(drc_out),
            "--exit-code-violations",
            "off",
            str(pcb_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    blob = "\n".join(
        [
            completed.stdout or "",
            completed.stderr or "",
            drc_out.read_text(encoding="utf-8") if drc_out.is_file() else "",
        ]
    )
    assert "Failed to load" not in blob


def test_pcb_set_track_width_and_idempotence() -> None:
    before = _pcb()
    op = {"op": "set_track_width", "uuid": SEGMENT_UUID, "width_mm": 0.35}
    result = apply_edit_ops("pcb", before, [op])
    row, _report = _oracle("pcb", before, result, change="changed", item_type="segment")
    assert "width 0.2 -> 0.35" in row["details"]
    second = apply_edit_ops("pcb", result["text"], [op])
    assert second["text"] == result["text"]
    idle = diff_kicad_text("pcb", result["text"], second["text"])
    assert idle["summary"]["changed"] == 0


def test_pcb_set_property_value_and_reject_reference() -> None:
    before = _pcb()
    result = apply_edit_ops(
        "pcb",
        before,
        [{"op": "set_property", "ref": "R2", "name": "Value", "value": "4.7k"}],
    )
    row, _report = _oracle("pcb", before, result, change="changed", item_type="footprint", ref="R2")
    assert "value 10k -> 4.7k" in row["details"]
    with pytest.raises(KicadEditError):
        apply_edit_ops(
            "pcb",
            before,
            [{"op": "set_property", "ref": "R2", "name": "Reference", "value": "R99"}],
        )


def test_pcb_set_property_custom_field() -> None:
    before = _pcb()
    op = {"op": "set_property", "ref": "R2", "name": "EditNote", "value": "pcb-note"}
    result = apply_edit_ops("pcb", before, [op])
    row, _report = _oracle("pcb", before, result, change="changed", item_type="footprint", ref="R2")
    assert any("property EditNote" in detail and "pcb-note" in detail for detail in row["details"])
    second = apply_edit_ops("pcb", result["text"], [op])
    assert second["text"] == result["text"]


def test_pcb_delete_segment_and_footprint_confirm() -> None:
    before = _pcb()
    segment = apply_edit_ops("pcb", before, [{"op": "delete", "uuid": SEGMENT_UUID}])
    row, _report = _oracle("pcb", before, segment, change="removed", item_type="segment")
    assert row["uuid"] == SEGMENT_UUID
    with pytest.raises(KicadEditError):
        apply_edit_ops("pcb", before, [{"op": "delete", "uuid": R3_PCB_UUID}])
    deleted = apply_edit_ops(
        "pcb",
        before,
        [{"op": "delete", "uuid": R3_PCB_UUID, "confirm": True}],
    )
    row, _report = _oracle("pcb", before, deleted, change="removed", item_type="footprint", ref="R3")
    assert row["uuid"] == R3_PCB_UUID


def test_pcb_delete_via() -> None:
    before = _pcb()
    result = apply_edit_ops("pcb", before, [{"op": "delete", "uuid": VIA_UUID}])
    row, _report = _oracle("pcb", before, result, change="removed", item_type="via")
    assert row["uuid"] == VIA_UUID


def test_ambiguous_and_unknown_identity() -> None:
    before = _sch()
    with pytest.raises(KicadEditError, match="unknown uuid"):
        apply_edit_ops(
            "schematic",
            before,
            [{"op": "move", "uuid": UNKNOWN_UUID, "x_mm": 1, "y_mm": 1}],
        )
    dup = """(kicad_sch
  (symbol (lib_id "Device:R") (at 1 1 0)
    (uuid "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    (property "Reference" "R1" (at 1 1 0))
    (property "Value" "1k" (at 1 1 0))
  )
  (symbol (lib_id "Device:R") (at 2 2 0)
    (uuid "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
    (property "Reference" "R1" (at 2 2 0))
    (property "Value" "2k" (at 2 2 0))
  )
)
"""
    with pytest.raises(KicadEditError, match="ambiguous reference"):
        apply_edit_ops("schematic", dup, [{"op": "move", "ref": "R1", "x_mm": 3, "y_mm": 3}])


def test_ref_does_not_address_labels() -> None:
    before = _sch()
    with pytest.raises(KicadEditError, match="ref addressing applies to symbols and footprints"):
        apply_edit_ops("schematic", before, [{"op": "move", "ref": "GND", "x_mm": 1, "y_mm": 1}])
    with pytest.raises(KicadEditError, match="ref addressing applies to symbols and footprints"):
        apply_edit_ops(
            "schematic",
            before,
            [{"op": "move", "ref": "HOST_3V3", "x_mm": 1, "y_mm": 1}],
        )


def test_empty_ops_still_validates_input() -> None:
    valid = _sch()
    result = apply_edit_ops("schematic", valid, [])
    assert result["text"] == valid
    assert result["applied"] == []
    with pytest.raises(KicadEditError):
        apply_edit_ops("schematic", "(", [])
    with pytest.raises(KicadEditError):
        apply_edit_ops("schematic", "not-kicad", [])
    with pytest.raises(KicadEditError):
        apply_edit_ops("schematic", _pcb(), [])
    with pytest.raises(KicadEditError):
        apply_edit_ops("pcb", valid, [])


def test_numeric_values_must_be_real_int_or_float() -> None:
    before = _sch()
    pcb = _pcb()
    for value in ("1.0", True, None, float("nan"), float("inf")):
        with pytest.raises(KicadEditError):
            apply_edit_ops(
                "schematic",
                before,
                [{"op": "move", "ref": "R2", "x_mm": value, "y_mm": 1}],
            )
        with pytest.raises(KicadEditError):
            apply_edit_ops("schematic", before, [{"op": "rotate", "ref": "R2", "degrees": value}])
        with pytest.raises(KicadEditError):
            apply_edit_ops(
                "pcb",
                pcb,
                [{"op": "set_track_width", "uuid": SEGMENT_UUID, "width_mm": value}],
            )


def test_unknown_extra_and_authority_keys() -> None:
    before = _sch()
    with pytest.raises(KicadEditError):
        apply_edit_ops(
            "schematic",
            before,
            [{"op": "move", "ref": "R2", "x_mm": 1, "y_mm": 1, "note": "extra"}],
        )
    for key in ("authorized", "release", "power_on"):
        with pytest.raises(KicadEditError):
            apply_edit_ops(
                "schematic",
                before,
                [{"op": "set_flag", "ref": "R2", "flag": "dnp", "value": True, key: True}],
            )


def test_non_finite_huge_coordinates_and_too_many_ops() -> None:
    before = _sch()
    for value in (float("inf"), float("nan"), 1e6, -1e6):
        with pytest.raises(KicadEditError):
            apply_edit_ops(
                "schematic",
                before,
                [{"op": "move", "ref": "R2", "x_mm": value, "y_mm": 1}],
            )
    with pytest.raises(KicadEditError):
        apply_edit_ops(
            "schematic",
            before,
            [{"op": "set_property", "ref": "R2", "name": "Value", "value": "x"}] * 201,
        )


def test_crlf_and_tab_indent_preserved() -> None:
    result = apply_edit_ops(
        "schematic",
        CRLF_TAB_SCH,
        [
            {
                "op": "add_label",
                "text": "CRLF_NET",
                "x_mm": 3,
                "y_mm": 4,
                "label_kind": "local",
                "uuid_seed": "crlf",
            }
        ],
    )
    assert "\r\n" in result["text"]
    assert "\n" not in result["text"].replace("\r\n", "")
    assert "\t(label" in result["text"]
    moved = apply_edit_ops(
        "schematic",
        CRLF_TAB_SCH,
        [{"op": "move", "ref": "R1", "x_mm": 11, "y_mm": 21}],
    )
    assert moved["text"].startswith("(kicad_sch\r\n")
    assert "\t(symbol" in moved["text"]
    k6 = apply_edit_ops(
        "schematic",
        K6_SCH.replace("\n", "\r\n"),
        [{"op": "set_property", "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "name": "Value", "value": "4.7k"}],
    )
    assert "\r\n" in k6["text"]
    row, _report = _oracle(
        "schematic",
        K6_SCH.replace("\n", "\r\n"),
        k6,
        change="changed",
        item_type="symbol",
        ref="R1",
    )
    assert "value 10k -> 4.7k" in row["details"]


def test_sequential_ops_see_earlier_edits() -> None:
    before = _sch()
    result = apply_edit_ops(
        "schematic",
        before,
        [
            {"op": "move", "ref": "R2", "x_mm": 187.96, "y_mm": 82.55},
            {"op": "set_property", "ref": "R2", "name": "Value", "value": "4.7k"},
        ],
    )
    report = diff_kicad_text("schematic", before, result["text"])
    assert report["summary"]["changed"] == 1
    assert report["summary"]["added"] == 0
    assert report["summary"]["removed"] == 0
    row = report["changes"][0]
    assert row["ref"] == "R2"
    assert any("moved from (185.42,82.55) to (187.96,82.55)" in detail for detail in row["details"])
    assert "value 10k -> 4.7k" in row["details"]
    assert result["applied"][0]["op"] == "move"
    assert result["applied"][1]["op"] == "set_property"


def test_failure_atomicity_leaves_input_untouched() -> None:
    original = _sch()
    snapshot = original
    with pytest.raises(KicadEditError):
        apply_edit_ops(
            "schematic",
            original,
            [
                {"op": "set_property", "ref": "R2", "name": "Value", "value": "4.7k"},
                {"op": "set_property", "ref": "R3", "name": "Value", "value": "4.7k"},
                {"op": "move", "uuid": UNKNOWN_UUID, "x_mm": 1, "y_mm": 2},
            ],
        )
    assert original == snapshot == _sch()


def test_kicad_cli_load_proof(tmp_path: Path) -> None:
    if shutil.which("kicad-cli") is None:
        pytest.skip("kicad-cli is missing")
    sch_before = _sch()
    pcb_before = _pcb()
    sch = apply_edit_ops(
        "schematic",
        sch_before,
        [{"op": "set_property", "ref": "R2", "name": "Value", "value": "4.7k"}],
    )["text"]
    pcb = apply_edit_ops(
        "pcb",
        pcb_before,
        [{"op": "set_property", "ref": "R2", "name": "Value", "value": "4.7k"}],
    )["text"]
    sch_path = tmp_path / "edited.kicad_sch"
    pcb_path = tmp_path / "edited.kicad_pcb"
    sch_path.write_text(sch, encoding="utf-8")
    pcb_path.write_text(pcb, encoding="utf-8")
    erc_out = tmp_path / "erc.json"
    drc_out = tmp_path / "drc.json"
    erc = subprocess.run(
        [
            "kicad-cli",
            "sch",
            "erc",
            "--format",
            "json",
            "--output",
            str(erc_out),
            "--exit-code-violations",
            "off",
            str(sch_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    drc = subprocess.run(
        [
            "kicad-cli",
            "pcb",
            "drc",
            "--format",
            "json",
            "--output",
            str(drc_out),
            "--exit-code-violations",
            "off",
            str(pcb_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    blob = "\n".join(
        [
            erc.stdout or "",
            erc.stderr or "",
            drc.stdout or "",
            drc.stderr or "",
            erc_out.read_text(encoding="utf-8") if erc_out.is_file() else "",
            drc_out.read_text(encoding="utf-8") if drc_out.is_file() else "",
        ]
    )
    assert "Failed to load" not in blob


PCB_UNLOCKED = """(kicad_pcb
  (footprint "Pkg:R"
    (layer "F.Cu")
    (uuid "dddddddd-dddd-4ddd-8ddd-dddddddddddd")
    (at 10 20 unlocked)
    (property "Reference" "U9" (at 0 0 0))
    (property "Value" "x" (at 0 0 0))
    (pad "1" smd rect (at -0.8 0 unlocked) (size 1 1) (layers "F.Cu"))
  )
)
"""

PCB_EXPLICIT_ZERO = """(kicad_pcb
  (footprint "Pkg:R"
    (layer "F.Cu")
    (uuid "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
    (at 1 2 0)
    (property "Reference" "R9" (at 0 -1.43 0))
    (property "Value" "1k" (at 0 1.43 0))
    (pad "1" smd rect (at -0.775 0 180) (size 1 1) (layers "F.Cu"))
  )
)
"""

SCH_ROTATE_FIXTURE = """(kicad_sch
  (symbol (lib_id "Device:R") (at 0 0 0)
    (uuid "cccccccc-cccc-4ccc-8ccc-cccccccccccc")
    (property "Reference" "R8" (at 2 0 0))
    (property "Value" "1k" (at 0 1 0))
  )
)
"""


def _property_xy(text: str, uuid: str) -> dict[str, tuple[float, float]]:
    start, end = _item_span(text, uuid)
    block = text[start:end]
    found: dict[str, tuple[float, float]] = {}
    pos = 0
    while True:
        prop = block.find('(property "', pos)
        if prop < 0:
            break
        name_start = prop + len('(property "')
        name_end = block.find('"', name_start)
        name = block[name_start:name_end]
        at = block.find("(at ", name_end)
        close = block.find(")", at)
        parts = [part for part in block[at + 4 : close].split() if part not in {"unlocked", "locked"}]
        found[name] = (float(parts[0]), float(parts[1]))
        pos = name_end
    return found


def test_pcb_rotate_inserts_angle_before_at_flags() -> None:
    result = apply_edit_ops(
        "pcb",
        PCB_UNLOCKED,
        [{"op": "rotate", "uuid": "dddddddd-dddd-4ddd-8ddd-dddddddddddd", "degrees": 90}],
    )
    assert "(at 10 20 90 unlocked)" in result["text"]
    assert "(at -0.8 0 90 unlocked)" in result["text"]
    report = diff_kicad_text("pcb", PCB_UNLOCKED, result["text"])
    row = _only_change(report, change="changed", item_type="footprint", ref="U9")
    assert any("rotation 0.0 -> 90.0" in detail for detail in row["details"])


def test_pcb_explicit_zero_angle_kept_after_rotation() -> None:
    uuid = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
    once = apply_edit_ops("pcb", PCB_EXPLICIT_ZERO, [{"op": "rotate", "uuid": uuid, "degrees": 270}])
    assert "(at -0.775 0 90)" in once["text"]
    text = PCB_EXPLICIT_ZERO
    for _ in range(4):
        text = apply_edit_ops("pcb", text, [{"op": "rotate", "uuid": uuid, "degrees": 90}])["text"]
    assert _footprint_block(text, uuid) == _footprint_block(PCB_EXPLICIT_ZERO, uuid)
    assert "(at 0 -1.43 0)" in text


def test_schematic_rotate_moves_property_positions() -> None:
    # KiCad schematic y-axis is down; +90 maps relative (dx, dy) -> (dy, -dx).
    # Fixture origin (0,0): Reference (2,0) -> (0,-2); Value (0,1) -> (1,0).
    # (mirror x|y) is left untouched; KiCad applies rotate as a delta on (at).
    result = apply_edit_ops(
        "schematic",
        SCH_ROTATE_FIXTURE,
        [{"op": "rotate", "uuid": "cccccccc-cccc-4ccc-8ccc-cccccccccccc", "degrees": 90}],
    )
    xy = _property_xy(result["text"], "cccccccc-cccc-4ccc-8ccc-cccccccccccc")
    assert xy["Reference"] == (0.0, -2.0)
    assert xy["Value"] == (1.0, 0.0)
    assert "(at 0 0 90)" in result["text"]
    row, _report = _oracle(
        "schematic",
        SCH_ROTATE_FIXTURE,
        result,
        change="changed",
        item_type="symbol",
        ref="R8",
    )
    assert any("rotation 0.0 -> 90.0" in detail for detail in row["details"])
    before = _sch()
    original = _property_xy(before, R2_SCH_UUID)
    text = before
    for _ in range(4):
        text = apply_edit_ops("schematic", text, [{"op": "rotate", "ref": "R2", "degrees": 90}])["text"]
    restored = _property_xy(text, R2_SCH_UUID)
    for name, (x_mm, y_mm) in original.items():
        assert abs(restored[name][0] - x_mm) < 1e-6
        assert abs(restored[name][1] - y_mm) < 1e-6


def test_schematic_rotate_kicad_cli_load(tmp_path: Path) -> None:
    if shutil.which("kicad-cli") is None:
        pytest.skip("kicad-cli is missing")
    edited = apply_edit_ops("schematic", _sch(), [{"op": "rotate", "ref": "R2", "degrees": 90}])["text"]
    sch_path = tmp_path / "rotated.kicad_sch"
    sch_path.write_text(edited, encoding="utf-8")
    erc_out = tmp_path / "erc.json"
    completed = subprocess.run(
        [
            "kicad-cli",
            "sch",
            "erc",
            "--format",
            "json",
            "--output",
            str(erc_out),
            "--exit-code-violations",
            "off",
            str(sch_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    blob = "\n".join(
        [
            completed.stdout or "",
            completed.stderr or "",
            erc_out.read_text(encoding="utf-8") if erc_out.is_file() else "",
        ]
    )
    assert "Failed to load" not in blob


def test_add_label_shape_is_whitelisted() -> None:
    before = _sch()
    base = {
        "op": "add_label",
        "text": "SHP",
        "x_mm": 1,
        "y_mm": 2,
        "label_kind": "global",
        "uuid_seed": "shape",
    }
    for shape in ("input)(foo", "input extra", "", None, True, 1):
        with pytest.raises(KicadEditError):
            apply_edit_ops("schematic", before, [{**base, "shape": shape}])
    with pytest.raises(KicadEditError):
        apply_edit_ops(
            "schematic",
            before,
            [{**base, "label_kind": "local", "shape": "input"}],
        )
    ok = apply_edit_ops("schematic", before, [{**base, "shape": "output"}])
    assert "(shape output)" in ok["text"]
    row, _report = _oracle(
        "schematic",
        before,
        ok,
        change="added",
        item_type="global_label",
        ref="SHP",
    )
    assert row["item_type"] == "global_label"
