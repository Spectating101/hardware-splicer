"""Contract tests: missing upstream provenance fails; synthetic labels never authenticate origin."""
import copy

from test_kicad_native_pin_geometry_audit import actual_input  # noqa: F401
from hardware_splicer.integrations.kicad_native_coordinate_proof import prove_native_visual_positions
from hardware_splicer.integrations.kicad_native_pin_geometry_audit import _placed_symbols
from hardware_splicer.integrations.kicad_native_uuid_transport_contract import verify_native_uuid_transport
from hardware_splicer.netlist.import_kicad import parse_kicad_netlist


def _tagged(input_data):
    schematic, official, originals = input_data
    docs = copy.deepcopy(originals)
    native = _placed_symbols(schematic)[1]
    exported = {c.ref: c for c in parse_kicad_netlist(official).components}
    proof = prove_native_visual_positions(schematic, official, docs)
    for record in proof["correlations"]:
        ref = record["kicad_ref"]
        cid = record["converter_source_component_id"]
        uuid = native[ref]["uuid"]
        path = exported[ref].metadata["kicad_sheet_uuid_path"]
        for doc in docs:
            if (doc["type"] == "source_component" and doc["source_component_id"] == cid or
                doc["type"] == "source_port" and doc["source_component_id"] == cid):
                doc["native_kicad_symbol_uuid"] = uuid
                doc["native_kicad_sheet_uuid_path"] = path
    return schematic, official, docs


def test_real_unmodified_upstream_converter_abstains(actual_input):
    result = verify_native_uuid_transport(*actual_input)
    assert result["uuid_path_consistent_components"] == 0
    assert not result["converter_uuid_transport_contract_satisfied"]
    assert not result["converter_provenance_authenticated"]
    assert not result["visual_electrical_merge_allowed"]


def test_synthetic_fields_meet_contract_but_do_not_authenticate_origin(actual_input):
    result = verify_native_uuid_transport(*_tagged(actual_input))
    assert result["converter_uuid_transport_contract_satisfied"]
    assert result["uuid_path_consistent_components"] == 36
    assert result["uuid_path_consistent_ports"] == 79
    assert not result["original_converter_emission_proven"]
    assert not result["converter_provenance_authenticated"]


def test_swapped_native_uuid_is_rejected(actual_input):
    source, net, docs = _tagged(actual_input)
    components = [d for d in docs if d["type"] == "source_component"]
    components[0]["native_kicad_symbol_uuid"], components[1]["native_kicad_symbol_uuid"] = (
        components[1]["native_kicad_symbol_uuid"], components[0]["native_kicad_symbol_uuid"])
    result = verify_native_uuid_transport(source, net, docs)
    assert not result["converter_uuid_transport_contract_satisfied"]
    assert result["failure_count"] >= 1


def test_missing_single_port_path_is_rejected(actual_input):
    source, net, docs = _tagged(actual_input)
    next(d for d in docs if d["type"] == "source_port").pop("native_kicad_sheet_uuid_path")
    result = verify_native_uuid_transport(source, net, docs)
    assert not result["converter_uuid_transport_contract_satisfied"]


def test_path_mismatch_is_rejected(actual_input):
    source, net, docs = _tagged(actual_input)
    next(d for d in docs if d["type"] == "source_component")["native_kicad_sheet_uuid_path"] = "/forged/"
    result = verify_native_uuid_transport(source, net, docs)
    assert not result["converter_uuid_transport_contract_satisfied"]
