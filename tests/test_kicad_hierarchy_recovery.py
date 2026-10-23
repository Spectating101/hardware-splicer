"""KiCad 9 genuine hierarchical demo exports: reference/sheet/path integrity.

These test *official KiCad demo projects* installed by the open-source
kicad-demos package. When unavailable, the real-export tests are skipped;
always-on synthetic negative controls still protect empty pin handling.

The original demo designs and their licenses remain owned by KiCad authors.
No KiCad demo files are redistributed in this repository.
"""
from __future__ import annotations

import collections
import subprocess
from pathlib import Path

import pytest

from hardware_splicer.integrations.circuit_json_import import circuit_json_to_netlist
from hardware_splicer.integrations.kicad_circuit_json_recovery import recover_connected_source_circuit_json
from hardware_splicer.netlist.import_kicad import parse_kicad_netlist

DEMO = Path("/usr/share/kicad/demos")
PROJECTS = [
    ("complex_hierarchy", "complex_hierarchy.kicad_sch",
     (68, 52, 164, 50, 162, 3, 0)),
    ("flat_hierarchy", "flat_hierarchy.kicad_sch",
     (64, 117, 238, 34, 161, 3, 6)),
    ("multichannel", "multichannel_mixer.kicad_sch",
     (114, 80, 280, 79, 279, 5, 0)),
]


@pytest.mark.parametrize("folder,root_file,expected", PROJECTS)
def test_official_kicad_hierarchical_schematic_instances_survive_roundtrip(
    folder, root_file, expected, tmp_path: Path
):
    root=DEMO/folder/root_file
    if not root.is_file():
        pytest.skip("Install kicad-demos and KiCad 9 CLI for genuine multischeet project verification")
    if subprocess.run(["which", "kicad-cli"],capture_output=True).returncode:
        pytest.skip("kicad-cli unavailable")
    export=tmp_path/(folder+".net")
    process=subprocess.run([
        "kicad-cli","sch","export","netlist","--format","kicadsexpr",
        "--output",str(export),str(root)
    ], capture_output=True,text=True,timeout=120)
    assert process.returncode == 0, process.stdout+process.stderr
    text=export.read_text(encoding="utf-8")
    original=parse_kicad_netlist(text)
    output=recover_connected_source_circuit_json(text)
    ir=circuit_json_to_netlist(output["documents"])
    receipt=output["receipt"]
    c,n,p,connected,connected_pins,sheets,unnumbered=expected
    assert (receipt["components"],receipt["source_nets"],receipt["source_pin_memberships"]) == (c,n,p)
    assert (receipt["connected_multi_pin_nets"],receipt["imported_multi_pin_memberships"]) == (connected,connected_pins)
    assert receipt["hierarchy"]["sheet_count"]==sheets
    assert len(receipt["source_unnumbered_no_connect_nets"])==unnumbered
    assert receipt["hierarchy"]["component_instances_with_sheet_path"]==c
    assert receipt["hierarchy"]["source_sheet_scopes_preserved"]
    assert receipt["topology_exact_multi_pin_match"]
    assert not receipt["manufacturing_authorized"]
    assert {x.ref for x in original.components}=={x.ref for x in ir.components}
    assert {
        x.ref:x.metadata.get("kicad_sheet_name") for x in original.components
    } == {
        x.ref:x.metadata.get("subcircuit_id") for x in ir.components
    }
    # Exactly preserve every connected REF.PIN and named net; additionally
    # preserve single/unaddressable NC positions separately as source data.
    def topology(o):
        return {net.name:{pin.key() for pin in net.pins} for net in o.nets if len(net.pins)>=2}
    assert topology(original)==topology(ir)
    assert all(str(x.get("pin",None))=="" for x in receipt["source_unnumbered_no_connect_nets"].values())
    if folder=="multichannel":
        counts=collections.Counter(x.metadata["subcircuit_id"] for x in ir.components)
        assert all(counts[f"/CH{k}/"]==26 for k in range(1,5))
        assert counts["/"]==10
        assert len(set(x.ref for x in ir.components))==114
        assert len(set(x.metadata["kicad_sheet_uuid_path"] for x in original.components if x.metadata["kicad_sheet_name"].startswith("/CH")))==4
    if folder=="complex_hierarchy":
        names={x["name"]:x["source_filename"] for x in receipt["hierarchy"]["sheets"]}
        assert names["/ampli_ht_vertical/"]==names["/ampli_ht_horizontal/"]=="ampli_ht.kicad_sch"


