from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.kicad_diff import (
    KicadDiffError,
    MAX_CHANGES,
    SCHEMA_VERSION,
    diff_kicad_files,
    diff_kicad_text,
    parse_kicad_sexp,
)

REPO = Path(__file__).resolve().parents[1]
REF = REPO / "hardware" / "reference_designs" / "spi_flash_adapter_v1"
SCH = REF / "spi_flash_adapter_v1.kicad_sch"
PCB = REF / "spi_flash_adapter_v1.kicad_pcb"

R2_AT = '\t\t(lib_id "Device:R")\n\t\t(at 185.42 82.55 0)\n\t\t(unit 1)'
R2_AT_MOVED = '\t\t(lib_id "Device:R")\n\t\t(at 187.96 82.55 0)\n\t\t(unit 1)'
R2_VALUE = (
    '\t\t(property "Reference" "R2"\n'
    "\t\t\t(at 187.452 82.55 90)\n"
    "\t\t\t(effects\n"
    "\t\t\t\t(font\n"
    "\t\t\t\t\t(size 1.27 1.27)\n"
    "\t\t\t\t)\n"
    "\t\t\t\t(justify left)\n"
    "\t\t\t)\n"
    "\t\t)\n"
    '\t\t(property "Value" "10k"'
)
R2_VALUE_NEW = R2_VALUE.replace('"10k"', '"4.7k"', 1)
WIRE_BLOCK = (
    "\t(wire\n"
    "\t\t(pts\n"
    "\t\t\t(xy 30.48 90.17) (xy 25.4 90.17)\n"
    "\t\t)\n"
    "\t\t(stroke\n"
    "\t\t\t(width 0)\n"
    "\t\t\t(type default)\n"
    "\t\t)\n"
    '\t\t(uuid "56c7e1f9-ded6-43f5-8417-8d308fb4226b")\n'
    "\t)"
)
OTHER_WIRE_BLOCK = (
    "\t(wire\n"
    "\t\t(pts\n"
    "\t\t\t(xy 30.48 92.71) (xy 25.4 92.71)\n"
    "\t\t)\n"
    "\t\t(stroke\n"
    "\t\t\t(width 0)\n"
    "\t\t\t(type default)\n"
    "\t\t)\n"
    '\t\t(uuid "0b5c1285-2b69-47bf-90aa-44425aa1ef44")\n'
    "\t)"
)
ADDED_LABEL = (
    '\t(label "DIFF_TEST_NET"\n'
    "\t\t(at 10 10 0)\n"
    '\t\t(uuid "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")\n'
    "\t)\n"
)
SEGMENT_WIDTH = (
    "\t(segment\n"
    "\t\t(start 133.175 67.8517)\n"
    "\t\t(end 133.175 74)\n"
    "\t\t(width 0.2)\n"
    '\t\t(layer "F.Cu")\n'
    "\t\t(net 1)\n"
    '\t\t(uuid "0abb31d8-7d09-4cf1-9b15-9cb8ff1c70fb")\n'
    "\t)"
)
SEGMENT_WIDTH_NEW = SEGMENT_WIDTH.replace("(width 0.2)", "(width 0.35)", 1)
ZONE_NET = (
    "\t\t(net 10)\n"
    '\t\t(net_name "/GND")\n'
    '\t\t(layer "F.Cu")\n'
    '\t\t(uuid "7920bc50-3bd7-407e-afb4-36b8e79dfccb")'
)
ZONE_NET_NEW = (
    "\t\t(net 2)\n"
    '\t\t(net_name "/3V3")\n'
    '\t\t(layer "F.Cu")\n'
    '\t\t(uuid "7920bc50-3bd7-407e-afb4-36b8e79dfccb")'
)
ADDED_VIA = (
    "\t(via\n"
    "\t\t(at 101 61)\n"
    "\t\t(size 0.6)\n"
    "\t\t(drill 0.3)\n"
    '\t\t(layers "F.Cu" "B.Cu")\n'
    "\t\t(net 10)\n"
    '\t\t(uuid "ffffffff-1111-2222-3333-444444444444")\n'
    "\t)\n"
)
R3_UUID = "031d0661-2bd1-460a-80a0-ce2fcebe1b77"
J1_UUID = "b5d5c85a-d95c-4484-b78f-e4b6b54fdda0"
K6_SCH = """(kicad_sch (version 20211123) (generator eeschema)
  (paper "A4")
  (symbol (lib_id "Device:R") (at 50 50 0) (unit 1)
    (in_bom yes) (on_board yes)
    (tstamp a1b2c3d4-e5f6-7890-abcd-ef1234567890)
    (property "Reference" "R1" (id 0) (at 52 50 0))
    (property "Value" "10k" (id 1) (at 50 50 0))
    (property "Footprint" "Resistor_SMD:R_0603" (id 2) (at 50 50 0))
  )
)
"""
K6_SCH_VALUE = K6_SCH.replace('(property "Value" "10k"', '(property "Value" "4.7k"', 1)