def test_explicit_unumbered_mounting_hole_no_connect_is_preserved_without_a_fake_pin():
    text='''(export (components
        (comp (ref "HOLE1") (value "MountingHole"))
        (comp (ref "U1") (value "IC")))
      (nets
        (net (code "1") (name "A") (node (ref "U1") (pin "1"))
                                   (node (ref "U1") (pin "2")))
        (net (code "2") (name "unconnected-(HOLE1-1-Pad)")
            (node (ref "HOLE1") (pin "") (pinfunction "1")
                  (pintype "passive+no_connect")))))'''
    source=parse_kicad_netlist(text)
    assert source.metadata["kicad_export"]["unnumbered_no_connect_terminals"]==[
        {"net":"unconnected-(HOLE1-1-Pad)","ref":"HOLE1","pin":"",
         "pinfunction":"1","pintype":"passive+no_connect"}
    ]
    recovered=recover_connected_source_circuit_json(text)
    assert recovered["receipt"]["source_unnumbered_no_connect_nets"][
        "unconnected-(HOLE1-1-Pad)"
    ]["pin"]==""
    assert not any("kicad_port_HOLE1_" in str(doc) for doc in recovered["documents"])
    assert recovered["receipt"]["connected_multi_pin_nets"]==1
    assert recovered["receipt"]["imported_multi_pin_memberships"]==2


@pytest.mark.parametrize("netname,pintype,nodes", [
    ("VCC","passive+no_connect",'(node (ref "HOLE1") (pin "") (pintype "passive+no_connect"))'),
    ("unconnected-(HOLE1-1-Pad)","passive",'(node (ref "HOLE1") (pin "") (pintype "passive"))'),
    ("unconnected-(HOLE1-1-Pad)","passive+no_connect",'(node (ref "HOLE1") (pin "") (pintype "passive+no_connect")) (node (ref "U1") (pin "3"))'),
])
def test_do_not_suppress_missing_real_pin_on_connected_or_unverified_nets(netname,pintype,nodes):
    text=f'''(export (components (comp (ref "U1") (value "IC"))
                   (comp (ref "HOLE1") (value "MountingHole")))
       (nets (net (code "1") (name "A") (node (ref "U1") (pin "1"))
                                      (node (ref "U1") (pin "2")))
             (net (code "2") (name "{netname}") {nodes})))'''
    with pytest.raises(ValueError, match="Malformed KiCad net node"):
        parse_kicad_netlist(text)


def test_source_port_ids_cannot_collide_when_ref_and_pin_both_have_underscores():
    text='''(export
      (components
        (comp (ref "U_1") (value "Chip"))
        (comp (ref "U") (value "Chip")))
      (nets
        (net (code "1") (name "X")
             (node (ref "U_1") (pin "2"))
             (node (ref "U") (pin "1_2")))
        (net (code "2") (name "Y")
             (node (ref "U_1") (pin "3"))
             (node (ref "U") (pin "4")))))'''
    result=recover_connected_source_circuit_json(text)
    ports=[x for x in result["documents"] if x["type"]=="source_port"]
    assert len(ports)==4
    assert len({p["source_port_id"] for p in ports})==4
    assert result["receipt"]["topology_exact_multi_pin_match"]


def test_unnumbered_source_contact_must_belong_to_real_exported_component():
    text='''(export
      (components (comp (ref "U1") (value "Chip")))
      (nets
        (net (code "1") (name "X")
             (node (ref "U1") (pin "2"))
             (node (ref "U1") (pin "3")))
        (net (code "2") (name "unconnected-(HOLE1-1-Pad)")
             (node (ref "HOLE1") (pin "") (pintype "passive+no_connect")))))'''
    with pytest.raises(ValueError, match="no component reference"):
        recover_connected_source_circuit_json(text)