def _sch() -> str:
    return SCH.read_text(encoding="utf-8")


def _pcb() -> str:
    return PCB.read_text(encoding="utf-8")


def _replace_once(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, old[:80]
    return text.replace(old, new, 1)


def _swap_blocks(text: str, left: str, right: str) -> str:
    assert text.count(left) == 1 and text.count(right) == 1
    return text.replace(left, "@@LEFT@@", 1).replace(right, left, 1).replace("@@LEFT@@", right, 1)


def _remove_sexp_with_uuid(text: str, uuid: str) -> str:
    needle = f'(uuid "{uuid}")'
    pos = text.find(needle)
    assert pos != -1
    start = text.rfind("\n\t(", 0, pos)
    if start == -1:
        start = text.rfind("\n(footprint", 0, pos)
    assert start != -1
    start += 1
    depth = 0
    index = start
    while index < len(text):
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                end = index + 1
                if end < len(text) and text[end] == "\n":
                    end += 1
                return text[:start] + text[end:]
        index += 1
    raise AssertionError("unclosed node")


def _insert_before_close(text: str, block: str) -> str:
    end = text.rstrip()
    assert end.endswith(")")
    return end[:-1] + block + ")\n"


def _only_change(report: dict, *, change: str, item_type: str, ref: str | None = None):
    assert report["summary"]["added"] + report["summary"]["removed"] + report["summary"]["changed"] == 1
    assert len(report["changes"]) == 1
    row = report["changes"][0]
    assert row["change"] == change
    assert row["item_type"] == item_type
    if ref is not None:
        assert row["ref"] == ref
    return row


def _near(position: dict | None, x: float, y: float) -> None:
    assert position is not None
    assert abs(position["x_mm"] - x) <= 0.001
    assert abs(position["y_mm"] - y) <= 0.001


def test_tokenizer_quoted_escapes_nested_lists_numbers_and_atoms() -> None:
    tree = parse_kicad_sexp('(root "hello \\"x\\"" nested (child 1 2.5 bare) "café")')
    assert tree[0] == "root"
    assert tree[1] == 'hello "x"'
    assert tree[2] == "nested"
    assert tree[3] == ["child", "1", "2.5", "bare"]
    assert tree[4] == "café"


def test_identical_reference_schematic_has_no_changes() -> None:
    text = _sch()
    report = diff_kicad_text("schematic", text, text)
    assert report["schema_version"] == SCHEMA_VERSION
    assert report["kind"] == "schematic"
    assert report["summary"] == {"added": 0, "removed": 0, "changed": 0, "unchanged": report["summary"]["unchanged"]}
    assert report["summary"]["unchanged"] > 0
    assert report["changes"] == []
    assert report["limits"] == {"truncated": False, "max_changes": MAX_CHANGES}


def test_identical_reference_pcb_has_no_changes() -> None:
    text = _pcb()
    report = diff_kicad_text("pcb", text, text)
    assert report["summary"]["added"] == 0
    assert report["summary"]["removed"] == 0
    assert report["summary"]["changed"] == 0
    assert report["summary"]["unchanged"] > 0
    assert report["changes"] == []


def test_resistor_value_change() -> None:
    report = diff_kicad_text("schematic", _sch(), _replace_once(_sch(), R2_VALUE, R2_VALUE_NEW))
    row = _only_change(report, change="changed", item_type="symbol", ref="R2")
    assert "value 10k -> 4.7k" in row["details"]
    _near(row["position"], 185.42, 82.55)


def test_moved_symbol() -> None:
    report = diff_kicad_text("schematic", _sch(), _replace_once(_sch(), R2_AT, R2_AT_MOVED))
    row = _only_change(report, change="changed", item_type="symbol", ref="R2")
    assert any(detail.startswith("moved from (185.42,82.55) to (187.96,82.55)") or
               detail.startswith("moved from (185.42, 82.55) to (187.96, 82.55)") or
               "moved from" in detail for detail in row["details"])
    assert any("185.42" in detail and "187.96" in detail for detail in row["details"])
    _near(row["position"], 187.96, 82.55)


def test_deleted_wire() -> None:
    report = diff_kicad_text("schematic", _sch(), _replace_once(_sch(), WIRE_BLOCK, ""))
    row = _only_change(report, change="removed", item_type="wire")
    _near(row["position"], 30.48, 90.17)
    assert row["uuid"] == "56c7e1f9-ded6-43f5-8417-8d308fb4226b"
    assert row["label"].startswith("Wire (30.48,90.17)->(25.4,90.17)")
    assert row["details"]
    assert any("was at" in detail for detail in row["details"])


def test_added_net_label() -> None:
    report = diff_kicad_text("schematic", _sch(), _insert_before_close(_sch(), ADDED_LABEL))
    row = _only_change(report, change="added", item_type="label", ref="DIFF_TEST_NET")
    _near(row["position"], 10.0, 10.0)
    assert row["label"] == 'Label "DIFF_TEST_NET" at (10,10)'
    assert any(detail == "at (10,10)" for detail in row["details"])


def test_deleted_footprint() -> None:
    report = diff_kicad_text("pcb", _pcb(), _remove_sexp_with_uuid(_pcb(), R3_UUID))
    row = _only_change(report, change="removed", item_type="footprint", ref="R3")
    _near(row["position"], 181.0, 88.0)
    assert row["label"] == "R3 10k"
    assert any("was at" in detail for detail in row["details"])


def test_track_width_change() -> None:
    report = diff_kicad_text("pcb", _pcb(), _replace_once(_pcb(), SEGMENT_WIDTH, SEGMENT_WIDTH_NEW))
    row = _only_change(report, change="changed", item_type="segment")
    assert "width 0.2 -> 0.35" in row["details"]
    _near(row["position"], 133.175, 67.852)
    assert row["label"].startswith("Track F.Cu net 1")


def test_added_via() -> None:
    report = diff_kicad_text("pcb", _pcb(), _insert_before_close(_pcb(), ADDED_VIA))
    row = _only_change(report, change="added", item_type="via")
    _near(row["position"], 101.0, 61.0)
    assert row["label"].startswith("Via net 10 at (101,61)")
    assert any(detail.startswith("at (") for detail in row["details"])


def test_zone_net_change() -> None:
    report = diff_kicad_text("pcb", _pcb(), _replace_once(_pcb(), ZONE_NET, ZONE_NET_NEW))
    row = _only_change(report, change="changed", item_type="zone")
    assert any("net" in detail and "10" in detail and "2" in detail for detail in row["details"])
    assert row["ref"] in {"GND reference F.Cu", "/3V3", "/GND"}


def test_order_stable_under_unrelated_shuffles() -> None:
    edited = _replace_once(_sch(), R2_VALUE, R2_VALUE_NEW)
    shuffled = _swap_blocks(edited, WIRE_BLOCK, OTHER_WIRE_BLOCK)
    uuid_shuffled = shuffled.replace(J1_UUID, "00000000-0000-0000-0000-000000000099", 1)
    first = diff_kicad_text("schematic", _sch(), edited)
    second = diff_kicad_text("schematic", _sch(), shuffled)
    third = diff_kicad_text("schematic", _sch(), uuid_shuffled)
    assert first["changes"] == second["changes"]
    assert [row["item_type"] for row in third["changes"]] == [row["item_type"] for row in first["changes"]]
    assert third["summary"]["changed"] == 1
    assert third["changes"][0]["ref"] == "R2"
    assert first["changes"] == sorted(
        first["changes"],
        key=lambda row: (
            row["item_type"],
            row.get("ref") or "",
            (row.get("position") or {}).get("x_mm"),
            (row.get("position") or {}).get("y_mm"),
            row.get("uuid") or "",
        ),
    )


def test_truncation_keeps_true_summary_counts() -> None:
    labels = "\n".join(
        f'\t(label "N{index}" (at {index} 0 0) (uuid "{index:08d}-0000-0000-0000-000000000000"))'
        for index in range(510)
    )
    other = "\n".join(
        f'\t(label "M{index}" (at {index} 1 0) (uuid "{index:08d}-1111-1111-1111-111111111111"))'
        for index in range(510)
    )
    base = f"(kicad_sch (version 20250114) (uuid \"base\")\n{labels}\n)\n"
    candidate = f"(kicad_sch (version 20250114) (uuid \"cand\")\n{other}\n)\n"
    report = diff_kicad_text("schematic", base, candidate)
    assert report["summary"]["added"] == 510
    assert report["summary"]["removed"] == 510
    assert report["summary"]["changed"] == 0
    assert len(report["changes"]) == MAX_CHANGES
    assert report["limits"]["truncated"] is True
    assert report["limits"]["max_changes"] == MAX_CHANGES


def test_malformed_and_empty_input_raise() -> None:
    with pytest.raises(KicadDiffError):
        diff_kicad_text("schematic", "", "(kicad_sch (version 1))")
    with pytest.raises(KicadDiffError):
        diff_kicad_text("schematic", "(kicad_sch (version 1))", "   ")
    with pytest.raises(KicadDiffError):
        diff_kicad_text("schematic", "(kicad_sch", "(kicad_sch (version 1))")
    with pytest.raises(KicadDiffError):
        diff_kicad_text("pcb", "(kicad_sch (version 1))", "(kicad_pcb (version 1))")
    with pytest.raises(KicadDiffError, match="kind"):
        diff_kicad_text("gerber", "(kicad_sch (version 1))", "(kicad_sch (version 1))")


def test_crlf_and_kicad6_tstamp_still_diff() -> None:
    crlf = K6_SCH.replace("\n", "\r\n")
    identical = diff_kicad_text("schematic", K6_SCH, crlf)
    assert identical["summary"]["changed"] == 0
    assert identical["summary"]["added"] == 0
    assert identical["summary"]["unchanged"] > 0
    changed = diff_kicad_text("schematic", crlf, K6_SCH_VALUE.replace("\n", "\r\n"))
    row = _only_change(changed, change="changed", item_type="symbol", ref="R1")
    assert "value 10k -> 4.7k" in row["details"]
    assert row["uuid"] == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


def test_diff_kicad_text_never_mutates_or_opens_files(monkeypatch: pytest.MonkeyPatch) -> None:
    base = _sch()
    candidate = _replace_once(base, R2_VALUE, R2_VALUE_NEW)
    snapshot = (base, candidate)

    def _boom(*_args, **_kwargs):
        raise AssertionError("diff_kicad_text must not open files")

    monkeypatch.setattr("builtins.open", _boom)
    report = diff_kicad_text("schematic", base, candidate)
    assert (base, candidate) == snapshot
    assert report["summary"]["changed"] == 1


def test_diff_kicad_files_matches_text() -> None:
    from_files = diff_kicad_files("schematic", SCH, SCH)
    from_text = diff_kicad_text("schematic", _sch(), _sch())
    assert from_files == from_text


@pytest.mark.parametrize("atom", ["nan", "inf", "-inf", "1e999"])
@pytest.mark.parametrize(
    ("kind", "document"),
    [
        (
            "schematic",
            '(kicad_sch (version 1) (symbol (lib_id "Device:R") (at {atom} 0 0)'
            ' (property "Reference" "R1") (property "Value" "1") (uuid "sym-1")))',
        ),
        (
            "schematic",
            '(kicad_sch (version 1) (wire (pts (xy {atom} 0) (xy 1 1)) (uuid "wire-1")))',
        ),
        (
            "pcb",
            '(kicad_pcb (version 1) (layers (0 "F.Cu" signal))'
            ' (segment (start {atom} 0) (end 1 1) (width 0.2) (layer "F.Cu")'
            ' (net 0) (uuid "seg-1")))',
        ),
        (
            "pcb",
            '(kicad_pcb (version 1) (layers (0 "F.Cu" signal))'
            ' (via (at {atom} 0) (size 0.6) (drill 0.3) (net 0) (uuid "via-1")))',
        ),
    ],
)
def test_nonfinite_coordinates_raise(kind: str, document: str, atom: str) -> None:
    text = document.format(atom=atom)
    with pytest.raises(KicadDiffError, match="coordinate"):
        diff_kicad_text(kind, text, text)


def test_symlinked_file_rejected(tmp_path: Path) -> None:
    real = tmp_path / "board.kicad_sch"
    real.write_text(K6_SCH, encoding="utf-8")
    link = tmp_path / "link.kicad_sch"
    link.symlink_to(real)
    with pytest.raises(KicadDiffError, match="symlinked path not allowed"):
        diff_kicad_files("schematic", link, real)


def test_symlinked_parent_dir_rejected(tmp_path: Path) -> None:
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    real = real_dir / "board.kicad_sch"
    real.write_text(K6_SCH, encoding="utf-8")
    link_dir = tmp_path / "linkdir"
    link_dir.symlink_to(real_dir)
    linked = link_dir / "board.kicad_sch"
    with pytest.raises(KicadDiffError, match="symlinked path not allowed"):
        diff_kicad_files("schematic", linked, real)


def test_normal_file_ok() -> None:
    report = diff_kicad_files("schematic", SCH, SCH)
    assert report["summary"]["unchanged"] > 0
    assert report["changes"] == []


def test_reference_diffs_are_json_serialisable() -> None:
    schematic = diff_kicad_text("schematic", _sch(), _sch())
    pcb = diff_kicad_text("pcb", _pcb(), _pcb())
    changed = diff_kicad_text("schematic", _sch(), _replace_once(_sch(), R2_VALUE, R2_VALUE_NEW))
    json.dumps(schematic, allow_nan=False)
    json.dumps(pcb, allow_nan=False)
    json.dumps(changed, allow_nan=False)


def _replace_after(text: str, marker: str, old: str, new: str) -> str:
    pos = text.find(marker)
    assert pos != -1
    return text[:pos] + text[pos:].replace(old, new, 1)


TSTAMP_SCH = """(kicad_sch (version 20211123)
  (symbol (lib_id "Device:R") (at 10 10 0) (unit 1) (tstamp sym-1)
    (property "Reference" "R1") (property "Value" "1k"))
  (wire (pts (xy 0 0) (xy 2 0)) (tstamp wire-1))
  (wire (pts (xy 0 1) (xy 2 1)) (tstamp wire-2))
  (wire (pts (xy 0 2) (xy 2 2)) (tstamp wire-3))
)
"""
WIRE3 = "  (wire (pts (xy 0 2) (xy 2 2)) (tstamp wire-3))\n"


def _strip_or_rename_ids(text: str, *, rename: bool) -> str:
    if rename:
        return (
            text.replace("(tstamp sym-1)", '(uuid "new-sym")')
            .replace("(tstamp wire-1)", '(uuid "new-w1")')
            .replace("(tstamp wire-2)", '(uuid "new-w2")')
            .replace("(tstamp wire-3)", '(uuid "new-w3")')
        )
    return (
        text.replace(" (tstamp sym-1)", "")
        .replace(" (tstamp wire-1)", "")
        .replace(" (tstamp wire-2)", "")
        .replace(" (tstamp wire-3)", "")
    )


def test_reference_rename_is_changed() -> None:
    schematic = _replace_once(_sch(), '\t\t(property "Reference" "R2"\n', '\t\t(property "Reference" "R5"\n')
    sch_report = diff_kicad_text("schematic", _sch(), schematic)
    sch_row = _only_change(sch_report, change="changed", item_type="symbol", ref="R5")
    assert "reference R2 -> R5" in sch_row["details"]

    pcb = _replace_once(_pcb(), '\t\t(property "Reference" "R3"\n', '\t\t(property "Reference" "R5"\n')
    pcb_report = diff_kicad_text("pcb", _pcb(), pcb)
    pcb_row = _only_change(pcb_report, change="changed", item_type="footprint", ref="R5")
    assert "reference R3 -> R5" in pcb_row["details"]


def test_zone_outline_vertex_move() -> None:
    edited = _replace_after(
        _pcb(),
        '(uuid "7920bc50-3bd7-407e-afb4-36b8e79dfccb")',
        "(xy 189.5 109.5)",
        "(xy 190.5 110.5)",
    )
    report = diff_kicad_text("pcb", _pcb(), edited)
    row = _only_change(report, change="changed", item_type="zone")
    assert any("outline changed" in detail for detail in row["details"])
    assert row["bbox_mm"] is not None
    assert abs(row["bbox_mm"]["max_x"] - 190.5) <= 0.001
    assert abs(row["bbox_mm"]["max_y"] - 110.5) <= 0.001


@pytest.mark.parametrize(
    ("kind", "document"),
    [
        ("schematic", '(kicad_sch (version 1) (wire (pts (xy abc 0) (xy 1 1)) (uuid "w")))'),
        (
            "schematic",
            '(kicad_sch (version 1) (symbol (lib_id "Device:R") (at abc 0 0)'
            ' (property "Reference" "R1") (property "Value" "1")))',
        ),
        ("pcb", '(kicad_pcb (version 1) (via (at 1 1) (size abc) (drill 0.3) (uuid "v")))'),
        (
            "pcb",
            '(kicad_pcb (version 1) (zone (net 0) (layer "F.Cu") (uuid "z")'
            " (polygon (pts (xy abc 0) (xy 1 0) (xy 1 1) (xy 0 1)))))",
        ),
    ],
)
def test_non_numeric_geometry_raises(kind: str, document: str) -> None:
    with pytest.raises(KicadDiffError, match="malformed coordinate"):
        diff_kicad_text(kind, document, document)


def test_tstamp_versus_stripped_or_renamed_uuid_is_unchanged() -> None:
    for candidate in (
        _strip_or_rename_ids(TSTAMP_SCH, rename=False),
        _strip_or_rename_ids(TSTAMP_SCH, rename=True),
    ):
        report = diff_kicad_text("schematic", TSTAMP_SCH, candidate)
        assert report["summary"]["added"] == 0
        assert report["summary"]["removed"] == 0
        assert report["summary"]["changed"] == 0
        assert report["summary"]["unchanged"] > 0
        assert report["changes"] == []


def test_tstamp_versus_stripped_uuid_with_deleted_wire() -> None:
    deleted = TSTAMP_SCH.replace(WIRE3, "")
    report = diff_kicad_text("schematic", TSTAMP_SCH, _strip_or_rename_ids(deleted, rename=False))
    row = _only_change(report, change="removed", item_type="wire")
    _near(row["position"], 0.0, 2.0)
    assert row["details"]


def test_unlocked_at_list_is_not_a_coordinate() -> None:
    unlocked = _replace_once(_sch(), R2_AT, R2_AT.replace("(at 185.42 82.55 0)", "(at 185.42 82.55 unlocked)"))
    report = diff_kicad_text("schematic", _sch(), unlocked)
    assert report["summary"]["added"] == 0
    assert report["summary"]["removed"] == 0
    assert report["summary"]["changed"] == 0
    pcb_unlocked = '(kicad_pcb (version 1) (footprint "R:0603" (layer "F.Cu") (at 10 20 unlocked) (property "Reference" "R1") (property "Value" "1k")) (via (at 1 2 unlocked) (size 0.6) (drill 0.3) (net 1)))'
    assert diff_kicad_text("pcb", pcb_unlocked, pcb_unlocked)["summary"]["changed"] == 0


def test_flag_changes_on_reference_design() -> None:
    r2_flags = (
        '\t\t(lib_id "Device:R")\n'
        "\t\t(at 185.42 82.55 0)\n"
        "\t\t(unit 1)\n"
        "\t\t(exclude_from_sim no)\n"
        "\t\t(in_bom yes)\n"
        "\t\t(on_board yes)\n"
        "\t\t(dnp no)"
    )
    flipped = r2_flags.replace("(exclude_from_sim no)", "(exclude_from_sim yes)").replace(
        "(on_board yes)", "(on_board no)"
    )
    sch = diff_kicad_text("schematic", _sch(), _replace_once(_sch(), r2_flags, flipped))
    row = _only_change(sch, change="changed", item_type="symbol", ref="R2")
    assert "exclude_from_sim no -> yes" in row["details"]
    assert "on_board yes -> no" in row["details"]

    hidden = _replace_once(
        _sch(),
        '\t(label "HOST_3V3"\n\t\t(at 25.4 90.17 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n\t\t\t)\n\t\t\t(justify right bottom)\n\t\t)',
        '\t(label "HOST_3V3"\n\t\t(at 25.4 90.17 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n\t\t\t)\n\t\t\t(justify right bottom)\n\t\t\t(hide yes)\n\t\t)',
    )
    label_report = diff_kicad_text("schematic", _sch(), hidden)
    label_row = _only_change(label_report, change="changed", item_type="label", ref="HOST_3V3")
    assert "hide no -> yes" in label_row["details"]

    via = _replace_once(
        _pcb(),
        '\t\t(locked yes)\n\t\t(net 10)\n\t\t(uuid "22b157e5-11d4-498e-9e5e-c23412c1fe0c")',
        '\t\t(locked no)\n\t\t(net 10)\n\t\t(uuid "22b157e5-11d4-498e-9e5e-c23412c1fe0c")',
    )
    via_report = diff_kicad_text("pcb", _pcb(), via)
    via_row = _only_change(via_report, change="changed", item_type="via")
    assert "locked yes -> no" in via_row["details"]

    zone = _replace_after(_pcb(), '(uuid "7920bc50-3bd7-407e-afb4-36b8e79dfccb")', "(fill yes", "(fill no")
    zone_report = diff_kicad_text("pcb", _pcb(), zone)
    zone_row = _only_change(zone_report, change="changed", item_type="zone")
    assert "fill yes -> no" in zone_row["details"]

    fp = _replace_once(_pcb(), '\t\t(at 181 88)\n', '\t\t(at 181 88)\n\t\t(locked yes)\n\t\t(placed no)\n')
    fp_report = diff_kicad_text("pcb", _pcb(), fp)
    fp_row = _only_change(fp_report, change="changed", item_type="footprint", ref="R3")
    assert "locked no -> yes" in fp_row["details"]
    assert "placed yes -> no" in fp_row["details"]

    base_gl = '(kicad_sch (version 1) (global_label "VBUS" (shape input) (at 1 2 0) (uuid "g1")))'
    cand_gl = base_gl.replace("(shape input)", "(shape output)")
    gl = _only_change(diff_kicad_text("schematic", base_gl, cand_gl), change="changed", item_type="global_label")
    assert "shape input -> output" in gl["details"]


def test_wires_sharing_start_point_match_full_geometry() -> None:
    base = """(kicad_sch (version 1)
  (wire (pts (xy 0 0) (xy 1 0)) (uuid "w1"))
  (wire (pts (xy 0 0) (xy 0 1)) (uuid "w2"))
)
"""
    candidate = """(kicad_sch (version 1)
  (wire (pts (xy 0 0) (xy 0 1)))
  (wire (pts (xy 0 0) (xy 1 0)))
)
"""
    report = diff_kicad_text("schematic", base, candidate)
    assert report["summary"] == {"added": 0, "removed": 0, "changed": 0, "unchanged": report["summary"]["unchanged"]}
    assert report["changes"] == []


def test_intermediate_wire_vertex_move() -> None:
    base = '(kicad_sch (version 1) (wire (pts (xy 0 0) (xy 1 1) (xy 2 0)) (uuid "w")))'
    candidate = '(kicad_sch (version 1) (wire (pts (xy 0 0) (xy 1 2) (xy 2 0)) (uuid "w")))'
    report = diff_kicad_text("schematic", base, candidate)
    row = _only_change(report, change="changed", item_type="wire")
    assert "vertex 2 moved from (1,1) to (1,2)" in row["details"]
    assert row["bbox_mm"] == {"min_x": 0.0, "min_y": 0.0, "max_x": 2.0, "max_y": 2.0}


def test_zone_layers_node_is_compared() -> None:
    edited = _replace_once(
        _pcb(),
        '\t\t(layer "F.Cu")\n\t\t(uuid "7920bc50-3bd7-407e-afb4-36b8e79dfccb")',
        '\t\t(layers "F.Cu" "B.Cu")\n\t\t(uuid "7920bc50-3bd7-407e-afb4-36b8e79dfccb")',
    )
    report = diff_kicad_text("pcb", _pcb(), edited)
    row = _only_change(report, change="changed", item_type="zone")
    assert any("layer" in detail and "B.Cu" in detail for detail in row["details"])
    assert "B.Cu" in row["label"]


def test_kicad6_sheet_name_file_properties() -> None:
    base = """(kicad_sch (version 20211123)
  (sheet (at 10 20) (size 5 5) (tstamp sheet-1)
    (property "Sheet name" "Child")
    (property "Sheet file" "child.kicad_sch"))
)
"""
    candidate = base.replace('"Child"', '"Renamed"')
    report = diff_kicad_text("schematic", base, candidate)
    row = _only_change(report, change="changed", item_type="sheet", ref="Renamed")
    assert "name Child -> Renamed" in row["details"]


def test_pts_rejects_non_xy_entries() -> None:
    text = '(kicad_sch (version 1) (wire (pts abc (xy 1 1)) (uuid "w")))'
    with pytest.raises(KicadDiffError, match="malformed coordinate"):
        diff_kicad_text("schematic", text, text)


@pytest.mark.parametrize("depth", [10_000, 100_000])
def test_nested_parens_hit_depth_cap(depth: int) -> None:
    text = "(" * depth + "kicad_sch" + ")" * depth
    with pytest.raises(KicadDiffError, match="input nested too deeply"):
        parse_kicad_sexp(text)
